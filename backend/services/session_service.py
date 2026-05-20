from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, HTTPException, UploadFile
from firebase_admin import firestore
from google.api_core.exceptions import (
    AlreadyExists,
    DeadlineExceeded,
    NotFound,
    PermissionDenied,
    ServiceUnavailable,
)

try:
    from backend.agent.marathon_loop import AgentState, MarathonLoop, MarathonState
    from backend.repositories.audit_event_repository import AuditEventRepository
    from backend.repositories.session_repository import SessionRepository
    from backend.services.cloud_storage_service import cloud_storage_service
    from backend.services.cloud_tasks import CloudTasksService
    from backend.services.firebase import db
except ModuleNotFoundError:
    from agent.marathon_loop import AgentState, MarathonLoop, MarathonState
    from repositories.audit_event_repository import AuditEventRepository
    from repositories.session_repository import SessionRepository
    from services.cloud_storage_service import cloud_storage_service
    from services.cloud_tasks import CloudTasksService
    from services.firebase import db

logger = logging.getLogger("TitleTrust-SessionService")


class SessionService:
    def __init__(self) -> None:
        self._db = db
        self._session_repository = SessionRepository(db)
        self._audit_events = AuditEventRepository(db)
        self.cloud_tasks = CloudTasksService()

    def start_marathon(
        self,
        file: UploadFile,
        user_id: str,
        organization_id: str,
        background_tasks: BackgroundTasks,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        existing = self._existing_idempotent_session(idempotency_key, user_id)
        if existing:
            return existing
        suffix = self._validate_supported_suffix(file.filename or "")
        upload_result = cloud_storage_service.upload_fileobj(
            file_obj=file.file,
            filename=file.filename or "upload",
            content_type=getattr(file, "content_type", None),
            user_id=user_id,
            organization_id=organization_id,
            purpose="marathon-start",
        )
        return self._create_session_from_source(
            file_name=file.filename or "upload",
            user_id=user_id,
            organization_id=organization_id,
            background_tasks=background_tasks,
            idempotency_key=idempotency_key,
            source_uri=str(upload_result["object_path"]),
            source_mime_type=str(upload_result["content_type"] or self._mime_type_for_suffix(suffix)),
        )

    def start_marathon_from_storage(
        self,
        object_path: str,
        original_filename: str,
        user_id: str,
        organization_id: str,
        background_tasks: BackgroundTasks,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        existing = self._existing_idempotent_session(idempotency_key, user_id)
        if existing:
            return existing
        suffix = self._validate_supported_suffix(original_filename)
        return self._create_session_from_source(
            file_name=original_filename,
            user_id=user_id,
            organization_id=organization_id,
            background_tasks=background_tasks,
            idempotency_key=idempotency_key,
            source_uri=object_path,
            source_mime_type=self._mime_type_for_suffix(suffix),
        )

    def _create_session_from_source(
        self,
        *,
        file_name: str,
        user_id: str,
        organization_id: str,
        background_tasks: BackgroundTasks,
        idempotency_key: Optional[str],
        source_uri: str,
        source_mime_type: str,
    ) -> Dict[str, Any]:
        session_id = str(uuid.uuid4())
        initial_state = MarathonState(
            session_id=session_id,
            status=AgentState.QUEUED,
            image_uri=source_uri,
            image_mime_type=source_mime_type,
            source_filename=file_name,
            memory=[f"Received initial object: {source_uri}"],
        )

        try:
            self._session_repository.create(
                session_id=session_id,
                user_id=user_id,
                payload=initial_state.model_dump(),
                organization_id=organization_id,
            )
        except AlreadyExists as exc:
            raise HTTPException(status_code=409, detail="Session already exists") from exc

        if idempotency_key:
            self._session_repository.register_idempotency_key(idempotency_key, session_id, user_id)

        self._audit_events.append(
            session_id=session_id,
            event_type="audit.started",
            payload={
                "filename": file_name,
                "status": AgentState.QUEUED.value,
                "source_uri": source_uri,
            },
            actor_id=user_id,
        )

        background_tasks.add_task(self.bootstrap, session_id, user_id)

        return {
            "session_id": session_id,
            "status": "QUEUED",
            "message": "Investigation starting. Analyzing document...",
        }

    @staticmethod
    def _validate_supported_suffix(filename: str) -> str:
        suffix = os.path.splitext(filename)[1].lower()
        if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".mp4", ".mov"}:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
        return suffix

    @staticmethod
    def _mime_type_for_suffix(suffix: str) -> str:
        return {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
        }.get(suffix, "application/octet-stream")

    def _existing_idempotent_session(self, idempotency_key: Optional[str], user_id: str) -> Dict[str, Any] | None:
        if not idempotency_key:
            return None
        existing = self._session_repository.resolve_idempotency_key(idempotency_key, user_id)
        if not existing:
            return None
        existing_session = self._session_repository.get(existing) or {}
        return {
            "session_id": existing,
            "status": existing_session.get("status", AgentState.QUEUED.value),
            "message": "Existing investigation reused for idempotent request.",
        }

    def bootstrap(self, session_id: str, user_id: str) -> None:
        try:
            data = self._session_repository.get(session_id)
            if not data:
                logger.error("Bootstrap skipped: missing session", extra={"session_id": session_id, "user_id": user_id})
                return

            agent = MarathonLoop(self._db, session_id)
            result = agent.run_single_step()
            self._audit_events.append(
                session_id=session_id,
                event_type="audit.bootstrap.completed",
                payload=result,
                actor_id=user_id,
            )
            if result["status"] == AgentState.RUNNING:
                self.cloud_tasks.schedule_next_tick(session_id, result["next_tick_seconds"])
        except (NotFound, PermissionDenied, DeadlineExceeded, ServiceUnavailable) as exc:
            logger.exception("Bootstrap failed due to cloud storage access")
            self._session_repository.update(
                session_id,
                {
                    "status": AgentState.FAILED.value,
                    "error": self._user_facing_source_error(exc),
                },
            )
            self._audit_events.append(
                session_id=session_id,
                event_type="audit.bootstrap.failed",
                payload={"error": str(exc)},
                actor_id=user_id,
            )
        except Exception as exc:
            logger.exception("Bootstrap failed")
            self._session_repository.update(
                session_id,
                {
                    "status": AgentState.FAILED.value,
                    "error": f"Bootstrap failed: {exc}",
                },
            )
            self._audit_events.append(
                session_id=session_id,
                event_type="audit.bootstrap.failed",
                payload={"error": str(exc)},
                actor_id=user_id,
            )

    def tick(self, session_id: str, user_id: str) -> Dict[str, Any]:
        data = self._session_repository.get(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        if data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        agent = MarathonLoop(self._db, session_id)
        result = agent.run_single_step()
        self._audit_events.append(
            session_id=session_id,
            event_type="audit.tick",
            payload=result,
            actor_id=user_id,
        )
        status = result["status"]
        if status == AgentState.RUNNING:
            self.cloud_tasks.schedule_next_tick(session_id, result["next_tick_seconds"])
        return {"status": "success", "agent_status": status}

    def get_status(self, session_id: str, user_id: str) -> Dict[str, Any]:
        data = self._session_repository.get(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        if data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return {
            "session_id": session_id,
            "status": data.get("status"),
            "progress": data.get("progress_checklist", {}),
            "total_steps": data.get("total_steps", 0),
            "last_thought": data.get("last_thought") or data.get("latest_thought"),
            "error": data.get("error"),
            "findings": data.get("findings", []),
            "audit_conclusion": data.get("audit_conclusion"),
        }

    def retry(self, session_id: str, user_id: str) -> Dict[str, Any]:
        data = self._session_repository.get(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        if data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        status = data.get("status")
        if status not in [AgentState.FAILED.value, AgentState.WAITING_FOR_USER.value, AgentState.QUEUED.value]:
            raise HTTPException(status_code=400, detail=f"Cannot retry session with status: {status}")

        retry_count = int(data.get("retry_count", 0)) + 1
        self._session_repository.update(
            session_id,
            {
                "status": AgentState.RUNNING.value,
                "retry_count": retry_count,
                "last_update": firestore.SERVER_TIMESTAMP,
            },
        )
        self._audit_events.append(
            session_id=session_id,
            event_type="audit.retry.requested",
            payload={"retry_count": retry_count},
            actor_id=user_id,
        )
        self.cloud_tasks.schedule_next_tick(session_id, 1)
        return {
            "session_id": session_id,
            "status": "RETRYING",
            "message": "Session retry scheduled",
        }

    @staticmethod
    def _user_facing_source_error(exc: Exception) -> str:
        if isinstance(exc, NotFound):
            return "The uploaded document could not be found in cloud storage. Please upload it again."
        if isinstance(exc, PermissionDenied):
            return "The uploaded document could not be accessed due to a storage permission error."
        if isinstance(exc, (DeadlineExceeded, ServiceUnavailable)):
            return "The uploaded document could not be read from cloud storage right now. Please try again."
        return f"Bootstrap failed: {exc}"


session_service = SessionService()
