from __future__ import annotations

from typing import Any, Dict, Optional

from firebase_admin import firestore

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings


class JobRepository:
    def __init__(self, db: firestore.Client) -> None:
        self._jobs = db.collection(settings.JOB_COLLECTION)
        self._dead_letters = db.collection(settings.DEAD_LETTER_COLLECTION)

    def create(self, job_id: str, payload: Dict[str, Any]) -> None:
        self._jobs.document(job_id).set(
            {
                **payload,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        doc = self._jobs.document(job_id).get()
        return doc.to_dict() if doc.exists else None

    def update(self, job_id: str, payload: Dict[str, Any]) -> None:
        self._jobs.document(job_id).set(
            {
                **payload,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def dead_letter(self, job_id: str, payload: Dict[str, Any]) -> None:
        self._dead_letters.document(job_id).set(
            {
                **payload,
                "moved_at": firestore.SERVER_TIMESTAMP,
            }
        )
