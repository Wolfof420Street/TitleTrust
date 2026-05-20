from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

try:
    from backend.core.authorization import require_permission
    from backend.domain.authz import Permission
    from backend.schemas.upload import SignedUploadRequest, SignedUploadResponse
    from backend.services.cloud_storage_service import cloud_storage_service
except ModuleNotFoundError:
    from core.authorization import require_permission
    from domain.authz import Permission
    from schemas.upload import SignedUploadRequest, SignedUploadResponse
    from services.cloud_storage_service import cloud_storage_service

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post("/signed-url", response_model=SignedUploadResponse)
async def create_signed_upload_url(
    payload: SignedUploadRequest,
    user: Dict[str, Any] = Depends(require_permission(Permission.AUDIT_START)),
):
    if not isinstance(user, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication context")
    user_id = user.get("uid")
    claims = user.get("claims", {}) if isinstance(user, dict) else {}
    organization_id = claims.get("org_id") or user.get("org_id")
    if not user_id or not organization_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authenticated identity context")
    try:
        return cloud_storage_service.create_signed_upload(
            filename=payload.filename,
            content_type=payload.content_type,
            user_id=user_id,
            organization_id=organization_id,
            purpose=payload.purpose,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
