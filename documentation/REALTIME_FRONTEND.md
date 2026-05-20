Realtime Frontend Integration (Flutter)
-------------------------------------

This document now reflects the actual Flutter realtime implementation in `frontend/titletrust/lib/realtime/`.

Core classes
------------

- `RealtimeService` ([frontend/titletrust/lib/realtime/realtime_service.dart](frontend/titletrust/lib/realtime/realtime_service.dart))
  - Opens the SSE connection to `/realtime/sse`.
  - Sends `Last-Event-ID` when reconnecting.
  - Applies exponential backoff with jitter.
  - Emits connection state updates (`connecting`, `reconnecting`, `replaying`, `degraded`).
  - Parses `data:` SSE payloads into `RealtimeEventEnvelope` objects.

- `RealtimeController` ([frontend/titletrust/lib/realtime/realtime_controller.dart](frontend/titletrust/lib/realtime/realtime_controller.dart))
  - Dedupe events by `event_id`.
  - Reorders events using `sequence_id`.
  - Detects gaps and triggers authoritative recovery via `RecoveryCoordinator.fetchLastState()`.
  - Persists checkpoints and the latest event/sequence in shared preferences via `RealtimeRepository`.
  - Exposes timeline, warnings, and diagnostics to the UI.

- `RecoveryCoordinator` ([frontend/titletrust/lib/realtime/recovery_coordinator.dart](frontend/titletrust/lib/realtime/recovery_coordinator.dart))
  - Fetches `/realtime/last-state/{session_id}`.
  - Reconciles optimistic state with authoritative server state.

What the UI does
----------------

- The investigation and geospatial screens subscribe to realtime state and render the latest timeline entries, warnings, and connection state.
- The UI uses the recovery path when gaps or disconnects appear so users can continue from the most recent authoritative snapshot.

Security and transport
----------------------

- The SSE request reuses the app's existing auth/device-session headers.
- Secrets are never passed in query parameters.
- Reconnect behavior is local and idempotent; the client can resume after foreground/background transitions.
