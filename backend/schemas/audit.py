from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StartAuditResponse(BaseModel):
    session_id: str
    status: str
    message: str


class SessionStatusResponse(BaseModel):
    session_id: str
    status: Optional[str] = None
    progress: Dict[str, Any] = Field(default_factory=dict)
    total_steps: int = 0
    last_thought: Optional[str] = None
    error: Optional[str] = None
    findings: List[Any] = Field(default_factory=list)
    audit_conclusion: Optional[str] = None


class RetryAuditResponse(BaseModel):
    session_id: str
    status: str
    message: str
