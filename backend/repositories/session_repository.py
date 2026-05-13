from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from firebase_admin import firestore

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings


@dataclass
class SessionRecord:
    session_id: str
    user_id: str
    data: Dict[str, Any]


class SessionRepository:
    def __init__(self, db: firestore.Client) -> None:
        self._db = db
        self._collection = db.collection(settings.SESSION_COLLECTION)
        self._idempotency = db.collection(settings.IDEMPOTENCY_COLLECTION)

    def create(self, session_id: str, user_id: str, payload: Dict[str, Any], organization_id: str) -> None:
        self._collection.document(session_id).create(
            {
                **payload,
                "user_id": user_id,
                "organization_id": organization_id,
                "created_at": firestore.SERVER_TIMESTAMP,
                "last_update": firestore.SERVER_TIMESTAMP,
            }
        )

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        doc = self._collection.document(session_id).get()
        return doc.to_dict() if doc.exists else None

    def update(self, session_id: str, payload: Dict[str, Any]) -> None:
        self._collection.document(session_id).set(
            {**payload, "last_update": firestore.SERVER_TIMESTAMP},
            merge=True,
        )

    def register_idempotency_key(self, key: str, session_id: str, user_id: str) -> None:
        self._idempotency.document(key).set(
            {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )

    def resolve_idempotency_key(self, key: str, user_id: str) -> Optional[str]:
        doc = self._idempotency.document(key).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        if data.get("user_id") != user_id:
            return None
        return data.get("session_id")
