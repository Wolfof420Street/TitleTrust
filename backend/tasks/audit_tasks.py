from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

try:
    from backend.forensic_engine import perform_forensic_audit
    from backend.geospatial_engine import vision_map_sync
    from backend.models import AuditRequest, Document, DocumentType
except ModuleNotFoundError:
    from forensic_engine import perform_forensic_audit
    from geospatial_engine import vision_map_sync
    from models import AuditRequest, Document, DocumentType

logger = logging.getLogger("TitleTrust-AuditTasks")


def run_forensic_task(job_id: str, user_id: str, file_paths: List[str]) -> Dict[str, Any]:
    documents = [
        Document(document_id=f"{job_id}:{index}", type=DocumentType.OTHER, gcs_path=f"temp://{path}")
        for index, path in enumerate(file_paths)
    ]
    request = AuditRequest(
        request_id=job_id,
        user_id=user_id,
        documents=documents,
        status="PROCESSING",
    )
    findings = perform_forensic_audit(request, file_paths=file_paths)
    status = "FLAGGED" if any("CRITICAL" in str(finding) for finding in findings) else "COMPLETED"
    return {
        "request_id": job_id,
        "status": status,
        "findings": findings,
    }


def run_geospatial_task(job_id: str, lat: float, lng: float, file_path: str) -> Dict[str, Any]:
    return vision_map_sync(lat, lng, file_path)


def cleanup_files(file_paths: List[str]) -> None:
    for path in file_paths:
        if os.path.exists(path):
            os.remove(path)
