from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    from backend.config import settings
    from backend.security.secret_manager import get_secret_manager
except ModuleNotFoundError:
    from config import settings
    from security.secret_manager import get_secret_manager

logger = logging.getLogger("TitleTrust-DeviceSessionSecrets")
DEV_FALLBACK_WRAPPING_SECRET = "titletrust-device-session-dev-fallback-key"


class DeviceSessionSecretProtector:
    """Encrypt device-session request secrets at rest using an app-managed wrapping key."""

    def __init__(self) -> None:
        self._secret_manager = get_secret_manager()

    def fingerprint(self, secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    def encrypt(self, secret: str) -> str:
        aesgcm = AESGCM(self._wrapping_key())
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, secret.encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        raw = base64.urlsafe_b64decode(ciphertext.encode("utf-8"))
        nonce, encrypted = raw[:12], raw[12:]
        aesgcm = AESGCM(self._wrapping_key())
        return aesgcm.decrypt(nonce, encrypted, None).decode("utf-8")

    def _wrapping_key(self) -> bytes:
        configured_secret = self._secret_manager.get_secret("device-session-wrapping-key", required=False)
        if configured_secret:
            return hashlib.sha256(configured_secret.encode("utf-8")).digest()
        if settings.is_production:
            raise ValueError("device-session-wrapping-key secret is required in production")
        logger.warning("Using development fallback for device-session wrapping key")
        return hashlib.sha256(DEV_FALLBACK_WRAPPING_SECRET.encode("utf-8")).digest()


device_session_secret_protector = DeviceSessionSecretProtector()
