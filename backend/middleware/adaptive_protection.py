"""Adaptive abuse protection middleware."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import threading
from typing import Callable, Optional

from fastapi import Request, Response
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

from backend.security.abuse_detection import AbuseAction, AbuseDetectionEngine

logger = logging.getLogger("TitleTrust-AdaptiveProtection")

_UUID_SEGMENT = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
_NUMERIC_SEGMENT = re.compile(r"^\d+$")
_BG_LOOP: asyncio.AbstractEventLoop | None = None
_BG_LOOP_LOCK = threading.Lock()


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    parts = []
    for part in path.split("/"):
        if _UUID_SEGMENT.fullmatch(part):
            parts.append("{uuid}")
        elif _NUMERIC_SEGMENT.fullmatch(part):
            parts.append("{id}")
        else:
            parts.append(part)
    return "/".join(parts) or "/"


def _ensure_background_loop() -> asyncio.AbstractEventLoop:
    global _BG_LOOP
    if _BG_LOOP and _BG_LOOP.is_running():
        return _BG_LOOP
    with _BG_LOOP_LOCK:
        if _BG_LOOP and _BG_LOOP.is_running():
            return _BG_LOOP
        loop = asyncio.new_event_loop()

        def _run() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        threading.Thread(target=_run, daemon=True).start()
        _BG_LOOP = loop
        return loop

ABUSE_ASSESSMENTS = Counter(
    "titletrust_abuse_assessments_total",
    "Adaptive abuse assessments by action",
    ["action", "tenant_id", "path"],
)
ABUSE_SCORE = Histogram(
    "titletrust_abuse_score",
    "Adaptive abuse score distribution",
    ["tenant_id", "path"],
    buckets=(0, 10, 20, 40, 60, 80, 100),
)
ABUSE_BLOCKS = Counter(
    "titletrust_abuse_blocks_total",
    "Requests blocked by adaptive protection",
    ["tenant_id", "path"],
)


class AdaptiveProtectionMiddleware(BaseHTTPMiddleware):
    """Evaluate requests and enforce adaptive abuse controls."""

    def __init__(
        self,
        app,
        abuse_engine: AbuseDetectionEngine,
        challenge_hook: Optional[Callable[[Request, dict], None]] = None,
    ) -> None:
        super().__init__(app)
        self._abuse_engine = abuse_engine
        self._challenge_hook = challenge_hook

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant_id = request.headers.get("x-tenant-id", "public")
        device_id = request.headers.get("x-device-id", request.headers.get("x-user-id", "anonymous"))
        correlation_id = getattr(request.state, "correlation_id", request.headers.get("x-correlation-id", "unknown"))
        ip_address = self._resolve_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")

        assessment = self._abuse_engine.assess(
            tenant_id=tenant_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            method=request.method,
            path=request.url.path,
            correlation_id=correlation_id,
            headers=dict(request.headers),
            session=getattr(request.state, "session", None),
        )

        request.state.abuse_assessment = assessment
        self._abuse_engine.record_threat_indicator(assessment, tenant_id, device_id)
        normalized_path = _normalize_path(request.url.path)
        ABUSE_ASSESSMENTS.labels(assessment.action.value, tenant_id, normalized_path).inc()
        ABUSE_SCORE.labels(tenant_id, normalized_path).observe(assessment.score)

        if assessment.action == AbuseAction.BLOCK:
            ABUSE_BLOCKS.labels(tenant_id, normalized_path).inc()
            logger.warning(
                "abuse.blocked",
                extra={"correlation_id": correlation_id, "tenant_id": tenant_id, "score": assessment.score},
            )
            # Emit realtime security.blocked event
            try:
                import asyncio
                from backend.realtime.events import emit

                payload = {"tenant_id": tenant_id, "path": request.url.path, "score": assessment.score}
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(emit("security.blocked", payload, severity="warning", correlation_id=correlation_id))
                except RuntimeError:
                    asyncio.run_coroutine_threadsafe(
                        emit("security.blocked", payload, severity="warning", correlation_id=correlation_id),
                        _ensure_background_loop(),
                    )
            except Exception:
                pass

            return Response(
                content=json.dumps({"detail": "Request blocked by adaptive protection"}),
                status_code=403,
                media_type="application/json",
                headers={
                    "Retry-After": str(max(assessment.retry_after_seconds, 60)),
                    "X-Abuse-Action": assessment.action.value,
                    "X-Abuse-Score": str(assessment.score),
                },
            )

        if assessment.action in {AbuseAction.CHALLENGE, AbuseAction.QUARANTINE} and self._challenge_hook:
            try:
                challenge_payload = assessment.to_dict()
                if inspect.iscoroutinefunction(self._challenge_hook):
                    await self._challenge_hook(request, challenge_payload)
                else:
                    await asyncio.to_thread(self._challenge_hook, request, assessment.to_dict())
            except Exception:
                logger.exception("challenge hook failed")

        response = await call_next(request)
        response.headers["X-Abuse-Action"] = assessment.action.value
        response.headers["X-Abuse-Score"] = str(assessment.score)
        if assessment.retry_after_seconds:
            response.headers["Retry-After"] = str(assessment.retry_after_seconds)
        return response

    @staticmethod
    def _resolve_ip(request: Request) -> str:
        xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        return xff or (request.client.host if request.client else "unknown")
