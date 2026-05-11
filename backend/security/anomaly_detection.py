"""
Security anomaly detection and risk scoring engine.

Implements:
- IP anomaly detection (changes, impossible travel)
- Unusual device detection
- Token replay detection
- Brute-force heuristics
- Adaptive risk scoring
"""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import json

try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

from backend.domain.session_models import (
    SessionState,
    SessionRiskLevel,
    SecurityEvent,
    SecurityEventType,
)

logger = logging.getLogger("TitleTrust-AnomalyDetection")


class GeoLocation:
    """Approximate geolocation from IP for impossible travel detection."""
    
    # Simplified IP-to-location mapping (real system would use MaxMind GeoIP2)
    # In production, use proper GeoIP service
    _IP_LOCATIONS = {
        # US ISPs
        "1.2.3.": {"lat": 37.7749, "lng": -122.4194, "city": "San Francisco"},
        "8.8.8.": {"lat": 40.7128, "lng": -74.0060, "city": "New York"},
        # EU ISPs
        "2.3.4.": {"lat": 52.5200, "lng": 13.4050, "city": "Berlin"},
        "5.6.7.": {"lat": 48.8566, "lng": 2.3522, "city": "Paris"},
        # Asia ISPs
        "203.0.113.": {"lat": 35.6762, "lng": 139.6503, "city": "Tokyo"},
    }

    @staticmethod
    def get_location_for_ip(ip: str) -> Optional[Dict[str, Any]]:
        """Get approximate location for IP (simplified)."""
        for prefix, location in GeoLocation._IP_LOCATIONS.items():
            if ip.startswith(prefix):
                return location
        # Default to unknown
        return None

    @staticmethod
    def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate great-circle distance between coordinates in km."""
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
        c = 2 * asin(sqrt(a))
        r = 6371  # Earth radius in kilometers
        return c * r


class AnomalyDetectionEngine:
    """Detects security anomalies and scores session risk."""

    # Risk scoring thresholds
    MAX_RISK_SCORE = 100.0
    
    # Anomaly scores
    IP_CHANGE_SCORE = 15.0
    IMPOSSIBLE_TRAVEL_SCORE = 40.0
    DEVICE_CHANGED_SCORE = 25.0
    UNUSUAL_DEVICE_SCORE = 20.0
    TOKEN_REPLAY_SCORE = 50.0
    BRUTE_FORCE_ATTEMPT_SCORE = 30.0
    PRIVILEGE_ESCALATION_SCORE = 60.0

    # Risk level thresholds
    LOW_THRESHOLD = 20.0
    MEDIUM_THRESHOLD = 40.0
    HIGH_THRESHOLD = 70.0

    def __init__(self, db: Any):
        self.db = db
        self.sessions_collection = "sessions"
        self.security_events_collection = "security_events"

    def analyze_request(
        self,
        session: SessionState,
        ip_address: str,
        device_id: Optional[str] = None,
        correlation_id: str = "",
    ) -> Tuple[float, SessionRiskLevel, list]:
        """
        Analyze request for anomalies and compute risk score.

        Args:
            session: Current session state
            ip_address: Request IP address
            device_id: Device identifier
            correlation_id: Trace ID

        Returns:
            (risk_score, risk_level, detected_anomalies)
        """
        anomalies = []
        risk_delta = 0.0

        # Check IP address
        if session.current_ip != ip_address:
            anomalies.append(SecurityEventType.IP_CHANGED)
            risk_delta += self.IP_CHANGE_SCORE

            # Check for impossible travel
            if self._is_impossible_travel(session.current_ip, ip_address):
                anomalies.append(SecurityEventType.IMPOSSIBLE_TRAVEL)
                risk_delta += self.IMPOSSIBLE_TRAVEL_SCORE
                logger.error(
                    f"Impossible travel detected for session {session.session_id}: "
                    f"{session.current_ip} -> {ip_address}"
                )

        # Check device
        if device_id and session.device_fingerprint:
            if device_id != session.device_fingerprint.device_id:
                anomalies.append(SecurityEventType.DEVICE_CHANGED)
                risk_delta += self.DEVICE_CHANGED_SCORE

        # Check for unusual patterns
        if len(session.suspicious_events) > 3:
            anomalies.append(SecurityEventType.SUSPICIOUS_ACTIVITY)
            risk_delta += 10.0

        # Compute new risk level
        new_risk_score = min(
            self.MAX_RISK_SCORE,
            session.risk_score + risk_delta
        )
        new_risk_level = self._score_to_level(new_risk_score)

        # Log significant changes
        if new_risk_level != session.risk_level:
            logger.warning(
                f"Risk level changed for session {session.session_id}: "
                f"{session.risk_level.value} -> {new_risk_level.value} "
                f"(score: {session.risk_score:.1f} -> {new_risk_score:.1f})"
            )

        return new_risk_score, new_risk_level, anomalies

    def _is_impossible_travel(self, old_ip: str, new_ip: str) -> bool:
        """Detect impossible travel between two IPs."""
        old_location = GeoLocation.get_location_for_ip(old_ip)
        new_location = GeoLocation.get_location_for_ip(new_ip)

        if not old_location or not new_location:
            # Can't determine, assume possible
            return False

        distance_km = GeoLocation.distance_km(
            old_location["lat"],
            old_location["lng"],
            new_location["lat"],
            new_location["lng"],
        )

        # If distance > 2000 km in less than 1 hour, likely impossible
        # (assuming human travel speed max is ~1000 km/hour for planes)
        max_possible_distance = 1000.0  # km/hour
        if distance_km > max_possible_distance:
            return True

        return False

    def _score_to_level(self, score: float) -> SessionRiskLevel:
        """Convert risk score to risk level."""
        if score >= self.HIGH_THRESHOLD:
            return SessionRiskLevel.CRITICAL
        elif score >= self.MEDIUM_THRESHOLD:
            return SessionRiskLevel.HIGH
        elif score >= self.LOW_THRESHOLD:
            return SessionRiskLevel.MEDIUM
        else:
            return SessionRiskLevel.LOW

    def detect_token_replay(
        self,
        session_id: str,
        token_id: str,
        correlation_id: str = "",
    ) -> bool:
        """
        Detect if token is being replayed (used multiple times).

        Args:
            session_id: Session ID
            token_id: Token ID
            correlation_id: Trace ID

        Returns:
            True if replay detected
        """
        # Check recent token usage in audit logs
        try:
            recent_uses = (
                self.db.collection(self.security_events_collection)
                .where("session_id", "==", session_id)
                .where("event_type", "==", SecurityEventType.REFRESH_USED.value)
                .where("timestamp", ">", datetime.now() - timedelta(minutes=5))
                .stream()
            )

            uses = list(recent_uses)
            if len(uses) > 1:
                # Token used multiple times in short period
                logger.error(
                    f"Token replay detected: session {session_id}, "
                    f"token {token_id} used {len(uses)} times in 5 minutes"
                )
                return True

            return False

        except Exception as exc:
            logger.error(f"Failed to detect token replay: {exc}")
            return False

    def detect_brute_force(
        self,
        user_id: str,
        window_minutes: int = 15,
        threshold: int = 5,
    ) -> bool:
        """
        Detect brute force login attempts.

        Args:
            user_id: User to check
            window_minutes: Time window
            threshold: Failed attempts threshold

        Returns:
            True if brute force detected
        """
        try:
            failed_attempts = (
                self.db.collection(self.security_events_collection)
                .where("user_id", "==", user_id)
                .where("event_type", "==", SecurityEventType.SESSION_CREATED.value)
                .where("severity", "==", "error")
                .where(
                    "timestamp",
                    ">",
                    datetime.now() - timedelta(minutes=window_minutes),
                )
                .stream()
            )

            attempts = list(failed_attempts)
            if len(attempts) >= threshold:
                logger.warning(
                    f"Brute force detected: user {user_id}, "
                    f"{len(attempts)} failed attempts in {window_minutes} minutes"
                )
                return True

            return False

        except Exception as exc:
            logger.error(f"Failed to detect brute force: {exc}")
            return False

    def get_risk_summary(self, user_id: str) -> Dict[str, Any]:
        """Get risk summary for user across all sessions."""
        try:
            sessions = (
                self.db.collection(self.sessions_collection)
                .where("user_id", "==", user_id)
                .where("revoked", "==", False)
                .stream()
            )

            sessions_list = list(sessions)
            if not sessions_list:
                return {"user_id": user_id, "active_sessions": 0, "average_risk": 0.0}

            total_risk = sum(
                float(s.get("risk_score", 0))
                for s in [s.to_dict() for s in sessions_list]
            )
            avg_risk = total_risk / len(sessions_list)

            high_risk_count = sum(
                1
                for s in [s.to_dict() for s in sessions_list]
                if float(s.get("risk_score", 0)) >= self.HIGH_THRESHOLD
            )

            return {
                "user_id": user_id,
                "active_sessions": len(sessions_list),
                "average_risk": avg_risk,
                "high_risk_sessions": high_risk_count,
            }

        except Exception as exc:
            logger.error(f"Failed to get risk summary for user {user_id}: {exc}")
            return {}
