from types import SimpleNamespace

from backend.services.device_session_service import DeviceSessionService


def test_upsert_encrypts_request_secret_and_tracks_rotation(monkeypatch):
    writes = []
    existing = {
        "session_id": "session-1",
        "request_secret_fingerprint": "old-fingerprint",
        "request_secret_ciphertext": "old-ciphertext",
        "request_secret_version": 1,
    }

    service = DeviceSessionService.__new__(DeviceSessionService)
    service._repository = SimpleNamespace(
        get=lambda session_id: existing,
        upsert=lambda session_id, payload: writes.append((session_id, payload)),
    )

    monkeypatch.setattr(
        "backend.services.device_session_service.device_session_secret_protector",
        SimpleNamespace(
            fingerprint=lambda secret: f"fp:{secret}",
            encrypt=lambda secret: f"enc:{secret}",
        ),
    )

    service.upsert(
        user_id="user-1",
        organization_id="org-1",
        payload={
            "session_id": "session-1",
            "device_id": "device-1",
            "platform": "ios",
            "app_version": "1.0.0",
            "request_secret": "new-secret",
        },
    )

    _, payload = writes[0]
    assert payload["request_secret_ciphertext"] == "enc:new-secret"
    assert payload["request_secret_fingerprint"] == "fp:new-secret"
    assert payload["previous_request_secret_ciphertext"] == "old-ciphertext"
    assert payload["previous_request_secret_fingerprint"] == "old-fingerprint"
    assert payload["request_secret_version"] == 2
    assert "request_secret" not in payload


def test_get_request_signing_secrets_returns_decrypted_current_and_previous(monkeypatch):
    service = DeviceSessionService.__new__(DeviceSessionService)
    service._repository = SimpleNamespace(
        get=lambda session_id: {
            "request_secret_ciphertext": "enc:current",
            "previous_request_secret_ciphertext": "enc:previous",
        }
    )

    monkeypatch.setattr(
        "backend.services.device_session_service.device_session_secret_protector",
        SimpleNamespace(decrypt=lambda value: value.replace("enc:", "")),
    )

    assert service.get_request_signing_secrets("session-1") == ["current", "previous"]
