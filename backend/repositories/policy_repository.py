from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from firebase_admin import firestore

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings


DEFAULT_POLICY = {
    "version": 1,
    "statements": [
        {
            "effect": "allow",
            "actions": ["audit:start", "forensic:run", "geospatial:run", "titbits:read"],
            "roles": ["analyst", "auditor", "super_admin"],
        },
        {
            "effect": "allow",
            "actions": ["audit:read", "audit:retry"],
            "roles": ["auditor", "super_admin"],
        },
        {
            "effect": "allow",
            "actions": ["audit:read"],
            "roles": ["reviewer", "analyst"],
            "conditions": {"owner_only": True},
        },
    ],
}

DENY_ALL_POLICY = {
    "version": 1,
    "statements": [],
}


class PolicyRepository:
    def __init__(self, db: firestore.Client) -> None:
        self._policies = db.collection(settings.POLICY_COLLECTION)
        self._memberships = db.collection(settings.MEMBERSHIP_COLLECTION)

    def get_policy(self, organization_id: str) -> Dict[str, Any]:
        doc = self._policies.document(organization_id).get()
        if not doc.exists:
            return copy.deepcopy(DENY_ALL_POLICY)
        return doc.to_dict() or copy.deepcopy(DENY_ALL_POLICY)

    def get_membership(self, organization_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        document_id = f"{organization_id}:{user_id}"
        doc = self._memberships.document(document_id).get()
        return doc.to_dict() if doc.exists else None

    def upsert_membership(self, organization_id: str, user_id: str, payload: Dict[str, Any]) -> None:
        document_id = f"{organization_id}:{user_id}"
        self._memberships.document(document_id).set(
            {
                **payload,
                "organization_id": organization_id,
                "user_id": user_id,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
