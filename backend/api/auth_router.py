from typing import Any, Dict

from fastapi import APIRouter, Depends

try:
    from backend.core.authorization import require_permission
    from backend.domain.authz import Permission
    from backend.schemas.auth import DeviceSessionResponse, DeviceSessionUpsertRequest
    from backend.services.device_session_service import device_session_service
except ModuleNotFoundError:
    from core.authorization import require_permission
    from domain.authz import Permission
    from schemas.auth import DeviceSessionResponse, DeviceSessionUpsertRequest
    from services.device_session_service import device_session_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/device-sessions", response_model=DeviceSessionResponse)
async def list_device_sessions(
    user: Dict[str, Any] = Depends(require_permission(Permission.DEVICE_SESSION_MANAGE)),
):
    return {"sessions": device_session_service.list_for_user(user.get("uid", "unknown"))}


@router.post("/device-sessions")
async def upsert_device_session(
    request: DeviceSessionUpsertRequest,
    user: Dict[str, Any] = Depends(require_permission(Permission.DEVICE_SESSION_MANAGE)),
):
    org_id = user.get("claims", {}).get("org_id") or user.get("org_id") or "personal"
    device_session_service.upsert(user.get("uid", "unknown"), org_id, request.model_dump())
    return {"status": "registered"}


@router.post("/device-sessions/{session_id}/revoke")
async def revoke_device_session(
    session_id: str,
    user: Dict[str, Any] = Depends(require_permission(Permission.DEVICE_SESSION_MANAGE)),
):
    device_session_service.revoke(session_id, user.get("uid", "unknown"))
    return {"status": "revoked"}
