import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:titletrust/realtime/models.dart';
import 'package:titletrust/realtime/realtime_controller.dart';
import 'package:titletrust/realtime/realtime_repository.dart';
import 'package:titletrust/realtime/realtime_service.dart';
import 'package:titletrust/realtime/recovery_coordinator.dart';

class _FakeRealtimeService extends RealtimeService {
  _FakeRealtimeService() : super('http://127.0.0.1:0');

  final StreamController<RealtimeEventEnvelope> _events = StreamController<RealtimeEventEnvelope>.broadcast();
  final StreamController<RealtimeConnectionState> _states = StreamController<RealtimeConnectionState>.broadcast();

  @override
  Stream<RealtimeEventEnvelope> get events => _events.stream;

  @override
  Stream<RealtimeConnectionState> get connectionStates => _states.stream;

  @override
  RealtimeConnectionState get currentState => RealtimeConnectionState.synchronized;

  @override
  Future<void> start({required String sessionId, String? lastEventId}) async {
    _states.add(RealtimeConnectionState.connecting);
    _states.add(RealtimeConnectionState.synchronized);
  }

  @override
  Future<void> stop() async {
    _states.add(RealtimeConnectionState.disconnected);
  }

  void emit(RealtimeEventEnvelope event) => _events.add(event);
  void emitState(RealtimeConnectionState state) => _states.add(state);

  @override
  void dispose() {
    _events.close();
    _states.close();
    super.dispose();
  }
}

class _FakeRecoveryCoordinator extends RecoveryCoordinator {
  _FakeRecoveryCoordinator(this.snapshot) : super(Dio(), RealtimeRepository());

  final Map<String, dynamic> snapshot;
  int fetchCount = 0;

  @override
  Future<Map<String, dynamic>?> fetchLastState(String sessionId) async {
    fetchCount += 1;
    return snapshot;
  }

  @override
  Future<void> reconcile(String sessionId, Map<String, dynamic> authoritative, {required FutureOr<void> Function(Map<String, dynamic>) apply}) async {
    await apply(authoritative);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
  });

  test('controller reorders buffered events and recovers authoritative state on gap', () async {
    final repo = RealtimeRepository();
    final service = _FakeRealtimeService();
    final recovery = _FakeRecoveryCoordinator({
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
    });

    final controller = RealtimeController('session-1', repo, recovery, service);
    await Future<void>.delayed(const Duration(milliseconds: 50));

    service.emit(RealtimeEventEnvelope(
      eventId: 'e1',
      eventType: 'agent.thought',
      sequenceId: 1,
      sessionId: 'session-1',
      ts: DateTime.now().millisecondsSinceEpoch,
      payload: {'message': 'first'},
    ));
    service.emit(RealtimeEventEnvelope(
      eventId: 'e3',
      eventType: 'agent.evidence_registered',
      sequenceId: 3,
      sessionId: 'session-1',
      ts: DateTime.now().millisecondsSinceEpoch,
      payload: {'message': 'gap'},
    ));
    service.emit(RealtimeEventEnvelope(
      eventId: 'e2',
      eventType: 'agent.thought',
      sequenceId: 2,
      sessionId: 'session-1',
      ts: DateTime.now().millisecondsSinceEpoch,
      payload: {'message': 'reordered'},
    ));
    service.emit(RealtimeEventEnvelope(
      eventId: 'e3',
      eventType: 'agent.evidence_registered',
      sequenceId: 3,
      sessionId: 'session-1',
      ts: DateTime.now().millisecondsSinceEpoch,
      payload: {'message': 'duplicate'},
    ));
    service.emit(RealtimeEventEnvelope(
      eventId: 'e6',
      eventType: 'job.completed',
      sequenceId: 6,
      sessionId: 'session-1',
      ts: DateTime.now().millisecondsSinceEpoch,
      payload: {'message': 'gap to recovery'},
    ));

    await Future<void>.delayed(const Duration(milliseconds: 150));

    expect(controller.state.timeline, isNotEmpty);
    expect(controller.state.connectionState, RealtimeConnectionState.synchronized);
    expect(controller.state.authoritativeSnapshot, isNotNull);
    expect(controller.state.diagnostics.sequenceGaps, greaterThanOrEqualTo(1));
    expect(controller.state.diagnostics.duplicateEvents, greaterThanOrEqualTo(1));
    expect(recovery.fetchCount, greaterThanOrEqualTo(1));

    controller.dispose();
    service.dispose();
  });

  test('controller reflects reconnect and stale lifecycle transitions', () async {
    final repo = RealtimeRepository();
    final service = _FakeRealtimeService();
    final recovery = _FakeRecoveryCoordinator({
      'session': {'status': 'RUNNING', 'logs': [], 'findings': []},
      'job': {'status': 'RUNNING'},
      'evidence': {},
      'last_event_id': 'srv-1',
    });

    final controller = RealtimeController('session-2', repo, recovery, service);
    await Future<void>.delayed(const Duration(milliseconds: 50));

    service.emitState(RealtimeConnectionState.reconnecting);
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(controller.state.connectionState, RealtimeConnectionState.reconnecting);

    await controller.handleAppPaused();
    expect(controller.state.connectionState, RealtimeConnectionState.stale);

    await controller.handleAppResumed();
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(controller.state.connectionState, anyOf(RealtimeConnectionState.connecting, RealtimeConnectionState.synchronized));

    controller.dispose();
    service.dispose();
  });
}
