import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Optional, Protocol


class RateLimitStore(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> int: ...


class InMemoryRateLimitStore:
    def __init__(self) -> None:
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> int:
        now = time.time()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] > window_seconds:
                events.popleft()
            if len(events) >= limit:
                return 0
            events.append(now)
            return max(0, limit - len(events))


class RedisRateLimitStore:
    def __init__(self, redis_client) -> None:
        self.redis = redis_client

    def hit(self, key: str, limit: int, window_seconds: int) -> int:
        now = int(time.time())
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds + 1)
        _, current, _, _ = pipe.execute()
        if current >= limit:
            return 0
        return max(0, limit - int(current) - 1)


def build_store(redis_url: Optional[str]):
    if redis_url:
        try:
            import redis

            client = redis.Redis.from_url(redis_url, decode_responses=True)
            client.ping()
            return RedisRateLimitStore(client)
        except Exception:
            return InMemoryRateLimitStore()
    return InMemoryRateLimitStore()
