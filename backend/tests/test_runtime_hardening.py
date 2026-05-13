from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.middleware.adaptive_protection import AdaptiveProtectionMiddleware
from backend.middleware.observability import CorrelationMiddleware
from backend.middleware.security_headers import AdvancedSecurityHeadersMiddleware


class _CapturingAbuseEngine:
    def __init__(self) -> None:
        self.last_assessment_kwargs = None

    def assess(self, **kwargs):
        self.last_assessment_kwargs = kwargs
        return SimpleNamespace(
            action=SimpleNamespace(value="allow"),
            score=5,
            retry_after_seconds=0,
            to_dict=lambda: {"action": "allow", "score": 5},
        )

    def record_threat_indicator(self, assessment, tenant_id, device_id) -> None:
        return None


def test_middleware_order_propagates_generated_correlation_id():
    abuse_engine = _CapturingAbuseEngine()
    app = FastAPI()
    app.add_middleware(AdvancedSecurityHeadersMiddleware)
    app.add_middleware(AdaptiveProtectionMiddleware, abuse_engine=abuse_engine)
    app.add_middleware(CorrelationMiddleware)

    @app.get("/health")
    async def health():
        return {"ok": True}

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"]
    assert abuse_engine.last_assessment_kwargs["correlation_id"] == response.headers["X-Correlation-ID"]


def test_security_headers_middleware_adds_nonce_backed_csp_headers():
    app = FastAPI()
    app.add_middleware(AdvancedSecurityHeadersMiddleware)

    @app.get("/health")
    async def health():
        return {"ok": True}

    response = TestClient(app).get("/health")

    policy = response.headers.get("Content-Security-Policy-Report-Only", "")
    assert "script-src 'self' 'nonce-" in policy
    assert "frame-ancestors 'none'" in policy
    assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"
