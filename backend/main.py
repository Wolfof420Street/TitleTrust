from typing import Dict, Any, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from typing import List, Optional
import uuid

from .models import AuditRequest, Document, DocumentType, GeoCheck
from .forensic_engine import perform_forensic_audit
from .geospatial_engine import vision_map_sync

app = FastAPI(title="TitleTrust API", version="1.0.0")

@app.post("/audit/forensic", response_model=dict)
async def create_forensic_audit(
    files: List[UploadFile] = File(...),
):
    """
    Uploads a 'Deal Pack' of documents (Title Deed, Green Card, etc.) for forensic analysis.
    """
    request_id = str(uuid.uuid4())
    documents = []
    image_bytes_list = []
    
    # Process files
    for file in files:
        content = await file.read()
        image_bytes_list.append(content)
        
        # Determine likely type from filename (simple heuristic for MVP)
        filename = file.filename.lower()
        doc_type = DocumentType.OTHER
        if "green" in filename: doc_type = DocumentType.GREEN_CARD
        elif "title" in filename: doc_type = DocumentType.TITLE_DEED
        elif "mutation" in filename: doc_type = DocumentType.MUTATION_FORM
        elif "sale" in filename: doc_type = DocumentType.SALE_AGREEMENT
        
        documents.append(Document(
            document_id=str(uuid.uuid4()),
            type=doc_type,
            gcs_path=f"memory://{file.filename}" # Placeholder
        ))

    # Create Request
    audit_request = AuditRequest(
        request_id=request_id,
        user_id="user_demo", # authenticated user in real app
        documents=documents,
        status="PROCESSING"
    )
    
    # Run Audit
    # We pass the raw bytes for the AI to see
    findings = perform_forensic_audit(audit_request, image_data=image_bytes_list)
    
    audit_request.findings = findings
    audit_request.status = "FLAGGED" if any("CRITICAL" in f for f in findings) else "COMPLETED"
    
    return audit_request.model_dump()

@app.post("/audit/geospatial", response_model=GeoCheck)
async def create_geospatial_audit(
    lat: float = Form(...),
    lng: float = Form(...),
    image: UploadFile = File(...)
):
    """
    Uploads a site photo/video frame + coords for Vision-Map Sync.
    """
    content = await image.read()
    
    # Run Sync
    result = vision_map_sync(lat, lng, content)
    
    return result

@app.get("/")
def health_check():
    return {"status": "TitleTrust Backend Operational"}
