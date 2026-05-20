from __future__ import annotations

import logging
import socket
import time
import traceback
from typing import Any, Callable, Dict, Optional

try:
    from prometheus_client import Counter, Gauge, CollectorRegistry, REGISTRY
except ModuleNotFoundError:
    Counter = Gauge = REGISTRY = None

try:
    from backend.config import settings
    from backend.events.job_events import JobEvent
    from backend.queues.redis_queue import RedisQueue, time_limit
    from backend.repositories.audit_event_repository import AuditEventRepository
    from backend.repositories.job_repository import JobRepository
    from backend.services.firebase import db
    from backend.tasks.audit_tasks import cleanup_files, run_forensic_task, run_geospatial_task
    from backend.infrastructure import (
        CircuitBreaker,
        CircuitBreakerConfig,
        CircuitBreakerOpenError,
        TimeoutPolicies,
        DeadLetterEvent,
        DeadLetterQueueRepository,
        PoisonPillDetector,
        exponential_backoff,
        BackoffConfig,
    )
except ModuleNotFoundError:
    from config import settings
    from events.job_events import JobEvent
    from queues.redis_queue import RedisQueue, time_limit
    from repositories.audit_event_repository import AuditEventRepository
    from repositories.job_repository import JobRepository
    from services.firebase import db
    from tasks.audit_tasks import cleanup_files, run_forensic_task, run_geospatial_task
    from infrastructure import (
        CircuitBreaker,
        CircuitBreakerConfig,
        CircuitBreakerOpenError,
        TimeoutPolicies,
        DeadLetterEvent,
        DeadLetterQueueRepository,
        PoisonPillDetector,
        exponential_backoff,
        BackoffConfig,
    )

logger = logging.getLogger("TitleTrust-WorkerRuntime")

# Register metrics safely - they may already exist in the default registry
JOB_COUNTER = None
WORKER_HEARTBEAT = None
QUEUE_DEPTH_GAUGE = None
ACTIVE_JOBS_GAUGE = None

if Counter is not None and REGISTRY is not None:
    try:
        # Try to get existing metrics from the registry
        JOB_COUNTER = REGISTRY._names_to_collectors.get("titletrust_jobs_total")
        if not JOB_COUNTER:
            JOB_COUNTER = Counter(
                "titletrust_jobs_total",
                "Jobs processed",
                ["job_type", "status"]
            )
    except (KeyError, AttributeError):
        # If not found, create new
        try:
            JOB_COUNTER = Counter(
                "titletrust_jobs_total",
                "Jobs processed",
                ["job_type", "status"]
            )
        except Exception:
            # Metric already registered
            pass

    try:
        WORKER_HEARTBEAT = REGISTRY._names_to_collectors.get("titletrust_worker_heartbeat")
        if not WORKER_HEARTBEAT:
            WORKER_HEARTBEAT = Gauge(
                "titletrust_worker_heartbeat",
                "Worker heartbeat",
                ["worker_id"]
            )
    except (KeyError, AttributeError):
        # If not found, create new
        try:
            WORKER_HEARTBEAT = Gauge(
                "titletrust_worker_heartbeat",
                "Worker heartbeat",
                ["worker_id"]
            )
        except Exception:
            # Metric already registered
            pass

    try:
        QUEUE_DEPTH_GAUGE = REGISTRY._names_to_collectors.get("titletrust_worker_queue_depth")
        if not QUEUE_DEPTH_GAUGE:
            QUEUE_DEPTH_GAUGE = Gauge(
                "titletrust_worker_queue_depth",
                "Observed Redis queue depth",
                ["queue_name"],
            )
    except (KeyError, AttributeError):
        try:
            QUEUE_DEPTH_GAUGE = Gauge(
                "titletrust_worker_queue_depth",
                "Observed Redis queue depth",
                ["queue_name"],
            )
        except Exception:
            pass

    try:
        ACTIVE_JOBS_GAUGE = REGISTRY._names_to_collectors.get("titletrust_worker_active_jobs")
        if not ACTIVE_JOBS_GAUGE:
            ACTIVE_JOBS_GAUGE = Gauge(
                "titletrust_worker_active_jobs",
                "Active jobs currently being processed",
                ["worker_id"],
            )
    except (KeyError, AttributeError):
        try:
            ACTIVE_JOBS_GAUGE = Gauge(
                "titletrust_worker_active_jobs",
                "Active jobs currently being processed",
                ["worker_id"],
            )
        except Exception:
            pass


class WorkerRuntime:
    """
    Enterprise-grade worker runtime with resilience patterns.

    Features:
    - Circuit breakers for task handlers
    - Exponential backoff with jitter
    - Dead-letter queue for poison jobs
    - Timeout policies
    - Graceful error handling
    """

    def __init__(self) -> None:
        self._queue = RedisQueue()
        self._jobs = JobRepository(db)
        self._audit_events = AuditEventRepository(db)
        self._dead_letter_queue = DeadLetterQueueRepository(db)
        self._worker_id = socket.gethostname()

        # Circuit breakers for each job type
        self._circuit_breakers = {
            "forensic": CircuitBreaker(
                "forensic_task",
                CircuitBreakerConfig(
                    failure_threshold=5,
                    recovery_timeout_seconds=120,
                    success_threshold=2,
                ),
            ),
            "geospatial": CircuitBreaker(
                "geospatial_task",
                CircuitBreakerConfig(
                    failure_threshold=5,
                    recovery_timeout_seconds=120,
                    success_threshold=2,
                ),
            ),
        }

        # Backoff configuration for retries
        self._backoff_config = BackoffConfig(
            initial_delay=2.0,
            max_delay=60.0,
            multiplier=2.0,
            jitter=True,
            max_retries=settings.WORKER_MAX_RETRIES,
        )

        self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "forensic": self._handle_forensic,
            "geospatial": self._handle_geospatial,
        }

    def _emit(self, event: JobEvent) -> None:
        """Emit job event for audit trail."""
        try:
            self._audit_events.append(
                session_id=event.job_id,
                event_type=event.event_type,
                payload=event.payload,
                actor_id=self._worker_id,
            )
        except Exception as exc:
            logger.warning(f"Failed to emit event {event.event_type}: {exc}")
        # Publish structured realtime event for UI (best-effort)
        try:
            import asyncio
            from backend.realtime.events import emit

            envelope = {
                "event_type": event.event_type,
                "payload": event.payload,
                "job_id": event.job_id,
            }

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(emit(event.event_type, envelope, job_id=event.job_id))
            except RuntimeError:
                # No running loop; spawn thread to run coroutine
                import threading

                def _bg_emit(ev):
                    import asyncio as _asyncio
                    try:
                        _asyncio.run(emit(ev["event_type"], ev, job_id=ev.get("job_id")))
                    except Exception:
                        pass

                threading.Thread(target=_bg_emit, args=(envelope,), daemon=True).start()
        except Exception:
            pass

    def _handle_forensic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle forensic analysis task with timeout."""
        file_paths = payload.get("file_paths", [])
        timeout_sec = TimeoutPolicies.FORENSIC_ANALYSIS
        try:
            with time_limit(timeout_sec):
                return run_forensic_task(
                    payload["job_id"],
                    payload["user_id"],
                    file_paths,
                )
        finally:
            cleanup_files(file_paths)

    def _handle_geospatial(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle geospatial analysis task with timeout."""
        file_path = payload.get("file_path", "")
        timeout_sec = TimeoutPolicies.GEOSPATIAL_ANALYSIS
        try:
            with time_limit(timeout_sec):
                return run_geospatial_task(
                    payload["job_id"],
                    payload.get("lat", 0),
                    payload.get("lng", 0),
                    file_path,
                )
        finally:
            if file_path:
                cleanup_files([file_path])

    def process_job(self, payload: Dict[str, Any]) -> None:
        """
        Process a job from the queue.

        Handles retries, dead-lettering, and circuit breaker protection.
        """
        job_id = payload.get("job_id", "unknown")
        job_type = payload.get("job_type", "unknown")
        attempts = int(payload.get("attempts", 0)) + 1

        # Check if job is cancelled
        if self._queue.is_cancelled(job_id):
            self._jobs.update(
                job_id,
                {
                    "status": "CANCELLED",
                    "attempts": attempts,
                    "cancelled_at": self._now_iso(),
                },
            )
            self._emit(
                JobEvent(
                    job_id=job_id,
                    event_type="job.cancelled",
                    payload={"attempts": attempts},
                )
            )
            if JOB_COUNTER:
                JOB_COUNTER.labels(job_type, "cancelled").inc()
            return

        # Check if circuit breaker is open for this job type
        circuit_breaker = self._circuit_breakers.get(job_type)
        if circuit_breaker and circuit_breaker.metrics.state.value == "open":
            logger.warning(
                f"Circuit breaker open for {job_type}. "
                f"Deferring job {job_id} (attempt {attempts})"
            )
            self._defer_job(payload, "circuit_breaker_open")
            return

        # Update job status to running
        if ACTIVE_JOBS_GAUGE:
            ACTIVE_JOBS_GAUGE.labels(self._worker_id).inc()
        self._jobs.update(
            job_id,
            {
                "status": "RUNNING",
                "attempts": attempts,
                "worker_id": self._worker_id,
                "started_at": self._now_iso(),
            },
        )
        self._emit(
            JobEvent(
                job_id=job_id,
                event_type="job.started",
                payload={"job_type": job_type, "attempts": attempts},
            )
        )

        # Execute job with circuit breaker protection
        try:
            handler = self._handlers.get(job_type)
            if not handler:
                raise ValueError(f"Unknown job type: {job_type}")

            # Execute with circuit breaker
            if circuit_breaker:
                result = circuit_breaker.call(handler, payload)
            else:
                result = handler(payload)

            # Record success
            self._jobs.update(
                job_id,
                {
                    "status": "COMPLETED",
                    "result": result,
                    "completed_at": self._now_iso(),
                },
            )
            self._emit(
                JobEvent(
                    job_id=job_id,
                    event_type="job.completed",
                    payload={"job_type": job_type},
                )
            )
            if JOB_COUNTER:
                JOB_COUNTER.labels(job_type, "completed").inc()

        except CircuitBreakerOpenError as exc:
            logger.error(f"Circuit breaker open for {job_type}: {exc}")
            self._defer_job(payload, str(exc))

        except TimeoutError as exc:
            logger.error(f"Job {job_id} timed out: {exc}")
            self._handle_job_failure(payload, attempts, f"timeout: {exc}", job_type)

        except Exception as exc:
            logger.exception(f"Worker job {job_id} failed with {type(exc).__name__}")
            self._handle_job_failure(
                payload, attempts, str(exc), job_type, traceback.format_exc()
            )
        finally:
            if ACTIVE_JOBS_GAUGE:
                ACTIVE_JOBS_GAUGE.labels(self._worker_id).dec()

    def _handle_job_failure(
        self,
        payload: Dict[str, Any],
        attempts: int,
        error: str,
        job_type: str,
        stack_trace: Optional[str] = None,
    ) -> None:
        """Handle job failure with retry or dead-letter logic."""
        job_id = payload.get("job_id", "unknown")

        # Check if this is a poison pill
        if PoisonPillDetector.is_poison_pill(error, payload):
            self._send_to_dead_letter(
                job_id, job_type, payload, error, stack_trace, poison_pill=True
            )
            logger.error(f"Poison pill detected for job {job_id}: {error}")
            return

        # Check if we should retry
        if attempts < self._backoff_config.max_retries:
            delay = self._calculate_backoff(attempts)
            self._jobs.update(
                job_id,
                {
                    "status": "RETRYING",
                    "attempts": attempts,
                    "error": error,
                    "next_retry_at": self._now_iso(),
                },
            )
            self._emit(
                JobEvent(
                    job_id=job_id,
                    event_type="job.retrying",
                    payload={
                        "attempts": attempts,
                        "error": error,
                        "retry_delay_seconds": delay,
                    },
                )
            )
            logger.info(
                f"Job {job_id} will be retried in {delay:.1f}s "
                f"(attempt {attempts}/{self._backoff_config.max_retries})"
            )

            # Re-queue with updated attempt count
            payload["attempts"] = attempts
            time.sleep(delay)
            if self._queue.enabled:
                self._queue.enqueue(
                    settings.WORKER_QUEUE_NAME,
                    payload,
                    priority=payload.get("priority", "default"),
                )
            else:
                # Fallback: process immediately if queue disabled
                self.process_job(payload)
        else:
            # Max retries exceeded
            self._send_to_dead_letter(job_id, job_type, payload, error, stack_trace)

    def _send_to_dead_letter(
        self,
        job_id: str,
        job_type: str,
        payload: Dict[str, Any],
        error: str,
        stack_trace: Optional[str] = None,
        poison_pill: bool = False,
    ) -> None:
        """Send job to dead-letter queue."""
        severity = PoisonPillDetector.get_severity(error)

        event = DeadLetterEvent(
            job_id=job_id,
            job_type=job_type,
            original_data=payload,
            error_message=error,
            error_type=f"{severity}_{job_type}",
            attempt_count=payload.get("attempts", 1),
            max_retries=self._backoff_config.max_retries,
            stack_trace=stack_trace,
        )

        self._dead_letter_queue.store_failed_job(event)
        self._jobs.update(
            job_id,
            {
                "status": "DEAD_LETTERED",
                "error": error,
                "poison_pill": poison_pill,
                "dead_lettered_at": self._now_iso(),
            },
        )
        self._emit(
            JobEvent(
                job_id=job_id,
                event_type="job.dead_lettered",
                payload={"error": error, "severity": severity, "poison_pill": poison_pill},
            )
        )
        if JOB_COUNTER:
            JOB_COUNTER.labels(job_type, "dead_lettered").inc()

    def _defer_job(self, payload: Dict[str, Any], reason: str) -> None:
        """Defer job to be retried later."""
        job_id = payload.get("job_id", "unknown")
        job_type = payload.get("job_type", "unknown")
        delay = 30  # Defer for 30 seconds

        self._jobs.update(
            job_id,
            {
                "status": "DEFERRED",
                "error": reason,
                "next_retry_at": self._now_iso(),
            },
        )
        logger.warning(f"Job {job_id} deferred for {delay}s: {reason}")

        time.sleep(delay)
        if self._queue.enabled:
            self._queue.enqueue(
                settings.WORKER_QUEUE_NAME,
                payload,
                priority=payload.get("priority", "default"),
            )

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = min(
            self._backoff_config.initial_delay
            * (self._backoff_config.multiplier ** attempt),
            self._backoff_config.max_delay,
        )
        if self._backoff_config.jitter:
            import random
            delay *= 0.5 + random.random()
        return delay

    @staticmethod
    def _now_iso() -> str:
        """Get current time in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()

    def run_forever(self) -> None:
        """Main worker loop."""
        logger.info(f"Worker {self._worker_id} started")

        try:
            while True:
                # Update heartbeat
                self._queue.set_heartbeat(self._worker_id)
                if WORKER_HEARTBEAT:
                    WORKER_HEARTBEAT.labels(self._worker_id).set(time.time())
                if QUEUE_DEPTH_GAUGE and self._queue.enabled:
                    QUEUE_DEPTH_GAUGE.labels(settings.WORKER_QUEUE_NAME).set(
                        self._queue.queue_depth(settings.WORKER_QUEUE_NAME)
                    )

                # Poll queue
                envelope = self._queue.pop(settings.WORKER_QUEUE_NAME)
                if not envelope:
                    time.sleep(1)
                    continue

                # Process job
                self.process_job(envelope.get("payload", {}))

        except KeyboardInterrupt:
            logger.info(f"Worker {self._worker_id} shutting down")
        except Exception as exc:
            logger.exception("Worker crashed")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get worker status for monitoring."""
        total_jobs = {}
        if JOB_COUNTER:
            try:
                for metric_family in JOB_COUNTER.collect():
                    for sample in metric_family.samples:
                        total_jobs[f"{sample.name}_{sample.labels}"] = sample.value
            except Exception:
                total_jobs = {}
        
        return {
            "worker_id": self._worker_id,
            "queue_enabled": self._queue.enabled,
            "queue_depth": self._queue.queue_depth(settings.WORKER_QUEUE_NAME) if self._queue.enabled else 0,
            "circuit_breakers": {
                name: cb.get_status()
                for name, cb in self._circuit_breakers.items()
            },
            "metrics": {
                "total_jobs": total_jobs,
            },
        }

    def healthcheck(self) -> bool:
        """Validate worker runtime dependencies for liveness/readiness probes."""
        if settings.QUEUE_MODE == "redis":
            return self._queue.enabled and self._queue.ping()
        return True


worker_runtime = WorkerRuntime()
