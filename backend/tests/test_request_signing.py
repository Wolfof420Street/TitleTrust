from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from backend.api.auth_router import _require_registered_device_signature, _verify_signed_request
from backend.security.device_session_secrets import device_session_secret_protector
from backend.security.request_signing import (
    is_fresh_timestamp,
    sign_request,
    verify_request_signature,
)
from backend.services.device_session_service import DeviceSessionService


def test_verify_request_signature_accepts_frontend_compatible_payload():
    body = {
        "session_id": "device-session-1",
        "device_id": "device-host",
        "platform": "android",
        "app_version": "1.0.0",
        "request_secret": "secret-value",
    }
    signature = sign_request(
        secret="secret-value",
        method="POST",
        path="/auth/device-sessions",
        timestamp="1710000000000",
        correlation_id="corr-1",
        body=body,
    )

    assert verify_request_signature(
        secret="secret-value",
        method="POST",
        path="/auth/device-sessions",
        timestamp="1710000000000",
        correlation_id="corr-1",
        body=body,
        signature=signature,
    )
    assert not verify_request_signature(
        secret="secret-value",
        method="POST",
        path="/auth/device-sessions",
        timestamp="1710000000000",
        correlation_id="corr-1",
        body={**body, "device_id": "tampered-device"},
        signature=signature,
    )


def test_request_signature_timestamp_freshness_window_enforced():
    now = datetime.now(timezone.utc)
    fresh = str(int(now.timestamp() * 1000))
    stale = str(int((now - timedelta(minutes=6)).timestamp() * 1000))

    assert is_fresh_timestamp(fresh, now=now)
    assert not is_fresh_timestamp(stale, now=now)


def test_upsert_signature_verification_rejects_tampered_body():
    app = FastAPI()

    @app.post("/auth/device-sessions")
    async def register(request: Request):
        payload = await request.json()
        request.state._cached_json_body = payload
        await _verify_signed_request(
            request,
            secret=payload["request_secret"],
            device_session_id=payload["session_id"],
            signature=request.headers.get("X-Request-Signature"),
            timestamp=request.headers.get("X-Request-Timestamp"),
            correlation_id=request.headers.get("X-Correlation-ID"),
            user_id="user-1",
        )
        return {"status": "registered"}

    timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    original_body = {
        "session_id": "device-session-1",
        "device_id": "device-host",
        "platform": "android",
        "app_version": "1.0.0",
        "request_secret": "secret-value",
    }
    tampered_body = {**original_body, "platform": "ios"}
    signature = sign_request(
        secret="secret-value",
        method="POST",
        path="/auth/device-sessions",
        timestamp=timestamp,
        correlation_id="corr-1",
        body=original_body,
    )

    response = TestClient(app).post(
        "/auth/device-sessions",
        json=tampered_body,
        headers={
            "X-Correlation-ID": "corr-1",
            "X-Request-Timestamp": timestamp,
            "X-Request-Signature": signature,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid request signature"


def test_registered_device_signature_requires_owned_active_session(monkeypatch):
    app = FastAPI()

    @app.post("/auth/device-sessions/device-session-1/revoke")
    async def revoke(request: Request):
        try:
            await _require_registered_device_signature(
                request,
                {"uid": "user-1"},
                request.headers.get("X-Device-Session-ID"),
                request.headers.get("X-Request-Signature"),
                request.headers.get("X-Request-Timestamp"),
                request.headers.get("X-Correlation-ID"),
            )
        except HTTPException as exc:
            raise exc
        return {"status": "revoked"}

    monkeypatch.setattr(
        "backend.api.auth_router.device_session_service",
        SimpleNamespace(
            get=lambda session_id: {
                "session_id": session_id,
                "user_id": "user-1",
                "revoked": False,
                "request_secret_ciphertext": device_session_secret_protector.encrypt("secret-value"),
            },
            get_request_signing_secrets=lambda session_id: ["secret-value"],
        ),
    )

    timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    body = {}
    signature = sign_request(
        secret="secret-value",
        method="POST",
        path="/auth/device-sessions/device-session-1/revoke",
        timestamp=timestamp,
        correlation_id="corr-2",
        body=body,
    )

    response = TestClient(app).post(
        "/auth/device-sessions/device-session-1/revoke",
        json=body,
        headers={
            "X-Device-Session-ID": "device-session-1",
            "X-Correlation-ID": "corr-2",
            "X-Request-Timestamp": timestamp,
            "X-Request-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "revoked"


def test_device_session_listing_strips_request_secrets():
    service = DeviceSessionService.__new__(DeviceSessionService)
    service._repository = SimpleNamespace(
        list_for_user=lambda user_id: [
            {
                "session_id": "device-session-1",
                "request_secret_ciphertext": "ciphertext",
                "request_secret_fingerprint": "fingerprint",
                "previous_request_secret_ciphertext": "ciphertext-2",
                "platform": "android",
            }
        ]
    )

    sessions = service.list_for_user("user-1")

    assert sessions == [{"session_id": "device-session-1", "platform": "android"}]


def test_registered_device_signature_uses_rotated_previous_secret(monkeypatch):
    app = FastAPI()

    @app.get("/auth/device-sessions")
    async def list_sessions(request: Request):
        try:
            await _require_registered_device_signature(
                request,
                {"uid": "user-1"},
                request.headers.get("X-Device-Session-ID"),
                request.headers.get("X-Request-Signature"),
                request.headers.get("X-Request-Timestamp"),
                request.headers.get("X-Correlation-ID"),
            )
        except HTTPException as exc:
            raise exc
        return {"sessions": []}

    monkeypatch.setattr(
        "backend.api.auth_router.device_session_service",
        SimpleNamespace(
            get=lambda session_id: {
                "session_id": session_id,
                "user_id": "user-1",
                "revoked": False,
            },
            get_request_signing_secrets=lambda session_id: ["current-secret", "previous-secret"],
        ),
    )

    timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    signature = sign_request(
        secret="previous-secret",
        method="GET",
        path="/auth/device-sessions",
        timestamp=timestamp,
        correlation_id="corr-3",
        body=None,
    )

    response = TestClient(app).get(
        "/auth/device-sessions",
        headers={
            "X-Device-Session-ID": "device-session-1",
            "X-Correlation-ID": "corr-3",
            "X-Request-Timestamp": timestamp,
            "X-Request-Signature": signature,
        },
    )

    assert response.status_code == 200
