"""
Immutable audit export pipeline with cryptographic signing.

Implements:
- Signed audit exports
- Tamper detection
- Export manifests
- Chain verification
- Regulatory compliance
"""

import logging
import hashlib
import json
import hmac
from typing import Dict, Any, List, Optional
from datetime import datetime
import base64

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
except ImportError:
    hashes = None

from backend.config import settings

logger = logging.getLogger("TitleTrust-AuditExport")


class AuditSigner:
    """Sign audit exports for tamper detection."""

    def __init__(self, signing_key_path: Optional[str] = None):
        """
        Initialize signer with RSA key.

        Args:
            signing_key_path: Path to private key (PEM format)
        """
        self.signing_key_path = signing_key_path or getattr(
            settings, "AUDIT_SIGNING_KEY_PATH", None
        )
        self._private_key = None
        self._public_key = None

        if self.signing_key_path:
            self._load_keys()
        else:
            logger.warning("No signing key configured for audit exports")

    def _load_keys(self) -> None:
        """Load RSA keys from disk."""
        try:
            with open(self.signing_key_path, "rb") as f:
                key_data = f.read()
                self._private_key = serialization.load_pem_private_key(
                    key_data, password=None, backend=default_backend()
                )
                self._public_key = self._private_key.public_key()
                logger.info(f"Loaded signing key from {self.signing_key_path}")
        except Exception as exc:
            logger.error(f"Failed to load signing key: {exc}")
            raise

    def sign_export(self, export_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign audit export data.

        Args:
            export_data: Export contents to sign

        Returns:
            Export with signature
        """
        if not self._private_key:
            logger.error("Cannot sign: private key not loaded")
            return export_data

        try:
            # Create canonical JSON representation
            canonical_json = json.dumps(
                export_data, sort_keys=True, separators=(",", ":")
            )

            # Sign the canonical JSON
            signature = self._private_key.sign(
                canonical_json.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

            # Return export with signature
            return {
                **export_data,
                "_signature": {
                    "algorithm": "RSA-PSS-SHA256",
                    "signature": base64.b64encode(signature).decode(),
                    "timestamp": datetime.now().isoformat(),
                },
            }

        except Exception as exc:
            logger.error(f"Failed to sign export: {exc}")
            return export_data

    def verify_signature(
        self, export_with_signature: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Verify export signature.

        Args:
            export_with_signature: Export with signature

        Returns:
            (is_valid, error_message)
        """
        if not self._public_key:
            return False, "Public key not loaded"

        try:
            signature_data = export_with_signature.get("_signature")
            if not signature_data:
                return False, "No signature present"

            # Extract signature
            signature = base64.b64decode(signature_data["signature"])

            # Recreate canonical data (without signature)
            export_data = {
                k: v for k, v in export_with_signature.items() if k != "_signature"
            }
            canonical_json = json.dumps(
                export_data, sort_keys=True, separators=(",", ":")
            )

            # Verify signature
            self._public_key.verify(
                signature,
                canonical_json.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

            return True, None

        except Exception as exc:
            return False, f"Signature verification failed: {exc}"


class AuditExportService:
    """Service for generating and exporting audits."""

    def __init__(self, db: Any, signer: Optional[AuditSigner] = None):
        self.db = db
        self.signer = signer or AuditSigner()
        self.audit_collection = "audit_events"
        self.export_collection = "audit_exports"

    def export_session_audit(
        self,
        session_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Export complete audit trail for a session.

        Args:
            session_id: Session to export
            user_id: User identifier

        Returns:
            Signed export, or None on error
        """
        try:
            # Retrieve all audit events for session
            events = (
                self.db.collection(self.audit_collection)
                .where("session_id", "==", session_id)
                .order_by("timestamp")
                .stream()
            )

            events_list = [e.to_dict() for e in events]

            # Create export manifest
            export = {
                "export_id": self._generate_id(),
                "export_timestamp": datetime.now().isoformat(),
                "exported_by": "audit_export_service",
                "session_id": session_id,
                "user_id": user_id,
                "event_count": len(events_list),
                "events": events_list,
                "manifest": {
                    "format_version": "1.0",
                    "audit_standard": "SOC2",
                    "immutable": True,
                },
            }

            # Compute hash for integrity verification
            export_json = json.dumps(events_list, sort_keys=True)
            export["content_hash"] = hashlib.sha256(export_json.encode()).hexdigest()

            # Sign export
            signed_export = self.signer.sign_export(export)

            # Store export for audit trail
            self.db.collection(self.export_collection).document(
                export["export_id"]
            ).set(signed_export)

            logger.info(
                f"Exported audit for session {session_id} "
                f"({len(events_list)} events, signed)"
            )
            return signed_export

        except Exception as exc:
            logger.error(f"Failed to export audit: {exc}")
            return None

    def verify_export(
        self, export_id: str
    ) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Verify an exported audit.

        Args:
            export_id: Export to verify

        Returns:
            (is_valid, export_data, error_message)
        """
        try:
            doc = self.db.collection(self.export_collection).document(export_id).get()
            if not doc.exists:
                return False, None, "Export not found"

            export = doc.to_dict()

            # Verify signature
            is_valid, error_msg = self.signer.verify_signature(export)
            if not is_valid:
                return False, None, error_msg

            # Verify content hash
            export_json = json.dumps(export.get("events", []), sort_keys=True)
            computed_hash = hashlib.sha256(export_json.encode()).hexdigest()
            if computed_hash != export.get("content_hash"):
                return (
                    False,
                    None,
                    f"Content hash mismatch (tamper detected): "
                    f"{computed_hash} != {export.get('content_hash')}",
                )

            return True, export, None

        except Exception as exc:
            return False, None, f"Verification failed: {exc}"

    def list_exports(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List exports for a user."""
        try:
            docs = (
                self.db.collection(self.export_collection)
                .where("user_id", "==", user_id)
                .order_by("export_timestamp", direction="DESCENDING")
                .limit(limit)
                .stream()
            )
            return [doc.to_dict() for doc in docs]
        except Exception as exc:
            logger.error(f"Failed to list exports: {exc}")
            return []

    @staticmethod
    def _generate_id() -> str:
        """Generate export ID."""
        import uuid
        return f"export_{uuid.uuid4().hex[:16]}"

    def get_export_integrity_report(
        self, export_id: str
    ) -> Dict[str, Any]:
        """Generate integrity verification report."""
        is_valid, export, error = self.verify_export(export_id)

        return {
            "export_id": export_id,
            "valid": is_valid,
            "verified_at": datetime.now().isoformat(),
            "error": error,
            "event_count": export.get("event_count", 0) if export else 0,
            "content_hash": export.get("content_hash") if export else None,
            "signature_algorithm": (
                export.get("_signature", {}).get("algorithm")
                if export
                else None
            ),
        }
