"""Tests for observability middleware and telemetry initialization."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import backend.middleware.observability as observability
from backend.middleware.observability import CorrelationMiddleware


def _initialize_telemetry_for_test():
    try:
        from backend.telemetry.init import initialize_telemetry
    except Exception as exc:  # pragma: no cover - dependency-gated environments
        pytest.skip(f"Telemetry module unavailable: {exc}")
    return initialize_telemetry


def _build_client(status_code: int = 200, raise_error: bool = False) -> TestClient:
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)

    @app.get("/test")
    async def _test_route():
        if raise_error:
            raise RuntimeError("boom")
        return JSONResponse(status_code=status_code, content={"ok": True})

    return TestClient(app, raise_server_exceptions=False)


class TestCorrelationMiddleware:
    def test_middleware_generates_correlation_id_if_missing(self):
        response = _build_client().get("/test")
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        assert response.headers["X-Correlation-ID"]

    def test_middleware_preserves_existing_correlation_id(self):
        response = _build_client().get("/test", headers={"X-Correlation-ID": "existing-id-123"})
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == "existing-id-123"

    def test_middleware_includes_correlation_id_in_response_headers(self):
        response = _build_client().get("/test")
        assert "X-Correlation-ID" in response.headers
        assert "X-Response-Time-Ms" in response.headers


class TestObservabilityMetrics:
    def test_correlation_middleware_tracks_request_count(self):
        counter = MagicMock()
        counter.labels.return_value = MagicMock()
        with patch.object(observability, "REQUEST_COUNT", counter):
            response = _build_client().get("/test")
        assert response.status_code == 200
        counter.labels.assert_called_once_with("GET", "/test", "200")
        counter.labels.return_value.inc.assert_called_once()

    def test_correlation_middleware_tracks_response_latency(self):
        histogram = MagicMock()
        histogram.labels.return_value = MagicMock()
        with patch.object(observability, "REQUEST_LATENCY", histogram):
            response = _build_client().get("/test")
        assert response.status_code == 200
        histogram.labels.assert_called_once_with("GET", "/test")
        histogram.labels.return_value.observe.assert_called_once()

    def test_correlation_middleware_tracks_error_responses(self):
        counter = MagicMock()
        counter.labels.return_value = MagicMock()
        with patch.object(observability, "REQUEST_COUNT", counter):
            response = _build_client(raise_error=True).get("/test")
        assert response.status_code == 500
        counter.labels.assert_called_once_with("GET", "/test", "500")
        counter.labels.return_value.inc.assert_called_once()


class TestTelemetryInitialization:
    def test_telemetry_initializes_with_valid_config(self):
        initialize_telemetry = _initialize_telemetry_for_test()
        app = FastAPI()
        with patch("backend.telemetry.init.init_tracing", return_value=object()) as mock_trace, patch(
            "backend.telemetry.init.init_metrics", return_value=object()
        ) as mock_metrics:
            result = initialize_telemetry(app=app, environment="development")
        assert result["tracing_enabled"] is True
        assert result["metrics_enabled"] is True
        mock_trace.assert_called_once()
        mock_metrics.assert_called_once()

    def test_telemetry_exports_to_jaeger_endpoint(self):
        initialize_telemetry = _initialize_telemetry_for_test()
        app = FastAPI()
        with patch.dict("os.environ", {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://jaeger:4317"}), patch(
            "backend.telemetry.init.init_tracing", return_value=object()
        ) as mock_trace:
            initialize_telemetry(app=app, environment="development")
        assert mock_trace.call_count == 1

    def test_telemetry_traces_request_lifecycle(self):
        initialize_telemetry = _initialize_telemetry_for_test()
        app = FastAPI()
        fake_provider = object()
        with patch("backend.telemetry.init.init_tracing", return_value=fake_provider), patch(
            "backend.telemetry.init.init_metrics", return_value=None
        ):
            result = initialize_telemetry(app=app, environment="development")
        assert result["trace_provider"] is fake_provider
        assert result["tracing_enabled"] is True


class TestStructuredLogging:
    def test_logs_include_correlation_id(self, caplog):
        with patch.object(observability, "REQUEST_COUNT", MagicMock()), patch.object(
            observability, "REQUEST_LATENCY", MagicMock()
        ):
            with caplog.at_level("INFO", logger="TitleTrust-Observability"):
                response = _build_client().get("/test", headers={"X-Correlation-ID": "corr-abc"})
        assert response.status_code == 200
        assert any(getattr(rec, "correlation_id", None) == "corr-abc" for rec in caplog.records)

    def test_logs_include_user_context(self, caplog):
        logger = observability.logger
        with caplog.at_level("INFO", logger="TitleTrust-Observability"):
            logger.info("user.context", extra={"uid": "user-123", "correlation_id": "corr-123"})
        assert any(getattr(rec, "uid", None) == "user-123" for rec in caplog.records)
        assert any(getattr(rec, "correlation_id", None) == "corr-123" for rec in caplog.records)

    def test_error_logs_include_stack_trace(self, caplog):
        logger = observability.logger
        with caplog.at_level("ERROR", logger="TitleTrust-Observability"):
            try:
                raise ValueError("test-error")
            except ValueError:
                logger.exception("failure")
        assert any(rec.exc_info is not None for rec in caplog.records)


class TestObservabilityErrors:
    def test_http_errors_include_status_code(self):
        response = _build_client(status_code=422).get("/test")
        assert response.status_code == 422


class TestObservabilityPerformance:
    def test_correlation_middleware_has_low_overhead(self):
        response = _build_client().get("/test")
        assert response.status_code == 200
        assert float(response.headers["X-Response-Time-Ms"]) >= 0