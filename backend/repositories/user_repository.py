from __future__ import annotations

from typing import Any, Dict, Optional

from firebase_admin import firestore

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings


class UserRepository:
    """Repository for user persistence."""
    
    def __init__(self, db: firestore.Client) -> None:
        self._db = db
        self._collection = db.collection(settings.USERS_COLLECTION)

    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        doc = self._collection.document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def create(self, user_id: str, payload: Dict[str, Any]) -> None:
        """Create or initialize user document."""
        self._collection.document(user_id).set(
            {
                **payload,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

    def update(self, user_id: str, payload: Dict[str, Any]) -> None:
        """Update user document."""
        self._collection.document(user_id).set(
            {**payload, "updated_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )

    def get_fcm_token(self, user_id: str) -> Optional[str]:
        """Get FCM token for push notifications."""
        doc = self._collection.document(user_id).get()
        if not doc.exists:
            return None
        return doc.to_dict().get("fcm_token")

    def set_fcm_token(self, user_id: str, fcm_token: str) -> None:
        """Update FCM token for user."""
        self._collection.document(user_id).set(
            {"fcm_token": fcm_token, "updated_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )

    def remove_fcm_token(self, user_id: str) -> None:
        """Remove FCM token from user."""
        self._collection.document(user_id).set(
            {"fcm_token": firestore.DELETE_FIELD, "updated_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )
