# TitleTrust Operations and Runtime

This document covers local development, container runtime, Kubernetes deployment, worker health, CI gates, and the operational surfaces encoded in the repository.

## 1) Runtime Modes

The backend supports two execution styles:
- inline/background task mode for local or simplified deployment
- Redis queue mode for distributed background execution

The switch is controlled by `QUEUE_MODE` in [backend/config.py](backend/config.py).

Operational implication:
- the API can still work in a dev environment without Redis, but queue semantics are preserved when Redis is present.

## 2) Local Development

Relevant files:
- [Makefile](Makefile)
- [docker-compose.yml](docker-compose.yml)
- [backend/Dockerfile](backend/Dockerfile)
- [backend/scripts/bootstrap_backend.sh](backend/scripts/bootstrap_backend.sh)

Useful commands defined in the Makefile:
- `make bootstrap`
- `make backend-run`
- `make worker`
- `make test`
- `make lint`
- `make docker-up`

Docker Compose brings up:
- `titletrust-backend`
- `titletrust-worker`
- `redis`
- `jaeger`
- a dev container

Notable runtime configuration:
- backend and worker both export OTLP traces to Jaeger
- Redis is the default queue backend in compose
- backend healthcheck is `/health/live`
- worker healthcheck uses `python -m backend.workers.run_worker --healthcheck`

## 3) Kubernetes Deployment

Relevant manifests:
- [k8s/base/backend-hpa.yaml](k8s/base/backend-hpa.yaml)
- [k8s/base/worker-hpa.yaml](k8s/base/worker-hpa.yaml)
- [k8s/base/worker-deployment.yaml](k8s/base/worker-deployment.yaml)

Operational characteristics:
- backend HPA scales on CPU and memory
- worker HPA scales separately from the API
- worker readiness/liveness probes reuse the worker module healthcheck entrypoint

Why this matters:
- background job throughput can be scaled without scaling the API tier in lockstep
- the deployment explicitly recognizes that model/analysis work is a different load profile than request handling

## 4) CI and Security Gates

Relevant workflows:
- [.github/workflows/ci.yml](.github/workflows/ci.yml)
- [.github/workflows/security-validation.yml](.github/workflows/security-validation.yml)

CI checks include:
- Ruff
- Mypy
- Bandit
- pip-audit
- backend tests
- Flutter analyze
- secret scanning
- SBOM generation

Security validation adds:
- SARIF uploads
- Trivy scans
- security-specific tests and coverage
- container scanning on main

Operational takeaway:
- the repo has explicit automation for code quality and security hygiene, not just app tests.

## 5) Telemetry and Observability Runtime

Backend telemetry is initialized in [backend/telemetry/init.py](backend/telemetry/init.py).

What is enabled when configured:
- OTLP tracing export
- OTLP metrics export
- FastAPI instrumentation
- requests instrumentation

What the app also exposes:
- Prometheus metrics from middleware and worker runtime
- response headers with correlation id, latency, and abuse score

Frontend telemetry:
- Crashlytics and Sentry capture client-side failures in [frontend/titletrust/lib/telemetry/frontend_telemetry_service.dart](frontend/titletrust/lib/telemetry/frontend_telemetry_service.dart)

Operational implication:
- the system can be observed even if a specific telemetry exporter is unavailable, because key metrics are also exposed in-process.

## 6) Health and Failure Surfaces

Runtime health surfaces:
- backend live health endpoint
- worker healthcheck command
- Redis ping / queue depth
- worker heartbeat key in Redis
- Cloud Tasks scheduling logs

Failure handling patterns:
- transient Redis failures retry in the queue abstraction
- transient network failures retry in the client executor
- model/worker failures retry with backoff then dead-letter
- telemetry initialization failure degrades silently rather than breaking the app

What does not fail open:
- auth verification
- request signatures
- permission checks
- upload validation
- abuse blocks

## 7) Storage and Infrastructure Expectations

Expected backend services:
- Firebase Admin
- Firestore
- Redis
- Cloud Tasks
- Gemini / GenAI
- Google Maps for geospatial verification
- Firebase Messaging for client push token storage
- Jaeger or another OTLP sink for traces

Environmental inputs in [backend/config.py](backend/config.py):
- `GCP_PROJECT_ID`
- `GEMINI_API_KEY`
- `REDIS_URL`
- `CLOUD_TASKS_PROJECT_ID`
- `CLOUD_RUN_URL`
- `WORKER_QUEUE_NAME`
- `API_RATE_LIMIT_PER_MINUTE`
- `ALLOWED_ORIGINS`

Operational implication:
- the application is environment-driven and can be run locally, in Docker, or in a cloud-native deployment with the same code paths.

## 8) Worker Runtime Behavior

The worker in [backend/workers/runtime.py](backend/workers/runtime.py):
- emits a heartbeat
- tracks queue depth
- increments active job gauges
- handles cancellations before execution
- checks circuit breakers before expensive work
- applies time limits to task handlers
- retries with exponential backoff and jitter
- dead-letters poison or exhausted jobs

Why this matters:
- the worker is designed as a resilient state machine, not a bare queue consumer.

Operational risk:
- if Redis is down, the runtime can fall back to in-process execution paths, but that changes capacity and isolation characteristics.

## 9) Database and Audit Operations

Firestore collections are used as system-of-record stores, not as ephemeral cache only:
- `sessions`
- `jobs`
- `device_sessions`
- `audit_events`
- `memberships`
- `policies`
- `idempotency_keys`
- `dead_letter_jobs`
- `security_events`

Operational note:
- audit events are append-only and sequence-numbered, which makes incident review and forensic reconstruction materially easier.

## 10) Runbook-Driven Operations

The repository already contains operational documentation under [ops/runbooks](ops/runbooks), [ops/dashboards](ops/dashboards), and [ops/alerts](ops/alerts).

The most concrete example is the adaptive abuse runbook, which expects operators to:
- inspect abuse assessments
- review correlation windows
- determine whether a request was throttled, challenged, quarantined, or blocked
- preserve evidence when the request touched a protected workflow

This is a sign of operational maturity: the codebase is not just instrumented, it also has a response model.
