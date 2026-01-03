import pytest
import os
from unittest.mock import MagicMock

# Set dummy env vars before importing backend components to avoid validation errors
os.environ["GCP_PROJECT_ID"] = "test-project"
os.environ["MAPS_API_KEY"] = "test-key"
os.environ["VERTEX_AI_LOCATION"] = "us-central1"

@pytest.fixture
def mock_pdf_bytes():
    return b"%PDF-1.4 mock pdf content"

@pytest.fixture
def mock_image_bytes():
    return b"\xFF\xD8\xFF\xE0 mock jpeg content"

@pytest.fixture
def mock_gemini_response():
    class MockResponse:
        def __init__(self, text_content):
            self.text = text_content
    return MockResponse
