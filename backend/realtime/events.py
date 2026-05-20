import time
import logging
from typing import Any, Dict, Optional
from backend.realtime.broadcaster import broadcaster
from backend.realtime.redact import sanitize_event_payload
from backend.config import settings
try:
    from opentelemetry import trace
except Exception:
    trace = None

logger = logging.getLogger("TitleTrust-RealtimeEvents")


def _current_trace_id() -> Optional[str]:
    try:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            return f"{ctx.trace_id:032x}"
    except Exception:
        pass
    return None


async def emit(
    event_type: str,
    payload: Dict[str, Any],
    *,
    severity: str = "info",
    session_id: Optional[str] = None,
    job_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> None:
    """Emit a structured realtime event and publish via broadcaster.

    This is best-effort and non-blocking from caller perspective.
    """
    envelope = {
        "event_type": event_type,
        "timestamp": time.time(),
        "severity": severity,
        "session_id": session_id,
        "job_id": job_id,
        "correlation_id": correlation_id,
        "trace_id": trace_id or _current_trace_id(),
        "payload": sanitize_event_payload(payload),
    }

    try:
        await broadcaster.publish(envelope)
    except Exception as e:
        logger.warning("Failed to publish realtime event %s: %s", event_type, e)