from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.main import app

try:
    import backend.api.upload_router as upload_router_module
    import backend.api.audit_router as audit_router_module
except ModuleNotFoundError:
    import api.upload_router as upload_router_module
    import api.audit_router as audit_router_module

try:
    from backend.auth import get_current_user
    from backend.repositories.policy_repository import PolicyRepository
except ModuleNotFoundError:
    from auth import get_current_user
    from repositories.policy_repository import PolicyRepository


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_auth(monkeypatch):
    def _mock_user():
        return {
            "uid": "test-user",
            "org_id": "test-org",
            "claims": {
                "org_id": "test-org",
                "roles": ["super_admin"],
            },
        }

    app.dependency_overrides[get_current_user] = _mock_user
    monkeypatch.setattr(PolicyRepository, "upsert_membership", lambda *args, **kwargs: None)
    yield
    app.dependency_overrides.clear()


def test_create_signed_upload_url(client, monkeypatch):
    mock_storage = MagicMock()
    mock_storage.create_signed_upload.return_value = {
        "upload_url": "https://storage.example/upload",
        "object_path": "gs://bucket/path/file.jpg",
        "method": "PUT",
        "headers": {"Content-Type": "image/jpeg"},
        "expires_in_seconds": 900,
    }
    monkeypatch.setattr(upload_router_module, "cloud_storage_service", mock_storage)

    response = client.post(
        "/uploads/signed-url",
        json={
            "filename": "title.jpg",
            "content_type": "image/jpeg",
            "purpose": "marathon-start",
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["object_path"] == "gs://bucket/path/file.jpg"


def test_start_audit_from_storage(client, monkeypatch):
    mock_session = MagicMock()
    mock_session.start_marathon_from_storage.return_value = {
        "session_id": "session-123",
        "status": "QUEUED",
        "message": "Investigation starting. Analyzing document...",
    }
    monkeypatch.setattr(audit_router_module, "session_service", mock_session)

    response = client.post(
        "/audit/start/from-storage",
        json={
            "object_path": "gs://bucket/path/title.jpg",
            "original_filename": "title.jpg",
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "session-123"
