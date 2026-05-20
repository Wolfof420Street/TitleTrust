"""
Dead-letter queue handling for failed jobs.

Prevents poison jobs from blocking the queue while preserving failure context.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
import json

try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

logger = logging.getLogger("TitleTrust-DeadLetterQueue")


class DeadLetterEvent:
    """Represents a failed job sent to dead-letter queue."""

    def __init__(
        self,
        job_id: str,
        job_type: str,
        original_data: Dict[str, Any],
        error_message: str,
        error_type: str,
        attempt_count: int,
        max_retries: int,
        stack_trace: Optional[str] = None,
    ):
        self.job_id = job_id
        self.job_type = job_type
        self.original_data = original_data
        self.error_message = error_message
        self.error_type = error_type
        self.attempt_count = attempt_count
        self.max_retries = max_retries
        self.stack_trace = stack_trace
        self.created_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Firestore document."""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "original_data": self.original_data,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "attempt_count": self.attempt_count,
            "max_retries": self.max_retries,
            "stack_trace": self.stack_trace,
            "created_at": firestore.SERVER_TIMESTAMP if firestore else self.created_at,
            "status": "dead_letter",
            "resolved": False,
            "resolution_notes": None,
        }


class DeadLetterQueueRepository:
    """Repository for managing dead-letter queue."""

    def __init__(self, db: Optional[Any] = None, collection: str = "dead_letter_queue"):
        self.db = db
        self.collection = collection

    def store_failed_job(self, event: DeadLetterEvent) -> str:
        """
        Store a failed job in the dead-letter queue.

        Args:
            event: DeadLetterEvent containing failure information

        Returns:
            Document ID of the stored event
        """
        if not self.db:
            logger.error(
                f"Dead-letter queue not available. Job {event.job_id} would be lost: "
                f"{event.error_message}"
            )
            return ""

        try:
            doc_ref = self.db.collection(self.collection).document(event.job_id)
            doc_ref.set(event.to_dict())
            logger.error(
                f"Job {event.job_id} ({event.job_type}) sent to dead-letter queue: "
                f"{event.error_type} - {event.error_message}"
            )
            # Emit realtime DLQ event (best-effort)
            try:
                import asyncio
                from backend.realtime.events import emit

                payload = {"job_id": event.job_id, "job_type": event.job_type, "error": event.error_message}
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(emit("job.dead_lettered", payload, severity="error", job_id=event.job_id))
                except RuntimeError:
                    import threading

                    def _bg():
                        import asyncio as _asyncio
                        from backend.realtime.events import emit as _emit
                        try:
                            _asyncio.run(_emit("job.dead_lettered", payload, severity="error", job_id=event.job_id))
                        except Exception:
                            pass

                    threading.Thread(target=_bg, daemon=True).start()
            except Exception:
                pass
            return event.job_id
        except Exception as exc:
            logger.error(
                f"Failed to store job {event.job_id} in dead-letter queue: {exc}"
            )
            return ""

    def get_dead_letter_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a dead-letter job for inspection/retry."""
        if not self.db:
            return None

        try:
            doc = self.db.collection(self.collection).document(job_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as exc:
            logger.error(f"Failed to retrieve dead-letter job {job_id}: {exc}")
            return None

    def list_dead_letter_jobs(
        self, job_type: Optional[str] = None, limit: int = 100
    ) -> list:
        """List dead-letter jobs."""
        if not self.db:
            return []

        try:
            query = self.db.collection(self.collection)
            if job_type:
                query = query.where("job_type", "==", job_type)
            query = query.where("resolved", "==", False).order_by(
                "created_at", direction=firestore.Query.DESCENDING
            ).limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        except Exception as exc:
            logger.error(f"Failed to list dead-letter jobs: {exc}")
            return []

    def resolve_dead_letter_job(
        self, job_id: str, notes: str, retry: bool = False
    ) -> bool:
        """Mark a dead-letter job as resolved."""
        if not self.db:
            return False

        try:
            self.db.collection(self.collection).document(job_id).update(
                {
                    "resolved": True,
                    "resolved_at": firestore.SERVER_TIMESTAMP if firestore else datetime.now(),
                    "resolution_notes": notes,
                    "retried": retry,
                }
            )
            logger.info(f"Resolved dead-letter job {job_id}")
            return True
        except Exception as exc:
            logger.error(f"Failed to resolve dead-letter job {job_id}: {exc}")
            return False

    def get_dead_letter_stats(self) -> Dict[str, Any]:
        """Get statistics on dead-letter jobs."""
        if not self.db:
            return {}

        try:
            unresolved = (
                self.db.collection(self.collection)
                .where("resolved", "==", False)
                .count()
                .get()[0][0].value
            )
            by_type = {}
            for doc in (
                self.db.collection(self.collection)
                .where("resolved", "==", False)
                .stream()
            ):
                data = doc.to_dict()
                job_type = data.get("job_type", "unknown")
                by_type[job_type] = by_type.get(job_type, 0) + 1

            return {
                "total_unresolved": unresolved,
                "by_job_type": by_type,
            }
        except Exception as exc:
            logger.error(f"Failed to get dead-letter stats: {exc}")
            return {}


class PoisonPillDetector:
    """Detects poison jobs that should be skipped."""

    # Job types that are known to fail catastrophically
    KNOWN_POISON_PATTERNS = [
        "corrupted_image",
        "oversized_file",
        "unsupported_format",
    ]

    @staticmethod
    def is_poison_pill(error_type: str, job_data: Dict[str, Any]) -> bool:
        """
        Determine if a job is a poison pill that should be skipped.

        A poison pill is a job that will ALWAYS fail due to data corruption
        or unsupported content, not due to transient failures.
        """
        # Check error type patterns
        for pattern in PoisonPillDetector.KNOWN_POISON_PATTERNS:
            if pattern in error_type.lower():
                return True

        # Check file size
        if job_data.get("file_size", 0) > 100 * 1024 * 1024:  # 100 MB
            return True

        # Check file type
        file_type = job_data.get("file_type", "").lower()
        supported_types = ["pdf", "jpg", "jpeg", "png"]
        if file_type and file_type not in supported_types:
            return True

        return False

    @staticmethod
    def get_severity(error_type: str) -> str:
        """Classify error severity."""
        transient_indicators = ["timeout", "rate_limit", "connection", "temporary"]
        permanent_indicators = ["corrupted", "unsupported", "invalid_format", "permission"]

        error_lower = error_type.lower()

        for indicator in permanent_indicators:
            if indicator in error_lower:
                return "permanent"

        for indicator in transient_indicators:
            if indicator in error_lower:
                return "transient"

        return "unknown"
