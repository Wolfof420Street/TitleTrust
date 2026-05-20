import time
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import deque
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger("TitleTrust-Realtime-Store")


class RealtimeEventStore(ABC):
    @abstractmethod
    async def append(self, payload: str) -> Optional[str]:
        """Append raw JSON payload to persistent store. Returns store id."""

    @abstractmethod
    async def replay(self, last_id: Optional[str] = None, count: int = 100) -> List[str]:
        """Return events after last_id (exclusive). If last_id is None return latest `count` entries."""

    @abstractmethod
    async def trim(self, maxlen: int) -> None:
        """Trim the store to `maxlen` most recent entries."""

    @abstractmethod
    async def fetch_latest_state(self, session_id: str) -> Dict:
        """Fetch latest known state for a session (best-effort)."""


class InMemoryEventStore(RealtimeEventStore):
    def __init__(self, maxlen: int = 1000):
        self._buffer = deque(maxlen=maxlen)

    async def append(self, payload: str) -> Optional[str]:
        eid = f"mem-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"
        self._buffer.append((eid, payload))
        return eid

    async def replay(self, last_id: Optional[str] = None, count: int = 100) -> List[str]:
        items = list(self._buffer)
        if last_id is None:
            return [p for (_id, p) in items[-count:]]
        out = []
        found = False
        for _id, p in items:
            if found:
                out.append(p)
            elif _id == last_id:
                found = True
        return out

    async def trim(self, maxlen: int) -> None:
        # deque enforces maxlen automatically
        return None

    async def fetch_latest_state(self, session_id: str) -> Dict:
        # best-effort: scan buffer for most recent event with session_id
        for _id, p in reversed(self._buffer):
            try:
                obj = json.loads(p)
                if obj.get("session_id") == session_id:
                    return obj
            except Exception:
                continue
        return {}


class RedisStreamsEventStore(RealtimeEventStore):
    def __init__(self, redis_client, stream_key: str):
        self._redis = redis_client
        self._stream_key = stream_key

    async def append(self, payload: str) -> Optional[str]:
        try:
            sid = await self._redis.xadd(self._stream_key, {"data": payload}, maxlen=None)
            return sid.decode() if isinstance(sid, bytes) else str(sid)
        except Exception as e:
            logger.exception("RedisStreamsEventStore append failed: %s", e)
            return None

    async def replay(self, last_id: Optional[str] = None, count: int = 100) -> List[str]:
        try:
            entries = list(reversed(await self._redis.xrevrange(self._stream_key, count=count)))
            if not last_id:
                out = []
                for _eid, fields in entries:
                    data = fields.get(b"data") if isinstance(fields, dict) else fields.get("data")
                    data_str = data.decode() if isinstance(data, bytes) else str(data)
                    out.append(data_str)
                return out

            out = []
            found = False
            for eid, fields in entries:
                data = fields.get(b"data") if isinstance(fields, dict) else fields.get("data")
                data_str = data.decode() if isinstance(data, bytes) else str(data)
                eid_str = eid.decode() if isinstance(eid, bytes) else str(eid)
                if not found:
                    if eid_str == last_id:
                        found = True
                        continue
                    try:
                        obj = json.loads(data_str)
                        if obj.get("event_id") == last_id:
                            found = True
                            continue
                    except Exception:
                        pass
                    continue
                out.append(data_str)
            return out
        except Exception as e:
            logger.exception("RedisStreamsEventStore replay failed: %s", e)
            return []

    async def trim(self, maxlen: int) -> None:
        try:
            await self._redis.xtrim(self._stream_key, maxlen=maxlen, approximate=False)
        except Exception:
            logger.exception("Failed to trim redis stream")

    async def fetch_latest_state(self, session_id: str) -> Dict:
        # best-effort scan latest N entries for session_id
        try:
            entries = await self._redis.xrevrange(self._stream_key, count=1000)
            for eid, fields in entries:
                data = fields.get(b"data") if isinstance(fields, dict) else fields.get("data")
                data_str = data.decode() if isinstance(data, bytes) else str(data)
                try:
                    obj = json.loads(data_str)
                    if obj.get("session_id") == session_id:
                        return obj
                except Exception:
                    continue
        except Exception:
            logger.exception("Failed to fetch latest state from redis stream")
        return {}
