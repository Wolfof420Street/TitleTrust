from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import pytest

from backend.config import settings
from backend.realtime.broadcaster import broadcaster
from tests.support.failure_injector import FailureInjector
from tests.support.fake_redis import DeterministicFakeRedis


@asynccontextmanager
async def _patched_broadcaster(fake_redis: DeterministicFakeRedis):
    original_state = {
        "_redis": broadcaster._redis,
        "_store": broadcaster._store,
        "_replay_buffer": broadcaster._replay_buffer,
        "_subscribers": broadcaster._subscribers,
        "_degraded_mode": broadcaster._degraded_mode,
        "_seq_counters": dict(broadcaster._seq_counters),
    }
    broadcaster._redis = fake_redis
    broadcaster._store = None  # replaced by individual tests
    broadcaster._replay_buffer.clear()
    broadcaster._subscribers.clear()
    broadcaster._degraded_mode = False
    broadcaster._seq_counters.clear()
    try:
        yield
    finally:
        broadcaster._redis = original_state["_redis"]
        broadcaster._store = original_state["_store"]
        broadcaster._replay_buffer = original_state["_replay_buffer"]
        broadcaster._subscribers = original_state["_subscribers"]
        broadcaster._degraded_mode = original_state["_degraded_mode"]
        broadcaster._seq_counters = original_state["_seq_counters"]


def _decode_stream_events(fake_redis: DeterministicFakeRedis):
    decoded = []
    for _, fields in fake_redis.snapshot_stream(settings.BROADCASTER_STREAM_KEY):
        payload = fields["data"] if isinstance(fields, dict) else fields.get("data")
        decoded.append(json.loads(payload))
    return decoded


@pytest.mark.asyncio
async def test_concurrent_publish_assigns_monotonic_sequence_ids(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_STREAMS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "REDIS_PUBSUB_ENABLED", True, raising=False)

    fake_redis = DeterministicFakeRedis(FailureInjector(redis_available=True))
    async with _patched_broadcaster(fake_redis):
        from backend.realtime.store import RedisStreamsEventStore

        broadcaster._store = RedisStreamsEventStore(fake_redis, settings.BROADCASTER_STREAM_KEY)

        async def _publish(index: int):
            await broadcaster.publish(
                {
                    "event_type": "agent.thought",
                    "session_id": "session-a",
                    "payload": {"message": f"event-{index}"},
                }
            )

        await asyncio.gather(*[_publish(index) for index in range(1, 26)])

        events = _decode_stream_events(fake_redis)
        sequence_ids = [event["sequence_id"] for event in events]
        event_ids = [event["event_id"] for event in events]

        assert len(sequence_ids) == 25
        assert sequence_ids == sorted(sequence_ids)
        assert len(set(sequence_ids)) == 25
        assert len(set(event_ids)) == 25


@pytest.mark.asyncio
async def test_publish_crash_falls_back_to_local_fanout(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_STREAMS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "REDIS_PUBSUB_ENABLED", True, raising=False)

    fake_redis = DeterministicFakeRedis(FailureInjector(redis_available=True, fail_xadd_on_n=1))
    async with _patched_broadcaster(fake_redis):
        from backend.realtime.store import RedisStreamsEventStore

        broadcaster._store = RedisStreamsEventStore(fake_redis, settings.BROADCASTER_STREAM_KEY)

        queue = await broadcaster.register()
        await broadcaster.publish(
            {
                "event_type": "worker.progress",
                "session_id": "session-b",
                "payload": {"message": "publish should survive xadd crash"},
            }
        )

        item = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert "worker.progress" in item
        assert fake_redis.snapshot_stream(settings.BROADCASTER_STREAM_KEY) == []
        await broadcaster.unregister(queue)


@pytest.mark.asyncio
async def test_redis_restart_mid_stream_resume_from_durable_stream(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_STREAMS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "REDIS_PUBSUB_ENABLED", True, raising=False)

    fake_redis = DeterministicFakeRedis(FailureInjector(redis_available=True))
    async with _patched_broadcaster(fake_redis):
        from backend.realtime.store import RedisStreamsEventStore

        broadcaster._store = RedisStreamsEventStore(fake_redis, settings.BROADCASTER_STREAM_KEY)
        for index in range(1, 4):
            await broadcaster.publish(
                {
                    "event_type": "agent.thought",
                    "session_id": "session-c",
                    "payload": {"message": f"durable-{index}"},
                }
            )

        durable_events = _decode_stream_events(fake_redis)
        assert len(durable_events) == 3

        fake_redis.injector.redis_available = False
        await broadcaster.publish(
            {
                "event_type": "agent.thought",
                "session_id": "session-c",
                "payload": {"message": "ephemeral-while-down"},
            }
        )
        assert broadcaster._degraded_mode is False or broadcaster._degraded_mode is True

        fake_redis.injector.redis_available = True
        replay_queue = await broadcaster.register(last_event_id=durable_events[0]["event_id"])
        replayed = []
        while not replay_queue.empty():
            replayed.append(json.loads(await replay_queue.get()))

        assert [event["sequence_id"] for event in replayed] == [2, 3]
        assert all(event["session_id"] == "session-c" for event in replayed)


@pytest.mark.asyncio
async def test_stream_truncation_triggers_partial_replay_window(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_STREAMS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "REDIS_PUBSUB_ENABLED", False, raising=False)

    injector = FailureInjector(redis_available=True, truncate_stream_at=3)
    fake_redis = DeterministicFakeRedis(injector)
    async with _patched_broadcaster(fake_redis):
        from backend.realtime.store import RedisStreamsEventStore

        broadcaster._store = RedisStreamsEventStore(fake_redis, settings.BROADCASTER_STREAM_KEY)
        for index in range(1, 7):
            await broadcaster.publish(
                {
                    "event_type": "agent.thought",
                    "session_id": "session-d",
                    "payload": {"message": f"trimmed-{index}"},
                }
            )

        events = _decode_stream_events(fake_redis)
        assert len(events) == 3
        assert [event["sequence_id"] for event in events] == [4, 5, 6]

