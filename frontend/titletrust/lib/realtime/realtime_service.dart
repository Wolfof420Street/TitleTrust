import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'models.dart';

class RealtimeService {
  final String baseUrl;
  final HttpClient _client = HttpClient();
  final StreamController<RealtimeEventEnvelope> _eventsController = StreamController<RealtimeEventEnvelope>.broadcast();
  final StreamController<RealtimeConnectionState> _statusController = StreamController<RealtimeConnectionState>.broadcast();

  bool _running = false;
  bool _disposed = false;
  String? _sessionId;
  String? _lastEventId;
  HttpClientRequest? _activeRequest;
  int _retryAttempts = 0;
  final int _retryBudget = 8;
  final Duration _heartbeatTimeout = const Duration(seconds: 35);

  RealtimeService(this.baseUrl);

  factory RealtimeService.fromEnvironment() {
    const defaultBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://127.0.0.1:8000');
    return RealtimeService(defaultBaseUrl);
  }

  Stream<RealtimeEventEnvelope> get events => _eventsController.stream;
  Stream<RealtimeConnectionState> get connectionStates => _statusController.stream;
  RealtimeConnectionState _currentState = RealtimeConnectionState.disconnected;
  RealtimeConnectionState get currentState => _currentState;

  Future<void> start({required String sessionId, String? lastEventId}) async {
    _sessionId = sessionId;
    _lastEventId = lastEventId;
    if (_running) {
      return;
    }
    _running = true;
    unawaited(_connectionLoop());
  }

  Future<void> stop() async {
    _running = false;
    try {
      _activeRequest?.abort();
    } catch (_) {}
    _emitState(RealtimeConnectionState.disconnected);
  }

  Future<void> _connectionLoop() async {
    final rng = Random();
    while (_running && !_disposed) {
      try {
        _emitState(_retryAttempts == 0 ? RealtimeConnectionState.connecting : RealtimeConnectionState.reconnecting);
        final uri = Uri.parse('$baseUrl/realtime/sse');
        final request = await _client.getUrl(uri);
        _activeRequest = request;
        request.headers.set(HttpHeaders.acceptHeader, 'text/event-stream');
        if (_lastEventId != null && _lastEventId!.isNotEmpty) {
          request.headers.set('Last-Event-ID', _lastEventId!);
        }
        if (_sessionId != null && _sessionId!.isNotEmpty) {
          request.headers.set('X-Session-ID', _sessionId!);
        }

        final response = await request.close();
        if (response.statusCode >= 400) {
          throw HttpException('SSE returned ${response.statusCode}');
        }

        if (_retryAttempts > 0) {
          _emitState(RealtimeConnectionState.replaying);
        }
        _retryAttempts = 0;

        final lineStream = response.transform(utf8.decoder).transform(const LineSplitter()).timeout(
          _heartbeatTimeout,
          onTimeout: (sink) => sink.addError(TimeoutException('SSE heartbeat timeout')),
        );

        await for (final line in lineStream) {
          if (!_running || _disposed) {
            break;
          }
          if (line.isEmpty || line.startsWith(':')) {
            continue;
          }
          if (!line.startsWith('data:')) {
            continue;
          }
          final payload = line.substring(5).trimLeft();
          try {
            final event = RealtimeEventEnvelope.fromData(payload);
            _eventsController.add(event);
            _lastEventId = event.eventId;
          } catch (_) {
            // Malformed payloads are isolated so the connection stays alive.
          }
        }
      } catch (_) {
        if (!_running || _disposed) {
          break;
        }
        _retryAttempts += 1;
        _emitState(_retryAttempts >= _retryBudget ? RealtimeConnectionState.degraded : RealtimeConnectionState.reconnecting);
        final backoffSeconds = min(30, pow(2, _retryAttempts).toInt());
        final jitterMs = rng.nextInt(700);
        await Future.delayed(Duration(seconds: backoffSeconds, milliseconds: jitterMs));
        continue;
      }

      if (_running && !_disposed) {
        _retryAttempts += 1;
        _emitState(RealtimeConnectionState.reconnecting);
        final backoffSeconds = min(30, pow(2, _retryAttempts).toInt());
        await Future.delayed(Duration(seconds: backoffSeconds));
      }
    }
  }

  void _emitState(RealtimeConnectionState state) {
    _currentState = state;
    if (!_statusController.isClosed) {
      _statusController.add(state);
    }
  }

  void dispose() {
    _disposed = true;
    _running = false;
    try {
      _activeRequest?.abort();
    } catch (_) {}
    if (!_eventsController.isClosed) {
      _eventsController.close();
    }
    if (!_statusController.isClosed) {
      _statusController.close();
    }
    _client.close(force: true);
  }
}
