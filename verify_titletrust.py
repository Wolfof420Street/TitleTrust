import sys
from backend.models import AuditRequest, Document, DocumentType
from backend.forensic_engine import perform_forensic_audit, SYSTEM_INSTRUCTION
from backend.geospatial_engine import vision_map_sync

def test_forensic_engine():
    print("--- Testing Forensic Engine ---")
    
    # Mock Green Card Data (Fraudulent: Discharge before Charge)
    mock_extracted_data = {
        "entries": [
            {
                "entry_no": "1",
                "date": "01/01/2010",
                "nature": "Transfer to John Kamau",
                "party_name": "John Kamau"
            },
            {
                "entry_no": "2",
                "date": "15/06/2015",
                "nature": "Charge to Equity Bank",
                "party_name": "Equity Bank"
            },
            {
                "entry_no": "3",
                "date": "10/06/2015", # FRAUD: Discharge is BEFORE Charge!
                "nature": "Discharge of Charge",
                "party_name": "Equity Bank"
            }
        ]
    }
    
    doc = Document(
        document_id="doc_1",
        type=DocumentType.GREEN_CARD,
        gcs_path="gs://bucket/greencard.jpg",
        extracted_data=mock_extracted_data
    )
    
    request = AuditRequest(
        request_id="req_1",
        user_id="user_1",
        documents=[doc],
        status="PENDING"
    )
    
    findings = perform_forensic_audit(request)
    
    print(f"Findings: {findings}")
    
    # Assertions
    has_critical_error = any("CRITICAL" in f for f in findings)
    if has_critical_error:
        print("[PASS] Forensic Engine correctly flagged temporal anomaly.")
    else:
        print("[FAIL] Forensic Engine missed temporal anomaly.")
        sys.exit(1)

def test_geospatial_engine():
    print("\n--- Testing Geospatial Engine ---")
    
    # 1. Test Riparian Risk
    # Coords linked to Riparian Mock Data
    glat, glng = -1.2921, 36.8219 
    check = vision_map_sync(glat, glng, "I see a river and some trees.")
    
    print(f"Riparian Check Result: Risk={check.risk_level}, Analysis='{check.satellite_analysis_result}'")
    
    if check.risk_level == "CRITICAL" and "Riparian" in check.satellite_analysis_result:
        print("[PASS] Geospatial Engine correctly flagged Riparian Land.")
    else:
         print("[FAIL] Geospatial Engine missed Riparian Risk.")
         sys.exit(1)

    # 2. Test Mismatch (Bait and Switch)
    # Coords linked to 'Residential' (Flat, red soil)
    flat, flng = -1.1462, 36.9531
    # User claims they see a river (Mismatch)
    check_mismatch = vision_map_sync(flat, flng, "I see a river and heavy forest.")
    
    print(f"Mismatch Check Result: Risk={check_mismatch.risk_level}, Analysis='{check_mismatch.satellite_analysis_result}'")
    
    if check_mismatch.risk_level == "HIGH" and "Visual Discrepancy" in check_mismatch.satellite_analysis_result:
         print("[PASS] Geospatial Engine correctly flagged Visual Discrepancy.")
    else:
         print("[FAIL] Geospatial Engine missed Visual Discrepancy.")
         sys.exit(1)

def main():
    test_forensic_engine()
    test_geospatial_engine()
    print("\n=== SYSTEM INSTRUCTIONS (PROMPT) ===")
    print(SYSTEM_INSTRUCTION[:200] + "...") # Print snippet to verify

if __name__ == "__main__":
    main()
