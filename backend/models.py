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
    trace_id: Optional[str] = None
    evidence_sha256: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class AuditRequest(BaseModel):
    request_id: str
    user_id: str
    documents: List[Document]
    status: str # PENDING, PROCESSING, COMPLETED, FLAGGED
    findings: List[str] = [] # List of "Red Flags" or human-readable findings
    geo_check: Optional[GeoCheck] = None
    created_at: datetime = Field(default_factory=datetime.now)

class ForgeryRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class VisualAnomaly(BaseModel):
    description: str = Field(..., description="Description of the visual flaw (e.g., 'Pixelated crest')")
    severity: str = Field(..., description="High, Medium, or Low")
    location: str = Field(..., description="Where on the document this occurs")

class VerificationStep(BaseModel):
    step_name: str = Field(..., description="The action taken (e.g., 'Registrar Verification')")
    evidence_found: str = Field(..., description="What was found via Search or Code Execution")
    status: str = Field(..., description="PASS or FAIL")

class ForensicReport(BaseModel):
    title_number: str = Field(..., description="The extracted title number")
    risk_score: int = Field(..., description="0 to 100 risk score")
    final_verdict: str = Field(..., description="AUTHENTIC, SUSPICIOUS, or FORGERY")
    reasoning_summary: str = Field(..., description="The chain of thought leading to this conclusion")
    visual_anomalies: List[VisualAnomaly]
    investigation_steps: List[VerificationStep]
    trace_id: Optional[str] = None
    evidence_sha256: Optional[str] = None

class LiveTokenRequest(BaseModel):
    session_id: str
    lat: float
    lng: float
    title_number: str
    expected_size: str
    user_name: str = "Surveyor"
