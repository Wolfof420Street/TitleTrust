import hashlib

from fastapi import HTTPException, Request, status

try:
    from backend.config import get_settings
except ImportError:  # pragma: no cover - fallback for local module execution
    from config import get_settings
try:
    from backend.infrastructure.rate_limit_store import build_store
except ImportError:  # pragma: no cover - fallback for local module execution
    from infrastructure.rate_limit_store import build_store

settings = get_settings()
store = build_store(getattr(settings, "REDIS_URL", None))


def _request_key(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = xff or (request.client.host if request.client else "unknown")
    auth_header = request.headers.get("authorization", "")
    device_session_id = request.headers.get("x-device-session-id", "")
    principal = auth_header or device_session_id or "anonymous"
    principal_fingerprint = hashlib.sha256(principal.encode("utf-8")).hexdigest()[:16]
    return f"rl:{request.url.path}:{ip}:{principal_fingerprint}"


async def enforce_rate_limit(request: Request) -> None:
    key = _request_key(request)
    remaining = store.hit(
        key=key,
        limit=settings.API_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )
    if remaining <= 0:
            # Emit realtime event about rate limit enforcement (best-effort)
            try:
                import asyncio
                from backend.realtime.events import emit

                payload = {
                    "path": request.url.path,
                    "ip": request.client.host if request.client else "unknown",
                    "rule_key": key,
                }
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(emit("security.rate_limited", payload, severity="warning", correlation_id=request.headers.get("x-correlation-id")))
                except RuntimeError:
                    # run in background thread if no loop
                    import threading

                    def _run_emit():
                        try:
                            import asyncio as _asyncio
                            from backend.realtime.events import emit as _emit

                            _asyncio.run(_emit("security.rate_limited", payload, severity="warning", correlation_id=request.headers.get("x-correlation-id")))
                        except Exception:
                            pass

                    threading.Thread(target=_run_emit, daemon=True).start()
            except Exception:
                pass

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": "60"},
            )
