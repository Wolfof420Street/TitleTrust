from __future__ import annotations

from typing import Dict, List

try:
    from backend.repositories.device_session_repository import DeviceSessionRepository
    from backend.services.firebase import db
except ModuleNotFoundError:
    from repositories.device_session_repository import DeviceSessionRepository
    from services.firebase import db


class DeviceSessionService:
    def __init__(self) -> None:
        self._repository = DeviceSessionRepository(db)

    def upsert(self, user_id: str, organization_id: str, payload: Dict[str, str]) -> None:
        self._repository.upsert(
            payload["session_id"],
            {
                **payload,
                "user_id": user_id,
                "organization_id": organization_id,
                "revoked": False,
            },
        )

    def revoke(self, session_id: str, user_id: str) -> None:
        self._repository.revoke(session_id, user_id)

    def list_for_user(self, user_id: str) -> List[Dict[str, str]]:
        return self._repository.list_for_user(user_id)


device_session_service = DeviceSessionService()
