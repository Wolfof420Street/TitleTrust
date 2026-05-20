import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:titletrust/realtime/models.dart';
import 'package:titletrust/realtime/realtime_controller.dart';
import 'package:titletrust/realtime/realtime_repository.dart';
import 'package:titletrust/realtime/recovery_coordinator.dart';

import 'package:dio/dio.dart';

import 'support/realtime_chaos.dart';

class _FakeRecoveryCoordinator extends RecoveryCoordinator {
  _FakeRecoveryCoordinator(this.server) : super(Dio(), RealtimeRepository());

  final FakeBackendSnapshotServer server;
  int fetchCount = 0;

  @override
  Future<Map<String, dynamic>?> fetchLastState(String sessionId) async {
    fetchCount += 1;
    return server.snapshotFor(sessionId);
  }

  @override
  Future<void> reconcile(String sessionId, Map<String, dynamic> authoritative, {required FutureOr<void> Function(Map<String, dynamic>) apply}) async {
    await apply(authoritative);
  }
}

RealtimeEventEnvelope _event(int sequenceId, String sessionId, String message, {String eventType = 'agent.thought'}) {
  return RealtimeEventEnvelope(
    eventId: 'e$sequenceId-$message',
    eventType: eventType,
    sequenceId: sequenceId,
    sessionId: sessionId,
    ts: DateTime.now().millisecondsSinceEpoch,
    payload: {'message': message},
  );
}

Map<String, dynamic> _authoritativeSnapshot() {
  return {
    'session': {
      'status': 'COMPLETED',
      'logs': [
        {'message': 'authoritative thought', 'type': 'thought', 'timestamp': DateTime.now().millisecondsSinceEpoch},
        {'message': 'authoritative evidence', 'type': 'evidence', 'timestamp': DateTime.now().millisecondsSinceEpoch},
      ],
      'findings': [
        {'description': 'Recovered finding', 'evidence': 'Recovered evidence'},
      ],
    },
    'job': {'status': 'COMPLETED', 'summary': 'Recovered from authoritative snapshot'},
    'evidence': {'graph': 'rebuilt'},
    'last_event_id': 'srv-2',
  };
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
  });

  test('duplicate floods and gaps converge to authoritative backend state', () async {
    final server = FakeBackendSnapshotServer()..seedSnapshot('session-chaos', _authoritativeSnapshot());
    final service = SimulatedRealtimeService();
    final recovery = _FakeRecoveryCoordinator(server);
    final controller = RealtimeController('session-chaos', RealtimeRepository(), recovery, service);

    await Future<void>.delayed(const Duration(milliseconds: 25));

    service.emitDuplicate(_event(1, 'session-chaos', 'first')); // duplicate flood
    service.emitEvent(_event(3, 'session-chaos', 'gap-open'));
    service.emitEvent(_event(2, 'session-chaos', 'late-arrival'));
    service.emitEvent(_event(6, 'session-chaos', 'gap-trigger', eventType: 'job.completed'));

    await Future<void>.delayed(const Duration(milliseconds: 150));

    expect(controller.state.connectionState, RealtimeConnectionState.synchronized);
    expect(controller.state.isRecovering, isFalse);
    expect(controller.state.diagnostics.sequenceGaps, greaterThanOrEqualTo(1));
    expect(controller.state.diagnostics.duplicateEvents, greaterThanOrEqualTo(1));
    expect(recovery.fetchCount, greaterThanOrEqualTo(1));

    final normalized = normalizeTimeline(controller.state);
    expect(normalized.map((item) => item['id']).toSet().length, normalized.length);
    expect(normalized.any((item) => item['message'] == 'Recovered finding — Recovered evidence'), isTrue);

    final expectedNormalized = [
      {
        'id': 'auth-log-0',
        'title': 'Thought',
        'message': 'authoritative thought',
        'kind': 'thought',
        'sequence_id': 1,
        'session_id': 'session-chaos',
        'stream_offset': null,
        'origin_instance_id': null,
        'authoritative': true,
      },
      {
        'id': 'auth-log-1',
        'title': 'Evidence Registered',
        'message': 'authoritative evidence',
        'kind': 'evidence',
        'sequence_id': 2,
        'session_id': 'session-chaos',
        'stream_offset': null,
        'origin_instance_id': null,
        'authoritative': true,
      },
    ];

    expect(normalized.take(2).map((item) => item['message']).toList(), expectedNormalized.map((item) => item['message']).toList());
    controller.dispose();
    service.dispose();
  });

  test('pause resume churn preserves checkpoints and reconnects with last event id', () async {
    final server = FakeBackendSnapshotServer()..seedSnapshot('session-resume', _authoritativeSnapshot());
    final service = SimulatedRealtimeService();
    final repo = RealtimeRepository();
    final recovery = _FakeRecoveryCoordinator(server);
    final controller = RealtimeController('session-resume', repo, recovery, service);

    await Future<void>.delayed(const Duration(milliseconds: 25));
    service.emitEvent(_event(1, 'session-resume', 'first'));
    service.emitEvent(_event(2, 'session-resume', 'second'));
    await Future<void>.delayed(const Duration(milliseconds: 25));

    await controller.handleAppPaused();
    expect(controller.state.connectionState, RealtimeConnectionState.stale);
    await controller.handleAppResumed();
    await Future<void>.delayed(const Duration(milliseconds: 25));

    expect(service.startCount, greaterThanOrEqualTo(2));
    expect(service.lastEventId, isNotNull);
    expect(controller.state.connectionState, anyOf(RealtimeConnectionState.connecting, RealtimeConnectionState.synchronized));

    controller.dispose();
    service.dispose();
  });

  test('buffer eviction keeps timeline bounded under slow consumer pressure', () async {
    final server = FakeBackendSnapshotServer()..seedSnapshot('session-bounded', _authoritativeSnapshot());
    final service = SimulatedRealtimeService();
    final recovery = _FakeRecoveryCoordinator(server);
    final controller = RealtimeController('session-bounded', RealtimeRepository(), recovery, service);

    await Future<void>.delayed(const Duration(milliseconds: 25));
    for (var index = 1; index <= 240; index++) {
      service.emitEvent(_event(index, 'session-bounded', 'event-$index'));
    }
    await Future<void>.delayed(const Duration(milliseconds: 150));

    expect(controller.state.timeline.length, lessThanOrEqualTo(200));
    expect(controller.state.diagnostics.sequenceGaps, lessThanOrEqualTo(1));
    expect(controller.state.diagnostics.reconnectAttempts, lessThanOrEqualTo(3));

    controller.dispose();
    service.dispose();
  });
}
