import os
import re
import json
import logging
import requests
import base64
from io import BytesIO
from typing import Dict, Any, List, Optional
from datetime import datetime

# Third-party Imports
import googlemaps
from google import genai
from google.genai import types

# Local Config
from config import settings

# --- SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [TOOLS] - %(message)s")
logger = logging.getLogger(__name__)

# Initialize Google Maps Client
# Production: Fail fast if Key is missing
gmaps = googlemaps.Client(key=settings.MAPS_API_KEY)

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
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        
        # Convert binary to base64 for Gemini
        image_b64 = base64.b64encode(response.content).decode("utf-8")
        
        return {
            "status": "success",
            "mime_type": "image/png",
            "data": image_b64,
            "metadata": f"Satellite view of {lat}, {lng} at zoom {zoom}"
        }
    except Exception as e:
        print(f"❌ [TOOL ERROR] Maps API failed: {e}")
        return {"status": "error", "error": str(e)}

def get_satellite_ground_truth(lat: float, lng: float) -> Dict[str, Any]:
    """
    Fetches official map data (Reverse Geocoding + Nearby Places) from Google Maps.
    Used to detect if land is in a protected area (River, Park, School).
    """
    logger.info(f"Querying Maps API for: {lat}, {lng}")
    
    if not gmaps:
        return {"error": "Maps API not configured."}

    context = {
        "coordinates": f"{lat},{lng}", 
        "timestamp": datetime.now().isoformat(),
        "risk_factors": []
    }

    try:
        # 1. Reverse Geocode (What is the legal address?)
        reverse = gmaps.reverse_geocode((lat, lng))
        if reverse:
            context["formatted_address"] = reverse[0].get('formatted_address', 'Unknown')
            # Extract types (e.g., 'park', 'political', 'establishment')
            context["location_types"] = reverse[0].get('types', [])

        # 2. Nearby Search (Are we near sensitive features?)
        # We search 200m radius for protected features
        places = gmaps.places_nearby(
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
