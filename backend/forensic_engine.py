from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting
from models import Document, AuditRequest, DocumentType
from config import settings

# Initialize Vertex AI
vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.VERTEX_AI_LOCATION)

# --- SYSTEM PROMPT ---
SYSTEM_INSTRUCTION = """
You are an expert Forensic Land Auditor and Conveyancing Lawyer in Kenya. Your task is to analyze a set of real estate documents (Title Deed, Green Card, Mutation Form) and identify risks of fraud, forgery, or procedural error.

Operational Constraints:
1. Think step-by-step.
2. Quote specific data points.
3. Reference specific sections of the Land Registration Act 2012.
4. If handwriting is illegible, state "Illegible".

Task:
Analyze the provided images of land documents.
Output a JSON object ONLY, with the following structure:
{
  "documents_identified": ["list of document types found"],
  "entries": [
      {
        "entry_no": "string",
        "date": "DD/MM/YYYY",
        "nature": "string (e.g. Charge, Discharge, Transfer)",
        "party_name": "string",
        "id_no": "string"
      }
  ],
  "mutation_details": {
      "surveyor_name": "string or null",
      "plot_size": "string or null"
  },
  "sale_agreement_details": {
      "seller_name": "string or null",
      "buyer_name": "string or null",
      "sale_date": "DD/MM/YYYY or null"
  },
  "raw_analysis": "Your step-by-step forensic reasoning here."
}
"""

# --- MOCK DATABASES (Kept for Phase 1) ---
BAD_ACTOR_DB = {
    "surveyors": ["James Kamwere", "Samuel Ochieng"], 
    "developers": ["Lesedi Developers", "Gakuyo Real Estate", "Ekeza Sacco"], 
}

# --- HELPERS ---

def parse_date(date_str: str) -> Optional[datetime]:
    if not date_str: return None
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        return None

def check_bad_actor(name: str, role: str) -> Optional[str]:
    if not name: return None
    if role == "surveyor" and name in BAD_ACTOR_DB["surveyors"]:
        return f"WARNING: Surveyor '{name}' is listed as Deregistered."
    if role == "developer" and name in BAD_ACTOR_DB["developers"]:
        return f"CRITICAL: Developer '{name}' is flagged for fraud."
    return None

# --- CORE LOGIC ---

def extract_data_with_gemini(image_parts: List[Part]) -> Dict[str, Any]:
    """
    Calls Gemini 1.5 Pro to extract structured data from document images.
    """
    model = GenerativeModel(settings.FORENSIC_MODEL_NAME, system_instruction=[SYSTEM_INSTRUCTION])
    
    generation_config = {
        "max_output_tokens": 8192,
        "temperature": 0.2,
        "response_mime_type": "application/json",
    }

    try:
        response = model.generate_content(
            image_parts,
            generation_config=generation_config,
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini Extraction Error: {e}")
        return {"error": str(e)}

def perform_forensic_audit(audit_request: AuditRequest, image_data: List[bytes] = None) -> List[str]:
    """
    Orchestrates the audit:
    1. Sends images to Vertex AI (Gemini) for Extraction.
    2. Runs deterministic Logic Engine on the extracted JSON.
    """
    findings = []
    
    # 1. AI Extraction
    extracted_data = {}
    if image_data:
        # Convert bytes to Vertex AI Parts
        parts = [Part.from_data(data=img, mime_type="image/jpeg") for img in image_data]
        # Add a text prompt to guide the extraction specifically
        parts.append("Extract data from these land documents.")
        
        extracted_data = extract_data_with_gemini(parts)
        # Store extracted data back into the request's first document for reference (simplified)
        if audit_request.documents:
            audit_request.documents[0].extracted_data = extracted_data
    elif audit_request.documents and audit_request.documents[0].extracted_data:
        # data already provided (e.g. from mock)
         extracted_data = audit_request.documents[0].extracted_data
    
    # 2. Deterministic Logic Checks
    
    # Chronological Logic (Green Card)
    entries = extracted_data.get("entries", [])
    if entries:
        # Sort by Entry No (handling potential non-int entry nos)
        entries.sort(key=lambda x: int(x.get("entry_no", 0)) if str(x.get("entry_no", "0")).isdigit() else 0)
        
        previous_date = None
        charges = {} 
        
        for entry in entries:
            current_date_str = entry.get("date")
            current_date = parse_date(current_date_str)
            
            # Rule 1: Sequence
            if previous_date and current_date and current_date < previous_date:
                findings.append(f"CRITICAL: Temporal Anomaly at Entry {entry.get('entry_no')}. Date ({current_date_str}) is earlier than previous entry.")
            
            if current_date:
                previous_date = current_date
            
            # Track Charges
            nature = entry.get("nature", "").lower()
            if "charge" in nature and "discharge" not in nature:
                charges[entry.get("entry_no")] = entry
            elif "discharge" in nature:
                if not charges:
                    findings.append(f"WARNING: Discharge at Entry {entry.get('entry_no')} without visible preceding Charge.")
                else:
                    # Check against the last open charge
                    last_charge_entry_no = list(charges.keys())[-1]
                    last_charge = charges[last_charge_entry_no]
                    
                    charge_date = parse_date(last_charge.get("date"))
                    discharge_date = parse_date(current_date_str)
                    
                    if charge_date and discharge_date and discharge_date < charge_date:
                         findings.append(f"CRITICAL: Forgery Risk. Discharge ({current_date_str}) predates Charge ({last_charge.get('date')}).")
                    
                    del charges[last_charge_entry_no]

        if charges:
             findings.append(f"CRITICAL: Undischarged Charge detected (Entries: {list(charges.keys())}). Land may be encumbered.")

    # Bad Actor Check
    mutation = extracted_data.get("mutation_details", {})
    if mutation and mutation.get("surveyor_name"):
        alert = check_bad_actor(mutation.get("surveyor_name"), "surveyor")
        if alert: findings.append(alert)

    sale = extracted_data.get("sale_agreement_details", {})
    if sale and sale.get("seller_name"):
        alert = check_bad_actor(sale.get("seller_name"), "developer")
        if alert: findings.append(alert)
    
    # Add AI's raw reasoning if available
    if extracted_data.get("raw_analysis"):
         findings.append(f"AI ANALYSIS: {extracted_data.get('raw_analysis')}")

    return findings
