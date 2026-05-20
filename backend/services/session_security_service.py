"""
Enterprise session security service.

Implements:
- Refresh token rotation with one-time-use enforcement
- Device-bound sessions with fingerprinting
- IP-aware session analysis
- Session revocation propagation
- Global logout support
- Concurrent session controls
"""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import secrets
import uuid

try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

from backend.domain.session_models import (
    SessionState,
    TokenInfo,
    TokenFamily,
    DeviceFingerprint,
    SecurityEvent,
    SecurityEventType,
    SessionRiskLevel,
)
from backend.repositories.token_repository import TokenRepository
from backend.config import settings

logger = logging.getLogger("TitleTrust-SessionSecurity")


class SessionSecurityService:
    """Enterprise-grade session security with token rotation."""

    def __init__(self, db: Any):
        self.db = db
        self.tokens = TokenRepository(db)
        self.sessions_collection = settings.SESSION_COLLECTION
        self.security_events_collection = "security_events"

    def create_session(
        self,
        user_id: str,
        device_fingerprint: Optional[DeviceFingerprint],
        ip_address: str,
        mfa_verified: bool = False,
    ) -> Tuple[str, str, str]:
        """
        Create new session with initial refresh token.

        Args:
            user_id: User identifier
            device_fingerprint: Device information
            ip_address: Client IP address
            mfa_verified: MFA completed

        Returns:
            (session_id, refresh_token, correlation_id)
        """
        session_id = str(uuid.uuid4())
        token_family = str(uuid.uuid4())
        refresh_token = self._generate_token()
        token_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())

        try:
            # Create session state
            session = SessionState(
                session_id=session_id,
                user_id=user_id,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24),
                last_activity_at=datetime.now(),
                current_refresh_token_id=token_id,
                token_family=token_family,
                generation=1,
                device_fingerprint=device_fingerprint,
                original_ip=ip_address,
                current_ip=ip_address,
                mfa_verified=mfa_verified,
                mfa_verified_at=datetime.now() if mfa_verified else None,
            )

            # Create token info
            token_info = TokenInfo(
                token_id=token_id,
                token_family=token_family,
                generation=1,
                issued_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=7 * 24),  # 7 days
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
                status=TokenFamily.ACTIVE,
            )

            # Store in batch
            batch = self.db.batch()

            # Store session
            batch.set(
                self.db.collection(self.sessions_collection).document(session_id),
                session.to_dict(),
            )

            # Store token
            self.tokens.store_token(token_id, refresh_token, token_info)

            # Record security event
            event = SecurityEvent(
                event_type=SecurityEventType.SESSION_CREATED,
                session_id=session_id,
                user_id=user_id,
                timestamp=datetime.now(),
                correlation_id=correlation_id,
                ip_address=ip_address,
                device_id=device_fingerprint.device_id if device_fingerprint else "",
                severity="info",
                details={
                    "token_family": token_family,
                    "mfa_verified": mfa_verified,
                },
            )
            batch.set(
                self.db.collection(self.security_events_collection).document(
                    event.event_id
                ),
                event.to_dict(),
            )

            batch.commit()

            logger.info(
                f"Created session {session_id} for user {user_id} "
                f"(device: {device_fingerprint.device_id if device_fingerprint else 'unknown'})"
            )
            return session_id, refresh_token, correlation_id

        except Exception as exc:
            logger.error(f"Failed to create session: {exc}")
            raise

    def rotate_refresh_token(
        self,
        session_id: str,
        old_token_id: str,
        old_refresh_token: str,
        ip_address: str,
        correlation_id: str,
    ) -> Optional[str]:
        """
        Rotate refresh token (one-time-use enforcement).

        Args:
            session_id: Session to rotate
            old_token_id: Current token ID
            old_refresh_token: Current token value
            ip_address: Request IP
            correlation_id: Trace ID

        Returns:
            New refresh token, or None if rotation failed
        """
        try:
            # Verify old token
            token_info = self.tokens.verify_and_get_token(
                old_token_id, old_refresh_token
            )
            if not token_info:
                logger.warning(
                    f"Token rotation failed: invalid or expired token {old_token_id}"
                )
                return None

            # Get session
            session = self._get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return None

            # Check for replay attacks (token used multiple times)
            if token_info.status == TokenFamily.ROTATED:
                logger.error(
                    f"Possible replay attack: attempting to reuse rotated token {old_token_id}"
                )
                # Revoke entire family due to suspected compromise
                self.tokens.revoke_token_family(
                    token_info.token_family,
                    reason="replay_attack_detected",
                )
                self.revoke_session(session_id, "replay_attack_detected", correlation_id)
                return None

            # Generate new token
            new_token_id = str(uuid.uuid4())
            new_refresh_token = self._generate_token()
            new_generation = token_info.generation + 1

            # Create new token info
            new_token_info = TokenInfo(
                token_id=new_token_id,
                token_family=token_info.token_family,
                generation=new_generation,
                issued_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=7 * 24),
                ip_address=ip_address,
                device_fingerprint=session.device_fingerprint,
                status=TokenFamily.ACTIVE,
            )

            # Update session and token in batch
            batch = self.db.batch()

            # Rotate token
            self.tokens.rotate_token(
                old_token_id, new_token_id, new_refresh_token, new_token_info
            )

            # Update session
            session.current_refresh_token_id = new_token_id
            session.previous_refresh_tokens.append(old_token_id)
            session.generation = new_generation
            session.last_activity_at = datetime.now()
            session.request_count += 1

            batch.update(
                self.db.collection(self.sessions_collection).document(session_id),
                {
                    "current_refresh_token_id": new_token_id,
                    "previous_refresh_tokens": session.previous_refresh_tokens,
                    "generation": new_generation,
                    "last_activity_at": firestore.SERVER_TIMESTAMP if firestore else datetime.now(),
                    "request_count": session.request_count,
                },
            )

            # Record event
            event = SecurityEvent(
                event_type=SecurityEventType.TOKEN_ROTATED,
                session_id=session_id,
                user_id=session.user_id,
                timestamp=datetime.now(),
                correlation_id=correlation_id,
                ip_address=ip_address,
                severity="info",
                details={
                    "generation": new_generation,
                    "old_token_id": old_token_id,
                    "new_token_id": new_token_id,
                },
            )
            batch.set(
                self.db.collection(self.security_events_collection).document(
                    event.event_id
                ),
                event.to_dict(),
            )

            batch.commit()

            logger.info(
                f"Rotated token for session {session_id} "
                f"(generation: {new_generation})"
            )
            return new_refresh_token

        except Exception as exc:
            logger.error(f"Token rotation failed: {exc}")
            return None

    def revoke_session(
        self,
        session_id: str,
        reason: str = "user_request",
        correlation_id: str = "",
    ) -> bool:
        """
        Revoke a session immediately.

        Args:
            session_id: Session to revoke
            reason: Revocation reason
            correlation_id: Trace ID

        Returns:
            True if revoked successfully
        """
        try:
            session = self._get_session(session_id)
            if not session:
                return False

            # Revoke all tokens in family
            self.tokens.revoke_token_family(session.token_family, reason)

            # Mark session as revoked
            self.db.collection(self.sessions_collection).document(session_id).update(
                {
                    "revoked": True,
                    "revoked_at": firestore.SERVER_TIMESTAMP if firestore else datetime.now(),
                    "revocation_reason": reason,
                }
            )

            # Record event
            event = SecurityEvent(
                event_type=SecurityEventType.SESSION_REVOKED,
                session_id=session_id,
                user_id=session.user_id,
                timestamp=datetime.now(),
                correlation_id=correlation_id,
                severity="warning" if "user" in reason else "critical",
                details={"reason": reason},
            )
            self.db.collection(self.security_events_collection).document(
                event.event_id
            ).set(event.to_dict())

            logger.warning(f"Revoked session {session_id}: {reason}")
            return True

        except Exception as exc:
            logger.error(f"Failed to revoke session {session_id}: {exc}")
            return False

    def global_logout(self, user_id: str, correlation_id: str = "") -> int:
        """
        Logout user from all sessions.

        Args:
            user_id: User to logout
            correlation_id: Trace ID

        Returns:
            Number of sessions revoked
        """
        try:
            docs = (
                self.db.collection(self.sessions_collection)
                .where("user_id", "==", user_id)
                .where("revoked", "==", False)
                .stream()
            )

            batch = self.db.batch()
            count = 0

            for doc in docs:
                session_data = doc.to_dict()
                token_family = session_data.get("token_family")

                # Revoke tokens
                if token_family:
                    self.tokens.revoke_token_family(token_family, "global_logout")

                # Mark session
                batch.update(
                    doc.reference,
                    {
                        "revoked": True,
                        "revoked_at": firestore.SERVER_TIMESTAMP if firestore else datetime.now(),
                        "revocation_reason": "global_logout",
                        "global_logout": True,
                    },
                )
                count += 1

            batch.commit()

            logger.warning(f"Global logout for user {user_id}: {count} sessions revoked")
            return count

        except Exception as exc:
            logger.error(f"Global logout failed for user {user_id}: {exc}")
            return 0

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session, checking for revocation."""
        session = self._get_session(session_id)
        if session and session.revoked:
            logger.warning(f"Accessing revoked session {session_id}")
            return None
        return session

    def _get_session(self, session_id: str) -> Optional[SessionState]:
        """Internal: get session without revocation check."""
        try:
            doc = self.db.collection(self.sessions_collection).document(session_id).get()
            if not doc.exists:
                return None
            return SessionState.from_dict(doc.to_dict())
        except Exception as exc:
            logger.error(f"Failed to get session {session_id}: {exc}")
            return None

    @staticmethod
    def _generate_token(length: int = 32) -> str:
        """Generate cryptographically secure token."""
        return secrets.token_urlsafe(length)

    def enforce_concurrent_session_limit(
        self,
        user_id: str,
        max_sessions: int = 5,
        correlation_id: str = "",
    ) -> None:
        """Enforce maximum concurrent sessions per user."""
        try:
            sessions = (
                self.db.collection(self.sessions_collection)
                .where("user_id", "==", user_id)
                .where("revoked", "==", False)
                .order_by("created_at")
                .stream()
            )

            sessions_list = list(sessions)
            if len(sessions_list) > max_sessions:
                # Revoke oldest sessions
                to_revoke = sessions_list[: len(sessions_list) - max_sessions]
                for doc in to_revoke:
                    session_id = doc.id
                    self.revoke_session(
                        session_id,
                        "concurrent_session_limit_exceeded",
                        correlation_id,
                    )

        except Exception as exc:
            logger.error(f"Failed to enforce concurrent session limit: {exc}")
