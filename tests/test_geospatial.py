import pytest
from unittest.mock import patch, MagicMock
from backend.models import GeoCheck

# Patch Clients
with patch("googlemaps.Client"):
    from backend.geospatial_engine import vision_map_sync

def test_geospatial_visual_discrepancy(mock_image_bytes, mock_gemini_response):
    """
    Test Case: Bait and Switch.
    Vision: 'Forest/River'
    Map: 'Desert/Arid' (implied by lack of river/forest features)
    """
    
    # 1. Mock Gemini (Vision)
    # Says "I see a dense forest and a river"
    mock_vision_resp = mock_gemini_response("I see a dense forest and a river.")
    
    # 2. Mock Google Maps (Metadata)
    # Returns "desert", "sand" -> No River keys
    mock_gmaps_features = ["desert", "sand", "arid"]
    
    with patch("backend.geospatial_engine.GenerativeModel") as MockModel, \
         patch("backend.geospatial_engine.get_map_metadata") as mock_get_meta:
        
        # Setup Vision Mock
        mock_instance = MockModel.return_value
        mock_instance.generate_content.return_value = mock_vision_resp
        
        # Setup Map Mock
        mock_get_meta.return_value = mock_gmaps_features
        
        # 3. Run Sync
        # Coords don't matter much as we mocked the metadata return
        result = vision_map_sync(lat=-1.0, lng=37.0, user_image_data=mock_image_bytes)
        
        # 4. Assertions
        # Vision says "River", Map does NOT -> Should be CRITICAL (Riparian Visual) or HIGH (Mismatch)
        # In our current logic: if visual says "river", and logic flags riparian_visual=True -> CRITICAL
        
        assert result.risk_level == "CRITICAL"
        assert "RIPARIAN RISK DETECTED" in result.satellite_analysis_result
