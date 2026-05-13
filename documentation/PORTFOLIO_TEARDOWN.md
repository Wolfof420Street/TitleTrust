# TitleTrust Portfolio Teardown

This is the staff-engineer-style readout of what is technically interesting in the repository, what was actually solved, and where the remaining risk sits.

## What Makes the Repository Interesting

The interesting part is not that it is a Flutter app with a FastAPI backend. It is that the codebase combines several non-trivial systems concerns in one product:
- Firebase-backed identity
- device-bound request integrity
- permission and policy evaluation
- queue-backed AI workflows
- recursive long-running investigations
- live Firestore-driven state updates
- observability and abuse protection at the edge
- worker resilience with retries and dead-letter handling

That combination is rare in a small codebase and gives the repo a real systems-engineering shape.

## Engineering Problems It Solves

1. It separates identity from transport integrity.
- Firebase says who the user is.
- The device secret proves the request came from a registered client installation.

2. It makes long-running AI work resumable.
- Session state is persisted in Firestore.
- Cloud Tasks or Redis workers continue the workflow.

3. It hardens the API edge.
- Abuse scoring runs before route handlers.
- Rate limits are principal-aware.
- Correlation ids are propagated.

4. It makes output observable.
- Jobs, audit events, and request traces are all persisted or emitted.

5. It supports graceful degradation.
- Missing telemetry does not crash the app.
- Redis is optional in local mode.
- Titbits and notifications have fallbacks.

## Why the Architecture Matters

The architecture matters because it is not just a CRUD backend:
- investigation state is a workflow, not a single request
- documents and geospatial evidence are model inputs, not static uploads
- security boundaries are explicit and layered
- the runtime is split between API, queue, worker, and telemetry planes

That is the difference between a demo and a production-shaped system.

## Production Concerns Addressed

Addressed in code:
- auth verification
- permission enforcement
- signature freshness and tamper detection
- file size and type validation
- dead-letter handling for failed jobs
- worker heartbeats
- correlation ids and request latency
- abuse block/challenge/quarantine behavior
- CI security scanning and SBOM generation

Partially addressed:
- notification delivery is scaffolded more than fully productized
- some cloud integrations degrade to local/no-op behavior when absent
- live token generation is constrained, but the product surface is still bounded by external Gemini availability

## Operational Maturity

Strong signs:
- Docker Compose runtime
- Kubernetes manifests
- HPA for backend and worker separately
- healthcheck entrypoints
- Prometheus metrics
- OTLP tracing hooks
- dashboards and alerting rules
- runbooks for abuse response

What that says:
- the repo was built with deployment and incident response in mind, not just feature shipping.

## Security Maturity

Strong signs:
- Firebase token verification
- role and permission abstraction
- device-session secret rotation
- HMAC-signed requests
- request timestamp freshness checks
- rate limiting
- adaptive abuse detection
- threat-intelligence signals
- secret hashing and encryption at rest
- security validation workflow in CI

Residual gaps:
- no hardware attestation of device trust
- telemetry cannot be used as a security source of truth
- in-memory threat intelligence is not a durable SOC system
- some cloud-dependent paths still degrade to local fallback behavior

## Scaling Considerations

The codebase already hints at the right scaling split:
- API is kept thin and fast
- worker scales independently
- Firestore holds durable state
- Redis handles queueing and limiting
- Cloud Tasks drives recursive investigation ticks

That is the right shape for a model-heavy workflow product.

## Systems-Thinking Decisions That Stand Out

- The app treats the mobile device as a semi-trusted trust anchor, not as a passive client.
- The backend uses audit-event sequencing and hash chaining rather than raw logs alone.
- The worker runtime has explicit circuit breakers, poison-pill detection, and backoff.
- The UI uses Firestore streams for live state rather than forcing the API to maintain websocket sessions.
- The repo keeps a separation between auth, authorization, request integrity, and abuse defense.

Those choices are the difference between a coherent system and a collection of features.

## Honest Residual Risk Analysis

Validated surfaces:
- auth token verification
- request signature verification
- rate limiting behavior
- adaptive abuse middleware behavior
- device-session secret handling
- queue and worker retry/dead-letter logic
- CI security checks

Partially validated surfaces:
- end-to-end mobile-to-backend happy paths
- geospatial and forensic model quality
- Cloud Tasks scheduling in real cloud runtime
- notification delivery beyond token storage
- live token generation in a real Gemini deployment

Unvalidated runtime assumptions:
- whether all cloud credentials are available and correct in every environment
- whether the worker queue will always have the same behavior under load as in local mode
- whether Firestore stream latency is acceptable at scale
- whether client secure storage survives all reinstall/upgrade edge cases

Deployment gaps:
- the repo includes infrastructure, but not a full production deployment proof
- cloud service configuration still matters materially

Concurrency gaps:
- multiple workers, retries, and queue cancellations are handled, but any distributed job system still needs real-world soak testing
- the code is resilient, but not formally proven under every race condition

Bottom line:
- this is a serious, production-shaped engineering system, but not a fully certified platform. The docs should describe it that way.
