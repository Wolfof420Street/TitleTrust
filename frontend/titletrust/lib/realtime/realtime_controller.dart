import 'dart:async';
import 'dart:collection';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:titletrust/core/network/dio_client.dart';

import 'models.dart';
import 'realtime_repository.dart';
import 'realtime_service.dart';
import 'recovery_coordinator.dart';

class RealtimeState {
  final RealtimeConnectionState connectionState;
  final String sessionId;
  final String? lastEventId;
  final int? lastSequenceId;
  final String? latestStreamOffset;
  final List<RealtimeTimelineEntry> timeline;
  final List<String> warnings;
  final Map<String, dynamic>? authoritativeSnapshot;
  final RealtimeDiagnostics diagnostics;
  final bool isRecovering;
  final bool isStale;
  final bool isOffline;

  const RealtimeState({
    required this.connectionState,
    required this.sessionId,
    this.lastEventId,
    this.lastSequenceId,
    this.latestStreamOffset,
    this.timeline = const [],
    this.warnings = const [],
    this.authoritativeSnapshot,
    required this.diagnostics,
    this.isRecovering = false,
    this.isStale = false,
    this.isOffline = false,
  });

  RealtimeState copyWith({
    RealtimeConnectionState? connectionState,
    String? sessionId,
    String? lastEventId,
    int? lastSequenceId,
    String? latestStreamOffset,
    List<RealtimeTimelineEntry>? timeline,
    List<String>? warnings,
    Map<String, dynamic>? authoritativeSnapshot,
    RealtimeDiagnostics? diagnostics,
    bool? isRecovering,
    bool? isStale,
    bool? isOffline,
  }) {
    return RealtimeState(
      connectionState: connectionState ?? this.connectionState,
      sessionId: sessionId ?? this.sessionId,
      lastEventId: lastEventId ?? this.lastEventId,
      lastSequenceId: lastSequenceId ?? this.lastSequenceId,
      latestStreamOffset: latestStreamOffset ?? this.latestStreamOffset,
      timeline: timeline ?? this.timeline,
      warnings: warnings ?? this.warnings,
      authoritativeSnapshot: authoritativeSnapshot ?? this.authoritativeSnapshot,
      diagnostics: diagnostics ?? this.diagnostics,
      isRecovering: isRecovering ?? this.isRecovering,
      isStale: isStale ?? this.isStale,
      isOffline: isOffline ?? this.isOffline,
    );
  }
}

class RealtimeController extends StateNotifier<RealtimeState> {
  final String sessionId;
  final RealtimeRepository _repo;
  final RecoveryCoordinator _recovery;
  final RealtimeService _service;

  final Set<String> _seenEventIds = <String>{};
  final Queue<String> _seenOrder = Queue<String>();
  final SplayTreeMap<int, RealtimeEventEnvelope> _reorderBuffer = SplayTreeMap<int, RealtimeEventEnvelope>();

  StreamSubscription<RealtimeEventEnvelope>? _eventSub;
  StreamSubscription<RealtimeConnectionState>? _statusSub;
  bool _disposed = false;
  bool _started = false;
  bool _pausedByLifecycle = false;
  int _reconnectAttempts = 0;
  int _duplicateEvents = 0;
  int _sequenceGaps = 0;
  int _replayRecoveries = 0;
  Duration? _averageReplayDuration;
  int? _expectedSequence;
  String? _currentLastEventId;
  String? _currentLatestOffset;
  Map<String, dynamic>? _checkpoint;

  RealtimeController(this.sessionId, this._repo, this._recovery, this._service)
      : super(
          RealtimeState(
            connectionState: RealtimeConnectionState.disconnected,
            sessionId: sessionId,
            diagnostics: const RealtimeDiagnostics(
              reconnectAttempts: 0,
              replayRecoveries: 0,
              sequenceGaps: 0,
              duplicateEvents: 0,
            ),
          ),
        ) {
    unawaited(start());
  }

  Future<void> start() async {
    if (_started || _disposed) {
      return;
    }
    _started = true;

    _currentLastEventId = await _repo.getLastEventId(sessionId);
    _expectedSequence = await _repo.getLatestSequence(sessionId);
    _checkpoint = await _repo.getCheckpoint(sessionId);
    await _repo.getRecoveredSnapshot(sessionId);

    _statusSub = _service.connectionStates.listen((status) {
      if (_disposed) {
        return;
      }
      if (status == RealtimeConnectionState.reconnecting) {
        _reconnectAttempts += 1;
      }
      if (_pausedByLifecycle && status == RealtimeConnectionState.disconnected) {
        state = state.copyWith(
          connectionState: RealtimeConnectionState.stale,
          isOffline: true,
          isStale: true,
          diagnostics: _diagnostics(),
        );
        return;
      }
      state = state.copyWith(
        connectionState: status,
        isOffline: status == RealtimeConnectionState.disconnected || status == RealtimeConnectionState.degraded,
        isStale: status == RealtimeConnectionState.replaying || status == RealtimeConnectionState.reconnecting,
        diagnostics: _diagnostics(),
      );
    });

    _eventSub = _service.events.listen(
      (event) => unawaited(_handleEvent(event)),
      onError: (Object error, StackTrace stackTrace) {
        if (_disposed) {
          return;
        }
        state = state.copyWith(
          connectionState: RealtimeConnectionState.reconnecting,
          isOffline: true,
          warnings: _trimWarnings([...state.warnings, 'Realtime stream error: $error']),
          diagnostics: _diagnostics(),
        );
      },
      onDone: () {
        if (_disposed) {
          return;
        }
        state = state.copyWith(connectionState: RealtimeConnectionState.disconnected, isOffline: true, diagnostics: _diagnostics());
      },
      cancelOnError: false,
    );

    await _service.start(sessionId: sessionId, lastEventId: _currentLastEventId);
    state = state.copyWith(connectionState: RealtimeConnectionState.connecting, diagnostics: _diagnostics());
  }

  Future<void> handleAppPaused() async {
    if (_disposed) {
      return;
    }
    _pausedByLifecycle = true;
    state = state.copyWith(connectionState: RealtimeConnectionState.stale, isStale: true, diagnostics: _diagnostics());
    await _service.stop();
  }

  Future<void> handleAppResumed() async {
    if (_disposed) {
      return;
    }
    _pausedByLifecycle = false;
    state = state.copyWith(connectionState: RealtimeConnectionState.reconnecting, isStale: true, diagnostics: _diagnostics());
    await _service.start(sessionId: sessionId, lastEventId: _currentLastEventId);
  }

  Future<void> _handleEvent(RealtimeEventEnvelope event) async {
    if (_disposed || (event.sessionId != null && event.sessionId != sessionId)) {
      return;
    }

    if (_seenEventIds.contains(event.eventId)) {
      _duplicateEvents += 1;
      state = state.copyWith(diagnostics: _diagnostics());
      return;
    }
    _recordSeen(event.eventId);

    if (event.sequenceId == null) {
      _applyEvent(event, authoritative: false);
      await _persistProgress(event);
      return;
    }

    _expectedSequence ??= event.sequenceId;

    if (event.sequenceId! < _expectedSequence!) {
      _duplicateEvents += 1;
      state = state.copyWith(diagnostics: _diagnostics());
      return;
    }

    if (event.sequenceId! > _expectedSequence!) {
      _sequenceGaps += 1;
      _reorderBuffer[event.sequenceId!] = event;
      if (_reorderBuffer.length > 128) {
        _reorderBuffer.remove(_reorderBuffer.firstKey());
      }
      state = state.copyWith(
        connectionState: RealtimeConnectionState.replaying,
        warnings: _trimWarnings([...state.warnings, 'Sequence gap detected at ${event.sequenceId}']),
        diagnostics: _diagnostics(),
      );
      if (event.sequenceId! - _expectedSequence! >= 3) {
        await _recoverFromGap(event.sessionId);
      }
      return;
    }

    _applyEvent(event, authoritative: false);
    _expectedSequence = event.sequenceId! + 1;
    await _persistProgress(event);
    await _drainReorderBuffer();
  }

  Future<void> _drainReorderBuffer() async {
    while (_expectedSequence != null && _reorderBuffer.containsKey(_expectedSequence)) {
      final next = _reorderBuffer.remove(_expectedSequence)!;
      _applyEvent(next, authoritative: false);
      _expectedSequence = next.sequenceId! + 1;
      await _persistProgress(next);
    }
  }

  Future<void> _recoverFromGap(String? eventSessionId) async {
    final targetSessionId = eventSessionId ?? sessionId;
    state = state.copyWith(
      connectionState: RealtimeConnectionState.recovering,
      isRecovering: true,
      warnings: _trimWarnings([...state.warnings, 'Recovering authoritative state...']),
      diagnostics: _diagnostics(),
    );

    final startedAt = DateTime.now();
    final authoritative = await _recovery.fetchLastState(targetSessionId);
    final elapsed = DateTime.now().difference(startedAt);
    _averageReplayDuration = _averageReplayDuration == null
        ? elapsed
        : Duration(milliseconds: ((_averageReplayDuration!.inMilliseconds + elapsed.inMilliseconds) / 2).round());

    if (authoritative == null) {
      state = state.copyWith(connectionState: RealtimeConnectionState.degraded, isRecovering: false, isStale: true, diagnostics: _diagnostics());
      return;
    }

    _replayRecoveries += 1;
    _checkpoint = {
      'session_id': targetSessionId,
      'last_event_id': authoritative['last_event_id'],
      'recovered_at': DateTime.now().toIso8601String(),
    };

    await _recovery.reconcile(
      targetSessionId,
      authoritative,
      apply: (snapshot) async {
        await _repo.persistRecoveredSnapshot(targetSessionId, snapshot);
      },
    );

    await _repo.persistRecoveredSnapshot(targetSessionId, authoritative);
    await _repo.persistCheckpoint(targetSessionId, _checkpoint!);

    final resolvedTimeline = _buildTimelineFromSnapshot(authoritative, authoritativeMode: true);
    final resolvedSequence = _extractSequence(authoritative);
    _expectedSequence = resolvedSequence != null ? resolvedSequence + 1 : _expectedSequence;
    _currentLastEventId = authoritative['last_event_id']?.toString() ?? _currentLastEventId;
    _currentLatestOffset = _currentLastEventId;
    _reorderBuffer.clear();
    _seenEventIds.clear();
    _seenOrder.clear();

    state = state.copyWith(
      connectionState: RealtimeConnectionState.synchronized,
      isRecovering: false,
      isStale: false,
      authoritativeSnapshot: authoritative,
      timeline: resolvedTimeline,
      lastEventId: _currentLastEventId,
      lastSequenceId: _expectedSequence == null ? null : _expectedSequence! - 1,
      latestStreamOffset: _currentLatestOffset,
      warnings: _trimWarnings([...state.warnings, 'Recovered authoritative state from backend']),
      diagnostics: _diagnostics(),
    );
  }

  Future<void> _persistProgress(RealtimeEventEnvelope event) async {
    if (event.sessionId == null) {
      return;
    }
    _currentLastEventId = event.eventId;
    _currentLatestOffset = event.streamOffset;
    await _repo.persistLastEventId(event.sessionId!, event.eventId);
    if (event.sequenceId != null) {
      await _repo.persistLatestSequence(event.sessionId!, event.sequenceId!);
    }
    await _repo.persistCheckpoint(event.sessionId!, {
      'session_id': event.sessionId,
      'event_id': event.eventId,
      'sequence_id': event.sequenceId,
      'stream_offset': event.streamOffset,
      'timestamp': event.ts,
    });
  }

  void _applyEvent(RealtimeEventEnvelope event, {required bool authoritative}) {
    final entry = _toTimelineEntry(event, authoritative: authoritative);
    final timeline = [...state.timeline.where((item) => item.id != entry.id), entry]
      ..sort((left, right) => (left.sequenceId ?? 0).compareTo(right.sequenceId ?? 0));

    final warnings = _warningsForEvent(event, state.warnings);
    final statusState = _statusFromEvent(event);
    state = state.copyWith(
      connectionState: statusState ?? state.connectionState,
      lastEventId: event.eventId,
      lastSequenceId: event.sequenceId ?? state.lastSequenceId,
      latestStreamOffset: event.streamOffset ?? state.latestStreamOffset,
      timeline: _capTimeline(timeline),
      warnings: _trimWarnings(warnings),
      diagnostics: _diagnostics(),
      isStale: false,
      isOffline: false,
    );
  }

  List<RealtimeTimelineEntry> _buildTimelineFromSnapshot(Map<String, dynamic> authoritative, {required bool authoritativeMode}) {
    final session = authoritative['session'];
    final job = authoritative['job'];
    final evidence = authoritative['evidence'];
    final entries = <RealtimeTimelineEntry>[];

    final logs = _extractLogs(session);
    for (var index = 0; index < logs.length; index++) {
      final log = logs[index];
      entries.add(
        RealtimeTimelineEntry(
          id: 'auth-log-$index',
          title: _titleFromType(log['type']?.toString() ?? 'thought'),
          message: log['message']?.toString() ?? '',
          kind: log['type']?.toString() ?? 'thought',
          sequenceId: index + 1,
          sessionId: sessionId,
          timestamp: _parseTimestamp(log['timestamp']) ?? DateTime.now(),
          authoritative: authoritativeMode,
        ),
      );
    }

    final findings = _extractFindings(session);
    for (var index = 0; index < findings.length; index++) {
      entries.add(
        RealtimeTimelineEntry(
          id: 'auth-finding-$index',
          title: 'Evidence Registered',
          message: _renderFindingDescription(findings[index]),
          kind: 'evidence',
          sequenceId: logs.length + index + 1,
          sessionId: sessionId,
          timestamp: DateTime.now(),
          authoritative: authoritativeMode,
        ),
      );
    }

    if (job is Map) {
      final status = job['status']?.toString();
      entries.add(
        RealtimeTimelineEntry(
          id: 'auth-job-status',
          title: status == 'COMPLETED' ? 'Job Completed' : (status == 'FAILED' ? 'Job Failed' : 'Job Updated'),
          message: job['summary']?.toString() ?? 'Backend job state synchronized.',
          kind: 'job',
          sequenceId: entries.length + 1,
          sessionId: sessionId,
          timestamp: DateTime.now(),
          authoritative: authoritativeMode,
        ),
      );
    }

    if (evidence is Map && evidence.isNotEmpty) {
      entries.add(
        RealtimeTimelineEntry(
          id: 'auth-evidence',
          title: 'Evidence Graph Synced',
          message: evidence.entries.map((entry) => '${entry.key}: ${entry.value}').join(' • '),
          kind: 'graph',
          sequenceId: entries.length + 1,
          sessionId: sessionId,
          timestamp: DateTime.now(),
          authoritative: authoritativeMode,
        ),
      );
    }

    return _capTimeline(entries);
  }

  List<Map<String, dynamic>> _extractLogs(Map<String, dynamic>? session) {
    final logs = session?['logs'];
    if (logs is List) {
      return logs.whereType<Map>().map((entry) => Map<String, dynamic>.from(entry)).toList();
    }
    final memory = session?['memory'];
    if (memory is List) {
      return memory.map((item) => <String, dynamic>{'message': item.toString(), 'type': 'thought'}).toList();
    }
    return <Map<String, dynamic>>[];
  }

  List<dynamic> _extractFindings(Map<String, dynamic>? session) {
    final findings = session?['findings'];
    if (findings is List) {
      return findings;
    }
    return const [];
  }

  String _renderFindingDescription(dynamic finding) {
    if (finding is Map) {
      final description = (finding['description'] ?? finding['details'] ?? finding['finding'] ?? '').toString();
      final evidence = (finding['evidence'] ?? finding['reasoning'] ?? '').toString();
      return [description, if (evidence.isNotEmpty) evidence].where((value) => value.trim().isNotEmpty).join(' — ');
    }
    return finding.toString();
  }

  int? _extractSequence(Map<String, dynamic> authoritative) {
    final session = authoritative['session'];
    if (session is Map) {
      final seq = session['sequence_id'] ?? session['last_sequence_id'];
      if (seq is int) {
        return seq;
      }
      if (seq != null) {
        return int.tryParse(seq.toString());
      }
    }
    return null;
  }

  DateTime? _parseTimestamp(dynamic value) {
    if (value == null) {
      return null;
    }
    if (value is DateTime) {
      return value;
    }
    if (value is int) {
      return DateTime.fromMillisecondsSinceEpoch(value);
    }
    return DateTime.tryParse(value.toString());
  }

  RealtimeTimelineEntry _toTimelineEntry(RealtimeEventEnvelope event, {required bool authoritative}) {
    final payload = event.payload ?? const <String, dynamic>{};
    return RealtimeTimelineEntry(
      id: event.eventId,
      title: _titleForEventType(event.eventType, payload),
      message: _messageForEvent(event.eventType, payload),
      kind: _kindForEventType(event.eventType),
      sequenceId: event.sequenceId,
      sessionId: event.sessionId,
      streamOffset: event.streamOffset,
      originInstanceId: event.originInstanceId,
      timestamp: DateTime.fromMillisecondsSinceEpoch(event.ts),
      authoritative: authoritative,
    );
  }

  String _titleFromType(String type) {
    switch (type) {
      case 'error':
        return 'Error';
      case 'success':
        return 'Success';
      case 'action':
        return 'Action';
      case 'warning':
        return 'Warning';
      default:
        return 'Thought';
    }
  }

  String _titleForEventType(String eventType, Map<String, dynamic> payload) {
    switch (eventType) {
      case 'agent.thought':
        return 'Agent Thought';
      case 'agent.evidence_registered':
      case 'evidence.registered':
        return 'Evidence Registered';
      case 'agent.started':
        return 'Verification Started';
      case 'agent.completed':
      case 'job.completed':
        return 'Verification Completed';
      case 'job.failed':
        return 'Verification Failed';
      case 'security.blocked':
      case 'security.rate_limited':
        return 'Security Warning';
      case 'geospatial.analysis':
        return 'Geospatial Analysis';
      default:
        return (payload['title'] ?? eventType).toString();
    }
  }

  String _messageForEvent(String eventType, Map<String, dynamic> payload) {
    final preferred = payload['message'] ?? payload['summary'] ?? payload['detail'] ?? payload['text'];
    if (preferred != null && preferred.toString().trim().isNotEmpty) {
      return preferred.toString();
    }
    if (payload['payload'] is Map) {
      final nested = payload['payload'] as Map;
      final nestedMessage = nested['message'] ?? nested['summary'] ?? nested['detail'] ?? nested['text'];
      if (nestedMessage != null && nestedMessage.toString().trim().isNotEmpty) {
        return nestedMessage.toString();
      }
    }
    return eventType.replaceAll('.', ' ');
  }

  String _kindForEventType(String eventType) {
    if (eventType.startsWith('security.')) {
      return 'security';
    }
    if (eventType.contains('evidence')) {
      return 'evidence';
    }
    if (eventType.contains('thought')) {
      return 'thought';
    }
    if (eventType.contains('job')) {
      return 'job';
    }
    if (eventType.contains('geo')) {
      return 'geospatial';
    }
    return 'info';
  }

  RealtimeConnectionState? _statusFromEvent(RealtimeEventEnvelope event) {
    if (event.eventType == 'job.completed' || event.eventType == 'agent.completed') {
      return RealtimeConnectionState.synchronized;
    }
    if (event.eventType == 'security.blocked' || event.eventType == 'security.rate_limited') {
      return RealtimeConnectionState.degraded;
    }
    return null;
  }

  List<String> _warningsForEvent(RealtimeEventEnvelope event, List<String> currentWarnings) {
    final warnings = [...currentWarnings];
    if (event.eventType == 'security.blocked' || event.eventType == 'security.rate_limited') {
      warnings.add(_messageForEvent(event.eventType, event.payload ?? const <String, dynamic>{}));
    }
    return warnings;
  }

  List<RealtimeTimelineEntry> _capTimeline(List<RealtimeTimelineEntry> entries) {
    if (entries.length <= 200) {
      return entries;
    }
    return entries.sublist(entries.length - 200);
  }

  List<String> _trimWarnings(List<String> warnings) {
    if (warnings.length <= 25) {
      return warnings;
    }
    return warnings.sublist(warnings.length - 25);
  }

  void _recordSeen(String eventId) {
    _seenEventIds.add(eventId);
    _seenOrder.add(eventId);
    while (_seenOrder.length > 512) {
      final removed = _seenOrder.removeFirst();
      _seenEventIds.remove(removed);
    }
  }

  RealtimeDiagnostics _diagnostics() {
    return RealtimeDiagnostics(
      reconnectAttempts: _reconnectAttempts,
      replayRecoveries: _replayRecoveries,
      sequenceGaps: _sequenceGaps,
      duplicateEvents: _duplicateEvents,
      averageReplayDuration: _averageReplayDuration,
      latestStreamOffset: _currentLatestOffset,
      subscriberLagSeconds: _subscriberLagSeconds(),
    );
  }

  int? _subscriberLagSeconds() {
    if (state.timeline.isEmpty) {
      return null;
    }
    return DateTime.now().difference(state.timeline.last.timestamp).inSeconds;
  }

  @override
  void dispose() {
    _disposed = true;
    unawaited(_eventSub?.cancel());
    unawaited(_statusSub?.cancel());
    unawaited(_service.stop());
    super.dispose();
  }
}

final realtimeRepositoryProvider = Provider.autoDispose<RealtimeRepository>((ref) {
  return RealtimeRepository();
});

final realtimeServiceProvider = Provider.autoDispose.family<RealtimeService, String>((ref, sessionId) {
  final service = RealtimeService.fromEnvironment();
  ref.onDispose(service.dispose);
  return service;
});

final realtimeRecoveryCoordinatorProvider = Provider.autoDispose<RecoveryCoordinator>((ref) {
  return RecoveryCoordinator(ref.watch(dioProvider), ref.watch(realtimeRepositoryProvider));
});

final realtimeControllerProvider = StateNotifierProvider.autoDispose.family<RealtimeController, RealtimeState, String>((ref, sessionId) {
  final controller = RealtimeController(
    sessionId,
    ref.watch(realtimeRepositoryProvider),
    ref.watch(realtimeRecoveryCoordinatorProvider),
    ref.watch(realtimeServiceProvider(sessionId)),
  );
  ref.onDispose(controller.dispose);
  return controller;
});
