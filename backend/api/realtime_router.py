import asyncio
import json
import logging
import time

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse

from backend.realtime.broadcaster import broadcaster
from backend.services.firebase import db
from backend.repositories.session_repository import SessionRepository
from backend.repositories.job_repository import JobRepository
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/realtime", tags=["realtime"])


@router.get("/sse")
async def sse_endpoint(request: Request):
    """Server-Sent Events endpoint that streams broadcaster events.

    Clients should connect and listen for `data: ...` messages.
    """

    async def event_generator():
        last_event_id = request.headers.get("Last-Event-ID") or request.headers.get("Last-Event-Id")
        q = await broadcaster.register(last_event_id=last_event_id)
        try:
            while True:
                # If client disconnected, stop
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    retry_hint = 3000
                    yield f":retry: {retry_hint}\n"
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # send a heartbeat comment to keep connection alive
                    yield "\n"
                    continue
        finally:
            await broadcaster.unregister(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/last-state/{session_id}")
async def last_state(session_id: str):
    """Return authoritative last known state for the given session.

    Merges session document, job status (if present), evidence snapshot, and last emitted event id.
    """
    try:
        sess_repo = SessionRepository(db)
        job_repo = JobRepository(db)

        session_doc = sess_repo.get(session_id) or {}
        job_id = session_doc.get("job_id") or session_doc.get("current_job_id")
        job_doc = job_repo.get(job_id) if job_id else None

        evidence = session_doc.get("verification_evidence") or {}

        # last event id: prefer Redis Streams if enabled
        last_event_id = None
        try:
            if settings.REDIS_STREAMS_ENABLED and broadcaster._redis:
                xr = await broadcaster._redis.xrevrange(settings.BROADCASTER_STREAM_KEY, count=1)
                if xr:
                    last_event_id = xr[0][0].decode() if isinstance(xr[0][0], bytes) else str(xr[0][0])
            else:
                # in-memory buffer
                if broadcaster._replay_buffer:
                    try:
                        obj = json.loads(broadcaster._replay_buffer[-1])
                        last_event_id = obj.get("event_id")
                    except Exception:
                        last_event_id = None
        except Exception:
            last_event_id = None

        return {
            "session": session_doc,
            "job": job_doc,
            "evidence": evidence,
            "last_event_id": last_event_id,
        }
    except Exception:
        logger.exception("Failed to fetch last-state", extra={"session_id": session_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health():
    """Realtime subsystem health summary."""
    try:
        redis_ok = False
        stream_len = None
        if broadcaster._redis:
            try:
                pong = await broadcaster._redis.ping()
                redis_ok = bool(pong)
                if settings.REDIS_STREAMS_ENABLED:
                    try:
                        stream_len = await broadcaster._redis.xlen(settings.BROADCASTER_STREAM_KEY)
                    except Exception:
                        stream_len = None
            except Exception:
                redis_ok = False

        return {
            "redis": redis_ok,
            "degraded_mode": broadcaster._degraded_mode,
            "active_subscribers": len(broadcaster._subscribers),
            "replay_buffer_size": len(broadcaster._replay_buffer),
            "stream_len": stream_len,
            "ts": time.time(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/subscribers")
async def debug_subscribers():
    async with broadcaster._lock:
        subs = []
        for s in list(broadcaster._subscribers):
            subs.append({"last_active": s.last_active, "queue_size": s.queue.qsize()})
    return {"count": len(subs), "subs": subs}


@router.get("/debug/streams")
async def debug_streams(count: int = 20):
    """Return recent stream entries for debugging (best-effort)."""
    if not broadcaster._redis or not settings.REDIS_STREAMS_ENABLED:
        return {"error": "redis streams not enabled"}
    try:
        entries = await broadcaster._redis.xrevrange(settings.BROADCASTER_STREAM_KEY, count=count)
        out = []
        for eid, fields in entries:
            data = fields.get(b"data") if isinstance(fields, dict) else fields.get("data")
            data_str = data.decode() if isinstance(data, bytes) else str(data)
            out.append({"id": eid.decode() if isinstance(eid, bytes) else str(eid), "data": data_str})
        return {"entries": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
