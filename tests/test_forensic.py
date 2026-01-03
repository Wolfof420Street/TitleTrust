import pytest
from unittest.mock import patch, MagicMock
import json
from backend.models import AuditRequest, Document, DocumentType

# Patch Vertex AI init to avoid real network calls on import
with patch("vertexai.init"):
    from backend.forensic_engine import perform_forensic_audit

def test_forensic_clean_case(mock_image_bytes, mock_gemini_response):
    """
    Test Case A: Mock Gemini returning 'Clean' data.
    """
    # 1. Prepare Mock Data
    clean_data = {
        "documents_identified": ["Green Card"],
        "entries": [
            {"entry_no": "1", "date": "01/01/2020", "nature": "Transfer", "party_name": "Seller A"},
            {"entry_no": "2", "date": "01/02/2020", "nature": "Charge to Bank X", "party_name": "Bank X"},
            {"entry_no": "3", "date": "01/06/2020", "nature": "Discharge of Charge", "party_name": "Bank X"}
        ],
        "raw_analysis": "All dates follow logical sequence."
    }
    
    # 2. Mock the Gemini Model
    with patch("backend.forensic_engine.GenerativeModel") as MockModel:
        mock_instance = MockModel.return_value
        mock_instance.generate_content.return_value = mock_gemini_response(json.dumps(clean_data))
        
        # 3. Create Request
        req = AuditRequest(
            request_id="test_1", 
            user_id="u1", 
            documents=[Document(document_id="d1", type=DocumentType.GREEN_CARD, gcs_path="mem://test")]
        )
        
        # 4. Run Function
        findings = perform_forensic_audit(req, image_data=[mock_image_bytes])
        
        # 5. Assertions
        assert len(findings) == 1 # Only the raw analysis
        assert "CRITICAL" not in str(findings)
        assert "WARNING" not in str(findings)
        assert "AI ANALYSIS" in findings[0]

def test_forensic_fraud_case(mock_image_bytes, mock_gemini_response):
    """
    Test Case B: Mock Gemini returning a Temporal Anomaly.
    Discharge Date (Jan) < Charge Date (Feb).
    """
    # 1. Prepare Fraud Data
    fraud_data = {
        "documents_identified": ["Green Card"],
        "entries": [
            {"entry_no": "1", "date": "01/01/2020", "nature": "Transfer", "party_name": "Seller A"},
            {"entry_no": "2", "date": "15/02/2020", "nature": "Charge to Bank X", "party_name": "Bank X"},
            {"entry_no": "3", "date": "10/01/2020", "nature": "Discharge of Charge", "party_name": "Bank X"} 
            # FRAUD: Discharge 10th Jan is BEFORE Charge 15th Feb
        ],
        "raw_analysis": "Detected temporal anomaly."
    }
    
    # 2. Mock the Gemini Model
    with patch("backend.forensic_engine.GenerativeModel") as MockModel:
        mock_instance = MockModel.return_value
        mock_instance.generate_content.return_value = mock_gemini_response(json.dumps(fraud_data))
        
        # 3. Create Request
        req = AuditRequest(
            request_id="test_2", 
            user_id="u1", 
            documents=[Document(document_id="d2", type=DocumentType.GREEN_CARD, gcs_path="mem://test")]
        )
        
        # 4. Run Function
        findings = perform_forensic_audit(req, image_data=[mock_image_bytes])
        
        # 5. Assertions
        # Should flag CRITICAL: Forgery Risk
        assert any("CRITICAL: Forgery Risk" in f for f in findings)
