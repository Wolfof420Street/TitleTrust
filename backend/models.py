from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class DocumentType(str, Enum):
    TITLE_DEED = "title_deed"
    GREEN_CARD = "green_card"
    MUTATION_FORM = "mutation_form"
    SALE_AGREEMENT = "sale_agreement"
    OTHER = "other"

class Document(BaseModel):
    document_id: str
    type: DocumentType
    gcs_path: str
    upload_timestamp: datetime = Field(default_factory=datetime.now)
    extracted_data: Optional[Dict[str, Any]] = None # JSON extracted by Gemini

class User(BaseModel):
    user_id: str
    name: str 
    email: str
    phone_number: str

class GeoCheck(BaseModel):
    check_id: str
    plot_coordinates: Dict[str, float] # {"lat": -1.2, "lng": 36.8}
    user_video_description: Optional[str] = None
    satellite_analysis_result: str
    risk_level: str # LOW, MEDIUM, CRITICAL
    timestamp: datetime = Field(default_factory=datetime.now)

class AuditRequest(BaseModel):
    request_id: str
    user_id: str
    documents: List[Document]
    status: str # PENDING, PROCESSING, COMPLETED, FLAGGED
    findings: List[str] = [] # List of "Red Flags" or human-readable findings
    geo_check: Optional[GeoCheck] = None
    created_at: datetime = Field(default_factory=datetime.now)
