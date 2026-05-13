# Backend Infrastructure Utilities

This file documents the `backend/infrastructure` helpers used by the worker and services for resilience and operational behavior.

Files and responsibilities (ground truth):

- `backend/infrastructure/resilience.py` — resilience primitives used across worker and service code (circuit breaker, retry helpers, backoff utilities).
- `backend/infrastructure/timeout_policies.py` — centralized timeout constants and context managers used for enforcing handler-level execution limits (e.g., forensic and geospatial time budgets).
- `backend/infrastructure/dead_letter_queue.py` — utilities and repository adapters for storing failed jobs and their diagnostic payloads.
- `backend/infrastructure/rate_limit_store.py` — Redis-backed rate limit store primitives used by middleware and rate-limit enforcement.
- `backend/infrastructure/graceful_degradation.py` — helpers that implement fallback behaviors when external dependencies are missing (e.g., fallback to in-process execution when Redis is unavailable).

Notes:
- These modules are implementation detail shared by `backend/workers/runtime.py`, `backend/services/background_job_service.py`, and queue abstractions. Treat them as internal primitives rather than public service interfaces.
