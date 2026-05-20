# TitleTrust API Reference (Route-by-Route Audit)

Audit date: 2026-05-13
Source of truth: `backend/main.py` and `backend/api/*.py`

This document reflects the exact routes, request payloads, auth requirements, and response structures currently implemented in code.

## Global Runtime Contract

- App title/version: `TitleTrust API` / `3.0.0`
- Mounted routers:
  - `/audit` from `backend/api/audit_router.py`
  - `/auth` from `backend/api/auth_router.py`
  - `/uploads` from `backend/api/upload_router.py`
  - health/metrics routes from `backend/api/health_router.py` (no prefix)
- Rate limiting (`enforce_rate_limit`) is applied to all `/audit`, `/auth`, and `/uploads` routes via `app.include_router(..., dependencies=[Depends(enforce_rate_limit)])`.
- Security/auth middleware and dependencies:
  - Bearer token authentication is required on all `/audit`, `/auth`, `/uploads` routes (via `require_permission(...)` -> Firebase token verification).
  - Health and metrics routes are not permission-gated in router code.
- CORS allows these custom headers: `X-Correlation-ID`, `X-Request-Signature`, `X-Request-Timestamp`, `X-Device-Session-ID`, `X-Request-Signed`.

## Authentication and Header Requirements

### Required on protected routes (`/audit`, `/auth`, `/uploads`)

- `Authorization: Bearer <firebase-id-token>`

If missing/invalid, typical errors are:
- `401 {"detail":"Missing authentication token"}`
- `401 {"detail":"Invalid authentication credentials"}`
- `503 {"detail":"Authentication service unavailable"}`
- `403 {"detail":"Insufficient permissions"}` when role lacks required permission.

### Request-signing headers (required only on specific `/auth/device-sessions*` routes)

- `X-Request-Signature`
- `X-Request-Timestamp`
- `X-Correlation-ID`
- `X-Device-Session-ID` (required for list and revoke routes)

Signature freshness window: 5 minutes (`MAX_REQUEST_SIGNATURE_AGE_MS = 300000`).

## Endpoint Catalog

## Health Router (`backend/api/health_router.py`)

### GET /

Auth: none

Response:
```json
{
  "status": "ok",
  "service": "titletrust-backend"
}
```

### GET /health/live

Auth: none

Response:
```json
{
  "status": "alive"
}
```

### GET /health/ready

Auth: none

Response (ready):
```json
{
  "status": "ready"
}
```

Response (degraded):
```json
{
  "status": "degraded"
}
```

### GET /metrics

Auth: none

Response type: `text/plain` (Prometheus exposition format)

## Upload Router (`backend/api/upload_router.py`)

### POST /uploads/signed-url

Permission: `audit:start`

Headers:
- `Authorization: Bearer <firebase-id-token>` (required)

Request JSON (`SignedUploadRequest`):
```json
{
  "filename": "parcel-photo.jpg",
  "content_type": "image/jpeg",
  "purpose": "marathon-start"
}
```

Notes:
- `filename` is required.
- `content_type` is optional; server infers if omitted.
- `purpose` defaults to `marathon-start`.

Response JSON (`SignedUploadResponse`):
```json
{
  "upload_url": "https://...",
  "object_path": "gs://<bucket>/<prefix>/<organization>/<user>/<purpose>/<uuid>-<filename>",
  "method": "PUT",
  "headers": {
    "Content-Type": "image/jpeg"
  },
  "expires_in_seconds": 900
}
```

Error cases:
- `400` when upload bucket/config input invalid (`ValueError`)
- `503` when storage client/runtime unavailable (`RuntimeError`)

## Auth Router (`backend/api/auth_router.py`)

### GET /auth/device-sessions

Permission: `device-session:manage`

Headers:
- `Authorization: Bearer <firebase-id-token>`
- `X-Device-Session-ID` (required)
- `X-Request-Signature` (required)
- `X-Request-Timestamp` (required)
- `X-Correlation-ID` (required)

Request body: none

Response JSON (`DeviceSessionResponse`):
```json
{
  "sessions": [
    {
      "session_id": "...",
      "device_id": "...",
      "platform": "...",
      "app_version": "...",
      "revoked": false
    }
  ]
}
```

Error cases:
- `400` missing signing headers/session identifier
- `401` unknown/revoked session, expired signature, invalid signature
- `403` device session ownership mismatch

### POST /auth/device-sessions

Permission: `device-session:manage`

Headers:
- `Authorization: Bearer <firebase-id-token>`
- `X-Request-Signature` (required)
- `X-Request-Timestamp` (required)
- `X-Correlation-ID` (required)

Request JSON (`DeviceSessionUpsertRequest`):
```json
{
  "session_id": "session-uuid",
  "device_id": "device-fingerprint",
  "platform": "android",
  "app_version": "1.2.3",
  "request_secret": "base64-or-random-secret"
}
```

Notes:
- Signature for this endpoint is verified using `payload.request_secret`.
- Organization context must exist in user claims or `org_id`; otherwise request is rejected.

Response JSON:
```json
{
  "status": "registered"
}
```

Error cases:
- `400` missing signing fields/secret/organization context
- `401` expired/invalid signature
- `403` insufficient permissions

### POST /auth/device-sessions/{session_id}/revoke

Permission: `device-session:manage`

Path params:
- `session_id` (string)

Headers:
- `Authorization: Bearer <firebase-id-token>`
- `X-Device-Session-ID` (required)
- `X-Request-Signature` (required)
- `X-Request-Timestamp` (required)
- `X-Correlation-ID` (required)

Request body: none

Response JSON:
```json
{
  "status": "revoked"
}
```

Error cases:
- same signing/session validation cases as `GET /auth/device-sessions`

## Audit Router (`backend/api/audit_router.py`)

### POST /audit/forensic

Permission: `forensic:run`

Headers:
- `Authorization: Bearer <firebase-id-token>`
- `X-Correlation-ID` (optional)

Request type: `multipart/form-data`

Form fields:
- `files` (required, repeated file field; type `UploadFile[]`)

Accepted file suffixes:
- `.pdf`, `.png`, `.jpg`, `.jpeg`

Per-file size limit:
- 50 MB

Response JSON (`JobAcceptedResponse`):
```json
{
  "job_id": "uuid",
  "status": "QUEUED",
  "job_type": "forensic"
}
```

### POST /audit/geospatial

Permission: `geospatial:run`

Headers:
- `Authorization: Bearer <firebase-id-token>`
- `X-Correlation-ID` (optional)

Request type: `multipart/form-data`

Form fields:
- `lat` (required float, `-90 <= lat <= 90`)
- `lng` (required float, `-180 <= lng <= 180`)
- `file` (required file field)

Accepted file suffixes:
- `.pdf`, `.png`, `.jpg`, `.jpeg`, `.mp4`, `.mov`

Per-file size limit:
- 50 MB

Response JSON (`JobAcceptedResponse`):
```json
{
  "job_id": "uuid",
  "status": "QUEUED",
  "job_type": "geospatial"
}
```

### POST /audit/geospatial/live-token

Permission: `geospatial:run`

Headers:
- `Authorization: Bearer <firebase-id-token>`

Request JSON (`LiveTokenRequest`):
```json
{
  "session_id": "session-uuid",
  "lat": -1.2921,
  "lng": 36.8219,
  "title_number": "IR 12345",
  "expected_size": "0.05 Ha",
  "user_name": "Surveyor"
}
```

Response JSON (service return shape):
```json
{
  "token": "ephemeral-token-name",
  "session_id": "session-uuid",
  "expiration": "2026-05-13T12:34:56.789012+00:00",
  "model": "<FORENSIC_MODEL_NAME>"
}
```

### POST /audit/start

Permission: `audit:start`

Headers:
- `Authorization: Bearer <firebase-id-token>`
- `Idempotency-Key` (optional)

Request type: `multipart/form-data`

Form fields:
- `file` (required file field)

Accepted file suffixes:
- `.pdf`, `.png`, `.jpg`, `.jpeg`, `.mp4`, `.mov`

Response JSON (`StartAuditResponse`):
```json
{
  "session_id": "uuid",
  "status": "QUEUED",
  "message": "Investigation starting. Analyzing document..."
}
```

If idempotency key resolves to existing session:
```json
{
  "session_id": "existing-session-id",
  "status": "QUEUED",
  "message": "Existing investigation reused for idempotent request."
}
```

### POST /audit/start/from-storage

Permission: `audit:start`

Headers:
- `Authorization: Bearer <firebase-id-token>`
- `Idempotency-Key` (optional)

Request JSON (`StartAuditFromStorageRequest`):
```json
{
  "object_path": "gs://bucket/path/file.pdf",
  "original_filename": "file.pdf"
}
```

Response JSON (`StartAuditResponse`):
```json
{
  "session_id": "uuid",
  "status": "QUEUED",
  "message": "Investigation starting. Analyzing document..."
}
```

### POST /audit/tick

Permission: `audit:start`

Headers:
- `Authorization: Bearer <firebase-id-token>`

Request JSON:
```json
{
  "session_id": "session-uuid"
}
```

Response JSON:
```json
{
  "status": "success",
  "agent_status": "RUNNING"
}
```

Error cases:
- `400 {"detail":"Missing session_id"}`
- `404 {"detail":"Session not found"}`
- `403 {"detail":"Access denied"}`

### GET /audit/status/{session_id}

Permission: `audit:read`

Path params:
- `session_id` (string)

Headers:
- `Authorization: Bearer <firebase-id-token>`

Response JSON (`SessionStatusResponse`):
```json
{
  "session_id": "session-uuid",
  "status": "RUNNING",
  "progress": {},
  "total_steps": 0,
  "last_thought": "...",
  "error": null,
  "findings": [],
  "audit_conclusion": null
}
```

### POST /audit/retry/{session_id}

Permission: `audit:retry`

Path params:
- `session_id` (string)

Headers:
- `Authorization: Bearer <firebase-id-token>`

Response JSON (`RetryAuditResponse`):
```json
{
  "session_id": "session-uuid",
  "status": "RETRYING",
  "message": "Session retry scheduled"
}
```

Error cases:
- `400` if session state is not retryable
- `404` session not found
- `403` access denied

### GET /audit/jobs/{job_id}

Permission: `audit:read`

Path params:
- `job_id` (string)

Headers:
- `Authorization: Bearer <firebase-id-token>`

Response JSON (`JobStatusResponse`):
```json
{
  "job_id": "job-uuid",
  "status": "QUEUED",
  "job_type": "forensic",
  "attempts": 0,
  "result": null,
  "error": null,
  "warnings": []
}
```

Error cases:
- `404 {"detail":"Job not found"}`
- `403 {"detail":"Access denied"}`

### POST /audit/jobs/{job_id}/cancel

Permission: `audit:retry`

Path params:
- `job_id` (string)

Headers:
- `Authorization: Bearer <firebase-id-token>`

Response JSON (`JobAcceptedResponse`):
```json
{
  "job_id": "job-uuid",
  "status": "CANCELLED",
  "job_type": "forensic"
}
```

### GET /audit/titbits

Permission: `titbits:read`

Headers:
- `Authorization: Bearer <firebase-id-token>`

Response JSON:
```json
{
  "titbits": [
    "A Green Card is stronger registry evidence than the printed title deed alone.",
    "..."
  ]
}
```

## Discrepancies vs Existing API Docs

Compared against `backend/README.md` API section:

1. Existing docs list only 3 endpoints, but code exposes 18 routes.
2. `POST /audit/forensic` is documented as synchronous analysis response; code returns async job acceptance (`job_id`, `QUEUED`, `job_type`).
3. `POST /audit/geospatial` request field is documented as `image`; code requires multipart field name `file` and returns async job acceptance.
4. Auth/device-session contract is undocumented in existing docs but is mandatory for signed-device workflow.
5. Upload bootstrap route (`POST /uploads/signed-url`) is undocumented in existing docs.
6. Session-marathon routes (`/audit/start`, `/audit/start/from-storage`, `/audit/tick`, `/audit/status/{session_id}`, `/audit/retry/{session_id}`) are undocumented in existing docs.
7. Job-control routes (`/audit/jobs/{job_id}`, `/audit/jobs/{job_id}/cancel`) are undocumented in existing docs.
8. Existing docs only mention `GET /`; code also has `/health/live`, `/health/ready`, `/metrics`.

## Deprecated/Removed

None found in current docs: all previously documented endpoint paths still exist in code.

## Strict OpenAPI Parity Pass

OpenAPI extraction source:
- `app.openapi()` from `backend.main:app`
- generated snapshot: `documentation/openapi.generated.json`

### Parity Findings

1. OpenAPI currently declares `200` (and `422` where applicable) for route operations, but does not explicitly enumerate most runtime `HTTPException` statuses raised in route code, dependencies, and service calls (`400`, `401`, `403`, `404`, `503`).
2. Global handlers in `backend/main.py` add a runtime `500` contract for unhandled exceptions on all routes, but this is not explicitly listed per operation in OpenAPI.
3. `422` is represented in OpenAPI for operations with request bodies, path params, or typed form fields; the runtime body shape matches the custom validation exception handler output.

### Response Model Parity (200 Responses)

Verified `response_model` declarations are reflected in OpenAPI `200` schema refs:

- `POST /audit/forensic` -> `#/components/schemas/JobAcceptedResponse`
- `POST /audit/geospatial` -> `#/components/schemas/JobAcceptedResponse`
- `GET /audit/jobs/{job_id}` -> `#/components/schemas/JobStatusResponse`
- `POST /audit/jobs/{job_id}/cancel` -> `#/components/schemas/JobAcceptedResponse`
- `POST /audit/retry/{session_id}` -> `#/components/schemas/RetryAuditResponse`
- `POST /audit/start` -> `#/components/schemas/StartAuditResponse`
- `POST /audit/start/from-storage` -> `#/components/schemas/StartAuditResponse`
- `GET /audit/status/{session_id}` -> `#/components/schemas/SessionStatusResponse`
- `GET /auth/device-sessions` -> `#/components/schemas/DeviceSessionResponse`
- `POST /uploads/signed-url` -> `#/components/schemas/SignedUploadResponse`

Endpoints without explicit `response_model` use OpenAPI inline/default object schema (`N/A` ref in extraction), which is expected for:

- `GET /`, `GET /health/live`, `GET /health/ready`, `GET /metrics`
- `POST /audit/geospatial/live-token`, `POST /audit/tick`, `GET /audit/titbits`
- `POST /auth/device-sessions`, `POST /auth/device-sessions/{session_id}/revoke`

### Canonical Error Body Shapes

Standard HTTP exception shape (used by route/dependency/service raises and Starlette HTTP exceptions):

```json
{
  "detail": "<string or structured detail>"
}
```

Validation error shape (`RequestValidationError`, including Pydantic body parsing and typed form/path coercion):

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

Unhandled server error shape (global catch-all):

```json
{
  "detail": "Internal server error"
}
```

### Error Contract Matrix (OpenAPI vs Runtime)

Legend:
- `OpenAPI`: status appears in `openapi.generated.json` operation responses.
- `Runtime`: status raised by route code, dependencies (`require_permission`/Firebase auth/request signing), service layer, or global handlers.

| Endpoint | OpenAPI statuses | Runtime statuses | Error body shape(s) | 422 conditions |
|---|---|---|---|---|
| `GET /` | `200` | `500` | `{"detail":"Internal server error"}` | none |
| `GET /health/live` | `200` | `500` | `{"detail":"Internal server error"}` | none |
| `GET /health/ready` | `200` | `500` | `{"detail":"Internal server error"}` | none |
| `GET /metrics` | `200` | `500` | `{"detail":"Internal server error"}` | none |
| `POST /uploads/signed-url` | `200, 422` | `400, 401, 403, 422, 500, 503` | `{"detail":"..."}` or validation array shape | invalid/missing JSON body fields for `SignedUploadRequest` |
| `GET /auth/device-sessions` | `200, 422` | `400, 401, 403, 422, 500, 503` | `{"detail":"..."}` or validation array shape | malformed request data resolved by FastAPI validation/dependency parsing |
| `POST /auth/device-sessions` | `200, 422` | `400, 401, 403, 422, 500, 503` | `{"detail":"..."}` or validation array shape | invalid/missing JSON body fields for `DeviceSessionUpsertRequest` |
| `POST /auth/device-sessions/{session_id}/revoke` | `200, 422` | `400, 401, 403, 422, 500, 503` | `{"detail":"..."}` or validation array shape | malformed path/header/dependency input validation |
| `POST /audit/forensic` | `200, 422` | `400, 401, 403, 422, 500, 503` | `{"detail":"..."}` or validation array shape | missing `files` field / multipart parsing issues |
| `POST /audit/geospatial` | `200, 422` | `400, 401, 403, 422, 500, 503` | `{"detail":"..."}` or validation array shape | missing/invalid `lat`, `lng`, or `file`; out-of-range `lat`/`lng` |
| `POST /audit/geospatial/live-token` | `200, 422` | `401, 403, 422, 500, 503` | `{"detail":"..."}` or validation array shape | invalid/missing JSON body fields for `LiveTokenRequest` |
| `POST /audit/start` | `200, 422` | `400, 401, 403, 422, 500, 503` | `{"detail":"..."}` or validation array shape | missing multipart `file` |
| `POST /audit/start/from-storage` | `200, 422` | `400, 401, 403, 422, 500, 503` | `{"detail":"..."}` or validation array shape | invalid/missing JSON body fields for `StartAuditFromStorageRequest` |
| `POST /audit/tick` | `200, 422` | `400, 401, 403, 404, 422, 500, 503` | `{"detail":"..."}` or validation array shape | malformed JSON payload type coercion |
| `GET /audit/status/{session_id}` | `200, 422` | `401, 403, 404, 422, 500, 503` | `{"detail":"..."}` or validation array shape | invalid path parameter format/coercion |
| `POST /audit/retry/{session_id}` | `200, 422` | `400, 401, 403, 404, 422, 500, 503` | `{"detail":"..."}` or validation array shape | invalid path parameter format/coercion |
| `GET /audit/jobs/{job_id}` | `200, 422` | `401, 403, 404, 422, 500, 503` | `{"detail":"..."}` or validation array shape | invalid path parameter format/coercion |
| `POST /audit/jobs/{job_id}/cancel` | `200, 422` | `401, 403, 404, 422, 500, 503` | `{"detail":"..."}` or validation array shape | invalid path parameter format/coercion |
| `GET /audit/titbits` | `200` | `401, 403, 500, 503` | `{"detail":"..."}` or `{"detail":"Internal server error"}` | none |

### Route-Level Runtime Status Source Notes

- `400` sources include explicit raises in route/service code such as:
  - missing `session_id` in `POST /audit/tick`
  - unsupported file suffix or file size limit checks in job/session services
  - request-signing header/secret requirements in auth routes
- `401` sources include authentication and signing checks:
  - Firebase auth token failures
  - expired/invalid request signatures
  - unknown/revoked device sessions
- `403` sources include:
  - permission denial (`Insufficient permissions`)
  - ownership checks (`Access denied`)
  - device session/user mismatch
- `404` sources include missing `session_id`/`job_id` resources in service and router lookups.
- `503` sources include:
  - Firebase auth infrastructure errors (`Authentication service unavailable`)
  - storage service runtime failures in `/uploads/signed-url`
- `500` source is the global unhandled exception handler in `backend/main.py` returning `{"detail":"Internal server error"}`.

### Endpoint/Error Table (CSV-style Markdown)

This table is intended for QA and test-case generation. Cells are intentionally compact and machine-readable.

| endpoint | method | auth | request shape | success | runtime errors | 422 conditions |
|---|---|---|---|---|---|---|
| `/` | `GET` | none | none | `200 {"status":"ok","service":"titletrust-backend"}` | `500 {"detail":"Internal server error"}` | n/a |
| `/health/live` | `GET` | none | none | `200 {"status":"alive"}` | `500 {"detail":"Internal server error"}` | n/a |
| `/health/ready` | `GET` | none | none | `200 {"status":"ready"}\n` or `200 {"status":"degraded"}` | `500 {"detail":"Internal server error"}` | n/a |
| `/metrics` | `GET` | none | none | `200 text/plain` | `500 {"detail":"Internal server error"}` | n/a |
| `/uploads/signed-url` | `POST` | Bearer + `audit:start` | JSON: `SignedUploadRequest` | `200 SignedUploadResponse` | `400`, `403`, `503`, `500` (`{"detail":"..."}`) | malformed/missing JSON body fields |
| `/auth/device-sessions` | `GET` | Bearer + `device-session:manage` + signed headers | headers: `X-Device-Session-ID`, `X-Request-Signature`, `X-Request-Timestamp`, `X-Correlation-ID` | `200 {"sessions":[...]}` | `400`, `401`, `403`, `500` (`{"detail":"..."}`) | dependency/header validation failures |
| `/auth/device-sessions` | `POST` | Bearer + `device-session:manage` + signed headers | JSON: `DeviceSessionUpsertRequest` | `200 {"status":"registered"}` | `400`, `401`, `403`, `500` (`{"detail":"..."}`) | malformed/missing JSON body fields |
| `/auth/device-sessions/{session_id}/revoke` | `POST` | Bearer + `device-session:manage` + signed headers | path `session_id` | `200 {"status":"revoked"}` | `400`, `401`, `403`, `500` (`{"detail":"..."}`) | path/header validation failures |
| `/audit/forensic` | `POST` | Bearer + `forensic:run` | multipart: repeated `files` | `200 {"job_id":"...","status":"QUEUED","job_type":"forensic"}` | `400`, `401`, `403`, `500` (`{"detail":"..."}`) | missing/invalid multipart form or files |
| `/audit/geospatial` | `POST` | Bearer + `geospatial:run` | multipart: `lat`, `lng`, `file` | `200 {"job_id":"...","status":"QUEUED","job_type":"geospatial"}` | `400`, `401`, `403`, `500` (`{"detail":"..."}`) | invalid/missing `lat`, `lng`, or `file` |
| `/audit/geospatial/live-token` | `POST` | Bearer + `geospatial:run` | JSON: `LiveTokenRequest` | `200 token payload` | `401`, `403`, `500` (`{"detail":"..."}`) | malformed/missing JSON body fields |
| `/audit/start` | `POST` | Bearer + `audit:start` | multipart: `file` | `200 {"session_id":"...","status":"QUEUED","message":"..."}` | `400`, `401`, `403`, `409`, `500` (`{"detail":"..."}`) | missing multipart file / body coercion issues |
| `/audit/start/from-storage` | `POST` | Bearer + `audit:start` | JSON: `StartAuditFromStorageRequest` | `200 {"session_id":"...","status":"QUEUED","message":"..."}` | `400`, `401`, `403`, `409`, `500` (`{"detail":"..."}`) | malformed/missing JSON body fields |
| `/audit/tick` | `POST` | Bearer + `audit:start` | JSON: `{"session_id":"..."}` | `200 {"status":"success","agent_status":"..."}` | `400`, `401`, `403`, `404`, `500` (`{"detail":"..."}`) | malformed JSON body / session_id coercion |
| `/audit/status/{session_id}` | `GET` | Bearer + `audit:read` | path `session_id` | `200 SessionStatusResponse` | `401`, `403`, `404`, `500` (`{"detail":"..."}`) | path coercion failures |
| `/audit/retry/{session_id}` | `POST` | Bearer + `audit:retry` | path `session_id` | `200 RetryAuditResponse` | `400`, `401`, `403`, `404`, `500` (`{"detail":"..."}`) | path coercion failures |
| `/audit/jobs/{job_id}` | `GET` | Bearer + `audit:read` | path `job_id` | `200 JobStatusResponse` | `401`, `403`, `404`, `500` (`{"detail":"..."}`) | path coercion failures |
| `/audit/jobs/{job_id}/cancel` | `POST` | Bearer + `audit:retry` | path `job_id` | `200 {"job_id":"...","status":"CANCELLED","job_type":"..."}` | `401`, `403`, `404`, `500` (`{"detail":"..."}`) | path coercion failures |
| `/audit/titbits` | `GET` | Bearer + `titbits:read` | none | `200 {"titbits":[...]}` | `401`, `403`, `500` (`{"detail":"..."}`) | n/a |
