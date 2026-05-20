from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, HTTPException, UploadFile

try:
    from backend.config import settings
    from backend.events.job_events import JobEvent
    from backend.queues.redis_queue import RedisQueue
    from backend.repositories.audit_event_repository import AuditEventRepository
    from backend.repositories.job_repository import JobRepository
    from backend.services.firebase import db
    from backend.workers.runtime import worker_runtime
except ModuleNotFoundError:
    from config import settings
    from events.job_events import JobEvent
    from queues.redis_queue import RedisQueue
    from repositories.audit_event_repository import AuditEventRepository
    from repositories.job_repository import JobRepository
    from services.firebase import db
    from workers.runtime import worker_runtime

logger = logging.getLogger("TitleTrust-BackgroundJobService")

ALLOWED_DOC_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_MEDIA_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".mp4", ".mov"}
MAX_FILE_SIZE = 50 * 1024 * 1024


class BackgroundJobService:
    def __init__(self) -> None:
        self._jobs = JobRepository(db)
        self._audit_events = AuditEventRepository(db)
        self._queue = RedisQueue()

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

    @staticmethod
    def _persist_upload(file: UploadFile, suffix: str) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            return tmp.name

    def _emit(self, event: JobEvent, actor_id: Optional[str] = None) -> None:
        self._audit_events.append(
            session_id=event.job_id,
            event_type=event.event_type,
            payload=event.payload,
            actor_id=actor_id,
        )

    def enqueue_forensic(
        self,
        *,
        files: List[UploadFile],
        user_id: str,
        organization_id: str,
        background_tasks: BackgroundTasks,
        correlation_id: Optional[str],
    ) -> Dict[str, Any]:
        job_id = str(uuid.uuid4())
        file_paths: List[str] = []
        for file in files:
            suffix = self._validate(file, ALLOWED_DOC_SUFFIXES)
            file_paths.append(self._persist_upload(file, suffix))

        payload = {
            "job_id": job_id,
            "job_type": "forensic",
            "status": "QUEUED",
            "user_id": user_id,
            "organization_id": organization_id,
            "file_paths": file_paths,
            "attempts": 0,
            "correlation_id": correlation_id,
            "priority": "high",
        }
        self._jobs.create(job_id, payload)
        self._emit(JobEvent(job_id=job_id, event_type="job.queued", payload={"job_type": "forensic", "file_count": len(file_paths)}), actor_id=user_id)
        self._dispatch(payload, background_tasks)
        return {"job_id": job_id, "status": "QUEUED", "job_type": "forensic"}

    def enqueue_geospatial(
        self,
        *,
        lat: float,
        lng: float,
        file: UploadFile,
        user_id: str,
        organization_id: str,
        background_tasks: BackgroundTasks,
        correlation_id: Optional[str],
    ) -> Dict[str, Any]:
        job_id = str(uuid.uuid4())
        suffix = self._validate(file, ALLOWED_MEDIA_SUFFIXES)
        file_path = self._persist_upload(file, suffix)
        payload = {
            "job_id": job_id,
            "job_type": "geospatial",
            "status": "QUEUED",
            "user_id": user_id,
            "organization_id": organization_id,
            "file_path": file_path,
            "lat": lat,
            "lng": lng,
            "attempts": 0,
            "correlation_id": correlation_id,
            "priority": "high",
        }
        self._jobs.create(job_id, payload)
        self._emit(JobEvent(job_id=job_id, event_type="job.queued", payload={"job_type": "geospatial"}), actor_id=user_id)
        self._dispatch(payload, background_tasks)
        return {"job_id": job_id, "status": "QUEUED", "job_type": "geospatial"}

    def _dispatch(self, payload: Dict[str, Any], background_tasks: BackgroundTasks) -> None:
        if settings.QUEUE_MODE == "redis" and self._queue.enabled:
            self._queue.enqueue(settings.WORKER_QUEUE_NAME, payload, priority=payload.get("priority", "default"))
            return
        background_tasks.add_task(worker_runtime.process_job, payload)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._jobs.get(job_id)

    def cancel_job(self, job_id: str, user_id: str) -> Dict[str, Any]:
        job = self._jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        self._jobs.update(job_id, {"status": "CANCELLED"})
        self._queue.cancel(job_id)
        self._emit(JobEvent(job_id=job_id, event_type="job.cancel_requested", payload={}), actor_id=user_id)
        return {"job_id": job_id, "status": "CANCELLED", "job_type": job.get("job_type", "unknown")}


background_job_service = BackgroundJobService()
