import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Patch dependencies before importing main to avoid init calls
with patch("vertexai.init"), patch("googlemaps.Client"):
    from backend.main import app

client = TestClient(app)

def test_api_forensic_endpoint(mock_image_bytes):
    """
    Test POST /audit/forensic with file upload.
    """
    # Mock the internal engine to return a fixed result
    with patch("backend.main.perform_forensic_audit") as mock_engine:
        mock_engine.return_value = ["AI ANALYSIS: Clean."]
        
        files = {
            "files": ("test_doc.jpg", mock_image_bytes, "image/jpeg")
        }
        
        response = client.post("/audit/forensic", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert len(data["findings"]) == 1
        assert "cleaned" not in data # simplistic check

def test_api_geospatial_endpoint(mock_image_bytes):
    """
    Test POST /audit/geospatial with form data + file.
    """
    from backend.models import GeoCheck
    
    mock_result = GeoCheck(
        check_id="GEO-TEST",
        plot_coordinates={"lat": -1.2, "lng": 36.8},
        user_video_description="Test Vision",
        satellite_analysis_result="Test Map",
        risk_level="LOW"
    )
    
    with patch("backend.main.vision_map_sync") as mock_sync:
        mock_sync.return_value = mock_result
        
        payload = {
            "lat": "-1.2",
            "lng": "36.8"
        }
        files = {
            "image": ("site.jpg", mock_image_bytes, "image/jpeg")
        }
        
        response = client.post("/audit/geospatial", data=payload, files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["check_id"] == "GEO-TEST"
        assert data["risk_level"] == "LOW"
