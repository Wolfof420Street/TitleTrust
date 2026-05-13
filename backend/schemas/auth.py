from __future__ import annotations

from typing import List

from pydantic import BaseModel


class DeviceSessionUpsertRequest(BaseModel):
    session_id: str
    device_id: str
    platform: str
    app_version: str
    request_secret: str


class DeviceSessionResponse(BaseModel):
    sessions: List[dict]
