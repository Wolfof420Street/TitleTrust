from typing import Dict, Optional, List
import googlemaps
from vertexai.generative_models import GenerativeModel, Part
from .models import GeoCheck
from .config import settings

# Initialize Google Maps Client
gmaps = googlemaps.Client(key=settings.MAPS_API_KEY)

def analyze_user_image_with_gemini(image_data: bytes) -> str:
    """
    Uses Gemini Flash to analyze the user-uploaded image/video frame.
    Asks for a description of terrain, vegetation, and structures.
    """
    model = GenerativeModel(settings.VISION_MODEL_NAME)
    
    prompt = """
    Analyze this image of a plot of land. 
    Describe the:
    1. Terrain (flat, sloped, cliff?)
    2. Vegetation (dense forest, riverine, dry grass, crops?)
    3. Structures (vacant, buildings, roads?)
    4. Soil (red, black cotton, rocky?)
    Be concise.
    """
    
    try:
        response = model.generate_content(
            [Part.from_data(data=image_data, mime_type="image/jpeg"), prompt],
            generation_config={"max_output_tokens": 512}
        )
        return response.text
    except Exception as e:
        print(f"Gemini Vision Error: {e}")
        return "Error analyzing visual feed."

def get_map_metadata(lat: float, lng: float) -> List[str]:
    """
    Uses Google Maps Geocoding/Places to get context about the location.
    Retuns a list of feature tags (e.g. 'park', 'political', 'road').
    """
    features = []
    try:
        # Reverse Geocode to get types
        reverse_geocode_result = gmaps.reverse_geocode((lat, lng))
        
        if reverse_geocode_result:
            # Extract types from the most specific result
            features.extend(reverse_geocode_result[0].get("types", []))
            # Also get formatted address for context
            address = reverse_geocode_result[0].get("formatted_address", "")
            if "River" in address: features.append("river")
            if "Forest" in address: features.append("forest")
            
        # Optional: Place Search nearby for "River" or "Reserve"
        places_result = gmaps.places_nearby(location=(lat, lng), radius=200, output='json')
        if places_result.get('results'):
             for place in places_result['results']:
                 features.extend(place.get('types', []))
                 name = place.get('name', '').lower()
                 if "river" in name: features.append("river")
                 if "dam" in name: features.append("dam")

    except Exception as e:
        print(f"Google Maps API Error: {e}")
        
    return list(set(features))

def vision_map_sync(lat: float, lng: float, user_image_data: bytes) -> GeoCheck:
    """
    Performs the Vision-Map Sync using Real APIs.
    """
    check_id = f"GEO-{int(lat*10000)}-{int(lng*10000)}"
    
    # 1. Vision Analysis (Gemini Flash)
    user_vision_desc = analyze_user_image_with_gemini(user_image_data)
    
    # 2. Satellite reconciliation (Maps Metadata)
    map_features = get_map_metadata(lat, lng)
    
    # 3. Comparison Logic
    satellite_analysis = f"Map Context: {', '.join(map_features)}"
    risk_level = "LOW"
    
    # Hard Rules for Risk
    risk_keywords = ["natural_feature", "park", "point_of_interest"] # Broad for now
    
    # Check for Riparian context in Maps data
    is_riparian_map = any(x in map_features for x in ["river", "dam", "aquarium"]) # aquarium is unlikely but 'natural_feature' is broad
    
    # Check for Riparian context in Vision
    user_desc_lower = user_vision_desc.lower()
    is_riparian_visual = "river" in user_desc_lower or "swamp" in user_desc_lower or "wetland" in user_desc_lower
    
    if is_riparian_map or is_riparian_visual:
        risk_level = "CRITICAL"
        satellite_analysis += ". RIPARIAN RISK DETECTED."
    
    # Mismatch check (Simple Keyword overlap)
    # If map says 'built context' (building, street) but vision says 'dense forest' -> Mismatch
    # Detailed heuristic omitted for brevity, focusing on the API integrations.
    
    return GeoCheck(
        check_id=check_id,
        plot_coordinates={"lat": lat, "lng": lng},
        user_video_description=user_vision_desc,
        satellite_analysis_result=satellite_analysis,
        risk_level=risk_level
    )
