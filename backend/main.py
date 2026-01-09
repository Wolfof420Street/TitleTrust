from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
import uuid

from models import AuditRequest, Document, DocumentType, GeoCheck
from forensic_engine import perform_forensic_audit
from geospatial_engine import vision_map_sync
from auth import get_current_user

app = FastAPI(title="TitleTrust API", version="1.0.0")

# Configure CORS middleware
# Configure CORS middleware
from config import settings
import os

# Read allowed origins from env or default to safe list
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080")
origins = [origin.strip() for origin in allowed_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.post("/audit/forensic", response_model=dict)
async def create_forensic_audit(
    files: List[UploadFile] = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
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
        user_id=user["uid"], # Authenticated user ID
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
    image: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
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
