# TitleTrust Security Boundaries

This document maps the trust model implemented in the codebase. It distinguishes between authenticated identity, device trust, queue trust, telemetry trust, and the remaining residual risks.

Anchors:
- Identity and auth: [backend/auth.py](backend/auth.py), [backend/core/authorization.py](backend/core/authorization.py)
- Device sessions: [backend/api/auth_router.py](backend/api/auth_router.py), [backend/services/device_session_service.py](backend/services/device_session_service.py), [backend/security/request_signing.py](backend/security/request_signing.py)
- Abuse and anomaly detection: [backend/middleware/adaptive_protection.py](backend/middleware/adaptive_protection.py), [backend/security/abuse_detection.py](backend/security/abuse_detection.py), [backend/security/anomaly_detection.py](backend/security/anomaly_detection.py)
- Queue and worker trust: [backend/queues/redis_queue.py](backend/queues/redis_queue.py), [backend/workers/runtime.py](backend/workers/runtime.py)
- Frontend secure storage and transport: [frontend/titletrust/lib/security/transport_security_service.dart](frontend/titletrust/lib/security/transport_security_service.dart), [frontend/titletrust/lib/core/services/device_session_service.dart](frontend/titletrust/lib/core/services/device_session_service.dart)

## 1) Trust Zones

### Zone A: Mobile client
- Untrusted by default.
- Holds Firebase user credentials, device-session id, and request secret in secure storage.
- Must assume local compromise is possible.

### Zone B: Transport edge
- TLS protects the channel, but the backend does not rely on TLS alone.
- Request signatures and timestamp checks protect request integrity and replay freshness.

### Zone C: Backend API
- Semi-trusted application boundary.
- Accepts verified identity and request-signing input, then enforces policy and ownership checks.

### Zone D: Queue and workers
- Internal but still not fully trusted.
- Worker payloads are validated, retried, and dead-lettered.

### Zone E: Firestore and cloud services
- Trusted for availability, but not trusted for caller intent.
- Must be accessed only through repository and service boundaries.

### Zone F: Telemetry systems
- Observability data is useful but not authoritative for authorization decisions.

## 2) Identity Boundary

Firebase ID tokens are the primary identity proof.

Implementation:
- [backend/auth.py](backend/auth.py) verifies the Firebase token with Firebase Admin.
- [backend/core/authorization.py](backend/core/authorization.py) expands roles and checks permissions.

Trust assumption:
- The backend trusts Firebase to validate the token signature and expiry.

Why this is safe enough here:
- The backend still performs its own permission and ownership checks after authentication.

Residual risk:
- If Firebase credentials or project trust are compromised, the identity boundary is weakened across the system.

## 3) Device-Session Boundary

Device sessions add a second trust layer on top of Firebase identity.

Implementation:
- The client generates a 256-bit request secret in [frontend/titletrust/lib/security/transport_security_service.dart](frontend/titletrust/lib/security/transport_security_service.dart).
- The secret is registered with `/auth/device-sessions` in [backend/api/auth_router.py](backend/api/auth_router.py).
- The backend stores the secret encrypted and keeps a fingerprint in [backend/services/device_session_service.py](backend/services/device_session_service.py).
- Requests are signed by [frontend/titletrust/lib/core/network/dio_client.dart](frontend/titletrust/lib/core/network/dio_client.dart) and verified by [backend/security/request_signing.py](backend/security/request_signing.py).

What the backend assumes:
- The device-session id belongs to the authenticated user.
- The request secret presented during registration is the same secret used for future signing.
- The request timestamp is reasonably fresh.

Residual risk:
- If secure storage on the device is compromised, the signed request path can be replayed until the session is revoked.
- Biometric unlock raises the bar for casual access, but it is not a full hardware-backed attestation system.

## 4) Signed-Request Boundary

The signature payload includes method, path, timestamp, correlation id, and body hash.

Why this matters:
- A stolen bearer token alone is not enough to forge a matching request if the device secret is unavailable.
- Tampering with body or path invalidates the signature.

What is protected:
- Request integrity
- Limited replay window
- Correlation between signed body and signed headers

What is not protected:
- Compromise of the client-side secret
- Abuse of a legitimately signed request within the allowed window

## 5) Authorization Boundary

Authorization is policy-driven, not claim-driven.

Implementation:
- `require_permission()` in [backend/core/authorization.py](backend/core/authorization.py) converts roles to permissions.
- `PolicyService` adds tenant policy and resource ownership evaluation.

Why this matters:
- A client claim alone does not grant access.
- Membership and policy state are checked on the backend for every protected route.

Residual risk:
- The policy and membership cache TTL is short, but any cache introduces a brief staleness window.

## 6) Queue Trust Boundary

Queue payloads are internal but untrusted enough to validate.

Implementation:
- [backend/services/background_job_service.py](backend/services/background_job_service.py) persists a sanitized payload.
- [backend/workers/runtime.py](backend/workers/runtime.py) re-checks job type, cancellation, timeout, retries, and poison-pill conditions.

Why this matters:
- Jobs can be retried, moved between queues, or resumed after failures.
- The worker must not assume the payload is well formed just because it came from Redis or background tasks.

Residual risk:
- If the Redis instance is compromised, malicious job payloads could still be injected. The worker’s validations and dead-letter path reduce but do not eliminate that risk.

## 7) Telemetry Trust Boundary

Telemetry is observable, not authoritative.

Implementation:
- Correlation ids and trace ids are attached in [backend/middleware/observability.py](backend/middleware/observability.py).
- Abuse scores and counters are emitted in [backend/middleware/adaptive_protection.py](backend/middleware/adaptive_protection.py).
- Frontend exceptions are routed to Crashlytics and Sentry in [frontend/titletrust/lib/telemetry/frontend_telemetry_service.dart](frontend/titletrust/lib/telemetry/frontend_telemetry_service.dart).

Assumption:
- Telemetry may be incomplete or missing in degraded environments.

Important constraint:
- Logging data must never be treated as proof of access or proof of integrity.

## 8) Secret Management Lifecycle

Mobile side:
- Request secret is generated once, stored locally, and rotated only when needed.

Backend side:
- The request secret is encrypted at rest in Firestore.
- Previous ciphertext is retained to support rotation, then deleted on revoke.

Why this matters:
- The system can survive app reinstalls, secret rotation, and temporary token refreshes without forcing a full backend reset.

Residual risk:
- There is no hardware-backed remote attestation in the current codebase.

## 9) Replay-Defense Lifecycle

Implementation:
- Timestamp freshness is enforced in [backend/security/request_signing.py](backend/security/request_signing.py).
- Device-session revocation removes the secret fields from Firestore.
- Token-family and session models encode replay and rotation state in [backend/domain/session_models.py](backend/domain/session_models.py).

Residual risk:
- A fresh but malicious request can still be accepted if it is correctly signed and otherwise authorized.

## 10) Anomaly and Quarantine Lifecycle

Implementation:
- Request fingerprints are built in [backend/security/request_fingerprinting.py](backend/security/request_fingerprinting.py).
- Threat signals are stored in [backend/security/threat_intelligence.py](backend/security/threat_intelligence.py).
- Adaptive protection uses those signals to allow, throttle, challenge, quarantine, or block.

Why this matters:
- The system can turn observed abuse into a longer-lived signal.

Residual risk:
- The in-memory threat store is session-lifetime scoped, so it is not a durable SOC system.

## 11) Fail-Open and Fail-Closed Surfaces

Fail-closed:
- Invalid signature
- Stale timestamp
- Revoked device session
- Missing permission
- Abuse block
- Oversize or unsupported upload

Fail-open or degraded:
- Telemetry initialization failures
- Notification initialization failures
- Local queue fallback when Redis is unavailable
- Titbits fallback when Gemini is unavailable

This split is intentional: security-critical boundaries fail closed; convenience and visibility surfaces degrade.

## 12) Residual Risks

Implemented protections:
- Firebase auth
- Device-bound request signing
- Ownership and permission checks
- Rate limiting
- Abuse scoring and quarantine
- Worker retries and dead-lettering
- Secret hashing/encryption at rest

Residual gaps:
- No hardware attestation of device trust
- No complete proof that client storage is uncompromised
- No durable central threat-intelligence backend
- Queue and worker correctness depend on Redis availability and deployment hygiene
- Some flows still rely on in-process or fallback behavior when cloud infra is absent

Bottom line:
- The system is meaningfully hardened, but it should still be treated as a security-conscious application rather than a formally certified security appliance.
