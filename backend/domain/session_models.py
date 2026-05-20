"""
Session security domain models for enterprise authentication.

Implements:
- Token rotation tracking
- Device-bound sessions  
- Session risk scoring
- Replay attack detection
- Security event classification
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid


class TokenFamily(str, Enum):
    """Token rotation family tracking for replay detection."""
    ACTIVE = "active"              # Current family
    ROTATED = "rotated"            # Replaced by rotation
    REVOKED = "revoked"            # Explicitly revoked
    EXPIRED = "expired"            # Time-expired


class SessionRiskLevel(str, Enum):
    """Session risk classification."""
    LOW = "low"                    # Normal operation
    MEDIUM = "medium"              # Minor anomalies
    HIGH = "high"                  # Significant anomalies
    CRITICAL = "critical"          # Requires immediate action


class SecurityEventType(str, Enum):
    """Classification of security events."""
    TOKEN_ISSUED = "token_issued"
    TOKEN_ROTATED = "token_rotated"
    TOKEN_REVOKED = "token_revoked"
    TOKEN_EXPIRED = "token_expired"
    REFRESH_USED = "refresh_used"
    REPLAY_DETECTED = "replay_detected"
    SESSION_CREATED = "session_created"
    SESSION_REFRESHED = "session_refreshed"
    SESSION_REVOKED = "session_revoked"
    DEVICE_CHANGED = "device_changed"
    IP_CHANGED = "ip_changed"
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    UNUSUAL_DEVICE = "unusual_device"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    STEP_UP_REQUIRED = "step_up_required"
    SESSION_TERMINATED = "session_terminated"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


@dataclass
class DeviceFingerprint:
    """Device identification for session binding."""
    device_id: str                          # Unique device identifier
    device_type: str                        # Mobile, desktop, tablet, etc.
    os: str                                 # iOS, Android, macOS, Linux, etc.
    os_version: str                         # OS version
    app_version: str                        # App/client version
    user_agent: str                         # Full user agent string
    fingerprint_hash: str                   # SHA-256 of fingerprint data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "os": self.os,
            "os_version": self.os_version,
            "app_version": self.app_version,
            "user_agent": self.user_agent,
            "fingerprint_hash": self.fingerprint_hash,
        }


@dataclass
class TokenInfo:
    """Refresh token information for rotation tracking."""
    token_id: str                           # Unique token ID
    token_family: str                       # Family for rotation tracking
    generation: int                         # Generation number in family
    issued_at: datetime                     # Creation timestamp
    expires_at: datetime                    # Expiration time
    last_used_at: Optional[datetime] = None # Last rotation timestamp
    used_count: int = 0                     # Number of times used
    status: TokenFamily = TokenFamily.ACTIVE
    ip_address: str = ""                    # IP when issued
    device_fingerprint: Optional[DeviceFingerprint] = None
    revoked_at: Optional[datetime] = None   # Revocation timestamp
    revocation_reason: str = ""             # Why was it revoked
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Firestore-compatible dict."""
        return {
            "token_id": self.token_id,
            "token_family": self.token_family,
            "generation": self.generation,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "used_count": self.used_count,
            "status": self.status.value,
            "ip_address": self.ip_address,
            "device_fingerprint": self.device_fingerprint.to_dict() if self.device_fingerprint else None,
            "revoked_at": self.revoked_at,
            "revocation_reason": self.revocation_reason,
        }


@dataclass
class SessionState:
    """Complete session state with security context."""
    session_id: str                         # Unique session ID
    user_id: str                            # User identifier
    created_at: datetime                    # Session creation
    expires_at: datetime                    # Session expiration
    last_activity_at: datetime              # Last request time
    
    # Token tracking
    current_refresh_token_id: str           # Current refresh token
    previous_refresh_tokens: List[str] = field(default_factory=list)  # Rotation history
    token_family: str = ""                  # Current family ID
    generation: int = 0                     # Current generation
    
    # Device binding
    device_fingerprint: Optional[DeviceFingerprint] = None
    device_binding_enforced: bool = True
    
    # IP tracking
    original_ip: str = ""                   # IP where session created
    current_ip: str = ""                    # Current request IP
    ip_changes: List[Dict[str, Any]] = field(default_factory=list)  # IP change history
    
    # Risk scoring
    risk_level: SessionRiskLevel = SessionRiskLevel.LOW
    risk_score: float = 0.0                 # 0-100
    last_risk_assessment_at: Optional[datetime] = None
    
    # Security state
    mfa_verified: bool = False              # MFA completed this session
    mfa_verified_at: Optional[datetime] = None
    step_up_required: bool = False          # Step-up auth needed
    concurrent_sessions_allowed: int = 5    # Max concurrent sessions
    
    # Activity tracking
    request_count: int = 0                  # Requests in this session
    suspicious_events: List[SecurityEventType] = field(default_factory=list)
    
    # Revocation tracking
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    revocation_reason: str = ""
    global_logout: bool = False             # Part of global logout
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Firestore document."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_activity_at": self.last_activity_at,
            "current_refresh_token_id": self.current_refresh_token_id,
            "previous_refresh_tokens": self.previous_refresh_tokens,
            "token_family": self.token_family,
            "generation": self.generation,
            "device_fingerprint": self.device_fingerprint.to_dict() if self.device_fingerprint else None,
            "device_binding_enforced": self.device_binding_enforced,
            "original_ip": self.original_ip,
            "current_ip": self.current_ip,
            "ip_changes": self.ip_changes,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "last_risk_assessment_at": self.last_risk_assessment_at,
            "mfa_verified": self.mfa_verified,
            "mfa_verified_at": self.mfa_verified_at,
            "step_up_required": self.step_up_required,
            "concurrent_sessions_allowed": self.concurrent_sessions_allowed,
            "request_count": self.request_count,
            "suspicious_events": [e.value for e in self.suspicious_events],
            "revoked": self.revoked,
            "revoked_at": self.revoked_at,
            "revocation_reason": self.revocation_reason,
            "global_logout": self.global_logout,
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SessionState":
        """Create from Firestore document."""
        device_fp_data = data.get("device_fingerprint")
        device_fp = None
        if device_fp_data:
            device_fp = DeviceFingerprint(**device_fp_data)
        
        return SessionState(
            session_id=data.get("session_id", ""),
            user_id=data.get("user_id", ""),
            created_at=data.get("created_at", datetime.now()),
            expires_at=data.get("expires_at", datetime.now() + timedelta(hours=24)),
            last_activity_at=data.get("last_activity_at", datetime.now()),
            current_refresh_token_id=data.get("current_refresh_token_id", ""),
            previous_refresh_tokens=data.get("previous_refresh_tokens", []),
            token_family=data.get("token_family", ""),
            generation=data.get("generation", 0),
            device_fingerprint=device_fp,
            device_binding_enforced=data.get("device_binding_enforced", True),
            original_ip=data.get("original_ip", ""),
            current_ip=data.get("current_ip", ""),
            ip_changes=data.get("ip_changes", []),
            risk_level=SessionRiskLevel(data.get("risk_level", "low")),
            risk_score=float(data.get("risk_score", 0.0)),
            last_risk_assessment_at=data.get("last_risk_assessment_at"),
            mfa_verified=data.get("mfa_verified", False),
            mfa_verified_at=data.get("mfa_verified_at"),
            step_up_required=data.get("step_up_required", False),
            concurrent_sessions_allowed=data.get("concurrent_sessions_allowed", 5),
            request_count=data.get("request_count", 0),
            suspicious_events=[
                SecurityEventType(e) for e in data.get("suspicious_events", [])
            ],
            revoked=data.get("revoked", False),
            revoked_at=data.get("revoked_at"),
            revocation_reason=data.get("revocation_reason", ""),
            global_logout=data.get("global_logout", False),
        )


@dataclass
class SecurityEvent:
    """Structured security event for audit trail."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: SecurityEventType = SecurityEventType.SESSION_CREATED
    session_id: str = ""
    user_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: str = ""                # Trace correlation ID
    ip_address: str = ""
    device_id: str = ""
    severity: str = "info"                  # info, warning, error, critical
    details: Dict[str, Any] = field(default_factory=dict)
    risk_score_delta: float = 0.0           # Change to session risk
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Firestore document."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "ip_address": self.ip_address,
            "device_id": self.device_id,
            "severity": self.severity,
            "details": self.details,
            "risk_score_delta": self.risk_score_delta,
        }
