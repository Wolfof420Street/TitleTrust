from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest

try:
    from backend.services.firebase import db
except ModuleNotFoundError:
    from services.firebase import db

router = APIRouter(tags=["Health"])


@router.get("/")
def health_check():
    return {"status": "ok", "service": "titletrust-backend"}


@router.get("/health/live")
def liveness_check():
    return {"status": "alive"}


@router.get("/health/ready")
def readiness_check():
    try:
        db.collection("_health").limit(1).get()
        return {"status": "ready"}
    except Exception:
        return {"status": "degraded"}


@router.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return generate_latest().decode("utf-8")
