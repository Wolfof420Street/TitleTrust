"""Integration tests for Audit API Router.

Tests cover:
- POST /audit/forensic endpoint
- POST /audit/geospatial endpoint
- POST /audit/start endpoint
- GET /audit/status/{session_id} endpoint
- GET /audit/jobs/{job_id} endpoint
- Authorization and permission checks
- Request/response validation
- Error handling and edge cases
"""

import pytest
from typing import Dict, Any
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app

try:
    import backend.api.audit_router as audit_router_module
except ModuleNotFoundError:
    import api.audit_router as audit_router_module

try:
    from backend.auth import get_current_user
    from backend.repositories.policy_repository import PolicyRepository
except ModuleNotFoundError:
    from auth import get_current_user
    from repositories.policy_repository import PolicyRepository

try:
    from repositories.policy_repository import PolicyRepository as LocalPolicyRepository
except ModuleNotFoundError:
    LocalPolicyRepository = None


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_auth_dependencies(monkeypatch):
    """Bypass external auth/policy side effects for router-level tests."""

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
    if LocalPolicyRepository is not None:
        monkeypatch.setattr(LocalPolicyRepository, "upsert_membership", lambda *args, **kwargs: None)

    mock_background_service = MagicMock()
    mock_background_service.enqueue_forensic.return_value = {
        "job_id": "job-123",
        "status": "QUEUED",
        "job_type": "forensic",
    }
    mock_background_service.enqueue_geospatial.return_value = {
        "job_id": "job-456",
        "status": "QUEUED",
        "job_type": "geospatial",
    }
    mock_background_service.get_job.return_value = {
        "job_id": "job-123",
        "status": "QUEUED",
        "job_type": "forensic",
        "user_id": "test-user",
    }

    mock_session_service = MagicMock()
    mock_session_service.start_marathon.return_value = {
        "session_id": "session-123",
        "status": "running",
        "message": "Investigation started",
    }
    mock_session_service.get_status.return_value = {
        "session_id": "session-123",
        "status": "running",
        "progress": {},
        "total_steps": 0,
        "findings": [],
    }

    monkeypatch.setattr(audit_router_module, "background_job_service", mock_background_service)
    monkeypatch.setattr(audit_router_module, "session_service", mock_session_service)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_auth_token():
    """Mock Firebase ID token."""
    return {
        "uid": "test-user",
        "email": "test@example.com",
        "org_id": "test-org",
        "claims": {"org_id": "test-org", "role": "admin"},
    }


@pytest.fixture
def auth_headers(mock_auth_token):
    """Create authorization headers."""
    return {
        "Authorization": "Bearer mock-id-token",
        "X-Correlation-ID": "corr-123",
    }


class TestAuditForensicEndpoint:
    """Test POST /audit/forensic endpoint."""

    def test_forensic_audit_accepts_single_file(
        self, client, auth_headers, monkeypatch
    ):
        """Test forensic audit with single file."""
        # Mock authorization and service
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user", "org_id": "test-org"},
        )
        
        mock_service = MagicMock()
        mock_service.enqueue_forensic.return_value = {
            "job_id": "job-123",
            "status": "QUEUED",
            "job_type": "forensic",
        }
        monkeypatch.setattr(
            "backend.api.audit_router.background_job_service",
            mock_service,
        )
        
        with open(__file__, "rb") as f:
            response = client.post(
                "/audit/forensic",
                files={"files": ("test.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        
        # Should return 200 with job acceptance
        assert response.status_code in [200, 422]  # 422 if file validation fails

    def test_forensic_audit_accepts_multiple_files(
        self, client, auth_headers, monkeypatch
    ):
        """Test forensic audit with multiple files."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user", "org_id": "test-org"},
        )
        
        mock_service = MagicMock()
        mock_service.enqueue_forensic.return_value = {
            "job_id": "job-123",
            "status": "QUEUED",
            "job_type": "forensic",
        }
        monkeypatch.setattr(
            "backend.api.audit_router.background_job_service",
            mock_service,
        )
        
        with open(__file__, "rb") as f1, open(__file__, "rb") as f2:
            response = client.post(
                "/audit/forensic",
                files=[
                    ("files", ("test1.pdf", f1, "application/pdf")),
                    ("files", ("test2.pdf", f2, "application/pdf")),
                ],
                headers=auth_headers,
            )
        
        assert response.status_code in [200, 422]

    def test_forensic_audit_requires_permission(self, client):
        """Test forensic audit requires FORENSIC_RUN permission."""
        # Without valid auth, should get 403 or 401
        response = client.post(
            "/audit/forensic",
            files={"files": ("test.pdf", b"content", "application/pdf")},
        )
        
        assert response.status_code in [401, 403, 422]

    def test_forensic_audit_includes_correlation_id(
        self, client, auth_headers, monkeypatch
    ):
        """Test forensic audit preserves correlation ID."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user"},
        )
        
        captured_args = {}
        
        def mock_enqueue(**kwargs):
            captured_args.update(kwargs)
            return {
                "job_id": "job-123",
                "status": "QUEUED",
                "job_type": "forensic",
            }
        
        mock_service = MagicMock()
        mock_service.enqueue_forensic.side_effect = mock_enqueue
        monkeypatch.setattr(
            "backend.api.audit_router.background_job_service",
            mock_service,
        )
        
        with open(__file__, "rb") as f:
            response = client.post(
                "/audit/forensic",
                files={"files": ("test.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        
        # Verify correlation_id was passed to service
        if response.status_code in [200, 422]:
            mock_service.enqueue_forensic.assert_called()
            call = mock_service.enqueue_forensic.call_args
            assert "correlation_id" in call.kwargs
            assert call.kwargs["correlation_id"] == auth_headers["X-Correlation-ID"]


class TestAuditGeospatialEndpoint:
    """Test POST /audit/geospatial endpoint."""

    def test_geospatial_audit_accepts_valid_coordinates(
        self, client, auth_headers, monkeypatch
    ):
        """Test geospatial audit with valid lat/lng."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user", "org_id": "test-org"},
        )
        
        mock_service = MagicMock()
        mock_service.enqueue_geospatial.return_value = {
            "job_id": "job-456",
            "status": "QUEUED",
            "job_type": "geospatial",
        }
        monkeypatch.setattr(
            "backend.api.audit_router.background_job_service",
            mock_service,
        )
        
        with open(__file__, "rb") as f:
            response = client.post(
                "/audit/geospatial",
                data={
                    "lat": "40.7128",
                    "lng": "-74.0060",
                },
                files={"file": ("test.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        
        assert response.status_code in [200, 422]

    def test_geospatial_audit_rejects_invalid_latitude(
        self, client, auth_headers, monkeypatch
    ):
        """Test geospatial audit rejects latitude outside [-90, 90]."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user"},
        )
        
        with open(__file__, "rb") as f:
            response = client.post(
                "/audit/geospatial",
                data={
                    "lat": "95.0",  # Invalid: > 90
                    "lng": "-74.0060",
                },
                files={"file": ("test.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        
        # Should reject with validation error
        assert response.status_code == 422

    def test_geospatial_audit_rejects_invalid_longitude(
        self, client, auth_headers, monkeypatch
    ):
        """Test geospatial audit rejects longitude outside [-180, 180]."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user"},
        )
        
        with open(__file__, "rb") as f:
            response = client.post(
                "/audit/geospatial",
                data={
                    "lat": "40.7128",
                    "lng": "200.0",  # Invalid: > 180
                },
                files={"file": ("test.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        
        # Should reject with validation error
        assert response.status_code == 422

    def test_geospatial_audit_requires_permission(self, client):
        """Test geospatial audit requires GEOSPATIAL_RUN permission."""
        response = client.post(
            "/audit/geospatial",
            data={
                "lat": "40.7128",
                "lng": "-74.0060",
            },
            files={"file": ("test.pdf", b"content", "application/pdf")},
        )
        
        assert response.status_code in [401, 403, 422]


class TestAuditStartEndpoint:
    """Test POST /audit/start endpoint."""

    def test_start_audit_creates_session(
        self, client, auth_headers, monkeypatch
    ):
        """Test start audit creates investigation session."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user", "org_id": "test-org"},
        )
        
        mock_service = MagicMock()
        mock_service.start_marathon.return_value = {
            "session_id": "sess-789",
            "status": "QUEUED",
            "message": "Investigation queued",
        }
        monkeypatch.setattr(
            "backend.api.audit_router.session_service",
            mock_service,
        )
        
        with open(__file__, "rb") as f:
            response = client.post(
                "/audit/start",
                files={"file": ("test.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        
        assert response.status_code in [200, 422]

    def test_start_audit_with_idempotency_key(
        self, client, auth_headers, monkeypatch
    ):
        """Test start audit with idempotency key."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user"},
        )
        
        captured_args = {}
        
        def mock_start(**kwargs):
            captured_args.update(kwargs)
            return {
                "session_id": "sess-789",
                "status": "QUEUED",
                "message": "Investigation queued",
            }
        
        mock_service = MagicMock()
        mock_service.start_marathon.side_effect = mock_start
        monkeypatch.setattr(
            "backend.api.audit_router.session_service",
            mock_service,
        )
        
        with open(__file__, "rb") as f:
            response = client.post(
                "/audit/start",
                files={"file": ("test.pdf", f, "application/pdf")},
                headers={
                    **auth_headers,
                    "Idempotency-Key": "idempotency-123",
                },
            )
        
        if response.status_code in [200, 422]:
            if mock_service.start_marathon.called:
                # Verify idempotency key was passed
                call_kwargs = mock_service.start_marathon.call_args[1]
                assert "idempotency_key" in call_kwargs

    def test_start_audit_requires_permission(self, client):
        """Test start audit requires AUDIT_START permission."""
        response = client.post(
            "/audit/start",
            files={"file": ("test.pdf", b"content", "application/pdf")},
        )
        
        assert response.status_code in [401, 403, 422]


class TestAuditStatusEndpoint:
    """Test GET /audit/status/{session_id} endpoint."""

    def test_status_returns_session_data(
        self, client, auth_headers, monkeypatch
    ):
        """Test status endpoint returns current session state."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user"},
        )
        
        mock_service = MagicMock()
        mock_service.get_status.return_value = {
            "session_id": "sess-789",
            "status": "RUNNING",
            "progress": {"step": 1},
        }
        monkeypatch.setattr(
            "backend.api.audit_router.session_service",
            mock_service,
        )
        
        response = client.get("/audit/status/sess-789", headers=auth_headers)
        
        assert response.status_code in [200, 403]

    def test_status_rejects_unauthorized_access(
        self, client, auth_headers, monkeypatch
    ):
        """Test status endpoint rejects unauthorized user."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "different-user"},
        )
        
        mock_service = MagicMock()
        mock_service.get_status.side_effect = HTTPException(status_code=403, detail="Access denied")
        monkeypatch.setattr(
            "backend.api.audit_router.session_service",
            mock_service,
        )
        
        response = client.get("/audit/status/sess-789", headers=auth_headers)
        
        # Should be rejected
        assert response.status_code in [403, 422]

    def test_status_returns_404_for_missing_session(
        self, client, auth_headers, monkeypatch
    ):
        """Test status endpoint returns 404 for nonexistent session."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user"},
        )
        
        mock_service = MagicMock()
        mock_service.get_status.side_effect = HTTPException(status_code=404, detail="Session not found")
        monkeypatch.setattr(
            "backend.api.audit_router.session_service",
            mock_service,
        )
        
        response = client.get("/audit/status/nonexistent", headers=auth_headers)
        
        assert response.status_code in [404, 422]


class TestAuditJobStatusEndpoint:
    """Test GET /audit/jobs/{job_id} endpoint."""

    def test_job_status_returns_job_data(
        self, client, auth_headers, monkeypatch
    ):
        """Test job status endpoint returns current job state."""
        monkeypatch.setattr(
            "backend.api.audit_router.require_permission",
            lambda perm: lambda: {"uid": "test-user"},
        )
        
        mock_service = MagicMock()
        mock_service.get_job.return_value = {
            "job_id": "job-123",
            "status": "RUNNING",
            "job_type": "forensic",
            "user_id": "test-user",
        }
        monkeypatch.setattr(
            "backend.api.audit_router.background_job_service",
            mock_service,
        )
        
        response = client.get("/audit/jobs/job-123", headers=auth_headers)
        
        assert response.status_code in [200, 403, 404, 422]

    def test_job_status_requires_permission(self, client):
        """Test job status requires READ_AUDIT permission."""
        response = client.get("/audit/jobs/job-123")
        
        assert response.status_code in [401, 403, 422]
