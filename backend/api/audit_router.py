from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile

try:
    from backend.core.authorization import require_permission
    from backend.domain.authz import Permission
    from backend.models import GeoCheck, LiveTokenRequest
    from backend.schemas.audit import RetryAuditResponse, SessionStatusResponse, StartAuditResponse
    from backend.schemas.jobs import JobAcceptedResponse, JobStatusResponse
    from backend.services.audit_service import audit_service
    from backend.services.background_job_service import background_job_service
    from backend.services.session_service import session_service
    from backend.services.titbits_service import titbits_service
except ModuleNotFoundError:
    from core.authorization import require_permission
    from domain.authz import Permission
    from models import GeoCheck, LiveTokenRequest
    from schemas.audit import RetryAuditResponse, SessionStatusResponse, StartAuditResponse
    from schemas.jobs import JobAcceptedResponse, JobStatusResponse
    from services.audit_service import audit_service
    from services.background_job_service import background_job_service
    from services.session_service import session_service
    from services.titbits_service import titbits_service

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.post("/forensic", response_model=JobAcceptedResponse)
async def forensic_audit(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    correlation_id: Optional[str] = Header(default=None, alias="X-Correlation-ID"),
    user: Dict[str, Any] = Depends(require_permission(Permission.FORENSIC_RUN)),
):
    claims = user.get("claims", {}) if isinstance(user, dict) else {}
    return background_job_service.enqueue_forensic(
        files=files,
        user_id=user.get("uid", "unknown"),
        organization_id=claims.get("org_id") or user.get("org_id") or "personal",
        background_tasks=background_tasks,
        correlation_id=correlation_id,
    )


@router.post("/geospatial", response_model=JobAcceptedResponse)
async def geospatial_audit(
    background_tasks: BackgroundTasks,
    lat: float = Form(..., ge=-90, le=90),
    lng: float = Form(..., ge=-180, le=180),
    file: UploadFile = File(...),
    correlation_id: Optional[str] = Header(default=None, alias="X-Correlation-ID"),
    user: Dict[str, Any] = Depends(require_permission(Permission.GEOSPATIAL_RUN)),
):
    claims = user.get("claims", {}) if isinstance(user, dict) else {}
    return background_job_service.enqueue_geospatial(
        lat=lat,
        lng=lng,
        file=file,
        user_id=user.get("uid", "unknown"),
        organization_id=claims.get("org_id") or user.get("org_id") or "personal",
        background_tasks=background_tasks,
        correlation_id=correlation_id,
    )


@router.post("/geospatial/live-token")
async def live_token(
    req: LiveTokenRequest,
    _: Dict[str, Any] = Depends(require_permission(Permission.GEOSPATIAL_RUN)),
):
    return await audit_service.generate_live_token(req)


@router.post("/start", response_model=StartAuditResponse)
async def start_audit(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: Dict[str, Any] = Depends(require_permission(Permission.AUDIT_START)),
):
    return session_service.start_marathon(
        file=file,
        user_id=user.get("uid", "unknown"),
        organization_id=user.get("claims", {}).get("org_id") or user.get("org_id") or "personal",
        background_tasks=background_tasks,
        idempotency_key=idempotency_key,
    )


@router.post("/tick")
async def marathon_tick(payload: Dict[str, str]):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    return session_service.tick(session_id)


@router.get("/status/{session_id}", response_model=SessionStatusResponse)
async def get_audit_status(
    session_id: str,
    user: Dict[str, Any] = Depends(require_permission(Permission.AUDIT_READ)),
):
    return session_service.get_status(session_id, user.get("uid", "unknown"))


@router.post("/retry/{session_id}", response_model=RetryAuditResponse)
async def retry_stuck_audit(
    session_id: str,
    user: Dict[str, Any] = Depends(require_permission(Permission.AUDIT_RETRY)),
):
    return session_service.retry(session_id, user.get("uid", "unknown"))


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    user: Dict[str, Any] = Depends(require_permission(Permission.AUDIT_READ)),
):
    job = background_job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") != user.get("uid"):
        raise HTTPException(status_code=403, detail="Access denied")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobAcceptedResponse)
async def cancel_job(
    job_id: str,
    user: Dict[str, Any] = Depends(require_permission(Permission.AUDIT_RETRY)),
):
    return background_job_service.cancel_job(job_id, user.get("uid", "unknown"))


@router.get("/titbits")
async def get_land_titbits(
    _: Dict[str, Any] = Depends(require_permission(Permission.TITBITS_READ)),
):
    return titbits_service.generate()
