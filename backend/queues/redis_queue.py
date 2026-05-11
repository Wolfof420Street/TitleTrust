from __future__ import annotations

import json
import logging
import signal
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings

logger = logging.getLogger("TitleTrust-RedisQueue")


class RedisQueue:
    def __init__(self) -> None:
        self._client = None
        if settings.REDIS_URL:
            try:
                import redis

                self._client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            except Exception:
                logger.exception("Redis client initialization failed")

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def enqueue(self, queue_name: str, payload: Dict[str, Any], priority: str = "default") -> None:
        if not self._client:
            raise RuntimeError("Redis queue unavailable")
        envelope = {"priority": priority, "payload": payload}
        self._client.rpush(queue_name, json.dumps(envelope))

    def pop(self, queue_name: str, timeout_seconds: int = 5) -> Optional[Dict[str, Any]]:
        if not self._client:
            return None
        item = self._client.blpop(queue_name, timeout=timeout_seconds)
        if not item:
            return None
        _, raw = item
        return json.loads(raw)

    def set_heartbeat(self, worker_id: str) -> None:
        if not self._client:
            return
        self._client.setex(
            f"worker-heartbeat:{worker_id}",
            settings.WORKER_HEARTBEAT_TTL_SECONDS,
            str(time.time()),
        )

    def cancel(self, job_id: str) -> None:
        if not self._client:
            return
        self._client.set(f"cancel-job:{job_id}", "1", ex=settings.WORKER_TASK_TIMEOUT_SECONDS)

    def is_cancelled(self, job_id: str) -> bool:
        if not self._client:
            return False
        return self._client.get(f"cancel-job:{job_id}") == "1"


@contextmanager
def time_limit(seconds: int) -> Generator[None, None, None]:
    def _handle_timeout(signum, frame):
        raise TimeoutError("Worker task timeout exceeded")

    original = signal.signal(signal.SIGALRM, _handle_timeout)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original)
