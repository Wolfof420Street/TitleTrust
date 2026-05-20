from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any


MAX_REQUEST_SIGNATURE_AGE_MS = 5 * 60 * 1000


def hash_body(body: Any) -> str:
    if body is None:
        payload = ""
    elif isinstance(body, str):
        payload = body
    else:
        payload = json.dumps(body, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_signature_payload(
    *,
    method: str,
    path: str,
    timestamp: str,
    correlation_id: str,
    body: Any,
) -> str:
    return "\n".join(
        [
            method,
            path,
            timestamp,
            correlation_id,
            hash_body(body),
        ]
    )


def sign_request(
    *,
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    correlation_id: str,
    body: Any,
) -> str:
    payload = build_signature_payload(
        method=method,
        path=path,
        timestamp=timestamp,
        correlation_id=correlation_id,
        body=body,
    )
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def is_fresh_timestamp(timestamp: str, *, now: datetime | None = None) -> bool:
    try:
        request_ms = int(timestamp)
    except (TypeError, ValueError):
        return False

    current = now or datetime.now(timezone.utc)
    current_ms = int(current.timestamp() * 1000)
    age_ms = abs(current_ms - request_ms)
    return age_ms <= MAX_REQUEST_SIGNATURE_AGE_MS


def verify_request_signature(
    *,
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    correlation_id: str,
    body: Any,
    signature: str,
) -> bool:
    expected = sign_request(
        secret=secret,
        method=method,
        path=path,
        timestamp=timestamp,
        correlation_id=correlation_id,
        body=body,
    )
    return hmac.compare_digest(expected, signature)
