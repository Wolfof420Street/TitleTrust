"""
Token repository for managing refresh tokens with rotation tracking.

Implements:
- Token family tracking for replay detection
- One-time-use refresh tokens
- Token revocation chains
- Secure token hashing
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import hashlib
import hmac

try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

from backend.domain.session_models import (
    TokenInfo,
    TokenFamily,
    SecurityEvent,
    SecurityEventType,
)

logger = logging.getLogger("TitleTrust-TokenRepository")


def hash_refresh_token(token: str) -> str:
    """Hash refresh token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class TokenRepository:
    """Repository for managing refresh tokens securely."""

    def __init__(self, db: Any, collection: str = "refresh_tokens"):
        self.db = db
        self.collection = collection

    def store_token(
        self,
        token_id: str,
        refresh_token: str,
        token_info: TokenInfo,
    ) -> bool:
        """
        Store refresh token securely.

        Args:
            token_id: Unique token identifier
            refresh_token: The actual refresh token (will be hashed)
            token_info: Token metadata

        Returns:
            True if stored successfully
        """
        try:
            token_hash = hash_refresh_token(refresh_token)
            
            doc_data = token_info.to_dict()
            doc_data["token_hash"] = token_hash  # Store hash instead of token
            doc_data["created_at"] = firestore.SERVER_TIMESTAMP if firestore else datetime.now()
            
            self.db.collection(self.collection).document(token_id).set(doc_data)
            
            logger.info(f"Stored refresh token {token_id} (family: {token_info.token_family})")
            return True
            
        except Exception as exc:
            logger.error(f"Failed to store token {token_id}: {exc}")
            return False

    def verify_and_get_token(
        self,
        token_id: str,
        refresh_token: str,
    ) -> Optional[TokenInfo]:
        """
        Verify token and retrieve info.

        Args:
            token_id: Token identifier
            refresh_token: Token to verify

        Returns:
            TokenInfo if valid, None if invalid/expired/revoked
        """
        try:
            doc = self.db.collection(self.collection).document(token_id).get()
            if not doc.exists:
                logger.warning(f"Token {token_id} not found")
                return None

            data = doc.to_dict()
            stored_hash = data.get("token_hash")
            provided_hash = hash_refresh_token(refresh_token)
            if not isinstance(stored_hash, (str, bytes)) or not stored_hash:
                logger.warning("Token %s missing or invalid token_hash", token_id)
                return None

            # Verify hash matches
            if not hmac.compare_digest(stored_hash, provided_hash):
                logger.warning(f"Token hash mismatch for {token_id} - possible token theft")
                return None

            # Check status
            status = TokenFamily(data.get("status", "active"))
            if status != TokenFamily.ACTIVE:
                logger.warning(
                    f"Token {token_id} is {status.value}, not active"
                )
                return None

            # Check expiration
            expires_at = data.get("expires_at")
            if expires_at and isinstance(expires_at, datetime):
                if expires_at < datetime.now():
                    logger.warning(f"Token {token_id} expired at {expires_at}")
                    return None

            # Create TokenInfo from stored data
            token_info = TokenInfo(
                token_id=token_id,
                token_family=data.get("token_family", ""),
                generation=data.get("generation", 0),
                issued_at=data.get("issued_at", datetime.now()),
                expires_at=data.get("expires_at", datetime.now()),
                last_used_at=data.get("last_used_at"),
                used_count=data.get("used_count", 0),
                status=TokenFamily(data.get("status", "active")),
                ip_address=data.get("ip_address", ""),
                revoked_at=data.get("revoked_at"),
                revocation_reason=data.get("revocation_reason", ""),
            )

            logger.info(f"Token {token_id} verified successfully")
            return token_info

        except Exception as exc:
            logger.error(f"Error verifying token {token_id}: {exc}")
            return None

    def rotate_token(
        self,
        old_token_id: str,
        new_token_id: str,
        new_refresh_token: str,
        new_token_info: TokenInfo,
    ) -> bool:
        """
        Rotate refresh token (one-time-use).

        Args:
            old_token_id: Current token to retire
            new_token_id: New token identifier
            new_refresh_token: New token value
            new_token_info: New token metadata

        Returns:
            True if rotation successful
        """
        try:
            batch = self.db.batch()

            # Mark old token as rotated
            batch.update(
                self.db.collection(self.collection).document(old_token_id),
                {
                    "status": TokenFamily.ROTATED.value,
                    "last_used_at": firestore.SERVER_TIMESTAMP if firestore else datetime.now(),
                }
            )

            # Store new token
            token_hash = hash_refresh_token(new_refresh_token)
            new_doc_data = new_token_info.to_dict()
            new_doc_data["token_hash"] = token_hash
            new_doc_data["created_at"] = firestore.SERVER_TIMESTAMP if firestore else datetime.now()
            
            batch.set(
                self.db.collection(self.collection).document(new_token_id),
                new_doc_data
            )

            batch.commit()

            logger.info(
                f"Rotated token {old_token_id} -> {new_token_id} "
                f"(family: {new_token_info.token_family}, gen: {new_token_info.generation})"
            )
            return True

        except Exception as exc:
            logger.error(f"Failed to rotate token {old_token_id}: {exc}")
            return False

    def revoke_token(
        self,
        token_id: str,
        reason: str = "user_request",
    ) -> bool:
        """
        Revoke a refresh token immediately.

        Args:
            token_id: Token to revoke
            reason: Revocation reason

        Returns:
            True if revoked successfully
        """
        try:
            self.db.collection(self.collection).document(token_id).update(
                {
                    "status": TokenFamily.REVOKED.value,
                    "revoked_at": firestore.SERVER_TIMESTAMP if firestore else datetime.now(),
                    "revocation_reason": reason,
                }
            )

            logger.warning(f"Revoked token {token_id}: {reason}")
            return True

        except Exception as exc:
            logger.error(f"Failed to revoke token {token_id}: {exc}")
            return False

    def revoke_token_family(
        self,
        token_family: str,
        reason: str = "security_incident",
    ) -> int:
        """
        Revoke entire token family (family attack detection).

        Args:
            token_family: Family to revoke
            reason: Revocation reason

        Returns:
            Number of tokens revoked
        """
        try:
            docs = (
                self.db.collection(self.collection)
                .where("token_family", "==", token_family)
                .where("status", "==", TokenFamily.ACTIVE.value)
                .stream()
            )

            batch = self.db.batch()
            count = 0

            for doc in docs:
                batch.update(
                    doc.reference,
                    {
                        "status": TokenFamily.REVOKED.value,
                        "revoked_at": firestore.SERVER_TIMESTAMP if firestore else datetime.now(),
                        "revocation_reason": reason,
                    }
                )
                count += 1

            batch.commit()

            logger.warning(
                f"Revoked entire token family {token_family} ({count} tokens): {reason}"
            )
            return count

        except Exception as exc:
            logger.error(f"Failed to revoke token family {token_family}: {exc}")
            return 0

    def get_token_family_history(self, token_family: str) -> List[Dict[str, Any]]:
        """
        Get complete rotation history for a family.

        Args:
            token_family: Family to query

        Returns:
            Ordered list of all tokens in family
        """
        try:
            docs = (
                self.db.collection(self.collection)
                .where("token_family", "==", token_family)
                .order_by("generation")
                .stream()
            )

            return [doc.to_dict() for doc in docs]

        except Exception as exc:
            logger.error(f"Failed to get token family history {token_family}: {exc}")
            return []

    def cleanup_expired_tokens(self, older_than_days: int = 30) -> int:
        """
        Clean up expired and revoked tokens.

        Args:
            older_than_days: Delete tokens older than this

        Returns:
            Number of deleted tokens
        """
        try:
            cutoff = datetime.now() - timedelta(days=older_than_days)

            docs = (
                self.db.collection(self.collection)
                .where("expires_at", "<", cutoff)
                .stream()
            )

            batch = self.db.batch()
            count = 0

            for doc in docs:
                batch.delete(doc.reference)
                count += 1

            batch.commit()

            logger.info(f"Cleaned up {count} expired tokens")
            return count

        except Exception as exc:
            logger.error(f"Failed to cleanup expired tokens: {exc}")
            return 0

    def get_user_tokens(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all tokens for a user."""
        try:
            # This requires a subcollection structure or denormalization
            # For now, return empty - would need query on session_id index
            return []
        except Exception as exc:
            logger.error(f"Failed to get tokens for user {user_id}: {exc}")
            return []
