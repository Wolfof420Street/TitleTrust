from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

try:
    from backend.core.authorization import require_permission
    from backend.domain.authz import Permission
    from backend.schemas.auth import DeviceSessionResponse, DeviceSessionUpsertRequest
    from backend.security.request_signing import is_fresh_timestamp, verify_request_signature
    from backend.services.device_session_service import device_session_service
except ModuleNotFoundError:
    from core.authorization import require_permission
    from domain.authz import Permission
    from schemas.auth import DeviceSessionResponse, DeviceSessionUpsertRequest
    from security.request_signing import is_fresh_timestamp, verify_request_signature
    from services.device_session_service import device_session_service

router = APIRouter(prefix="/auth", tags=["Auth"])


async def _verify_signed_request(
    request: Request,
    *,
    secret: str | None,
    device_session_id: str | None,
    signature: str | None,
    timestamp: str | None,
    correlation_id: str | None,
    user_id: str,
) -> None:
    if not secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing device request secret")
    if not device_session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing device session identifier")
    if not signature or not timestamp or not correlation_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing request signing headers")
    if not is_fresh_timestamp(timestamp):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired request signature")

    body = getattr(request.state, "_cached_json_body", None)
    if body is None:
        raw_body = await request.body()
        body = None if not raw_body else await request.json()
        request.state._cached_json_body = body

    if not verify_request_signature(
        secret=secret,
        method=request.method,
        path=request.url.path,
        timestamp=timestamp,
        correlation_id=correlation_id,
        body=body,
        signature=signature,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid request signature")

    request.state.device_session_id = device_session_id
    request.state.request_signing_user_id = user_id


async def _require_registered_device_signature(
    request: Request,
    user: Dict[str, Any],
    device_session_id: str | None,
    signature: str | None,
    timestamp: str | None,
    correlation_id: str | None,
) -> None:
    if not device_session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing device session identifier")

    session = device_session_service.get(device_session_id)
    if not session or session.get("revoked"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown or revoked device session")
    if session.get("user_id") != user.get("uid", "unknown"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device session does not belong to user")

    secrets = device_session_service.get_request_signing_secrets(device_session_id)
    for secret in secrets:
        try:
            await _verify_signed_request(
                request,
                secret=secret,
                device_session_id=device_session_id,
                signature=signature,
                timestamp=timestamp,
                correlation_id=correlation_id,
                user_id=user.get("uid", "unknown"),
            )
            return
        except HTTPException as exc:
            if exc.status_code != status.HTTP_401_UNAUTHORIZED:
                raise
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid request signature")


@router.get("/device-sessions", response_model=DeviceSessionResponse)
async def list_device_sessions(
    request: Request,
    x_device_session_id: str | None = Header(default=None, alias="X-Device-Session-ID"),
    x_request_signature: str | None = Header(default=None, alias="X-Request-Signature"),
    x_request_timestamp: str | None = Header(default=None, alias="X-Request-Timestamp"),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    user: Dict[str, Any] = Depends(require_permission(Permission.DEVICE_SESSION_MANAGE)),
):
    await _require_registered_device_signature(
        request,
        user,
        x_device_session_id,
        x_request_signature,
        x_request_timestamp,
        x_correlation_id,
    )
    return {"sessions": device_session_service.list_for_user(user.get("uid", "unknown"))}


@router.post("/device-sessions")
async def upsert_device_session(
    http_request: Request,
    payload: DeviceSessionUpsertRequest,
    x_request_signature: str | None = Header(default=None, alias="X-Request-Signature"),
    x_request_timestamp: str | None = Header(default=None, alias="X-Request-Timestamp"),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    user: Dict[str, Any] = Depends(require_permission(Permission.DEVICE_SESSION_MANAGE)),
):
    http_request.state._cached_json_body = payload.model_dump()
    await _verify_signed_request(
        http_request,
        secret=payload.request_secret,
        device_session_id=payload.session_id,
        signature=x_request_signature,
        timestamp=x_request_timestamp,
        correlation_id=x_correlation_id,
        user_id=user.get("uid", "unknown"),
    )
    claims = user.get("claims", {}) if isinstance(user, dict) else {}
    org_id = claims.get("org_id") or user.get("org_id")
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing organization context")
    device_session_service.upsert(
        user_id=user.get("uid", "unknown"),
        organization_id=org_id,
        payload=payload.model_dump(),
    )
    return {"status": "registered"}


@router.post("/device-sessions/{session_id}/revoke")
async def revoke_device_session(
    request: Request,
    session_id: str,
    x_device_session_id: str | None = Header(default=None, alias="X-Device-Session-ID"),
    x_request_signature: str | None = Header(default=None, alias="X-Request-Signature"),
    x_request_timestamp: str | None = Header(default=None, alias="X-Request-Timestamp"),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    user: Dict[str, Any] = Depends(require_permission(Permission.DEVICE_SESSION_MANAGE)),
):
    await _require_registered_device_signature(
        request,
        user,
        x_device_session_id,
        x_request_signature,
        x_request_timestamp,
        x_correlation_id,
    )
    if session_id != x_device_session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session mismatch")
    device_session_service.revoke(session_id, user.get("uid", "unknown"))
    return {"status": "revoked"}
