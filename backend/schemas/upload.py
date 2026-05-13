from __future__ import annotations

from typing import Dict, Literal

from pydantic import BaseModel, Field


class SignedUploadRequest(BaseModel):
    filename: str = Field(..., min_length=1)
    content_type: str | None = None
    purpose: str = Field(default="marathon-start", min_length=1)


class SignedUploadResponse(BaseModel):
    upload_url: str
    object_path: str
    method: Literal["PUT"]
    headers: Dict[str, str]
    expires_in_seconds: int


class StartAuditFromStorageRequest(BaseModel):
    object_path: str = Field(..., min_length=1)
    original_filename: str = Field(..., min_length=1)
