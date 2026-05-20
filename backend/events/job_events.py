from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class JobEvent:
    job_id: str
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
