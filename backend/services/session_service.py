from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, HTTPException, UploadFile
from firebase_admin import firestore

try:
    from backend.agent.marathon_loop import AgentState, MarathonLoop, MarathonState
    from backend.repositories.audit_event_repository import AuditEventRepository
    from backend.repositories.session_repository import SessionRepository
    from backend.services.cloud_tasks import CloudTasksService
    from backend.services.firebase import db
except ModuleNotFoundError:
    from agent.marathon_loop import AgentState, MarathonLoop, MarathonState
    from repositories.audit_event_repository import AuditEventRepository
    from repositories.session_repository import SessionRepository
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
        if idempotency_key:
            existing = self._session_repository.resolve_idempotency_key(idempotency_key, user_id)
            if existing:
                return {
                    "session_id": existing,
                    "status": "QUEUED",
                    "message": "Existing investigation reused for idempotent request.",
                }

        suffix = os.path.splitext(file.filename or "")[1].lower()
        if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".mp4", ".mov"}:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

        session_id = str(uuid.uuid4())
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        initial_state = MarathonState(
            session_id=session_id,
            status=AgentState.QUEUED,
            image_path=tmp_path,
            memory=[f"Received initial file: {tmp_path}"],
        )

        self._session_repository.create(
            session_id=session_id,
            user_id=user_id,
            payload=initial_state.model_dump(),
            organization_id=organization_id,
        )
        if idempotency_key:
            self._session_repository.register_idempotency_key(idempotency_key, session_id, user_id)

        self._audit_events.append(
            session_id=session_id,
            event_type="audit.started",
            payload={"filename": file.filename, "status": AgentState.QUEUED.value},
            actor_id=user_id,
        )

        background_tasks.add_task(self.bootstrap, session_id, tmp_path, user_id)

        return {
            "session_id": session_id,
            "status": "QUEUED",
            "message": "Investigation starting. Analyzing document...",
        }

    def bootstrap(self, session_id: str, file_path: str, user_id: str) -> None:
        try:
            agent = MarathonLoop(self._db, session_id)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Bootstrap file missing: {file_path}")

            result = agent.run_single_step()
            self._audit_events.append(
                session_id=session_id,
                event_type="audit.bootstrap.completed",
                payload=result,
                actor_id=user_id,
            )
            if result["status"] == AgentState.RUNNING:
                self.cloud_tasks.schedule_next_tick(session_id, result["next_tick_seconds"])
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

    def tick(self, session_id: str) -> Dict[str, Any]:
        agent = MarathonLoop(self._db, session_id)
        result = agent.run_single_step()
        self._audit_events.append(
            session_id=session_id,
            event_type="audit.tick",
            payload=result,
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


session_service = SessionService()
