from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional

from firebase_admin import firestore

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings


class AuditEventRepository:
    def __init__(self, db: firestore.Client) -> None:
        self._db = db
        self._collection = db.collection(settings.AUDIT_EVENT_COLLECTION)

    def append(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        actor_id: Optional[str] = None,
    ) -> str:
        events = (
            self._collection
            .where("session_id", "==", session_id)
            .order_by("sequence", direction=firestore.Query.DESCENDING)
            .limit(1)
            .stream()
        )
        previous = next(events, None)
        previous_hash = previous.to_dict().get("event_hash", "") if previous else ""
        sequence = (previous.to_dict().get("sequence", 0) + 1) if previous else 1

        canonical_payload = json.dumps(payload, sort_keys=True, default=str)
        event_hash = hashlib.sha256(
            f"{session_id}:{sequence}:{event_type}:{actor_id or ''}:{previous_hash}:{canonical_payload}".encode("utf-8")
        ).hexdigest()

        document_id = f"{session_id}-{sequence:06d}"
        self._collection.document(document_id).set(
            {
                "session_id": session_id,
                "sequence": sequence,
                "event_type": event_type,
                "payload": payload,
                "actor_id": actor_id,
                "previous_hash": previous_hash,
                "event_hash": event_hash,
                "created_at": firestore.SERVER_TIMESTAMP,
                "created_at_epoch": time.time(),
            }
        )
        return event_hash
