# TitleTrust Backend

This backend is a FastAPI application that powers the forensic, geospatial, and realtime verification workflow. The current code routes realtime through SSE and uses Firestore-backed session/job state plus optional Redis fanout for live updates.

## What it actually does

- Authenticates and rate limits API traffic in `backend/main.py`.
- Runs forensic and geospatial audit routes through `backend/api/audit_router.py`.
- Exposes realtime streaming and recovery endpoints through `backend/api/realtime_router.py`.
- Persists session/job/audit state in Firestore via the repository layer.
- Starts the realtime broadcaster at app startup and stops it at shutdown.

## Key runtime entry points

- Backend app: [backend/main.py](backend/main.py)
- Realtime routes: [backend/api/realtime_router.py](backend/api/realtime_router.py)
- Forensic engine: [backend/forensic_engine.py](backend/forensic_engine.py)
- Geospatial engine: [backend/geospatial_engine.py](backend/geospatial_engine.py)
- Marathon loop: [backend/agent/marathon_loop.py](backend/agent/marathon_loop.py)

## Real API surface

The current backend exposes, among other routes:

- `GET /realtime/sse`
- `GET /realtime/last-state/{session_id}`
- `GET /realtime/health`
- `GET /realtime/debug/subscribers`
- `GET /realtime/debug/streams`

The broader application also includes auth, upload, health, and audit routes wired in `backend/main.py`.

## Realtime behavior

- [backend/realtime/broadcaster.py](backend/realtime/broadcaster.py) fans out events locally and can optionally use Redis Pub/Sub and Redis Streams.
- [backend/realtime/events.py](backend/realtime/events.py) builds structured envelopes with `event_type`, `timestamp`, `trace_id`, `session_id`, `job_id`, and redacted payloads.
- [backend/realtime/store.py](backend/realtime/store.py) provides in-memory replay or Redis Streams replay.

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

## Documentation

- API reference: [documentation/API_REFERENCE.md](../documentation/API_REFERENCE.md)
- Architecture notes: [documentation/SYSTEM_ARCHITECTURE.md](../documentation/SYSTEM_ARCHITECTURE.md)
- Realtime architecture: [documentation/REALTIME_ARCHITECTURE.md](../documentation/REALTIME_ARCHITECTURE.md)
