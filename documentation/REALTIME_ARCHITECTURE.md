**TitleTrust Realtime Architecture**

Overview
--------
This document describes the realtime event system currently implemented in TitleTrust. The design uses the existing SSE endpoint, in-process broadcaster, optional Redis Pub/Sub fanout, and Redis Streams durable replay without replacing the current backend and Flutter client abstractions.

Goals
-----
- Provide live agent cognition streaming (thoughts, tool choices, evidence registration)
- Preserve existing API contract at `/realtime/sse`
- Support multi-instance fanout via Redis Pub/Sub (optional)
- Support durable replay via Redis Streams (optional)
- Maintain graceful local-only operation when Redis is unavailable
- Ensure telemetry, traceability, and observability

High-level diagram (ASCII)

Client (Flutter) -> FastAPI `/realtime/sse` SSE
                      │
                      ▼
                Broadcaster (in-process)
                  /            \
                 /              \-- Redis Pub/Sub (optional)
                /                        \
          Worker Runtime                 Other instances
          Marathon Loop
          Forensic / Geo Agents

Key Components
--------------
- Broadcaster (`backend/realtime/broadcaster.py`):
  - Bounded per-subscriber asyncio queues
  - In-memory replay buffer (bounded)
  - Optional Redis Pub/Sub fanout (controlled by `REDIS_PUBSUB_ENABLED`)
  - Optional Redis Streams persistence when `REDIS_STREAMS_ENABLED` is enabled
  - Heartbeat and stale-subscriber pruning
  - Prometheus metrics: active subscribers, dropped events, publish latency, replay hits/misses, Redis reconnects

- Event Emitter (`backend/realtime/events.py`):
  - Produces structured envelopes: `event_type`, `timestamp`, `trace_id`, `correlation_id`, `session_id`, `job_id`, `payload`
  - Integrates with OpenTelemetry to attach span trace ids
  - Sanitizes payloads via `backend/realtime/redact.py`

- Integration points:
  - Worker runtime: job lifecycle events and retries
  - Marathon loop: agent thoughts, evidence registrations
  - Forensic / Geospatial engines: agent started/completed and structured evidence events
  - Dead-letter queue: `job.dead_lettered`
  - Adaptive protection and rate-limit: security events

Why SSE (over WebSockets)
-------------------------
- Simpler server model for fanout (HTTP-friendly)
- Works well with mobile platforms and HTTP infrastructure (load balancers, proxies)
- Easier to scale horizontally when backed by Redis Pub/Sub
- Preserves the existing API contract and client implementation
- Matches the Flutter client, which reconnects with `Last-Event-ID`

Ordering and consistency
------------------------
- Per-instance: events are published locally immediately and appended to a small replay buffer. Order is preserved per-instance.
- Cross-instance: Redis Pub/Sub delivers messages to subscribers in at-least-once order; ordering across instances is not strictly guaranteed.
- Durable replay: when Redis Streams is enabled, the broadcaster and `/realtime/last-state/{session_id}` can recover recent state from the durable stream.
- Clients should rely on `event_id`, `sequence_id`, and `timestamp` for deduplication and ordering.

Failure modes
-------------
- Redis unavailable: broadcaster falls back to pure in-process fanout. Events are not shared across instances but local UX remains functional.
- Slow subscribers: bounded queues drop events when full; dropped events increment a Prometheus counter. UI should show possible gaps and request re-sync via HTTP if necessary.
- Process restart: replay buffer is in-memory and lost; clients reconnect and request latest state via `/realtime/last-state/{session_id}`.
- Redis Streams enabled: recent events can be replayed from durable stream storage.

Operational guidance
--------------------
- For multi-instance, enable `REDIS_PUBSUB_ENABLED` and ensure `REDIS_URL` points to a resilient Redis cluster.
- Tune `BROADCASTER_REPLAY_BUFFER` to a size that balances memory and required replay window (default 256 events).
- Monitor `titletrust_realtime_dropped_events_total` to detect backpressure.
- Enable `REDIS_STREAMS_ENABLED` if you require stronger ordering, persistence, and replay guarantees.

Security & Privacy
------------------
- Payloads streamed are sanitized and truncated to avoid leaking secrets or long raw prompts.
- Sensitive fields (api_key, token, secret, authorization) are redacted by default.
- Do not stream raw model prompts, API keys, or internal tokens.

Frontend integration notes
-------------------------
- Reuse existing auth and device-session headers when opening the SSE connection.
- Use `Last-Event-ID` handling and local deduplication based on `event_id`.
- Implement exponential backoff reconnect with jitter and resume using a last-event-id.
- See the actual client implementation in [frontend/titletrust/lib/realtime/realtime_service.dart](frontend/titletrust/lib/realtime/realtime_service.dart) and [frontend/titletrust/lib/realtime/realtime_controller.dart](frontend/titletrust/lib/realtime/realtime_controller.dart).

Next steps and improvements
--------------------------
- Add a dedicated realtime ingress service for high fanout scenarios.
- Expand replay windows and gap healing for longer offline periods.
