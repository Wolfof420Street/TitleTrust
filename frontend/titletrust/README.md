# TitleTrust Flutter App

This Flutter app is the mobile client for TitleTrust. It shows investigation state, live realtime timeline entries, forensic findings, and geospatial verification results from the backend.

## What it actually does

- Opens the investigation screen and subscribes to realtime events.
- Reconnects to `/realtime/sse` with `Last-Event-ID` support.
- Dedupes and reorders events using `event_id` and `sequence_id`.
- Reconciles gaps with `/realtime/last-state/{session_id}`.
- Persists checkpoints and recovered snapshots locally.

## Realtime code paths

- Service: [lib/realtime/realtime_service.dart](lib/realtime/realtime_service.dart)
- Controller: [lib/realtime/realtime_controller.dart](lib/realtime/realtime_controller.dart)
- Recovery: [lib/realtime/recovery_coordinator.dart](lib/realtime/recovery_coordinator.dart)
- Local state: [lib/realtime/realtime_repository.dart](lib/realtime/realtime_repository.dart)
- Data models: [lib/realtime/models.dart](lib/realtime/models.dart)

## Relevant UI entry points

- Investigation screen: [lib/features/investigation/presentation/investigation_screen.dart](lib/features/investigation/presentation/investigation_screen.dart)
- Geospatial screen: [lib/features/geospatial/presentation/geospatial_screen.dart](lib/features/geospatial/presentation/geospatial_screen.dart)

## Setup

```bash
flutter pub get
flutter run
```

If you are working on the realtime features, run the Flutter tests that exercise the controller and SSE recovery flow:

```bash
flutter test
```
