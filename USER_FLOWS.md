# TitleTrust User Flows

This document traces the user journeys actually implemented in the app. It focuses on the front-end state transitions, network calls, backend control flow, queue behavior, and the visible outcome.

Key client anchors:
- App shell and startup: [frontend/titletrust/lib/main.dart](frontend/titletrust/lib/main.dart)
- Auth flow: [frontend/titletrust/lib/features/auth/presentation/auth_controller.dart](frontend/titletrust/lib/features/auth/presentation/auth_controller.dart), [frontend/titletrust/lib/features/auth/presentation/login_screen.dart](frontend/titletrust/lib/features/auth/presentation/login_screen.dart)
- Forensic flow: [frontend/titletrust/lib/features/forensic/presentation/forensic_controller.dart](frontend/titletrust/lib/features/forensic/presentation/forensic_controller.dart), [frontend/titletrust/lib/features/forensic/data/forensic_repository.dart](frontend/titletrust/lib/features/forensic/data/forensic_repository.dart)
- Geospatial flow: [frontend/titletrust/lib/features/geospatial/presentation/geospatial_controller.dart](frontend/titletrust/lib/features/geospatial/presentation/geospatial_controller.dart), [frontend/titletrust/lib/features/geospatial/data/geospatial_repository.dart](frontend/titletrust/lib/features/geospatial/data/geospatial_repository.dart)
- Marathon flow: [frontend/titletrust/lib/features/investigation/presentation/marathon_start_screen.dart](frontend/titletrust/lib/features/investigation/presentation/marathon_start_screen.dart), [frontend/titletrust/lib/features/investigation/data/marathon_service.dart](frontend/titletrust/lib/features/investigation/data/marathon_service.dart)
- Live job view: [frontend/titletrust/lib/features/investigation/presentation/investigation_screen.dart](frontend/titletrust/lib/features/investigation/presentation/investigation_screen.dart), [frontend/titletrust/lib/features/investigation/data/investigation_repository.dart](frontend/titletrust/lib/features/investigation/data/investigation_repository.dart)

Backend anchors:
- API wiring: [backend/main.py](backend/main.py)
- Auth and device sessions: [backend/api/auth_router.py](backend/api/auth_router.py), [backend/auth.py](backend/auth.py)
- Audit/session APIs: [backend/api/audit_router.py](backend/api/audit_router.py), [backend/services/session_service.py](backend/services/session_service.py), [backend/services/background_job_service.py](backend/services/background_job_service.py)
- Worker: [backend/workers/runtime.py](backend/workers/runtime.py)

## 1) Onboarding

1. Trigger
- App launches and `main()` checks SharedPreferences for `has_seen_onboarding`.

2. User action
- First-time users swipe through onboarding pages and tap Skip or Get Started.

3. Frontend flow
- [frontend/titletrust/lib/features/onboarding/presentation/onboarding_screen.dart](frontend/titletrust/lib/features/onboarding/presentation/onboarding_screen.dart) renders a PageView and writes `has_seen_onboarding=true`.
- Navigation returns to `AuthGuard`.

4. Riverpod/provider state flow
- No server state; the flow only flips local navigation state.

5. Network flow
- None.

6. Middleware/security flow
- None.

7. Backend service flow
- None.

8. Queue/worker flow
- None.

9. Database interactions
- SharedPreferences only.

10. Telemetry/tracing flow
- Startup telemetry is already initialized in `main.dart` before the screen appears.

11. Notifications/realtime updates
- None.

12. Failure handling
- If the preference is missing or unreadable, the app defaults to showing onboarding.

13. Recovery behavior
- User can always skip or complete onboarding and continue.

14. Final outcome
- User lands on the auth gate.

## 2) Login and Authentication

1. Trigger
- User taps Sign in with Google on [LoginScreen](frontend/titletrust/lib/features/auth/presentation/login_screen.dart).

2. User action
- Device biometrics unlock the session first, then Google/Firebase sign-in proceeds.

3. Frontend flow
- `AuthController.signInWithGoogle()` sets loading state.
- [frontend/titletrust/lib/security/device_security_service.dart](frontend/titletrust/lib/security/device_security_service.dart) is used to gate sign-in behind biometric unlock.
- [frontend/titletrust/lib/features/auth/data/auth_repository.dart](frontend/titletrust/lib/features/auth/data/auth_repository.dart) performs Google Sign-In and Firebase Auth.
- On success the device session is registered.

4. Riverpod/provider state flow
- `authControllerProvider` moves from idle to loading to resolved or failed.
- `authStateProvider` streams Firebase auth state changes and drives the auth guard.

5. Network flow
- Google/Firebase sign-in happens out of process.
- The first backend request later carries `Authorization: Bearer <firebase_id_token>` from [frontend/titletrust/lib/core/network/auth_interceptor.dart](frontend/titletrust/lib/core/network/auth_interceptor.dart).

6. Middleware/security flow
- Backend token verification occurs in [backend/auth.py](backend/auth.py).
- Permission checks are layered on top through [backend/core/authorization.py](backend/core/authorization.py).

7. Backend service flow
- The backend does not create a custom auth session here; it trusts Firebase and then binds the device session on the next call.

8. Queue/worker flow
- None.

9. Database interactions
- Client stores the user id locally.
- Backend membership and policy records are upserted when permissions are evaluated.

10. Telemetry/tracing flow
- Auth failures are recorded by the frontend telemetry service and backend logs.

11. Notifications/realtime updates
- None.

12. Failure handling
- Biometrics denied: local failure, no backend call.
- Firebase error: auth state reports error and UI shows retry.
- Backend auth failure: 401 or 503 depending on cause.

13. Recovery behavior
- User can retry sign-in; the controller clears loading state and surfaces the error.

14. Final outcome
- AuthGuard switches from LoginScreen to HomeScreen.

## 3) Device Session Registration

1. Trigger
- Sign-in succeeds and the app calls `DeviceSessionService.register()`.

2. User action
- None beyond sign-in.

3. Frontend flow
- The client reuses or generates a device session id and request secret in secure storage.
- [frontend/titletrust/lib/security/transport_security_service.dart](frontend/titletrust/lib/security/transport_security_service.dart) generates a 256-bit secret.
- [frontend/titletrust/lib/core/services/device_session_service.dart](frontend/titletrust/lib/core/services/device_session_service.dart) posts session metadata to `/auth/device-sessions`.

4. Riverpod/provider state flow
- The registration happens inside the auth controller’s async flow.

5. Network flow
- Request body contains session id, device id, platform, app version, and request secret.
- The request is signed by [frontend/titletrust/lib/core/network/dio_client.dart](frontend/titletrust/lib/core/network/dio_client.dart) and [frontend/titletrust/lib/security/transport_security_service.dart](frontend/titletrust/lib/security/transport_security_service.dart).

6. Middleware/security flow
- Backend validates Firebase auth, request timestamp freshness, and HMAC signature in [backend/api/auth_router.py](backend/api/auth_router.py).

7. Backend service flow
- [backend/services/device_session_service.py](backend/services/device_session_service.py) encrypts the secret, stores its fingerprint, and records rotation history if the secret changes.

8. Queue/worker flow
- None.

9. Database interactions
- Firestore `device_sessions` document is created or updated.

10. Telemetry/tracing flow
- Correlation id and request signature headers allow request-level tracing and audit correlation.

11. Notifications/realtime updates
- None.

12. Failure handling
- Signature mismatch or stale timestamp returns 401.
- Missing organization context returns 400.

13. Recovery behavior
- The client can retry registration after regenerating or reusing its secret.

14. Final outcome
- The device becomes a registered trust anchor for future signed requests.

## 4) Forensic Upload and Polling

1. Trigger
- User opens the forensic audit screen and selects documents.

2. User action
- Select one or more PDFs/images and submit.

3. Frontend flow
- [frontend/titletrust/lib/features/forensic/presentation/forensic_controller.dart](frontend/titletrust/lib/features/forensic/presentation/forensic_controller.dart) uses FilePicker.
- [frontend/titletrust/lib/features/forensic/data/forensic_repository.dart](frontend/titletrust/lib/features/forensic/data/forensic_repository.dart) posts multipart form data to `/audit/forensic`.
- The repository polls `/audit/jobs/{jobId}` until completion.

4. Riverpod/provider state flow
- Controller switches to loading and then resolves to `AuditResponse`.

5. Network flow
- POST /audit/forensic -> accepted job id.
- Repeated GET /audit/jobs/{jobId} calls until the job reaches a terminal state.

6. Middleware/security flow
- Bearer auth, request signing, rate limiting, and adaptive abuse protection all wrap the request.

7. Backend service flow
- [backend/services/background_job_service.py](backend/services/background_job_service.py) validates file size and suffix, stores temp files, writes job state, and dispatches work.
- [backend/workers/runtime.py](backend/workers/runtime.py) handles processing when Redis queue mode is enabled.

8. Queue/worker flow
- The job is queued or executed inline, then retried or dead-lettered on failure.

9. Database interactions
- Firestore `jobs` and `audit_events` are updated.

10. Telemetry/tracing flow
- Job enqueue, start, retry, completion, and dead-letter events are recorded.

11. Notifications/realtime updates
- UI is updated by polling rather than push for this flow.

12. Failure handling
- Client sees a network error if the job fails, cancels, or times out.
- Backend can retry with exponential backoff before dead-lettering.

13. Recovery behavior
- The user can re-submit or cancel and restart a fresh job.

14. Final outcome
- The user receives a flagged or completed audit response with findings.

## 5) Geospatial Reality Check

1. Trigger
- User opens the geospatial screen and taps VERIFY REALITY.

2. User action
- The app captures a camera frame after permission prompts.

3. Frontend flow
- [frontend/titletrust/lib/features/geospatial/presentation/geospatial_screen.dart](frontend/titletrust/lib/features/geospatial/presentation/geospatial_screen.dart) initializes camera and requests permissions.
- [frontend/titletrust/lib/features/geospatial/presentation/geospatial_controller.dart](frontend/titletrust/lib/features/geospatial/presentation/geospatial_controller.dart) gets location and calls the repository.
- [frontend/titletrust/lib/features/geospatial/data/geospatial_repository.dart](frontend/titletrust/lib/features/geospatial/data/geospatial_repository.dart) posts to `/audit/geospatial` and polls `/audit/jobs/{jobId}`.

4. Riverpod/provider state flow
- The controller transitions from null to loading to a completed `GeoCheck`.

5. Network flow
- Multipart upload includes lat, lng, and the captured image.
- The repository polls until the backend job becomes terminal.

6. Middleware/security flow
- Standard auth, request signing, abuse scoring, and rate limiting apply.

7. Backend service flow
- [backend/services/audit_service.py](backend/services/audit_service.py) validates and temporarily stores the media file, then invokes the geospatial verifier.
- [backend/geospatial_engine.py](backend/geospatial_engine.py) talks to Gemini and the Maps/Ground Truth toolchain.

8. Queue/worker flow
- May be inline or queued, depending on runtime mode.

9. Database interactions
- Job state and audit events are persisted in Firestore.

10. Telemetry/tracing flow
- Correlation and request timing are attached to the request and job trail.

11. Notifications/realtime updates
- The UI updates once the job completes; there is no dedicated websocket channel.

12. Failure handling
- Permission denial blocks capture locally.
- Missing or invalid coordinates are rejected by backend validation.
- Polling times out after a bounded number of attempts.

13. Recovery behavior
- The user can tap Check Another Location and retry.

14. Final outcome
- The app renders a risk verdict and satellite analysis summary.

## 6) Marathon Investigation

1. Trigger
- User selects a title image and taps START INVESTIGATION.

2. User action
- The user picks a local file from the gallery.

3. Frontend flow
- [frontend/titletrust/lib/features/investigation/presentation/marathon_start_screen.dart](frontend/titletrust/lib/features/investigation/presentation/marathon_start_screen.dart) uploads the file through [frontend/titletrust/lib/features/investigation/data/marathon_service.dart](frontend/titletrust/lib/features/investigation/data/marathon_service.dart).
- The returned session id is stored through [frontend/titletrust/lib/core/services/job_state_service.dart](frontend/titletrust/lib/core/services/job_state_service.dart).
- Navigation switches to [frontend/titletrust/lib/features/investigation/presentation/investigation_screen.dart](frontend/titletrust/lib/features/investigation/presentation/investigation_screen.dart).

4. Riverpod/provider state flow
- The screen is mostly imperative; the live session stream is sourced from Firestore via `investigationSessionProvider`.

5. Network flow
- POST /audit/start creates the session and returns a session id.
- The live screen reads Firestore session snapshots rather than repeatedly hitting the REST API.

6. Middleware/security flow
- Auth, signature, and rate limiting apply to the bootstrap request.

7. Backend service flow
- [backend/services/session_service.py](backend/services/session_service.py) persists the session and schedules the first bootstrap step.
- [backend/agent/marathon_loop.py](backend/agent/marathon_loop.py) advances the recursive decision loop.
- [backend/services/cloud_tasks.py](backend/services/cloud_tasks.py) schedules the next tick when the agent remains active.

8. Queue/worker flow
- Cloud Tasks or the local background task continues the chain.

9. Database interactions
- Firestore `sessions`, `audit_events`, and `idempotency_keys` are the durable state.

10. Telemetry/tracing flow
- Each tick appends audit events and can emit structured logs.

11. Notifications/realtime updates
- The UI updates from Firestore session documents; the current active job id is also restored locally.

12. Failure handling
- Bootstrap failure marks the session failed and surfaces an error on the tracker screen.
- The start screen reports a generic failure and keeps the app usable.

13. Recovery behavior
- Retry is allowed from the backend when the session is failed, waiting, or queued.

14. Final outcome
- The user sees either a completed report or an in-progress agent log stream.

## 7) Logout and Device Revocation

1. Trigger
- User signs out from the app.

2. User action
- Tap sign out or force logout after a session policy event.

3. Frontend flow
- `AuthController.signOut()` revokes the device session and clears Firebase auth.
- Session state is removed from secure storage by [frontend/titletrust/lib/resilience/session_resilience_service.dart](frontend/titletrust/lib/resilience/session_resilience_service.dart) when forced logout is propagated.

4. Riverpod/provider state flow
- Auth state falls back to null; the guard returns LoginScreen.

5. Network flow
- POST /auth/device-sessions/{session_id}/revoke is signed and authenticated.

6. Middleware/security flow
- Backend verifies ownership of the session before revocation.

7. Backend service flow
- The device session record is marked revoked and its secret fields are deleted.

8. Queue/worker flow
- None.

9. Database interactions
- Firestore `device_sessions` is updated in place.

10. Telemetry/tracing flow
- Revocation is an auditable security event.

11. Notifications/realtime updates
- No push notification is required; the UI state is enough.

12. Failure handling
- A missing session id is a no-op on the client.
- Backend rejects revocation if the session does not belong to the user.

13. Recovery behavior
- The user can sign in again and create a fresh device session.

14. Final outcome
- The client is returned to an unauthenticated state.

## 8) Rate Limit and Abuse Challenge

1. Trigger
- Repeated or suspicious requests hit the backend edge.

2. User action
- The user may be doing legitimate high-volume work or a bot-like burst.

3. Frontend flow
- The app receives 429 or 403 responses and surfaces a generic failure through the network executor.

4. Riverpod/provider state flow
- Feature controllers surface the error from the network layer.

5. Network flow
- The request never reaches the business handler if blocked by middleware or rate limiter.

6. Middleware/security flow
- [backend/middleware/adaptive_protection.py](backend/middleware/adaptive_protection.py) can block, quarantine, challenge, or throttle.
- [backend/middleware/rate_limit.py](backend/middleware/rate_limit.py) enforces a per-principal, per-path window.

7. Backend service flow
- No service executes when the request is rejected at the edge.

8. Queue/worker flow
- None.

9. Database interactions
- The edge counters and abuse signals may still be recorded in metrics or in-memory threat intel.

10. Telemetry/tracing flow
- Abuse action and score are exposed in headers and metrics.

11. Notifications/realtime updates
- None.

12. Failure handling
- 403 for blocked abuse, 429 for rate limit, both with Retry-After where applicable.

13. Recovery behavior
- The client can retry after cooldown; if the principal remains suspicious the challenge/quarantine may persist.

14. Final outcome
- Either the request is allowed through or it is denied before application logic runs.
