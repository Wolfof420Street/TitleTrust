import os
import re
import json
import math
import logging
import hashlib
import uuid
import requests
import base64
from io import BytesIO
from typing import Dict, Any, List, Optional
from datetime import datetime

# Third-party Imports
import googlemaps
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Local Config
try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings

# --- SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [TOOLS] - %(message)s")
logger = logging.getLogger(__name__)

KENYA_LAT_RANGE = (-5.5, 5.5)
KENYA_LNG_RANGE = (33.0, 42.5)
HTTP_TIMEOUT_SECONDS = 10

# Lazy-load Google Maps Client to allow imports without API key
_gmaps_client = None

def _get_gmaps_client() -> Optional[googlemaps.Client]:
    """Lazy-load Google Maps client on first use."""
    global _gmaps_client
    if _gmaps_client is None:
        if settings.MAPS_API_KEY:
            try:
                _gmaps_client = googlemaps.Client(key=settings.MAPS_API_KEY)
            except Exception as e:
                logger.error(f"Failed to initialize Google Maps client: {e}")
                _gmaps_client = False  # Sentinel for failed initialization
    return _gmaps_client if _gmaps_client is not False else None

# ==========================================
# 1. LEGAL & FORMAT TOOLS
# ==========================================

def validate_title_syntax(title_number: str) -> str:
    """
    Validates if a Land Title Number matches Kenyan Registry formats.
    Used by Forensic Agents to instantly detect obvious formatting forgeries.
    """
    if not title_number:
        return "INVALID: Null Title Number"
        
    logger.info(f"Checking syntax for: {title_number}")
    
    title_clean = title_number.strip().upper()
    
    # Regex Patterns for Kenyan Land Titles
    patterns = {
        "IR_NUMBER": r"^I\.R\.?\s?\d+$",          # Indenture Registry (e.g., I.R. 12345)
        "CR_NUMBER": r"^C\.R\.?\s?\d+$",          # Coastal Registry (e.g., C.R. 12345)
        "BLOCK_TITLE": r"^[A-Z]+\/BLOCK\s\d+\/\d+$", # Nairobi/Block 110/32
        "LR_NUMBER": r"^L\.R\.?\s?NO\.?\s?\d+(\/\d+)?$", # L.R. No. 209/400
        # ADDED: Pattern for District/Section/Parcel (e.g., KISUMU/KASULE/8781)
        # Allows for alphabetic District/Section names (with spaces) and a numeric parcel number.
        "DISTRICT_TITLE": r"^[A-Z\s]+\/[A-Z\s]+\/\d+$" 
    }
    
    matches = []
    for key, pattern in patterns.items():
        if re.match(pattern, title_clean):
            matches.append(key)
            
    if matches:
        return f"VALID_FORMAT: Matches {', '.join(matches)} pattern."
    else:
        return "INVALID_FORMAT: Does not match standard Kenyan I.R., C.R., Block, or District patterns."

# ==========================================
# 2. WEB INTELLIGENCE TOOLS
# ==========================================


def search_kenyan_web(query: str) -> str:
    """
    Uses Gemini 3 Google Search Grounding to find information about land cases.
    """
    print(f"🔎 [Search] Grounding Query: {query}")
    
    try:
        # Initialize Unified Client
        client = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )
        
        # Simple Grounding Config
        google_search_tool = types.Tool(
            google_search=types.GoogleSearch() 
        )

        response = client.models.generate_content(
            model=settings.FORENSIC_MODEL_NAME, 
            contents=f"Investigate this query in the context of Kenyan Land Law and Fraud Cases: {query}",
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                response_modalities=["TEXT"],
            )
        )
        
        # Extract text
        return response.text

    except Exception as e:
        print(f"❌ [Search] Error: {e}")
        return f"Search failed: {e}"



# ==========================================
# 3. GEOSPATIAL REALITY TOOLS
# ==========================================

def get_satellite_image(lat: float, lng: float, zoom: int = 18) -> Dict[str, Any]:
    """
    REAL API CALL: Fetches an actual satellite image from Google Maps Static API.
    Returns the base64 encoded image to be fed into Gemini.
    """
    print(f"🛰️ [TOOL] Fetching Google Earth Satellite data for {lat}, {lng}...")
    
    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        "center": f"{lat},{lng}",
        "zoom": zoom,
        "size": "600x400",
        "maptype": "satellite",
        "key": settings.MAPS_API_KEY
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        
        # Convert binary to base64 for Gemini
        image_b64 = base64.b64encode(response.content).decode("utf-8")
        
        return {
            "status": "success",
            "mime_type": "image/png",
            "data": image_b64,
            "metadata": f"Satellite view of {lat}, {lng} at zoom {zoom}"
        }
    except requests.exceptions.Timeout as e:
        logger.warning(f"Maps API timed out: {e}")
        return {"status": "error", "error": "Maps API request timed out"}
    except requests.exceptions.RequestException as e:
        print(f"❌ [TOOL ERROR] Maps API failed: {e}")
        return {"status": "error", "error": str(e)}
    except Exception as e:
        print(f"❌ [TOOL ERROR] Maps API failed: {e}")
        return {"status": "error", "error": str(e)}

def get_satellite_ground_truth(lat: float, lng: float) -> Dict[str, Any]:
    """
    Fetches official map data (Reverse Geocoding + Nearby Places) from Google Maps.
    Used to detect if land is in a protected area (River, Park, School).
    """
    logger.info(f"Querying Maps API for: {lat}, {lng}")
    
    gmaps_client = _get_gmaps_client()
    if not gmaps_client:
        return {"error": "Maps API not configured."}

    context = {
        "coordinates": f"{lat},{lng}", 
        "timestamp": datetime.now().isoformat(),
        "risk_factors": []
    }

    try:
        # 1. Reverse Geocode (What is the legal address?)
        reverse = gmaps_client.reverse_geocode((lat, lng))
        if reverse:
            context["formatted_address"] = reverse[0].get('formatted_address', 'Unknown')
            # Extract types (e.g., 'park', 'political', 'establishment')
            context["location_types"] = reverse[0].get('types', [])

        # 2. Nearby Search (Are we near sensitive features?)
        # We search 200m radius for protected features
        places = gmaps_client.places_nearby(
            location=(lat, lng), 
            radius=200, 
            type=['natural_feature', 'park', 'school', 'hospital', 'church']
        )
        
        found_features = []
        if places.get('results'):
            for p in places['results']:
                name = p.get('name')
                types = p.get('types', [])
                found_features.append(f"{name} ({', '.join(types)})")
                
                # Simple Risk Heuristics
                if 'natural_feature' in types or 'park' in types:
                    context["risk_factors"].append("CLOSE_TO_PROTECTED_AREA")
                if 'school' in types:
                    context["risk_factors"].append("CLOSE_TO_PUBLIC_INSTITUTION")
        
        context["nearby_landmarks"] = found_features

    except Exception as e:
        logger.error(f"Maps API error: {e}")
        return {"error": str(e)}

    return context


class BoundaryInspectionResult(BaseModel):
    coordinates: str
    rim_consistency: str = Field(description="CONSISTENT, INCONCLUSIVE, or INCONSISTENT")
    beacon_presence: str = Field(description="VISIBLE, NOT_VISIBLE, or UNCERTAIN")
    encroachment_indicators: List[str]
    observed_land_use: str
    title_land_use_consistency: str = Field(description="CONSISTENT or INCONSISTENT")
    discrepancy_detected: bool
    severity: str = Field(description="LOW, MEDIUM, HIGH")
    reasoning: str


def inspect_physical_boundaries(
    lat: float,
    lng: float,
    *,
    title_context: str,
    expected_land_use: str | None = None,
) -> Dict[str, Any]:
    """Cross-check satellite imagery for beacons, RIM consistency, and encroachment."""
    satellite = get_satellite_image(lat, lng)
    if satellite.get("status") != "success":
        return {"status": "error", "error": satellite.get("error", "Satellite image unavailable")}

    ground_truth = get_satellite_ground_truth(lat, lng)
    if ground_truth.get("error"):
        return {"status": "error", "error": ground_truth["error"]}

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prompt = f"""
You are a Kenyan cadastral and boundary verification specialist performing Step 4 Physical Boundary Verification.

Inspect the satellite image and official map context for:
1. Survey beacons or other visible boundary markers.
2. Whether visible parcel edges appear consistent with Registry Index Map (RIM) expectations.
3. Encroachment indicators: structures, walls, fencing, cultivation, roads, or drainage lines crossing expected boundaries.
4. Land-use mismatch: if the title context implies VACANT/AGRICULTURAL/RESIDENTIAL but the image shows conflicting use.

Title context:
{title_context}

Expected land use:
{expected_land_use or "UNKNOWN"}

Official map context:
{json.dumps(ground_truth, indent=2)}

Return a strict JSON result. If you see structures or boundary walls where the title context implies vacant land, set discrepancy_detected=true and severity=HIGH.
"""

    try:
        response = client.models.generate_content(
            model=settings.VISION_MODEL_NAME,
            contents=[
                types.Part.from_bytes(
                    data=base64.b64decode(satellite["data"]),
                    mime_type=str(satellite["mime_type"]),
                ),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BoundaryInspectionResult,
                temperature=0.1,
            ),
        )
        parsed = response.parsed.model_dump() if response.parsed else json.loads(response.text)
        parsed["status"] = "success"
        parsed["ground_truth"] = ground_truth
        parsed["provider"] = "gemini_vision"
        parsed["trace_id"] = f"vision-{uuid.uuid4().hex[:12]}"
        parsed["evidence_sha256"] = hashlib.sha256(
            json.dumps(
                {
                    "lat": lat,
                    "lng": lng,
                    "title_context": title_context,
                    "expected_land_use": expected_land_use,
                    "ground_truth": ground_truth,
                    "satellite": satellite,
                    "response": parsed,
                },
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        return parsed
    except Exception as e:
        logger.error(f"Boundary inspection failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def _utm_to_lat_lng(zone_number: int, hemisphere: str, easting: float, northing: float) -> tuple[float, float]:
    """Convert WGS84 UTM coordinates to latitude/longitude without external dependencies."""
    a = 6378137.0
    e = 0.081819191
    e1sq = 0.006739497
    k0 = 0.9996

    x = easting - 500000.0
    y = northing
    if hemisphere.upper() == "S":
        y -= 10000000.0

    m = y / k0
    mu = m / (a * (1 - e**2 / 4 - 3 * e**4 / 64 - 5 * e**6 / 256))
    e1 = (1 - math.sqrt(1 - e**2)) / (1 + math.sqrt(1 - e**2))

    j1 = 3 * e1 / 2 - 27 * e1**3 / 32
    j2 = 21 * e1**2 / 16 - 55 * e1**4 / 32
    j3 = 151 * e1**3 / 96
    j4 = 1097 * e1**4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)

    c1 = e1sq * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    r1 = a * (1 - e**2) / (1 - (e * math.sin(fp)) ** 2) ** 1.5
    n1 = a / math.sqrt(1 - (e * math.sin(fp)) ** 2)
    d = x / (n1 * k0)

    q1 = n1 * math.tan(fp) / r1
    q2 = d**2 / 2
    q3 = (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e1sq) * d**4 / 24
    q4 = (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e1sq - 3 * c1**2) * d**6 / 720
    lat = fp - q1 * (q2 - q3 + q4)

    q5 = d
    q6 = (1 + 2 * t1 + c1) * d**3 / 6
    q7 = (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e1sq + 24 * t1**2) * d**5 / 120
    lon = (q5 - q6 + q7) / math.cos(fp)
    lon0 = math.radians((zone_number - 1) * 6 - 180 + 3)

    return math.degrees(lat), math.degrees(lon0 + lon)


def parse_kenyan_coordinates(raw_text: str) -> Dict[str, Any]:
    """Parse Kenyan decimal or UTM coordinates from deed/agent text."""
    text = raw_text.strip()
    decimal_match = re.search(r"(-?\d{1,2}\.\d+)\s*[, ]\s*(-?\d{1,3}\.\d+)", text)
    if decimal_match:
        lat = float(decimal_match.group(1))
        lng = float(decimal_match.group(2))
        if KENYA_LAT_RANGE[0] <= lat <= KENYA_LAT_RANGE[1] and KENYA_LNG_RANGE[0] <= lng <= KENYA_LNG_RANGE[1]:
            return {"format": "decimal", "lat": lat, "lng": lng}
        return {
            "error": "Coordinates outside Kenya bounding box",
            "format": "decimal",
            "lat": lat,
            "lng": lng,
        }

    utm_match = re.search(
        r"(?:UTM\s*)?(?P<zone>3[67])\s*(?P<hemi>[NS])[\s,;:]+(?P<east>\d{5,6}(?:\.\d+)?)\s*[, ]\s*(?P<north>\d{6,7}(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if utm_match:
        try:
            lat, lng = _utm_to_lat_lng(
                int(utm_match.group("zone")),
                utm_match.group("hemi").upper(),
                float(utm_match.group("east")),
                float(utm_match.group("north")),
            )
        except Exception as exc:
            return {"error": f"UTM conversion failed: {exc}", "format": "utm"}

        if KENYA_LAT_RANGE[0] <= lat <= KENYA_LAT_RANGE[1] and KENYA_LNG_RANGE[0] <= lng <= KENYA_LNG_RANGE[1]:
            return {"format": "utm", "lat": lat, "lng": lng}

        return {
            "error": "Converted coordinates fall outside Kenya bounding box",
            "format": "utm",
            "lat": lat,
            "lng": lng,
        }

    return {"error": "No valid Kenyan coordinates found"}


def build_record_search_queries(
    *,
    title_number: str,
    owner_name: str | None = None,
    county: str | None = None,
) -> List[str]:
    """Generate Step 5 mandatory record cross-check queries."""
    county_fragment = f" {county}" if county else ""
    zoning_authority = f'"{county} County" zoning physical planning land use compliance' if county else '"Kenya county physical planning" zoning land use compliance'
    owner_fragment = f' "{owner_name}"' if owner_name else ""
    return [
        f'National Land Commission records "{title_number}"{owner_fragment}{county_fragment}',
        f'Kenya Gazette "{title_number}" land notice{county_fragment}',
        f'"{title_number}" "Land Registration Act 2012" conversion registry',
        f'"{title_number}" {zoning_authority}',
        f'"{title_number}" ownership history previous owner green card register{owner_fragment}',
    ]
