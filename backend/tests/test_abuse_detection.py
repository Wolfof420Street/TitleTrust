import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.domain.session_models import SessionState, SessionRiskLevel
from backend.middleware.adaptive_protection import AdaptiveProtectionMiddleware
from backend.security.abuse_detection import AbuseAction, AbuseDetectionEngine
from backend.security.anomaly_detection import AnomalyDetectionEngine


@pytest.fixture
def abuse_engine() -> AbuseDetectionEngine:
    return AbuseDetectionEngine(AnomalyDetectionEngine(None))


def _session() -> SessionState:
    return SessionState(
        session_id="session-1",
        user_id="user-1",
        created_at=__import__("datetime").datetime.now(),
        expires_at=__import__("datetime").datetime.now(),
        last_activity_at=__import__("datetime").datetime.now(),
        current_refresh_token_id="token-1",
        token_family="family-1",
        current_ip="1.2.3.4",
        risk_score=5.0,
        risk_level=SessionRiskLevel.LOW,
    )


def test_credential_stuffing_detected(abuse_engine: AbuseDetectionEngine) -> None:
    assessment = abuse_engine.assess(
        tenant_id="tenant-a",
        device_id="device-a",
        ip_address="1.2.3.4",
        user_agent="curl/8.0.1",
        method="POST",
        path="/auth/login",
        correlation_id="corr-1",
        headers={"x-tenant-id": "tenant-a", "x-device-id": "device-a"},
        session=_session(),
    )

    assert assessment.action in {AbuseAction.THROTTLE, AbuseAction.CHALLENGE}
    assert any("credential_stuffing" in reason for reason in assessment.reasons)


def test_quarantined_fingerprint_blocks(abuse_engine: AbuseDetectionEngine) -> None:
    request_headers = {"x-tenant-id": "tenant-a", "x-device-id": "device-a"}
    fingerprint = abuse_engine._fingerprinting.fingerprint(  # noqa: SLF001
        tenant_id="tenant-a",
        device_id="device-a",
        ip_address="1.2.3.4",
        user_agent="Mozilla/5.0",
        correlation_id="corr-2",
        method="GET",
        path="/health",
        headers=request_headers,
    )
    abuse_engine.quarantine_fingerprint(fingerprint.fingerprint_id)

    assessment = abuse_engine.assess(
        tenant_id="tenant-a",
        device_id="device-a",
        ip_address="1.2.3.4",
        user_agent="Mozilla/5.0",
        method="GET",
        path="/health",
        correlation_id="corr-2",
        headers=request_headers,
        session=_session(),
    )

    assert assessment.action in {AbuseAction.QUARANTINE, AbuseAction.BLOCK}
    assert "fingerprint_quarantined" in assessment.reasons


def test_middleware_attaches_abuse_headers(abuse_engine: AbuseDetectionEngine) -> None:
    app = FastAPI()
    app.add_middleware(AdaptiveProtectionMiddleware, abuse_engine=abuse_engine)

    @app.get("/health")
    async def health():
        return {"ok": True}

    client = TestClient(app)
    response = client.get(
        "/health",
        headers={
            "x-tenant-id": "tenant-a",
            "x-device-id": "device-a",
            "x-correlation-id": "corr-3",
            "user-agent": "Mozilla/5.0",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Abuse-Action"] in {"allow", "throttle", "challenge", "quarantine", "block"}
    assert "X-Abuse-Score" in response.headers
