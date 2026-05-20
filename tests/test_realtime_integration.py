import asyncio
import json
import time
import pytest

try:
    import fakeredis.aioredis as fakeredis_async
except Exception:
    fakeredis_async = None

from backend.realtime.broadcaster import Broadcaster, broadcaster
from backend.realtime.store import InMemoryEventStore, RedisStreamsEventStore
from backend.config import settings


@pytest.mark.asyncio
async def test_start_stop_lifecycle():
    # Ensure broadcaster start/stop do not raise
    b = Broadcaster()
    await b.start()
    assert b._running
    await b.stop()
    assert not b._running


@pytest.mark.asyncio
async def test_inmemory_append_and_replay():
    store = InMemoryEventStore(maxlen=10)
    sid1 = await store.append(json.dumps({"event": 1}))
    sid2 = await store.append(json.dumps({"event": 2}))
    items = await store.replay(None, count=10)
    assert len(items) >= 2


@pytest.mark.asyncio
async def test_sequence_assignment_fallback():
    b = Broadcaster()
    # no redis configured; sequence should be assigned in-memory
    ev = {"event_type": "test.seq", "session_id": "s1"}
    sid = await b.publish(ev)
    assert ev.get("sequence_id") is not None


@pytest.mark.asyncio
@pytest.mark.skipif(fakeredis_async is None, reason="fakeredis not installed")
async def test_redis_streams_append_and_replay(monkeypatch):
    # This requires fakeredis; runs a realistic redis-backed store test
    redis = await fakeredis_async.create_redis_pool()
    store = RedisStreamsEventStore(redis, "test:stream")
    await store.append(json.dumps({"x": 1}))
    await store.append(json.dumps({"x": 2}))
    items = await store.replay(None, count=10)
    assert len(items) >= 2
    redis.close()
    await redis.wait_closed()


@pytest.mark.asyncio
async def test_slow_consumer_eviction():
    b = Broadcaster()
    q = await b.register()
    # create a consumer that doesn't drain the queue;
    # publish more events than the queue size and ensure drops occur
    for i in range(settings.BROADCASTER_MAX_QUEUE_SIZE + 10):
        await b.publish({"event_type": "test.slow", "msg": str(i)})
    # give a moment
    await asyncio.sleep(0.1)
    # consumer should have some items but queue not grow unbounded
    assert q.qsize() <= settings.BROADCASTER_MAX_QUEUE_SIZE
    await b.unregister(q)

# More integration tests (multi-instance fanout, reconnect storms, replay-after-restart)
# should be added using a dockerized Redis fixture or testcontainers. TODO.
