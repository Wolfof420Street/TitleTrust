Realtime Subsystem - Operations and Recovery

This document summarizes the production operations, failure modes, and client recovery contract for the TitleTrust realtime subsystem.

**Deployment Topology (Mermaid)**

```mermaid
flowchart LR
  subgraph AppInstances
    A[Instance A] ---|pubsub| RedisPubSub((Redis))
    B[Instance B] ---|pubsub| RedisPubSub
    A -->|sse| Clients
    B -->|sse| Clients
  end
  RedisPubSub -->|streams| RedisStreams[(Redis Streams)]
  RedisStreams -->|replay| A
  RedisStreams -->|replay| B
```

**Redis Streams replay flow**

```mermaid
sequenceDiagram
  participant Client
  participant Instance as App Instance
  participant Redis as Redis Streams

  Client->>Instance: connect SSE (Last-Event-ID)
  Instance->>Redis: XREVRANGE/XRANGE replay lookup
  Redis-->>Instance: events
  Instance-->>Client: replay events
  Instance->>Client: resume live events via SSE
```

**SSE reconnect sequence**

```mermaid
sequenceDiagram
  Client->>Server: connect (no Last-Event-ID)
  Server-->>Client: heartbeat / events
  Note over Client,Server: network blip
  Client->>Server: reconnect (Last-Event-ID=X)
  Server->>Redis: XRANGE (X, +)
  alt gaps detected
    Server->>Server: trigger last-state fetch + sequence healing
    Server-->>Client: send /realtime/last-state
  end
  Server-->>Client: replay and resume
```

**Sequence healing (conceptual)**

```mermaid
flowchart LR
  A[Instance] --> Redis[Redis Streams]
  Redis -- gap detected --> A
  A -->|fetch authoritative state| SessionStore[Firestore Session]
  A -->|emit recovery events| Redis
```

Frontend recovery contract

- On reconnect, client MUST include `Last-Event-ID` header.
- The server-side SSE router uses `broadcaster.register(last_event_id=...)` to replay recent entries from Redis Streams or the in-memory buffer.
- The client should fetch `/realtime/last-state/{session_id}` when a gap is detected, reconcile optimistic UI state, then resume the SSE stream.
- The client should dedupe events by `event_id` and maintain ordering by `sequence_id` per `session_id`.

Client reconnect flow (summary):
1. reconnect SSE with `Last-Event-ID`
2. if server signals gap or the controller sees missing sequence numbers → fetch `/realtime/last-state/{session_id}`
3. reconcile optimistic state (idempotent apply)
4. resume streaming and resume local playback

Operational checks exposed by `/realtime/health` and `/realtime/debug/*`:
- active subscribers
- replay buffer utilization
- Redis ping/stream length
- recent stream entries

Chaos scenarios to validate during SRE testing

- Redis restart mid-stream (expect degraded fallback and no crash)
- Worker crash during publish (expect replay on restart)
- Network partition between instances and Redis (expect degraded mode and eventual healing)

*** End File
