from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple
from collections import deque

from .failure_injector import FailureInjector


@dataclass
class _Message:
    type: str
    data: Any


class FakePubSub:
    def __init__(self, redis: "DeterministicFakeRedis"):
        self._redis = redis
        self._queue: asyncio.Queue = asyncio.Queue()
        self._channels: set[str] = set()
        self._closed = False

    async def subscribe(self, channel: str) -> None:
        self._channels.add(channel)
        self._redis._subscribers.setdefault(channel, []).append(self)

    async def listen(self):
        while not self._closed:
            message = await self._queue.get()
            if message is None:
                break
            yield message

    async def close(self) -> None:
        self._closed = True
        await self._queue.put(None)

    def push(self, payload: Any) -> None:
        if not self._closed:
            self._queue.put_nowait(payload)


class DeterministicFakeRedis:
    """Minimal Redis stand-in for deterministic chaos tests.

    Supports the subset used by the realtime broadcaster: xadd/xrange/xrevrange,
    pubsub publish/subscribe, incr, ping, and xlen.
    """

    def __init__(self, injector: Optional[FailureInjector] = None):
        self.injector = injector or FailureInjector()
        self._streams: Dict[str, Deque[Tuple[str, Dict[str, Any]]]] = {}
        self._subscribers: Dict[str, List[FakePubSub]] = {}
        self._counters: Dict[str, int] = {}
        self._publish_index = 0
        self._xadd_index = 0

    def pubsub(self) -> FakePubSub:
        return FakePubSub(self)

    async def ping(self) -> bool:
        if not self.injector.redis_available:
            raise ConnectionError("redis unavailable")
        return True

    async def xadd(self, stream: str, fields: Dict[str, Any], maxlen: Optional[int] = None, approximate: bool = True):
        if not self.injector.redis_available:
            raise ConnectionError("redis unavailable")
        self._xadd_index += 1
        if self.injector.should_fail_xadd(self._xadd_index):
            raise ConnectionError("xadd injected failure")

        entries = self._streams.setdefault(stream, deque())
        event_id = f"{int(time.time() * 1000)}-{self._xadd_index}"
        entries.append((event_id, dict(fields)))
        if maxlen is not None:
            while len(entries) > maxlen:
                entries.popleft()
        if self.injector.truncate_stream_at is not None:
            while len(entries) > self.injector.truncate_stream_at:
                entries.popleft()
        return event_id

    async def xrange(self, stream: str, min: str = '-', max: str = '+', count: Optional[int] = None):
        entries = list(self._streams.get(stream, deque()))
        if min not in ('-', None):
            entries = [item for item in entries if item[0] >= str(min)]
        if count is not None:
            entries = entries[:count]
        return [(entry_id, fields) for entry_id, fields in entries]

    async def xrevrange(self, stream: str, count: Optional[int] = None):
        entries = list(reversed(list(self._streams.get(stream, deque()))))
        if count is not None:
            entries = entries[:count]
        return [(entry_id, fields) for entry_id, fields in entries]

    async def xlen(self, stream: str) -> int:
        return len(self._streams.get(stream, deque()))

    async def incr(self, key: str) -> int:
        current = self._counters.get(key, 0) + 1
        self._counters[key] = current
        return current

    async def publish(self, channel: str, payload: str):
        if not self.injector.redis_available:
            raise ConnectionError("redis unavailable")
        self._publish_index += 1
        if self.injector.should_fail_publish(self._publish_index):
            raise ConnectionError("publish injected failure")

        if self.injector.should_delay(self._publish_index):
            await asyncio.sleep(0.01)

        message_payload = payload
        if self.injector.should_malformed(self._publish_index):
            message_payload = '{"malformed": true'

        message = {"type": "message", "data": message_payload}
        subscribers = list(self._subscribers.get(channel, []))
        for sub in subscribers:
            if self.injector.should_drop(self._publish_index):
                continue
            sub.push(message)
            if self.injector.should_duplicate(self._publish_index):
                sub.push(message)

        return len(subscribers)

    async def close(self):
        for subscribers in self._subscribers.values():
            for sub in subscribers:
                await sub.close()

    def snapshot_stream(self, stream: str) -> List[Tuple[str, Dict[str, Any]]]:
        return list(self._streams.get(stream, deque()))

    def encode_event(self, event: Dict[str, Any]) -> str:
        return json.dumps(event)
