import asyncio
import pytest

from backend.realtime.broadcaster import broadcaster


@pytest.fixture(autouse=True)
async def reset_broadcaster_state():
    async with broadcaster._lock:
        broadcaster._subscribers.clear()
        broadcaster._replay_buffer.clear()
        broadcaster._seq_counters.clear()
    yield
    async with broadcaster._lock:
        broadcaster._subscribers.clear()
        broadcaster._replay_buffer.clear()
        broadcaster._seq_counters.clear()


@pytest.mark.asyncio
async def test_register_and_publish():
    q = await broadcaster.register()
    # publish a simple event
    await broadcaster.publish({"event_type": "test.event", "payload": {"x": 1}})
    # consume
    item = await asyncio.wait_for(q.get(), timeout=1.0)
    assert "test.event" in item
    await broadcaster.unregister(q)


@pytest.mark.asyncio
async def test_replay_buffer():
    # publish some events
    for i in range(5):
        await broadcaster.publish({"event_type": "replay.test", "payload": {"i": i}})

    q = await broadcaster.register()
    items = []
    while not q.empty():
        items.append(await asyncio.wait_for(q.get(), timeout=1.0))
    assert any("replay.test" in item for item in items)
    await broadcaster.unregister(q)


@pytest.mark.asyncio
async def test_bounded_queue_drop():
    # create a tiny queue to force drop
    original = broadcaster._replay_buffer
    try:
        broadcaster._replay_buffer = original
        q = asyncio.Queue(maxsize=1)
        # manually create Subscriber-like object
        class Sub:
            def __init__(self, queue):
                self.queue = queue
                self.last_active = 0

        sub = Sub(q)
        async with broadcaster._lock:
            broadcaster._subscribers.add(sub)
        # publish multiple events quickly
        await broadcaster.publish({"event_type": "drop.test", "payload": {"v": 1}})
        await broadcaster.publish({"event_type": "drop.test", "payload": {"v": 2}})
        # queue should contain at most 1
        assert q.qsize() <= 1
        async with broadcaster._lock:
            broadcaster._subscribers.discard(sub)
    finally:
        broadcaster._replay_buffer = original