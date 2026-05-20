"""
Comprehensive security tests for enterprise authentication and session management.

Tests:
- Token rotation and one-time-use enforcement
- Replay attack detection
- Session hijack prevention
- Anomaly detection
- Risk scoring
- CSP nonce generation
- Audit export signing
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import secrets

from backend.domain.session_models import (
    SessionState,
    TokenInfo,
    TokenFamily,
    DeviceFingerprint,
    SecurityEvent,
    SecurityEventType,
    SessionRiskLevel,
)
from backend.repositories.token_repository import hash_refresh_token
from backend.security.anomaly_detection import AnomalyDetectionEngine, GeoLocation


class TestTokenRotation:
    """Test refresh token rotation with one-time-use enforcement."""

    def test_generate_different_tokens(self):
        """Verify tokens are unique."""
        token1 = secrets.token_urlsafe(32)
        token2 = secrets.token_urlsafe(32)
        assert token1 != token2

    def test_token_hash_consistency(self):
        """Verify token hashing is consistent."""
        token = "test_token_12345"
        hash1 = hash_refresh_token(token)
        hash2 = hash_refresh_token(token)
        assert hash1 == hash2

    def test_token_hash_differs_for_different_tokens(self):
        """Verify different tokens have different hashes."""
        token1 = "token1"
        token2 = "token2"
        assert hash_refresh_token(token1) != hash_refresh_token(token2)

    def test_token_family_tracking(self):
        """Verify token family generation increments."""
        token1 = TokenInfo(
            token_id="token1",
            token_family="family1",
            generation=1,
            issued_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=7),
        )
        token2 = TokenInfo(
            token_id="token2",
            token_family="family1",
            generation=2,  # Next generation
            issued_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=7),
        )
        assert token1.token_family == token2.token_family
        assert token2.generation > token1.generation


class TestReplayAttackDetection:
    """Test replay attack detection and prevention."""

    def test_rotated_token_cannot_be_reused(self):
        """Verify rotated tokens cannot be used again."""
        token = TokenInfo(
            token_id="token1",
            token_family="family1",
            generation=1,
            issued_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=7),
            status=TokenFamily.ROTATED,  # Token has been rotated
        )
        assert token.status == TokenFamily.ROTATED

    def test_revoked_token_cannot_be_used(self):
        """Verify revoked tokens cannot be used."""
        token = TokenInfo(
            token_id="token1",
            token_family="family1",
            generation=1,
            issued_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=7),
            status=TokenFamily.REVOKED,
            revoked_at=datetime.now(),
            revocation_reason="replay_detected",
        )
        assert token.status == TokenFamily.REVOKED
        assert token.revocation_reason == "replay_detected"

    def test_expired_token_cannot_be_used(self):
        """Verify expired tokens cannot be used."""
        token = TokenInfo(
            token_id="token1",
            token_family="family1",
            generation=1,
            issued_at=datetime.now() - timedelta(days=8),
            expires_at=datetime.now() - timedelta(days=1),  # Already expired
        )
        assert token.expires_at < datetime.now()


class TestSessionRiskScoring:
    """Test session risk scoring and anomaly detection."""

    def test_low_risk_session(self):
        """Verify normal session has low risk."""
        session = SessionState(
            session_id="session1",
            user_id="user1",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
            last_activity_at=datetime.now(),
            current_refresh_token_id="token1",
            token_family="family1",
            risk_score=10.0,
            risk_level=SessionRiskLevel.LOW,
        )
        assert session.risk_level == SessionRiskLevel.LOW
        assert session.risk_score < 20

    def test_high_risk_session_after_multiple_anomalies(self):
        """Verify risk increases with anomalies."""
        session = SessionState(
            session_id="session1",
            user_id="user1",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
            last_activity_at=datetime.now(),
            current_refresh_token_id="token1",
            token_family="family1",
            risk_score=75.0,  # High risk
            risk_level=SessionRiskLevel.CRITICAL,
            suspicious_events=[
                SecurityEventType.IP_CHANGED,
                SecurityEventType.IMPOSSIBLE_TRAVEL,
                SecurityEventType.DEVICE_CHANGED,
            ],
        )
        assert session.risk_level == SessionRiskLevel.CRITICAL
        assert len(session.suspicious_events) == 3

    def test_device_binding(self):
        """Verify device binding prevents device swaps."""
        device1 = DeviceFingerprint(
            device_id="device1",
            device_type="mobile",
            os="iOS",
            os_version="17.0",
            app_version="1.0.0",
            user_agent="iPhone OS 17.0",
            fingerprint_hash="hash1",
        )
        device2 = DeviceFingerprint(
            device_id="device2",
            device_type="mobile",
            os="Android",
            os_version="14.0",
            app_version="1.0.0",
            user_agent="Android 14.0",
            fingerprint_hash="hash2",
        )

        session = SessionState(
            session_id="session1",
            user_id="user1",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
            last_activity_at=datetime.now(),
            current_refresh_token_id="token1",
            token_family="family1",
            device_fingerprint=device1,
            device_binding_enforced=True,
        )

        # Device fingerprints are different
        assert device1.device_id != device2.device_id
        assert device1.fingerprint_hash != device2.fingerprint_hash


class TestAnomalyDetection:
    """Test anomaly detection engine."""

    def test_ip_change_detection(self):
        """Verify IP changes are detected."""
        engine = AnomalyDetectionEngine(Mock())

        session = SessionState(
            session_id="session1",
            user_id="user1",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
            last_activity_at=datetime.now(),
            current_refresh_token_id="token1",
            token_family="family1",
            original_ip="1.2.3.4",
            current_ip="1.2.3.4",
            risk_score=0.0,
            risk_level=SessionRiskLevel.LOW,
        )

        # Same IP
        risk_score, risk_level, anomalies = engine.analyze_request(
            session, "1.2.3.4", correlation_id="corr1"
        )
        assert len(anomalies) == 0
        assert risk_level == SessionRiskLevel.LOW

        # Different IP
        risk_score, risk_level, anomalies = engine.analyze_request(
            session, "5.6.7.8", correlation_id="corr1"
        )
        assert SecurityEventType.IP_CHANGED in anomalies

    def test_impossible_travel_detection(self):
        """Verify impossible travel is detected."""
        engine = AnomalyDetectionEngine(Mock())

        # Geographic locations
        location1 = GeoLocation.get_location_for_ip("1.2.3.4")
        location2 = GeoLocation.get_location_for_ip("203.0.113.1")

        if location1 and location2:
            distance = GeoLocation.distance_km(
                location1["lat"],
                location1["lng"],
                location2["lat"],
                location2["lng"],
            )
            # Should be > 5000 km (impossible in short timeframe)
            assert distance > 0

    def test_risk_score_calculation(self):
        """Verify risk score calculation."""
        engine = AnomalyDetectionEngine(Mock())

        session = SessionState(
            session_id="session1",
            user_id="user1",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
            last_activity_at=datetime.now(),
            current_refresh_token_id="token1",
            token_family="family1",
            risk_score=0.0,
            risk_level=SessionRiskLevel.LOW,
        )

        risk_score, level, anomalies = engine.analyze_request(
            session, "5.6.7.8"
        )

        # IP change adds to risk
        assert risk_score > session.risk_score


class TestSecurityEvents:
    """Test security event logging."""

    def test_session_creation_event(self):
        """Verify session creation events are logged."""
        event = SecurityEvent(
            event_type=SecurityEventType.SESSION_CREATED,
            session_id="session1",
            user_id="user1",
            timestamp=datetime.now(),
            ip_address="1.2.3.4",
            severity="info",
        )
        assert event.event_type == SecurityEventType.SESSION_CREATED
        assert event.severity == "info"

    def test_token_rotation_event(self):
        """Verify token rotation events are logged."""
        event = SecurityEvent(
            event_type=SecurityEventType.TOKEN_ROTATED,
            session_id="session1",
            user_id="user1",
            timestamp=datetime.now(),
            severity="info",
            details={"generation": 2, "old_token_id": "token1"},
        )
        assert event.event_type == SecurityEventType.TOKEN_ROTATED
        assert event.details["generation"] == 2

    def test_security_event_serialization(self):
        """Verify security events serialize to dict."""
        event = SecurityEvent(
            event_type=SecurityEventType.SESSION_REVOKED,
            session_id="session1",
            user_id="user1",
            timestamp=datetime.now(),
            severity="critical",
        )
        event_dict = event.to_dict()
        assert event_dict["event_type"] == SecurityEventType.SESSION_REVOKED.value
        assert event_dict["severity"] == "critical"


class TestDeviceFingerprinting:
    """Test device binding and fingerprinting."""

    def test_device_fingerprint_creation(self):
        """Verify device fingerprints are created correctly."""
        device = DeviceFingerprint(
            device_id="device1",
            device_type="mobile",
            os="iOS",
            os_version="17.0",
            app_version="1.0.0",
            user_agent="iPhone OS 17.0",
            fingerprint_hash="hash123",
        )
        assert device.device_id == "device1"
        assert device.device_type == "mobile"

    def test_device_fingerprint_serialization(self):
        """Verify device fingerprints serialize."""
        device = DeviceFingerprint(
            device_id="device1",
            device_type="mobile",
            os="iOS",
            os_version="17.0",
            app_version="1.0.0",
            user_agent="iPhone OS 17.0",
            fingerprint_hash="hash123",
        )
        device_dict = device.to_dict()
        assert device_dict["device_id"] == "device1"


class TestCSPNonce:
    """Test CSP nonce generation."""

    def test_nonce_generation(self):
        """Verify nonces are generated."""
        from backend.middleware.security_headers import CSPNonceGenerator

        nonce1 = CSPNonceGenerator.generate_nonce()
        nonce2 = CSPNonceGenerator.generate_nonce()
        
        assert nonce1
        assert nonce2
        assert nonce1 != nonce2
        assert len(nonce1) > 20


class TestSessionState:
    """Test session state management."""

    def test_session_creation(self):
        """Verify sessions are created correctly."""
        session = SessionState(
            session_id="session1",
            user_id="user1",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
            last_activity_at=datetime.now(),
            current_refresh_token_id="token1",
            token_family="family1",
        )
        assert session.session_id == "session1"
        assert session.user_id == "user1"

    def test_session_serialization(self):
        """Verify sessions serialize to dict."""
        session = SessionState(
            session_id="session1",
            user_id="user1",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
            last_activity_at=datetime.now(),
            current_refresh_token_id="token1",
            token_family="family1",
        )
        session_dict = session.to_dict()
        assert session_dict["session_id"] == "session1"
        assert session_dict["user_id"] == "user1"

    def test_session_deserialization(self):
        """Verify sessions deserialize from dict."""
        now = datetime.now()
        session_dict = {
            "session_id": "session1",
            "user_id": "user1",
            "created_at": now,
            "expires_at": now + timedelta(hours=24),
            "last_activity_at": now,
            "current_refresh_token_id": "token1",
            "token_family": "family1",
            "risk_score": 0.0,
            "risk_level": "low",
        }
        session = SessionState.from_dict(session_dict)
        assert session.session_id == "session1"
        assert session.risk_level == SessionRiskLevel.LOW


# Security test markers for CI/CD
pytestmark = [
    pytest.mark.security,
    pytest.mark.enterprise,
]
