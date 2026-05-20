"""Adaptive abuse detection and throttling logic."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from datetime import timedelta
from threading import Lock
from typing import Deque, Dict, List, Optional

from backend.domain.session_models import SessionRiskLevel
from backend.security.anomaly_detection import AnomalyDetectionEngine

from .request_fingerprinting import RequestFingerprint, RequestFingerprinting
from .threat_intelligence import ThreatIndicator, ThreatIntelligenceStore, ThreatSeverity

logger = logging.getLogger("TitleTrust-AbuseDetection")


class AbuseAction(str, Enum):
    ALLOW = "allow"
    THROTTLE = "throttle"
    CHALLENGE = "challenge"
    QUARANTINE = "quarantine"
    BLOCK = "block"


@dataclass
class AbuseAssessment:
    action: AbuseAction
    score: float
    reasons: List[str] = field(default_factory=list)
    fingerprint: Optional[RequestFingerprint] = None
    retry_after_seconds: int = 0
    quarantine_minutes: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "action": self.action.value,
            "score": self.score,
            "reasons": list(self.reasons),
            "fingerprint": self.fingerprint.to_dict() if self.fingerprint else None,
            "retry_after_seconds": self.retry_after_seconds,
            "quarantine_minutes": self.quarantine_minutes,
        }


@dataclass
class AbuseObservation:
    fingerprint_id: str
    tenant_id: str
    device_id: str
    ip_address: str
    user_agent: str
    path: str
    correlation_id: str
    timestamp: datetime
    assessment: AbuseAssessment


class AbuseDetectionEngine:
    """Stateful abuse detection engine for adaptive throttling."""

    def __init__(
        self,
        anomaly_engine: AnomalyDetectionEngine,
        fingerprinting: Optional[RequestFingerprinting] = None,
        intelligence_store: Optional[ThreatIntelligenceStore] = None,
    ) -> None:
        self._anomaly_engine = anomaly_engine
        self._fingerprinting = fingerprinting or RequestFingerprinting()
        self._intel = intelligence_store or ThreatIntelligenceStore()
        self._lock = Lock()
        self._history: Dict[str, Deque[AbuseObservation]] = defaultdict(deque)
        self._quarantines: Dict[str, datetime] = {}

    def assess(
        self,
        *,
        tenant_id: str,
        device_id: str,
        ip_address: str,
        user_agent: str,
        method: str,
        path: str,
        correlation_id: str,
        headers: Optional[Dict[str, str]] = None,
        session=None,
    ) -> AbuseAssessment:
        fingerprint = self._fingerprinting.fingerprint(
            tenant_id=tenant_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
            method=method,
            path=path,
            headers=headers,
        )
        reasons: List[str] = []
        score = 0.0

        if fingerprint.entropy_score > 4.5:
            reasons.append("high_request_entropy")
            score += 10.0

        signal = self._intel.lookup(fingerprint.fingerprint_id)
        if signal:
            reasons.append("known_threat_fingerprint")
            score += 35.0 + min(15.0, signal.observation_count * 2.5)

        if self._is_quarantined(fingerprint.fingerprint_id):
            reasons.append("fingerprint_quarantined")
            score += 60.0

        observations = self._get_recent_observations(fingerprint.fingerprint_id)
        if len(observations) >= 8:
            reasons.append("request_cluster_detected")
            score += 20.0

        if self._is_velocity_anomalous(fingerprint.fingerprint_id, ip_address):
            reasons.append("velocity_anomaly")
            score += 20.0

        if session is not None:
            risk_score, risk_level, anomalies = self._anomaly_engine.analyze_request(
                session=session,
                ip_address=ip_address,
                device_id=device_id,
                correlation_id=correlation_id,
            )
            score += risk_score / 8.0
            if anomalies:
                reasons.extend(anomaly.value if hasattr(anomaly, "value") else str(anomaly) for anomaly in anomalies)
            if risk_level in (SessionRiskLevel.HIGH, SessionRiskLevel.CRITICAL):
                reasons.append(f"session_risk_{risk_level.value}")
                score += 20.0

        if self._looks_like_credential_stuffing(path, user_agent):
            reasons.append("credential_stuffing_pattern")
            score += 25.0

        assessment = self._classify(score, reasons, fingerprint)
        self._record_observation(fingerprint, assessment)
        logger.info(
            "abuse.assessment",
            extra={
                "tenant_id": tenant_id,
                "device_id": device_id,
                "ip_address": ip_address,
                "path": path,
                "correlation_id": correlation_id,
                "action": assessment.action.value,
                "score": assessment.score,
                "reasons": assessment.reasons,
            },
        )
        return assessment

    def quarantine_fingerprint(self, fingerprint_id: str, minutes: int = 15) -> None:
        with self._lock:
            self._quarantines[fingerprint_id] = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    def record_threat_indicator(self, assessment: AbuseAssessment, tenant_id: str, device_id: str) -> None:
        if assessment.fingerprint is None:
            return
        if assessment.action in {AbuseAction.CHALLENGE, AbuseAction.QUARANTINE, AbuseAction.BLOCK}:
            indicator = ThreatIndicator(
                name=assessment.action.value,
                severity=ThreatSeverity.HIGH if assessment.action != AbuseAction.BLOCK else ThreatSeverity.CRITICAL,
                score=assessment.score,
                description=",".join(assessment.reasons[:5]) or "abuse signal",
            )
            self._intel.mark_indicator(
                fingerprint_id=assessment.fingerprint.fingerprint_id,
                tenant_id=tenant_id,
                device_id=device_id,
                indicator=indicator,
            )

    def summarize(self, tenant_id: Optional[str] = None) -> Dict[str, object]:
        signals = self._intel.list_signals(tenant_id=tenant_id)
        with self._lock:
            quarantined = sum(1 for fingerprint_id in list(self._quarantines) if self._is_quarantined_locked(fingerprint_id))
        return {
            "tenant_id": tenant_id,
            "signals": len(signals),
            "quarantined_fingerprints": quarantined,
            "recent_observations": sum(len(obs) for obs in self._history.values()),
        }

    def _classify(self, score: float, reasons: List[str], fingerprint: RequestFingerprint) -> AbuseAssessment:
        if score >= 80:
            return AbuseAssessment(
                action=AbuseAction.BLOCK,
                score=round(score, 2),
                reasons=reasons,
                fingerprint=fingerprint,
                retry_after_seconds=900,
                quarantine_minutes=60,
            )
        if score >= 60:
            return AbuseAssessment(
                action=AbuseAction.QUARANTINE,
                score=round(score, 2),
                reasons=reasons,
                fingerprint=fingerprint,
                retry_after_seconds=300,
                quarantine_minutes=15,
            )
        if score >= 40:
            return AbuseAssessment(
                action=AbuseAction.CHALLENGE,
                score=round(score, 2),
                reasons=reasons,
                fingerprint=fingerprint,
                retry_after_seconds=60,
            )
        if score >= 20:
            return AbuseAssessment(
                action=AbuseAction.THROTTLE,
                score=round(score, 2),
                reasons=reasons,
                fingerprint=fingerprint,
                retry_after_seconds=15,
            )
        return AbuseAssessment(action=AbuseAction.ALLOW, score=round(score, 2), reasons=reasons, fingerprint=fingerprint)

    def _record_observation(self, fingerprint: RequestFingerprint, assessment: AbuseAssessment) -> None:
        observation = AbuseObservation(
            fingerprint_id=fingerprint.fingerprint_id,
            tenant_id=fingerprint.tenant_id,
            device_id=fingerprint.device_id,
            ip_address=fingerprint.ip_address,
            user_agent=fingerprint.user_agent,
            path=fingerprint.path,
            correlation_id=fingerprint.correlation_id,
            timestamp=datetime.now(timezone.utc),
            assessment=assessment,
        )
        with self._lock:
            observations = self._history[fingerprint.fingerprint_id]
            observations.append(observation)
            while len(observations) > 50:
                observations.popleft()

    def _get_recent_observations(self, fingerprint_id: str) -> Deque[AbuseObservation]:
        with self._lock:
            return self._history[fingerprint_id]

    def _is_quarantined(self, fingerprint_id: str) -> bool:
        with self._lock:
            return self._is_quarantined_locked(fingerprint_id)

    def _is_quarantined_locked(self, fingerprint_id: str) -> bool:
        expiry = self._quarantines.get(fingerprint_id)
        if not expiry:
            return False
        if expiry <= datetime.now(timezone.utc):
            self._quarantines.pop(fingerprint_id, None)
            return False
        return True

    def _is_velocity_anomalous(self, fingerprint_id: str, ip_address: str) -> bool:
        observations = list(self._get_recent_observations(fingerprint_id))
        if len(observations) < 4:
            return False
        unique_ips = {observation.ip_address for observation in observations[-4:]}
        return len(unique_ips) >= 3 and ip_address not in unique_ips

    @staticmethod
    def _looks_like_credential_stuffing(path: str, user_agent: str) -> bool:
        if "/auth/login" not in path and "/login" not in path:
            return False
        lowered = user_agent.lower()
        bot_signatures = ("curl", "wget", "python", "go-http-client", "bot", "scrapy")
        return any(signature in lowered for signature in bot_signatures)
