import logging
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Tuple

from fastapi import HTTPException, Request, status

logger = logging.getLogger("TitleTrust-Security")


class InMemoryRateLimiter:
    """Simple per-IP+path sliding-window limiter for API abuse resistance."""

    def __init__(self, requests_per_window: int = 60, window_seconds: int = 60) -> None:
        self._requests_per_window = requests_per_window
        self._window_seconds = window_seconds
        self._lock = Lock()
        self._events: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)

    def enforce(self, key: Tuple[str, str]) -> None:
        now = time.time()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] > self._window_seconds:
                events.popleft()

            if len(events) >= self._requests_per_window:
                logger.warning("Rate limit hit", extra={"client": key[0], "path": key[1]})
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please retry shortly.",
                )

            events.append(now)


rate_limiter = InMemoryRateLimiter()


async def enforce_rate_limit(request: Request) -> None:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client_host = forwarded_for or (request.client.host if request.client else "unknown")
    rate_limiter.enforce((client_host, request.url.path))
