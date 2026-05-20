# Release Readiness & Operational Runbook

This document captures the minimal, testable checklist and operational guidance to validate deployability and production survivability for TitleTrust. It is intentionally prescriptive and focused on deterministic checks, defensive defaults, and minimal code changes.

## Goals
- Deployment safety and rollback guidance
- Operational recovery and incident classification
- Observability completeness (metrics, logs, traces)
- Security posture and secret injection paths
- Runtime resilience (reconnects, graceful shutdown, idempotency)
- Migration and scaling assumptions

## Quick Start Smoke Tests (local)
- Build and run with docker-compose (development):

```bash
# build and run (local smoke)
docker-compose build titletrust-backend titletrust-worker
docker-compose up -d redis jaeger
docker-compose up -d titletrust-backend titletrust-worker
# check liveness and readiness
curl -f http://localhost:8080/health/live
curl -f http://localhost:8080/health/ready
# metrics
curl -s http://localhost:8080/metrics | head
```

- Worker healthcheck:

```bash
# Verify healthcheck CLI
python -m backend.workers.run_worker --healthcheck
```

- Redis failure startup test (expect app to start degraded):

```bash
# set REDIS_URL to an unreachable host and start
REDIS_URL=redis://127.0.0.1:9999/0 QUEUE_MODE=redis python -m backend.main
# expect /health/ready to return status degraded
curl http://localhost:8080/health/ready
```

## Kubernetes readiness & liveness checklist
- All Deployments must define both `readinessProbe` and `livenessProbe`.
- Probes should use a lightweight endpoint or `exec` that does not block (e.g. `--healthcheck`) and must complete within probe `timeoutSeconds`.
- `initialDelaySeconds` should be conservatively large for cold-starting workers (10-30s); readiness should be quicker than liveness.
- `terminationGracePeriodSeconds` set on PodSpec should be >= maximum known graceful shutdown time (workers: 600s if using long-running jobs).
- Rolling update strategy: `maxUnavailable: 1` and `maxSurge: 1` for low-risk rolling deploys.
- Immutable images: use pinned tags with semver / digest in production manifests.

Files checked: [k8s/base/worker-deployment.yaml](k8s/base/worker-deployment.yaml), [k8s/base/deployment.yaml](k8s/base/deployment.yaml)

## Dockerfile & container startup checks
- Dockerfile must set `HEALTHCHECK` for container platforms that respect it (we have one in `backend/Dockerfile`).
- Use non-root user and `readOnlyRootFilesystem` where possible (already set in k8s manifest).
- CMD uses shell form to expand `$PORT` at runtime to allow runtime port override.

Files checked: [backend/Dockerfile](backend/Dockerfile), [docker-compose.yml](docker-compose.yml)

## Startup lifecycle and hooks
- `@app.on_event('startup')` must not raise; failures should be logged and the app should start in degraded mode unless a hard dependency is required.
- Startup tasks (broadcaster, redis listeners) should have timeouts and fail-open or degrade gracefully with explicit logs.

File checked: [backend/main.py](backend/main.py)

## Redis reconnect and worker shutdown
- Redis client libraries must use reconnect/backoff jitter. Add client-side jitter and exponential backoff for reconnect attempts.
- Worker `SIGTERM` handler must stop fetching new jobs, finish inflight jobs, and call `redis.close()` / `pubsub.aclose()` and then exit within `terminationGracePeriodSeconds`.
- Validate drain by simulating `SIGTERM` and asserting inflight jobs finish (unit/integration test).

Suggested tests to add:
- `tests/test_probes.py`: assert `/health/live` and `/health/ready` semantics under healthy, degraded (redis down), and recovery states.
- `tests/test_worker_shutdown.py`: spawn a worker process, push a long-running job, send SIGTERM, assert job completes before shutdown and that process exits within the grace period.
- `tests/test_redis_reconnect.py`: mock redis to fail initial connect then succeed; assert the app recovers and queue ops resume.

## Observability & correlation guarantees
- Ensure `trace_id` and `correlation_id` are present in logs and exported traces for all request/worker flows.
- Metrics naming must be stable and cardinality bounded (normalize paths).
- Verify metrics emitted on startup/shutdown (broadcaster started/stopped, redis listener restarts).

Tests:
- end-to-end trace injection: run local OTEL collector (jaeger) and assert traces appear for a request.
- metric correlation test: fire requests and assert `REQUEST_COUNT` labels include expected method/path/status tuples.

## Security & secrets
- Secrets must be injected via `envFrom: secretRef` or mounted files; no secrets in image or repo.
- Validate device session secrets decryption handles malformed values (already patched).
- Ensure k8s manifests set `runAsNonRoot` and drop Linux capabilities.

## Fail-open vs fail-closed decisions
- Fail-closed (deny) for auth/ownership checks; fail-open only for non-essential telemetry or optional read-only features.
- Document every fail-open: where the code degrades to "degraded" mode and what functionality is lost.

## Migration & scaling assumptions
- HPA targets set to realistic CPU/memory metrics for stateless backends; workers should be horizontally scalable but must be idempotent for job handling.
- Provide playbook steps to drain a node and verify no job duplication.

## Incident classification & runbook (brief)
- Sev-1: data loss, unauthorized access, production outage > 5 minutes.
- Sev-2: degraded critical functionality (queue backlog growth, delayed processing) > 15 minutes.
- Sev-3: partial feature regressions, non-critical telemetry issues.

Rollback guidance
- Prefer immediate rollback to prior immutable image tag when a release causes Sev-1 or repeated deployment failures.
- Keep last-known-good image tags and document `kubectl rollout undo deployment/<name>` steps.

## Known acceptable failure modes
- OTLP export latency or temporary trace loss (telemetry can retry and resume).
- Non-critical analytics ingestion outages.

## Next actionable changes (minimal code & tests)
1. Add `tests/test_probes.py` and `tests/test_redis_reconnect.py` (deterministic assertions).
2. Add worker shutdown integration test (spawn process, SIGTERM, assert graceful exit).
3. Add structured startup diagnostic endpoint `/startup/diagnostics` (read-only) returning service versions, probe statuses; must be read-only and not expose secrets.
4. Add small smoke script `tools/smoke_check.sh` for CI pre-deploy validation.

Would you like me to implement the tests `tests/test_probes.py` and `tests/test_redis_reconnect.py` now and add the smoke script?