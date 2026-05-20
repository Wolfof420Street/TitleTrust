"""Unit tests for SessionService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from google.api_core.exceptions import NotFound

from backend.services.session_service import SessionService


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_session_repository():
    repo = MagicMock()
    repo.create = MagicMock()
    repo.update = MagicMock()
    repo.get = MagicMock(return_value={"session_id": "test-session", "user_id": "test-user"})
    repo.resolve_idempotency_key = MagicMock(return_value=None)
    repo.register_idempotency_key = MagicMock()
    return repo


@pytest.fixture
def mock_audit_events_repository():
    repo = MagicMock()
    repo.append = MagicMock()
    return repo


@pytest.fixture
def mock_cloud_tasks_service():
    service = MagicMock()
    service.schedule_next_tick = MagicMock()
    return service


@pytest.fixture
def session_service(mock_db, mock_session_repository, mock_audit_events_repository, mock_cloud_tasks_service):
    service = SessionService()
    service._db = mock_db
    service._session_repository = mock_session_repository
    service._audit_events = mock_audit_events_repository
    service.cloud_tasks = mock_cloud_tasks_service
    return service


@pytest.fixture
def mock_cloud_storage_service(monkeypatch):
    service = MagicMock()
    service.upload_fileobj.return_value = {
        "object_path": "gs://bucket/uploads/test-document.pdf",
        "content_type": "application/pdf",
    }
    monkeypatch.setattr("backend.services.session_service.cloud_storage_service", service)
    return service


@pytest.fixture
def mock_upload_file():
    file = MagicMock()
    file.filename = "test-document.pdf"
    file.content_type = "application/pdf"
    file.file = MagicMock()
    file.file.seek = MagicMock()
    return file


class TestSessionServiceMarathonCreation:
    def test_start_marathon_creates_session_with_gcs_source(
        self,
        session_service,
        mock_upload_file,
        mock_session_repository,
        mock_audit_events_repository,
        mock_cloud_storage_service,
    ):
        background_tasks = MagicMock()

        result = session_service.start_marathon(
            file=mock_upload_file,
            user_id="test-user",
            organization_id="test-org",
            background_tasks=background_tasks,
        )

        assert result["status"] == "QUEUED"
        payload = mock_session_repository.create.call_args.kwargs["payload"]
        assert payload["image_uri"] == "gs://bucket/uploads/test-document.pdf"
        assert payload["image_mime_type"] == "application/pdf"
        assert "image_path" not in payload
        mock_cloud_storage_service.upload_fileobj.assert_called_once()
        background_tasks.add_task.assert_called_once_with(
            session_service.bootstrap,
            result["session_id"],
            "test-user",
        )
        mock_audit_events_repository.append.assert_called_once()

    def test_start_marathon_with_supported_file_types(self, session_service, mock_cloud_storage_service):
        background_tasks = MagicMock()
        supported_types = ["test.pdf", "image.png", "photo.jpg", "photo.jpeg", "video.mp4", "video.mov"]

        for filename in supported_types:
            file = MagicMock()
            file.filename = filename
            file.content_type = "application/octet-stream"
            file.file = MagicMock()
            session_service._session_repository.reset_mock()

            result = session_service.start_marathon(
                file=file,
                user_id="test-user",
                organization_id="test-org",
                background_tasks=background_tasks,
            )

            assert result["status"] == "QUEUED"

    def test_start_marathon_rejects_unsupported_file_types(self, session_service, mock_cloud_storage_service):
        from fastapi import HTTPException

        background_tasks = MagicMock()
        unsupported_types = ["test.txt", "archive.zip", "script.py", "document.docx"]

        for filename in unsupported_types:
            file = MagicMock()
            file.filename = filename

            with pytest.raises(HTTPException) as exc_info:
                session_service.start_marathon(
                    file=file,
                    user_id="test-user",
                    organization_id="test-org",
                    background_tasks=background_tasks,
                )

            assert exc_info.value.status_code == 400
            assert "Unsupported file type" in exc_info.value.detail

    def test_start_marathon_with_idempotency_key_returns_existing_session(
        self, session_service, mock_upload_file, mock_session_repository, mock_cloud_storage_service
    ):
        mock_session_repository.resolve_idempotency_key.return_value = "existing-session-id"
        background_tasks = MagicMock()

        result = session_service.start_marathon(
            file=mock_upload_file,
            user_id="test-user",
            organization_id="test-org",
            background_tasks=background_tasks,
            idempotency_key="idempotency-123",
        )

        assert result["session_id"] == "existing-session-id"
        mock_cloud_storage_service.upload_fileobj.assert_not_called()
        mock_session_repository.create.assert_not_called()

    def test_start_marathon_registers_idempotency_key(
        self, session_service, mock_upload_file, mock_session_repository, mock_cloud_storage_service
    ):
        background_tasks = MagicMock()

        result = session_service.start_marathon(
            file=mock_upload_file,
            user_id="test-user",
            organization_id="test-org",
            background_tasks=background_tasks,
            idempotency_key="idempotency-456",
        )

        mock_session_repository.register_idempotency_key.assert_called_once_with(
            "idempotency-456",
            result["session_id"],
            "test-user",
        )

    def test_start_marathon_from_storage_bypasses_local_disk(
        self, session_service, mock_session_repository, mock_cloud_storage_service
    ):
        background_tasks = MagicMock()

        result = session_service.start_marathon_from_storage(
            object_path="gs://bucket/uploads/title.jpg",
            original_filename="title.jpg",
            user_id="test-user",
            organization_id="test-org",
            background_tasks=background_tasks,
        )

        assert result["status"] == "QUEUED"
        payload = mock_session_repository.create.call_args.kwargs["payload"]
        assert payload["image_uri"] == "gs://bucket/uploads/title.jpg"
        assert payload["image_mime_type"] == "image/jpeg"
        mock_cloud_storage_service.upload_fileobj.assert_not_called()


class TestSessionServiceBootstrap:
    def test_bootstrap_initializes_agent_and_schedules_tick(
        self, session_service, mock_audit_events_repository, mock_cloud_tasks_service
    ):
        session_id = "test-session"

        with patch("backend.services.session_service.MarathonLoop") as mock_marathon:
            mock_agent = MagicMock()
            mock_agent.run_single_step.return_value = {
                "status": "RUNNING",
                "next_tick_seconds": 5,
            }
            mock_marathon.return_value = mock_agent

            session_service.bootstrap(session_id, "test-user")

            mock_marathon.assert_called_once_with(session_service._db, session_id)
            mock_cloud_tasks_service.schedule_next_tick.assert_called_once_with(session_id, 5)
            mock_audit_events_repository.append.assert_called_once()

    def test_bootstrap_handles_missing_object(
        self, session_service, mock_session_repository, mock_audit_events_repository
    ):
        session_id = "test-session"

        with patch("backend.services.session_service.MarathonLoop") as mock_marathon:
            mock_agent = MagicMock()
            mock_agent.run_single_step.side_effect = NotFound("missing object")
            mock_marathon.return_value = mock_agent

            session_service.bootstrap(session_id, "test-user")

            mock_session_repository.update.assert_called_once()
            update_call = mock_session_repository.update.call_args
            assert update_call[0][0] == session_id
            assert update_call[0][1]["status"] == "FAILED"
            assert "could not be found" in update_call[0][1]["error"].lower()
            mock_audit_events_repository.append.assert_called_once()

    def test_bootstrap_handles_agent_errors_gracefully(self, session_service, mock_session_repository):
        session_id = "test-session"

        with patch("backend.services.session_service.MarathonLoop") as mock_marathon:
            mock_agent = MagicMock()
            mock_agent.run_single_step.side_effect = ValueError("Agent error")
            mock_marathon.return_value = mock_agent

            session_service.bootstrap(session_id, "test-user")

            mock_session_repository.update.assert_called_once()
            assert mock_session_repository.update.call_args[0][1]["status"] == "FAILED"


class TestSessionServiceTicking:
    def test_tick_advances_agent_state(
        self, session_service, mock_session_repository, mock_audit_events_repository, mock_cloud_tasks_service
    ):
        session_id = "test-session"
        mock_session_repository.get.return_value = {"session_id": session_id, "user_id": "test-user"}

        with patch("backend.services.session_service.MarathonLoop") as mock_marathon:
            mock_agent = MagicMock()
            mock_agent.run_single_step.return_value = {
                "status": "RUNNING",
                "next_tick_seconds": 10,
            }
            mock_marathon.return_value = mock_agent

            result = session_service.tick(session_id, "test-user")

            assert result["status"] == "success"
            assert result["agent_status"] == "RUNNING"
            mock_cloud_tasks_service.schedule_next_tick.assert_called_once_with(session_id, 10)
            mock_audit_events_repository.append.assert_called_once()

    def test_tick_does_not_schedule_when_completed(self, session_service, mock_session_repository, mock_cloud_tasks_service):
        session_id = "test-session"
        mock_session_repository.get.return_value = {"session_id": session_id, "user_id": "test-user"}

        with patch("backend.services.session_service.MarathonLoop") as mock_marathon:
            mock_agent = MagicMock()
            mock_agent.run_single_step.return_value = {"status": "COMPLETED"}
            mock_marathon.return_value = mock_agent

            result = session_service.tick(session_id, "test-user")

            assert result["agent_status"] == "COMPLETED"
            mock_cloud_tasks_service.schedule_next_tick.assert_not_called()

    def test_tick_rejects_access_from_different_user(self, session_service, mock_session_repository):
        from fastapi import HTTPException

        mock_session_repository.get.return_value = {"session_id": "test-session", "user_id": "owner-user"}

        with pytest.raises(HTTPException) as exc_info:
            session_service.tick("test-session", "different-user")

        assert exc_info.value.status_code == 403

    def test_tick_returns_404_for_missing_session(self, session_service, mock_session_repository):
        from fastapi import HTTPException

        mock_session_repository.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            session_service.tick("missing-session", "test-user")

        assert exc_info.value.status_code == 404


class TestSessionServiceStatus:
    def test_get_status_returns_normalized_session_data(self, session_service, mock_session_repository):
        mock_session_repository.get.return_value = {
            "session_id": "test-session",
            "user_id": "test-user",
            "status": "RUNNING",
            "progress_checklist": {"image_analyzed": True},
            "total_steps": 3,
            "findings": [],
        }

        result = session_service.get_status("test-session", "test-user")

        assert result["session_id"] == "test-session"
        assert result["status"] == "RUNNING"
        assert result["progress"] == {"image_analyzed": True}
        assert result["total_steps"] == 3

    def test_get_status_rejects_unauthorized_access(self, session_service, mock_session_repository):
        from fastapi import HTTPException

        mock_session_repository.get.return_value = {"session_id": "test-session", "user_id": "owner-user"}

        with pytest.raises(HTTPException) as exc_info:
            session_service.get_status("test-session", "different-user")

        assert exc_info.value.status_code == 403

    def test_get_status_returns_404_for_missing_session(self, session_service, mock_session_repository):
        from fastapi import HTTPException

        mock_session_repository.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            session_service.get_status("missing-session", "test-user")

        assert exc_info.value.status_code == 404
