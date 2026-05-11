import logging
import os
import tempfile
import shutil
import uuid
from typing import Any, Dict, List

from fastapi import HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

try:
    from backend.forensic_engine import perform_forensic_audit
    from backend.geospatial_engine import LiveGeospatialVerifier, vision_map_sync
    from backend.models import AuditRequest, Document, DocumentType
except ModuleNotFoundError:
    from forensic_engine import perform_forensic_audit
    from geospatial_engine import LiveGeospatialVerifier, vision_map_sync
    from models import AuditRequest, Document, DocumentType

logger = logging.getLogger("TitleTrust-AuditService")

ALLOWED_DOC_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_MEDIA_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".mp4", ".mov"}
MAX_FILE_SIZE = 50 * 1024 * 1024


class AuditService:
    def __init__(self) -> None:
        pass

    @staticmethod
    def _validate(file: UploadFile, allowed: set[str]) -> str:
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        suffix = os.path.splitext(file.filename or "")[1].lower()
        if suffix not in allowed:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
        if size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File {file.filename} exceeds 50MB limit")
        return suffix

    async def run_forensic(self, files: List[UploadFile], uid: str) -> Dict[str, Any]:
        request_id = str(uuid.uuid4())
        temp_paths: List[str] = []
        documents: List[Document] = []

        for file in files:
            suffix = self._validate(file, ALLOWED_DOC_SUFFIXES)
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(file.file, tmp)
                temp_paths.append(tmp.name)
            documents.append(
                Document(document_id=str(uuid.uuid4()), type=DocumentType.OTHER, gcs_path=f"temp://{temp_paths[-1]}")
            )

        try:
            request = AuditRequest(request_id=request_id, user_id=uid, documents=documents, status="PROCESSING")
            findings = await run_in_threadpool(perform_forensic_audit, request, file_paths=temp_paths)
            request.findings = findings
            request.status = "FLAGGED" if any("CRITICAL" in str(f) for f in findings) else "COMPLETED"
            return request.model_dump()
        finally:
            for path in temp_paths:
                if os.path.exists(path):
                    os.remove(path)

    async def run_geospatial(self, lat: float, lng: float, file: UploadFile) -> Dict[str, Any]:
        suffix = self._validate(file, ALLOWED_MEDIA_SUFFIXES)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        try:
            return await run_in_threadpool(vision_map_sync, lat, lng, tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def generate_live_token(self, req) -> Dict[str, Any]:
        verifier = LiveGeospatialVerifier()
        context = {
            "user": req.user_name,
            "title_number": req.title_number,
            "size": req.expected_size,
            "lat": req.lat,
            "lng": req.lng,
        }
        return await run_in_threadpool(verifier.generate_session_token, req.session_id, context)


audit_service = AuditService()
