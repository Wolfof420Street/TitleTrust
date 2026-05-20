import 'dart:async';

import 'package:titletrust/realtime/models.dart';
import 'package:titletrust/realtime/realtime_controller.dart';
import 'package:titletrust/realtime/realtime_service.dart';

class RealtimeFailureInjector {
  final int? duplicateEveryNthEvent;
  final int? dropEveryNthEvent;
  final int? malformedEveryNthEvent;

  const RealtimeFailureInjector({
    this.duplicateEveryNthEvent,
    this.dropEveryNthEvent,
    this.malformedEveryNthEvent,
  });

  bool shouldDuplicate(int index) => duplicateEveryNthEvent != null && duplicateEveryNthEvent! > 0 && index % duplicateEveryNthEvent! == 0;
  bool shouldDrop(int index) => dropEveryNthEvent != null && dropEveryNthEvent! > 0 && index % dropEveryNthEvent! == 0;
  bool shouldCorrupt(int index) => malformedEveryNthEvent != null && malformedEveryNthEvent! > 0 && index % malformedEveryNthEvent! == 0;
}

class FakeBackendSnapshotServer {
  final Map<String, Map<String, dynamic>> _snapshots = {};

  void seedSnapshot(String sessionId, Map<String, dynamic> snapshot) {
    _snapshots[sessionId] = snapshot;
  }

  Map<String, dynamic>? snapshotFor(String sessionId) => _snapshots[sessionId];
}

class SimulatedRealtimeService extends RealtimeService {
  SimulatedRealtimeService() : super('http://127.0.0.1:0');

  final StreamController<RealtimeEventEnvelope> _events = StreamController<RealtimeEventEnvelope>.broadcast();
  final StreamController<RealtimeConnectionState> _states = StreamController<RealtimeConnectionState>.broadcast();

  int startCount = 0;
  int stopCount = 0;
  String? lastSessionId;
  String? lastEventId;
  RealtimeConnectionState _currentState = RealtimeConnectionState.disconnected;

  @override
  Stream<RealtimeEventEnvelope> get events => _events.stream;

  @override
  Stream<RealtimeConnectionState> get connectionStates => _states.stream;

  @override
  RealtimeConnectionState get currentState => _currentState;

  @override
  Future<void> start({required String sessionId, String? lastEventId}) async {
    startCount += 1;
    lastSessionId = sessionId;
    this.lastEventId = lastEventId;
    _emitState(RealtimeConnectionState.connecting);
    _emitState(RealtimeConnectionState.synchronized);
  }

  @override
  Future<void> stop() async {
    stopCount += 1;
    _emitState(RealtimeConnectionState.disconnected);
  }

  void emitEvent(RealtimeEventEnvelope event) {
    _events.add(event);
  }

  void emitDuplicate(RealtimeEventEnvelope event) {
    _events.add(event);
    _events.add(event);
  }

  void emitGap(RealtimeEventEnvelope event) {
    _events.add(event);
  }

  void emitState(RealtimeConnectionState state) {
    _emitState(state);
  }

  void emitMalformed() {
    // malformed payloads are intentionally dropped before reaching the controller.
  }

  void _emitState(RealtimeConnectionState state) {
    _currentState = state;
    if (!_states.isClosed) {
      _states.add(state);
    }
  }

  @override
  void dispose() {
    if (!_events.isClosed) {
      _events.close();
    }
    if (!_states.isClosed) {
      _states.close();
    }
    super.dispose();
  }
}

List<Map<String, dynamic>> normalizeTimeline(RealtimeState state) {
  return state.timeline
      .map(
        (entry) => <String, dynamic>{
          'id': entry.id,
          'title': entry.title,
          'message': entry.message,
          'kind': entry.kind,
          'sequence_id': entry.sequenceId,
          'session_id': entry.sessionId,
          'stream_offset': entry.streamOffset,
          'origin_instance_id': entry.originInstanceId,
          'authoritative': entry.authoritative,
        },
      )
      .toList(growable: false);
}
