"""Threat intelligence helpers for adaptive abuse defense."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional


class ThreatSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ThreatIndicator:
    name: str
    severity: ThreatSeverity
    score: float
    description: str


@dataclass
class ThreatIntelSignal:
    fingerprint_id: str
    tenant_id: str
    device_id: str
    indicators: List[ThreatIndicator] = field(default_factory=list)
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    observation_count: int = 1

    def to_dict(self) -> Dict[str, object]:
        return {
            "fingerprint_id": self.fingerprint_id,
            "tenant_id": self.tenant_id,
            "device_id": self.device_id,
            "indicators": [indicator.__dict__ for indicator in self.indicators],
            "last_seen_at": self.last_seen_at.isoformat(),
            "observation_count": self.observation_count,
        }


class ThreatIntelligenceStore:
    """In-memory threat intelligence store with TTL semantics."""

    def __init__(self, signal_ttl_minutes: int = 60) -> None:
        self._signal_ttl = timedelta(minutes=signal_ttl_minutes)
        self._signals: Dict[str, ThreatIntelSignal] = {}

    def record_signal(self, signal: ThreatIntelSignal) -> None:
        self._signals[signal.fingerprint_id] = signal

    def lookup(self, fingerprint_id: str) -> Optional[ThreatIntelSignal]:
        signal = self._signals.get(fingerprint_id)
        if signal is None:
            return None
        if datetime.now(timezone.utc) - signal.last_seen_at > self._signal_ttl:
            self._signals.pop(fingerprint_id, None)
            return None
        return signal

    def mark_indicator(
        self,
        *,
        fingerprint_id: str,
        tenant_id: str,
        device_id: str,
        indicator: ThreatIndicator,
    ) -> ThreatIntelSignal:
        signal = self.lookup(fingerprint_id)
        if signal is None:
            signal = ThreatIntelSignal(
                fingerprint_id=fingerprint_id,
                tenant_id=tenant_id,
                device_id=device_id,
                indicators=[indicator],
            )
        else:
            signal.indicators.append(indicator)
            signal.observation_count += 1
            signal.last_seen_at = datetime.now(timezone.utc)
        self.record_signal(signal)
        return signal

    def list_signals(self, tenant_id: Optional[str] = None) -> List[ThreatIntelSignal]:
        signals = list(self._signals.values())
        if tenant_id is not None:
            signals = [signal for signal in signals if signal.tenant_id == tenant_id]
        return signals
