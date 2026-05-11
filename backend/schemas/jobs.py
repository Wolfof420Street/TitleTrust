from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: str
    job_type: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    job_type: str
    attempts: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
