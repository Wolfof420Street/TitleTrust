from __future__ import annotations

from typing import Any, Dict, List

from firebase_admin import firestore

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings


class DeviceSessionRepository:
    def __init__(self, db: firestore.Client) -> None:
        self._sessions = db.collection(settings.DEVICE_SESSION_COLLECTION)

    def upsert(self, session_id: str, payload: Dict[str, Any]) -> None:
        self._sessions.document(session_id).set(
            {
                **payload,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def revoke(self, session_id: str, user_id: str) -> None:
        self._sessions.document(session_id).set(
            {
                "revoked": True,
                "user_id": user_id,
                "request_secret_ciphertext": firestore.DELETE_FIELD,
                "request_secret_fingerprint": firestore.DELETE_FIELD,
                "previous_request_secret_ciphertext": firestore.DELETE_FIELD,
                "previous_request_secret_fingerprint": firestore.DELETE_FIELD,
                "request_secret_revoked_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def get(self, session_id: str) -> Dict[str, Any] | None:
        doc = self._sessions.document(session_id).get()
        if not doc.exists:
            return None
        return doc.to_dict()

    def list_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        docs = self._sessions.where("user_id", "==", user_id).stream()
        return [doc.to_dict() for doc in docs]
