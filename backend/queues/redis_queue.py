from __future__ import annotations

import json
import logging
import signal
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Optional

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings

logger = logging.getLogger("TitleTrust-RedisQueue")
DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 0.1


class RedisQueue:
    def __init__(self) -> None:
        self._client = None
        self._connect()

    def _connect(self) -> None:
        if not settings.REDIS_URL:
            self._client = None
            return
        try:
            import redis

            self._client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            self._client = None
            logger.exception("Redis client initialization failed")

    def _is_retryable_error(self, exc: Exception) -> bool:
        try:
            import redis

            return isinstance(exc, (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError))
        except Exception:
            return False

    def _execute(self, operation_name: str, func: Callable[[], Any]) -> Any:
        attempts = DEFAULT_RETRY_ATTEMPTS + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            if not self._client:
                self._connect()
            if not self._client:
                break
            try:
                return func()
            except Exception as exc:
                if not self._is_retryable_error(exc) or attempt == attempts:
                    logger.exception("Redis %s failed", operation_name, extra={"attempt": attempt})
                    raise RuntimeError(f"Redis {operation_name} failed") from exc
                last_error = exc
                logger.warning("Redis %s transient failure; retrying", operation_name, extra={"attempt": attempt})
                self._connect()
                time.sleep(DEFAULT_RETRY_BACKOFF_SECONDS * attempt)
        raise RuntimeError(f"Redis {operation_name} unavailable") from last_error

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def enqueue(self, queue_name: str, payload: Dict[str, Any], priority: str = "default") -> None:
        envelope = {"priority": priority, "payload": payload}
        self._execute("enqueue", lambda: self._client.rpush(queue_name, json.dumps(envelope)))

    def pop(self, queue_name: str, timeout_seconds: int = 5) -> Optional[Dict[str, Any]]:
        if not self._client:
            return None
        item = self._execute("pop", lambda: self._client.blpop(queue_name, timeout=timeout_seconds))
        if not item:
            return None
        _, raw = item
        return json.loads(raw)

    def set_heartbeat(self, worker_id: str) -> None:
        if not self._client:
            return
        self._execute(
            "set_heartbeat",
            lambda: self._client.setex(
                f"worker-heartbeat:{worker_id}",
                settings.WORKER_HEARTBEAT_TTL_SECONDS,
                str(time.time()),
            ),
        )

    def cancel(self, job_id: str) -> None:
        if not self._client:
            return
        self._execute(
            "cancel",
            lambda: self._client.set(f"cancel-job:{job_id}", "1", ex=settings.WORKER_TASK_TIMEOUT_SECONDS),
        )

    def is_cancelled(self, job_id: str) -> bool:
        if not self._client:
            return False
        return self._execute("is_cancelled", lambda: self._client.get(f"cancel-job:{job_id}") == "1")

    def queue_depth(self, queue_name: str) -> int:
        if not self._client:
            return 0
        return int(self._client.llen(queue_name))

    def ping(self) -> bool:
        if not self._client:
            return False
        try:
            return bool(self._execute("ping", lambda: self._client.ping()))
        except Exception:
            logger.exception("Redis ping failed")
            return False


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
