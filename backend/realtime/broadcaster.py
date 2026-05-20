import asyncio
import json
import time
import logging
import uuid
from collections import deque
from typing import Dict, Set, Deque, Optional
import socket

from prometheus_client import Counter, Gauge, Histogram, REGISTRY

from backend.config import settings
from backend.realtime.store import InMemoryEventStore, RedisStreamsEventStore

logger = logging.getLogger("TitleTrust-Broadcaster")


def _metric(factory, name: str, help_text: str, *args, **kwargs):
    try:
        return factory(name, help_text, *args, **kwargs)
    except ValueError:
        existing = REGISTRY._names_to_collectors.get(name)
        if existing is not None:
            return existing
        raise


class Subscriber:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.last_active = time.time()


class Broadcaster:
    """Redis-backed optional broadcaster with in-process fallback.

    Features:
    - optional Redis Pub/Sub fanout
    - bounded per-subscriber queues
    - in-memory replay buffer
    - heartbeat events
    - metrics: active subscribers, dropped events, publish latency
    """

    def __init__(self):
        self._subscribers: Set[Subscriber] = set()
        self._lock = asyncio.Lock()
        self._replay_buffer: Deque[str] = deque(maxlen=settings.BROADCASTER_REPLAY_BUFFER)
        self._redis = None
        self._redis_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        self._instance_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
        self._store = InMemoryEventStore(maxlen=settings.BROADCASTER_REPLAY_BUFFER)
        self._seq_counters: Dict[str, int] = {}
        self._degraded_mode = False

        # Metrics
        self.metrics_active = _metric(Gauge, "titletrust_realtime_active_subscribers", "Active SSE subscribers")
        self.metrics_dropped = _metric(Counter, "titletrust_realtime_dropped_events_total", "Dropped realtime events")
        self.metrics_publish_latency = _metric(Histogram, "titletrust_realtime_publish_latency_seconds", "Publish latency seconds")
        self.metrics_event_count = _metric(Counter, "titletrust_realtime_events_total", "Realtime events published", ["event_type"])
        self.metrics_connections = _metric(Counter, "titletrust_realtime_connections_total", "SSE connections established")
        self.metrics_disconnects = _metric(Counter, "titletrust_realtime_disconnects_total", "SSE disconnects")
        self.metrics_replay_hits = _metric(Counter, "titletrust_realtime_replay_hits_total", "Replay hits returned to new subscriber")
        self.metrics_replay_misses = _metric(Counter, "titletrust_realtime_replay_misses_total", "Replay misses when none available")
        self.metrics_redis_reconnects = _metric(Counter, "titletrust_realtime_redis_reconnects_total", "Redis pubsub reconnect attempts")
        self.metrics_subscriber_lag = _metric(Histogram, "titletrust_realtime_subscriber_lag_seconds", "Observed subscriber lag seconds")
        self.metrics_stream_write_failures = _metric(Counter, "titletrust_realtime_stream_write_failures_total", "Failures writing to stream")
        self.metrics_replay_duration = _metric(Histogram, "titletrust_realtime_replay_duration_seconds", "Duration of replay fetches")
        self.metrics_redis_failover = _metric(Gauge, "titletrust_realtime_redis_failover_mode", "1 when operating in degraded (no-redis) mode")
        self.metrics_oversized_payloads = _metric(Counter, "titletrust_realtime_oversized_payloads_total", "Events rejected for exceeding max payload size")

        # Start background Redis listener if enabled
        if settings.REDIS_PUBSUB_ENABLED and settings.REDIS_URL:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(settings.REDIS_URL)
                # do not start listener here; defer to explicit start()
                pass
            except Exception as e:
                logger.warning("Redis pubsub init failed, falling back to in-process: %s", e)

        # Start heartbeat
        # Defer background task creation until start() is called by application lifespan
        pass

    async def start(self) -> None:
        """Start background tasks: Redis listener and heartbeat."""
        if self._running:
            return
        if settings.REDIS_PUBSUB_ENABLED and settings.REDIS_URL and self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(settings.REDIS_URL)
            except Exception as e:
                logger.warning("Redis init on start failed: %s", e)

        loop = asyncio.get_event_loop()
        if settings.REDIS_PUBSUB_ENABLED and self._redis:
            self._redis_task = loop.create_task(self._redis_subscriber_loop())

        # If Redis Streams enabled, switch store implementation
        if settings.REDIS_STREAMS_ENABLED and self._redis:
            try:
                self._store = RedisStreamsEventStore(self._redis, settings.BROADCASTER_STREAM_KEY)
                self._degraded_mode = False
            except Exception:
                logger.exception("Failed to initialize RedisStreamsEventStore; staying in-memory")
                self._degraded_mode = True

        self._heartbeat_task = loop.create_task(self._heartbeat_loop())
        self._running = True

    async def stop(self) -> None:
        """Stop background tasks and flush subscribers."""
        self._running = False
        # cancel tasks
        tasks = [self._redis_task, self._heartbeat_task]
        for t in tasks:
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

        # flush pending messages to subscribers with a shutdown event
        async with self._lock:
            for sub in list(self._subscribers):
                try:
                    sub.queue.put_nowait(json.dumps({"event_type": "shutdown", "ts": time.time()}))
                except asyncio.QueueFull:
                    pass

        # allow small grace period for clients to receive shutdown
        await asyncio.sleep(0.1)

    def _start_redis_listener(self):
        try:
            loop = asyncio.get_event_loop()
            self._redis_task = loop.create_task(self._redis_subscriber_loop())
        except RuntimeError:
            # will be started later
            pass

    async def _redis_subscriber_loop(self):
        # resilient listener with exponential backoff and automatic restart
        attempt = 0
        base = 0.5
        while self._running:
            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe(settings.BROADCASTER_CHANNEL)
                logger.info("Subscribed to redis channel %s", settings.BROADCASTER_CHANNEL)
                attempt = 0
                async for message in pubsub.listen():
                    if not self._running:
                        break
                    if message is None:
                        continue
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if isinstance(data, bytes):
                        payload = data.decode("utf-8")
                    else:
                        payload = str(data)
                    await self._fanout_raw(payload)
            except asyncio.CancelledError:
                break
            except Exception as e:
                attempt += 1
                self.metrics_redis_reconnects.inc()
                self.metrics_redis_listener_restarts = getattr(self, "metrics_redis_listener_restarts", None)
                if self.metrics_redis_listener_restarts is None:
                    from prometheus_client import Counter

                    self.metrics_redis_listener_restarts = Counter("titletrust_realtime_redis_listener_restarts_total", "Redis listener restarts")
                self.metrics_redis_listener_restarts.inc()
                logger.exception("Redis subscriber loop failed, will retry: %s", e)
                # exponential backoff with jitter
                wait = min(30.0, base * (2 ** attempt))
                jitter = wait * 0.1 * (0.5 - (uuid.uuid4().int % 100) / 100)
                await asyncio.sleep(max(0.1, wait + jitter))
                # if many attempts, flip to degraded mode
                if attempt > 3:
                    self._degraded_mode = True
                    try:
                        # ensure we still have in-memory store
                        self._store = InMemoryEventStore(maxlen=settings.BROADCASTER_REPLAY_BUFFER)
                    except Exception:
                        pass
                continue

    async def _stream_add(self, payload: str) -> Optional[str]:
        """Append event to Redis Stream for durable replay. Returns stream id on success."""
        if not (settings.REDIS_STREAMS_ENABLED and self._redis):
            return None
        try:
            # xadd with maxlen
            kwargs = {"maxlen": settings.BROADCASTER_STREAM_MAXLEN, "approximate": True}
            # Redis asyncio client xadd signature: xadd(name, fields, maxlen=None, approx=False)
            stream_id = await self._redis.xadd(settings.BROADCASTER_STREAM_KEY, {"data": payload}, maxlen=settings.BROADCASTER_STREAM_MAXLEN, approximate=True)
            return stream_id.decode() if isinstance(stream_id, bytes) else str(stream_id)
        except Exception as e:
            logger.exception("Failed to append to redis stream: %s", e)
            return None

    async def _fanout_raw(self, payload: str) -> None:
        async with self._lock:
            self._replay_buffer.append(payload)
            bad = 0
            for sub in list(self._subscribers):
                try:
                    sub.queue.put_nowait(payload)
                    sub.last_active = time.time()
                except asyncio.QueueFull:
                    bad += 1
                    self.metrics_dropped.inc()
            if bad:
                logger.debug("Dropped %d events due to slow subscribers", bad)

    async def register(self, last_event_id: Optional[str] = None) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=settings.BROADCASTER_MAX_QUEUE_SIZE)
        sub = Subscriber(q)
        async with self._lock:
            self._subscribers.add(sub)
            self.metrics_active.set(len(self._subscribers))
            self.metrics_connections.inc()
            # If Redis Streams enabled, prefer durable replay from stream
            items = []
            if settings.REDIS_STREAMS_ENABLED and self._redis:
                try:
                    entries = list(reversed(await self._redis.xrevrange(settings.BROADCASTER_STREAM_KEY, count=settings.BROADCASTER_REPLAY_BUFFER)))
                    found = last_event_id is None
                    for eid, fields in entries:
                        data = fields.get(b"data") if isinstance(fields, dict) else fields.get("data")
                        data_str = data.decode() if isinstance(data, bytes) else str(data)
                        if last_event_id and not found:
                            eid_str = eid.decode() if isinstance(eid, bytes) else str(eid)
                            if eid_str == last_event_id:
                                found = True
                                continue
                            try:
                                obj = json.loads(data_str)
                                if obj.get("event_id") == last_event_id:
                                    found = True
                                    continue
                            except Exception:
                                pass
                            continue
                        if found:
                            items.append(data_str)

                    if last_event_id and not items:
                        found = False
                        for item in list(self._replay_buffer):
                            try:
                                obj = json.loads(item)
                                if not found and obj.get("event_id") == last_event_id:
                                    found = True
                                    continue
                                if obj.get("stream_offset") is None:
                                    continue
                            except Exception:
                                pass
                            if found:
                                items.append(item)
                except Exception:
                    logger.exception("Failed to read from redis stream for replay")
                    items = list(self._replay_buffer)
            else:
                # replay last events after last_event_id from local in-memory buffer
                if last_event_id is None:
                    items = list(self._replay_buffer)
                else:
                    items = []
                    found = False
                    for item in list(self._replay_buffer):
                        try:
                            obj = json.loads(item)
                            if found:
                                items.append(item)
                            elif obj.get("event_id") == last_event_id:
                                found = True
                        except Exception:
                            # on parse error, include conservatively
                            items.append(item)

            if items:
                self.metrics_replay_hits.inc()
            else:
                self.metrics_replay_misses.inc()

            for item in items:
                try:
                    q.put_nowait(item)
                except asyncio.QueueFull:
                    break
        return q

    async def unregister(self, q: asyncio.Queue) -> None:
        async with self._lock:
            to_remove = [s for s in self._subscribers if s.queue is q]
            for s in to_remove:
                self._subscribers.discard(s)
            self.metrics_active.set(len(self._subscribers))
            self.metrics_disconnects.inc()

    async def publish(self, event: Dict) -> None:
        event.setdefault("ts", time.time())
        event.setdefault("event_id", uuid.uuid4().hex)

        # basic schema validation
        if "event_type" not in event:
            logger.warning("Rejecting event without event_type: %s", event)
            return None

        session_id = event.get("session_id") or (event.get("payload") or {}).get("session_id")
        # assign sequence id per-session
        seq = None
        try:
            if session_id and self._redis:
                try:
                    seq = await self._redis.incr(f"seq:{session_id}")
                except Exception:
                    # fallback
                    seq = self._seq_counters.get(session_id, 0) + 1
                    self._seq_counters[session_id] = seq
            elif session_id:
                seq = self._seq_counters.get(session_id, 0) + 1
                self._seq_counters[session_id] = seq
        except Exception:
            seq = None

        if seq is not None:
            event["sequence_id"] = int(seq)

        event["origin_instance_id"] = self._instance_id

        # Serialize and append to store (durable or in-memory)
        serialized = json.dumps(event, default=str)
        # enforce payload size
        try:
            size = len(serialized.encode("utf-8"))
            if size > settings.MAX_EVENT_PAYLOAD_BYTES:
                self.metrics_oversized_payloads.inc()
                logger.warning("Rejecting oversized event payload (%d bytes)", size)
                return None
        except Exception:
            pass
        start = time.time()
        stream_id = None
        try:
            stream_id = await self._store.append(serialized)
            # if append returned None and redis expected, mark failure
            if settings.REDIS_STREAMS_ENABLED and stream_id is None:
                self.metrics_stream_write_failures.inc()
        except Exception:
            self.metrics_stream_write_failures.inc()
            logger.exception("Store append failed")

        # create envelope for fanout with stream_offset
        envelope = dict(event)
        envelope["stream_offset"] = stream_id
        payload = json.dumps(envelope, default=str)

        # publish to pubsub (best-effort)
        if settings.REDIS_PUBSUB_ENABLED and self._redis and not self._degraded_mode:
            try:
                asyncio.create_task(self._redis.publish(settings.BROADCASTER_CHANNEL, payload))
            except Exception:
                logger.exception("Failed to publish to Redis pubsub, continuing with local fanout")

        # Fanout locally
        await self._fanout_raw(payload)
        elapsed = time.time() - start
        self.metrics_publish_latency.observe(elapsed)
        self.metrics_event_count.labels(event.get("event_type", "unknown")).inc()
        # update failover gauge
        self.metrics_redis_failover.set(1 if self._degraded_mode else 0)
        return stream_id

    async def _heartbeat_loop(self):
        interval = settings.BROADCASTER_HEARTBEAT_INTERVAL_SECONDS or 15
        while True:
            try:
                await self.publish({"event_type": "heartbeat", "severity": "info", "payload": {}})
                await asyncio.sleep(interval)
                # prune stale subscribers
                await self._prune_inactive()
            except Exception:
                await asyncio.sleep(interval)

    async def _prune_inactive(self):
        cutoff = time.time() - (settings.BROADCASTER_HEARTBEAT_INTERVAL_SECONDS * 4)
        async with self._lock:
            removed = [s for s in self._subscribers if s.last_active < cutoff]
            for s in removed:
                try:
                    self._subscribers.discard(s)
                except Exception:
                    pass
            if removed:
                self.metrics_active.set(len(self._subscribers))


# Single global broadcaster instance
broadcaster = Broadcaster()
