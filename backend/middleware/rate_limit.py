from fastapi import HTTPException, Request, status

from config import get_settings
from infrastructure.rate_limit_store import build_store

settings = get_settings()
store = build_store(getattr(settings, "REDIS_URL", None))


def _request_key(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = xff or (request.client.host if request.client else "unknown")
    uid = request.headers.get("x-user-id", "anonymous")
    return f"rl:{request.url.path}:{ip}:{uid}"


async def enforce_rate_limit(request: Request) -> None:
    key = _request_key(request)
    remaining = store.hit(
        key=key,
        limit=settings.API_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )
    if remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": "60"},
        )
