from __future__ import annotations

import logging
import hashlib
from typing import Dict, List

try:
    from backend.repositories.device_session_repository import DeviceSessionRepository
    from backend.security.device_session_secrets import device_session_secret_protector
    from backend.services.firebase import db
except ModuleNotFoundError:
    from repositories.device_session_repository import DeviceSessionRepository
    from security.device_session_secrets import device_session_secret_protector
    from services.firebase import db

logger = logging.getLogger("TitleTrust-DeviceSessionService")


class DeviceSessionService:
    def __init__(self) -> None:
        self._repository = DeviceSessionRepository(db)

    def upsert(self, user_id: str, organization_id: str, payload: Dict[str, str]) -> None:
        session_id = payload.get("session_id")
        if not session_id:
            raise ValueError("Device session payload must include a non-empty session_id")
        request_secret = payload.get("request_secret")
        if not request_secret:
            raise ValueError("Device session payload must include a non-empty request_secret")

        existing = self._repository.get(session_id) or {}
        if existing:
            if existing.get("user_id") != user_id or existing.get("organization_id") != organization_id:
                raise ValueError("Device session ownership mismatch")
        request_secret_fingerprint = device_session_secret_protector.fingerprint(request_secret)
        stored_payload = {
            key: value
            for key, value in payload.items()
            if key != "request_secret"
        }
        stored_payload["request_secret_ciphertext"] = device_session_secret_protector.encrypt(request_secret)
        stored_payload["request_secret_fingerprint"] = request_secret_fingerprint
        stored_payload["request_secret_version"] = int(existing.get("request_secret_version", 0) or 0) or 1

        if existing.get("request_secret_fingerprint") and existing.get("request_secret_fingerprint") != request_secret_fingerprint:
            stored_payload["previous_request_secret_ciphertext"] = existing.get("request_secret_ciphertext")
            stored_payload["previous_request_secret_fingerprint"] = existing.get("request_secret_fingerprint")
            stored_payload["request_secret_version"] = int(existing.get("request_secret_version", 1) or 1) + 1
            stored_payload["request_secret_rotated_at"] = __import__("datetime").datetime.now().isoformat()
            logger.info(
                "Device session request secret rotated",
                extra={
                    "hashed_session_id": hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:12],
                    "hashed_user_id": hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12],
                },
            )

        self._repository.upsert(
            payload["session_id"],
            {
                **stored_payload,
                "user_id": user_id,
                "organization_id": organization_id,
                "revoked": False,
            },
        )

    def revoke(self, session_id: str, user_id: str) -> None:
        self._repository.revoke(session_id, user_id)

    def get(self, session_id: str) -> Dict[str, str] | None:
        return self._repository.get(session_id)

    def get_request_signing_secrets(self, session_id: str) -> List[str]:
        session = self._repository.get(session_id)
        if not session:
            return []

        secrets: List[str] = []
        for field_name in ("request_secret_ciphertext", "previous_request_secret_ciphertext"):
            ciphertext = session.get(field_name)
            if not ciphertext:
                continue
            try:
                secrets.append(device_session_secret_protector.decrypt(ciphertext))
            except Exception:
                logger.exception("Failed to decrypt device session secret", extra={"session_id": session_id, "field": field_name})
        return secrets

    def list_for_user(self, user_id: str) -> List[Dict[str, str]]:
        sessions = self._repository.list_for_user(user_id)
        return [
            {
                key: value
                for key, value in session.items()
                if key
                not in {
                    "request_secret",
                    "request_secret_ciphertext",
                    "request_secret_fingerprint",
                    "previous_request_secret_ciphertext",
                    "previous_request_secret_fingerprint",
                }
            }
            for session in sessions
        ]


device_session_service = DeviceSessionService()
