from __future__ import annotations

import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass
from threading import BoundedSemaphore, Lock
from typing import Any, Callable, Deque, Dict, TypeVar

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings

logger = logging.getLogger("TitleTrust-GeminiApiManager")

T = TypeVar("T")


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class GeminiApiManager:
    """Centralized throttling and caching for Gemini-bound document analysis."""

    def __init__(
        self,
        *,
        max_concurrent_requests: int | None = None,
        max_calls: int | None = None,
        period_seconds: int | None = None,
        cache_ttl_seconds: int | None = None,
        cache_enabled: bool | None = None,
    ) -> None:
        self._max_calls = max_calls or settings.GEMINI_RATE_LIMIT_CALLS
        self._period_seconds = period_seconds or settings.GEMINI_RATE_LIMIT_PERIOD_SECONDS
        self._cache_ttl_seconds = cache_ttl_seconds or settings.GEMINI_CACHE_TTL_SECONDS
        self._cache_enabled = settings.GEMINI_CACHE_ENABLED if cache_enabled is None else cache_enabled
        self._semaphore = BoundedSemaphore(max_concurrent_requests or settings.GEMINI_MAX_CONCURRENT_REQUESTS)
        self._rate_lock = Lock()
        self._cache_lock = Lock()
        self._call_timestamps: Deque[float] = deque()
        self._cache: Dict[str, CacheEntry] = {}

    def execute_forensic_analysis(self, file_path: str, callback: Callable[[], T]) -> T:
        cache_key = self._build_cache_key(file_path)
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.info("Gemini cache hit", extra={"cache_key": cache_key[:12]})
            return cached

        logger.info("Gemini cache miss", extra={"cache_key": cache_key[:12]})
        started = time.perf_counter()
        with self._semaphore:
            self._await_capacity()
            result = callback()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info("Gemini live analysis completed", extra={"cache_key": cache_key[:12], "latency_ms": elapsed_ms})

        self._set_cached(cache_key, result)
        return result

    def _await_capacity(self) -> None:
        while True:
            sleep_for = 0.0
            with self._rate_lock:
                now = time.time()
                while self._call_timestamps and self._call_timestamps[0] <= now - self._period_seconds:
                    self._call_timestamps.popleft()

                if len(self._call_timestamps) < self._max_calls:
                    self._call_timestamps.append(now)
                    return

                sleep_for = max(0.01, self._period_seconds - (now - self._call_timestamps[0]))

            logger.warning("Gemini rate window full; sleeping before next request", extra={"sleep_for": sleep_for})
            time.sleep(sleep_for)

    def _build_cache_key(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha256_hash.update(chunk)
        sha256_hash.update(settings.FORENSIC_MODEL_NAME.encode("utf-8"))
        return sha256_hash.hexdigest()

    def _get_cached(self, cache_key: str) -> T | None:
        if not self._cache_enabled:
            return None

        with self._cache_lock:
            entry = self._cache.get(cache_key)
            if not entry:
                return None
            if entry.expires_at <= time.time():
                self._cache.pop(cache_key, None)
                return None
            return entry.value

    def _set_cached(self, cache_key: str, value: T) -> None:
        if not self._cache_enabled:
            return
        if isinstance(value, dict) and value.get("error"):
            return

        with self._cache_lock:
            self._cache[cache_key] = CacheEntry(
                value=value,
                expires_at=time.time() + self._cache_ttl_seconds,
            )


gemini_api_manager = GeminiApiManager()
