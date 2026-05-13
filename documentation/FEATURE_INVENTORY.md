# TitleTrust Feature Inventory

This inventory is grounded in the current codebase, not a product brief. It maps the actual user-facing features, backend entrypoints, async paths, storage, and security boundaries implemented in the repository.

Primary anchors:
- Frontend app shell: [frontend/titletrust/lib/main.dart](frontend/titletrust/lib/main.dart)
- Flutter auth and request signing: [frontend/titletrust/lib/features/auth/presentation/auth_controller.dart](frontend/titletrust/lib/features/auth/presentation/auth_controller.dart), [frontend/titletrust/lib/core/network/dio_client.dart](frontend/titletrust/lib/core/network/dio_client.dart), [frontend/titletrust/lib/security/transport_security_service.dart](frontend/titletrust/lib/security/transport_security_service.dart)
- Backend app wiring: [backend/main.py](backend/main.py)
- Audit APIs: [backend/api/audit_router.py](backend/api/audit_router.py), [backend/services/audit_service.py](backend/services/audit_service.py), [backend/services/background_job_service.py](backend/services/background_job_service.py)
- Session/auth APIs: [backend/api/auth_router.py](backend/api/auth_router.py), [backend/services/device_session_service.py](backend/services/device_session_service.py), [backend/services/session_service.py](backend/services/session_service.py)
- Worker runtime: [backend/workers/runtime.py](backend/workers/runtime.py)

## 1) Authentication and App Entry

Purpose: bootstrap a Firebase-authenticated mobile client, gate first-run onboarding, and establish a signed device session before protected API calls.

Frontend entrypoint: [frontend/titletrust/lib/main.dart](frontend/titletrust/lib/main.dart), [frontend/titletrust/lib/features/auth/presentation/login_screen.dart](frontend/titletrust/lib/features/auth/presentation/login_screen.dart), [frontend/titletrust/lib/features/auth/presentation/auth_controller.dart](frontend/titletrust/lib/features/auth/presentation/auth_controller.dart)

Backend entrypoint: [backend/auth.py](backend/auth.py), [backend/api/auth_router.py](backend/api/auth_router.py)

Services involved:
- Flutter auth repository and controller
- Firebase Auth token validation in backend
- Device session registration and request-secret rotation
- Permission enforcement through [backend/core/authorization.py](backend/core/authorization.py)

Async jobs: none for sign-in itself

Storage involved:
- Firebase Auth user session on the client
- Secure storage for the user id, device session id, and request secret
- Firestore `device_sessions`, `memberships`, and `policies`

Telemetry involved:
- Frontend Crashlytics and Sentry in [frontend/titletrust/lib/telemetry/frontend_telemetry_service.dart](frontend/titletrust/lib/telemetry/frontend_telemetry_service.dart)
- Backend correlation and request latency in [backend/middleware/observability.py](backend/middleware/observability.py)

Security boundaries:
- Firebase ID token is the primary identity proof
- Device-bound request signature is a second factor for transport integrity
- Role and policy evaluation is enforced server-side on every protected route

User-facing behavior:
- First run shows onboarding once, then login
- Login is blocked until device biometrics succeed in [frontend/titletrust/lib/features/auth/presentation/auth_controller.dart](frontend/titletrust/lib/features/auth/presentation/auth_controller.dart)
- Success routes to the home shell

Failure behavior:
- Invalid or expired Firebase token returns 401
- Device auth denial stops sign-in locally
- Missing device-session secret or signature returns 400/401 from backend

Scaling considerations:
- Firebase handles identity scale
- Device-session registration is write-heavy but narrow in scope
- Request signing is stateless on the client and verification is O(1) per request

## 2) Onboarding

Purpose: explain the app’s land-verification workflows once per installation.

Frontend entrypoint: [frontend/titletrust/lib/features/onboarding/presentation/onboarding_screen.dart](frontend/titletrust/lib/features/onboarding/presentation/onboarding_screen.dart)

Backend entrypoint: none

Services involved:
- SharedPreferences onboarding flag
- Adaptive scaffold/navigation shell

Async jobs: none

Storage involved:
- Local `has_seen_onboarding` flag in SharedPreferences

Telemetry involved:
- None beyond app startup telemetry already initialized in `main.dart`

Security boundaries:
- Purely local UI state; no backend trust required

Failure behavior:
- Missing preference defaults to showing onboarding

Scaling considerations:
- No server cost

## 3) Device Session Registration and Signed Transport

Purpose: bind the mobile client to a device-scoped secret and sign all protected requests with a per-device HMAC.

Frontend entrypoint: [frontend/titletrust/lib/core/services/device_session_service.dart](frontend/titletrust/lib/core/services/device_session_service.dart), [frontend/titletrust/lib/security/transport_security_service.dart](frontend/titletrust/lib/security/transport_security_service.dart), [frontend/titletrust/lib/core/network/auth_interceptor.dart](frontend/titletrust/lib/core/network/auth_interceptor.dart)

Backend entrypoint: [backend/api/auth_router.py](backend/api/auth_router.py), [backend/security/request_signing.py](backend/security/request_signing.py), [backend/services/device_session_service.py](backend/services/device_session_service.py)

Services involved:
- Device session service on mobile and backend
- Request-signing interceptor in Dio
- Device secret protector in [backend/security/device_session_secrets.py](backend/security/device_session_secrets.py)

Async jobs: none

Storage involved:
- Mobile secure storage keeps `device_session_id` and `frontend_request_secret`
- Firestore `device_sessions` stores encrypted current and previous signing secrets

Telemetry involved:
- Correlation id is propagated in request headers and response headers
- Sign/verify failures are visible in backend logs and audit traces

Security boundaries:
- The secret never leaves the client in plaintext except during registration and signed request construction
- Backend accepts current and previous secret during rotation
- Timestamp freshness window is 5 minutes in [backend/security/request_signing.py](backend/security/request_signing.py)

Failure behavior:
- Bad signature or stale timestamp returns 401
- Missing device-session id returns 400 or 401 depending on the path
- Revoked device session returns 401

Scaling considerations:
- Verification uses Firestore lookups but no server-side crypto state beyond the stored secret
- Rotation support avoids hard failures during secret rollovers

## 4) Forensic Document Audit

Purpose: upload title-deed documents and run AI-assisted forensic analysis.

Frontend entrypoint: [frontend/titletrust/lib/features/forensic/presentation/forensic_screen.dart](frontend/titletrust/lib/features/forensic/presentation/forensic_screen.dart), [frontend/titletrust/lib/features/forensic/presentation/forensic_controller.dart](frontend/titletrust/lib/features/forensic/presentation/forensic_controller.dart), [frontend/titletrust/lib/features/forensic/data/forensic_repository.dart](frontend/titletrust/lib/features/forensic/data/forensic_repository.dart)

Backend entrypoint: [backend/api/audit_router.py](backend/api/audit_router.py), [backend/services/audit_service.py](backend/services/audit_service.py), [backend/services/background_job_service.py](backend/services/background_job_service.py), [backend/forensic_engine.py](backend/forensic_engine.py)

Services involved:
- Flutter file picker and repository
- Backend upload validation and temp-file persistence
- Forensic engine powered by Gemini via `perform_forensic_audit`
- Worker runtime when queue mode is enabled

Async jobs:
- In inline mode, the request can complete in-process
- In Redis mode, [backend/services/background_job_service.py](backend/services/background_job_service.py) enqueues a `forensic` job and [backend/workers/runtime.py](backend/workers/runtime.py) executes it

Storage involved:
- Temp filesystem files during analysis
- Firestore `jobs` and `audit_events`
- Dead-letter storage for unrecoverable job failures

Telemetry involved:
- Request correlation, job events, worker heartbeats, Prometheus counters/histograms

Security boundaries:
- File suffix and size validation are enforced before persistence
- Uploaded files are treated as data only and deleted after processing
- User/org access is checked by permission gates and job ownership checks

Failure behavior:
- Unsupported type or oversize upload returns 400
- Gemini or worker failures retry, then dead-letter
- Client polling throws a network error on failed or cancelled jobs

Scaling considerations:
- Upload handling is bounded by file size and temp disk
- Worker autoscaling is based on CPU/memory and queue depth
- Polling is client-driven and should remain bounded by 60 attempts at 2s intervals in the repositories

## 5) Geospatial Reality Check

Purpose: capture site imagery, compare it with satellite or map context, and return a geospatial risk judgment.

Frontend entrypoint: [frontend/titletrust/lib/features/geospatial/presentation/geospatial_screen.dart](frontend/titletrust/lib/features/geospatial/presentation/geospatial_screen.dart), [frontend/titletrust/lib/features/geospatial/presentation/geospatial_controller.dart](frontend/titletrust/lib/features/geospatial/presentation/geospatial_controller.dart), [frontend/titletrust/lib/features/geospatial/data/geospatial_repository.dart](frontend/titletrust/lib/features/geospatial/data/geospatial_repository.dart)

Backend entrypoint: [backend/api/audit_router.py](backend/api/audit_router.py), [backend/services/audit_service.py](backend/services/audit_service.py), [backend/geospatial_engine.py](backend/geospatial_engine.py)

Services involved:
- Camera and permission flow in Flutter
- Geolocation capture through `Geolocator`
- Geospatial verification agent and live token generation
- Job queue or inline processing depending on configuration

Async jobs:
- `geospatial` job in Redis queue or background tasks
- Live-token flow is synchronous but emits an ephemeral Gemini token

Storage involved:
- Temporary files for captured imagery
- Firestore job records and audit events

Telemetry involved:
- Correlation ids, backend logs, and job metrics

Security boundaries:
- Latitude/longitude are schema-validated
- Media files are size- and suffix-validated
- Live API token is constrained to a specific session and context

Failure behavior:
- Missing camera/location permission prevents capture
- Gemini or map lookup failure is surfaced as an error response
- Polling stops on failed or cancelled jobs

Scaling considerations:
- Geospatial work is slower and more model-heavy than document uploads
- This flow benefits from worker isolation and bounded retries

## 6) Marathon Investigation Flow

Purpose: start a recursive investigation session and keep stepping it through Cloud Tasks or local background execution.

Frontend entrypoint: [frontend/titletrust/lib/features/investigation/presentation/marathon_start_screen.dart](frontend/titletrust/lib/features/investigation/presentation/marathon_start_screen.dart), [frontend/titletrust/lib/features/investigation/data/marathon_service.dart](frontend/titletrust/lib/features/investigation/data/marathon_service.dart)

Backend entrypoint: [backend/api/audit_router.py](backend/api/audit_router.py), [backend/services/session_service.py](backend/services/session_service.py), [backend/agent/marathon_loop.py](backend/agent/marathon_loop.py), [backend/services/cloud_tasks.py](backend/services/cloud_tasks.py)

Services involved:
- File upload and investigation bootstrap on the client
- Session repository and audit-event repository
- Recursive agent loop and Cloud Tasks scheduler

Async jobs:
- Initial bootstrap is a background task
- Subsequent ticks are scheduled by Cloud Tasks

Storage involved:
- Firestore `sessions`, `audit_events`, and `idempotency_keys`
- Temp file storage for the uploaded image

Telemetry involved:
- Audit events record bootstrap, tick, retry, and completion milestones
- Cloud Tasks schedule is observable from backend logs

Security boundaries:
- Session ownership is checked on status, tick, and retry
- Idempotency key prevents duplicate investigation creation for the same caller

Failure behavior:
- Bootstrap failure marks the session failed and records an audit event
- Retry is only allowed from failed, waiting, or queued states

Scaling considerations:
- Cloud Tasks offloads recursive agent work from the API process
- The state machine is persisted so work can resume after worker restarts

## 7) Job Tracking, Polling, and Report View

Purpose: keep the UI synchronized with session or job state and render the final report.

Frontend entrypoint: [frontend/titletrust/lib/features/investigation/presentation/investigation_screen.dart](frontend/titletrust/lib/features/investigation/presentation/investigation_screen.dart), [frontend/titletrust/lib/features/investigation/presentation/investigation_report_view.dart](frontend/titletrust/lib/features/investigation/presentation/investigation_report_view.dart), [frontend/titletrust/lib/features/investigation/presentation/widgets/titbits_widget.dart](frontend/titletrust/lib/features/investigation/presentation/widgets/titbits_widget.dart), [frontend/titletrust/lib/core/services/job_state_service.dart](frontend/titletrust/lib/core/services/job_state_service.dart)

Backend entrypoint: [backend/api/audit_router.py](backend/api/audit_router.py), [backend/services/session_service.py](backend/services/session_service.py), [backend/services/titbits_service.py](backend/services/titbits_service.py)

Services involved:
- Firestore stream of session docs on the client
- Titbits service for lightweight educational content
- Job-state persistence to survive app restarts

Async jobs: none directly; this is a read path on top of async investigation state

Storage involved:
- Firestore session document is the source of truth for logs and findings
- Secure storage remembers the active job id

Telemetry involved:
- Session logs are effectively a live audit trail

Security boundaries:
- Report visibility is gated by the same auth/policy checks as the session itself

Failure behavior:
- Missing session doc yields a silent empty tracker or error state
- Titbits falls back to a local list if Gemini is unavailable

Scaling considerations:
- Client-side streaming avoids the need for explicit websocket infra
- Polling/streaming pressure shifts to Firestore rather than the API server

## 8) Notifications and Background Delivery

Purpose: preserve user awareness when jobs advance in the background.

Frontend entrypoint: [frontend/titletrust/lib/core/services/notification_service.dart](frontend/titletrust/lib/core/services/notification_service.dart)

Backend entrypoint: [backend/services/notification.py](backend/services/notification.py)

Services involved:
- Firebase Messaging on the client
- Mock FCM sender on the backend side of the repo

Async jobs: none

Storage involved:
- FCM token is persisted in Firestore `users/{uid}`

Telemetry involved:
- Notification initialization is visible in app startup logs

Security boundaries:
- Token save happens only after Firebase auth is active

Failure behavior:
- Permission denial leaves notifications disabled rather than fatal
- Backend sender is still a mock in the current codebase

Scaling considerations:
- Push notifications are externally scaled by Firebase

## 9) Titbits / Educational Facts

Purpose: generate short domain facts for the investigation UI.

Frontend entrypoint: [frontend/titletrust/lib/features/investigation/presentation/widgets/titbits_widget.dart](frontend/titletrust/lib/features/investigation/presentation/widgets/titbits_widget.dart)

Backend entrypoint: [backend/services/titbits_service.py](backend/services/titbits_service.py), [backend/api/audit_router.py](backend/api/audit_router.py)

Services involved:
- Optional Gemini generation with a deterministic fallback list

Async jobs: none

Storage involved: none

Telemetry involved:
- Failures are logged; the UI simply falls back

Security boundaries:
- Output is low-risk informational content only

Failure behavior:
- If Gemini is unavailable, a local default list is used

Scaling considerations:
- Cheap and cacheable

## 10) Abuse Detection and Rate Limiting

Purpose: classify abusive traffic, attach observable headers, and throttle hot principals.

Backend entrypoint: [backend/middleware/adaptive_protection.py](backend/middleware/adaptive_protection.py), [backend/middleware/rate_limit.py](backend/middleware/rate_limit.py), [backend/security/abuse_detection.py](backend/security/abuse_detection.py), [backend/security/anomaly_detection.py](backend/security/anomaly_detection.py)

Services involved:
- Request fingerprinting
- Threat intelligence store
- Session anomaly scoring
- Redis-backed rate limit store

Async jobs: none

Storage involved:
- In-memory threat intel and observations
- Redis for rate limiting and worker queue control

Telemetry involved:
- Prometheus counters and histograms for abuse score and block rate

Security boundaries:
- The middleware can block before business logic runs
- Rate limiting ignores user-supplied identity headers and keys on auth/device principal instead

Failure behavior:
- Blocked requests return 403 with abuse headers
- Rate limit exhaustion returns 429 with Retry-After

Scaling considerations:
- Abuse evaluation is synchronous but lightweight enough for edge enforcement

## 11) Back-end Session Security and Token Rotation

Purpose: maintain authenticated session state with token rotation, replay detection, and revocation.

Backend entrypoint: [backend/services/session_security_service.py](backend/services/session_security_service.py), [backend/repositories/token_repository.py](backend/repositories/token_repository.py), [backend/domain/session_models.py](backend/domain/session_models.py)

Services involved:
- Firestore-backed session and token repositories
- Security events emitted for session creation, rotation, and revocation

Async jobs: none

Storage involved:
- Firestore `sessions`, `security_events`, and refresh-token collection

Telemetry involved:
- Security events are the durable audit trail

Security boundaries:
- Refresh tokens are hashed at rest
- Session/device binding and replay detection are encoded in domain models

Failure behavior:
- Invalid tokens, replay attempts, or revoked families are rejected

Scaling considerations:
- Token family lookups are query-based and should remain indexed

## 12) User/Role/Policy Enforcement

Purpose: map Firebase identity claims to org membership and permissions.

Backend entrypoint: [backend/core/authorization.py](backend/core/authorization.py), [backend/services/policy_service.py](backend/services/policy_service.py), [backend/repositories/policy_repository.py](backend/repositories/policy_repository.py)

Services involved:
- Role hierarchy expansion
- Policy caching with short TTL
- Membership upsert during permission checks

Async jobs: none

Storage involved:
- Firestore policies and memberships

Telemetry involved:
- Permission denials are logged

Security boundaries:
- Every protected route relies on server-side policy evaluation, not client claims alone

Failure behavior:
- Missing membership or no matching allow policy returns 403

Scaling considerations:
- Short-lived caches reduce Firestore reads without making authorization state stale for long

## Summary Table

| Feature | Frontend | Backend | Async | Storage | Security boundary |
|---|---|---|---|---|---|
| Auth/onboarding | Flutter auth shell | Firebase auth + device sessions | No | Secure storage, Firestore | Token + request signature |
| Forensic audit | Document upload screen | Audit service, worker runtime | Yes | Temp files, jobs, audit events | File validation, ownership |
| Geospatial check | Camera + GPS screen | Audit service, geospatial engine | Yes | Temp files, jobs | Coord validation, token scope |
| Marathon investigation | Start screen, live tracker | Session service, Cloud Tasks | Yes | Sessions, idempotency keys | Session ownership |
| Titbits | Investigation UI | Titbits service | No | None | Low-risk content |
| Abuse protection | Implicit | Middleware + security engines | No | Redis, in-memory intel | Edge block/quarantine |
