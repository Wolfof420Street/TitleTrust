import 'dart:async';
import 'package:dio/dio.dart';
import 'realtime_repository.dart';

class RecoveryCoordinator {
  final Dio _dio;
  final RealtimeRepository _repo;

  RecoveryCoordinator(this._dio, this._repo);

  /// Fetches authoritative last-state and returns parsed map.
  Future<Map<String, dynamic>?> fetchLastState(String sessionId) async {
    final resp = await _dio.get('/realtime/last-state/$sessionId');
    if (resp.statusCode == 200) {
      return resp.data as Map<String, dynamic>;
    }
    return null;
  }

  /// Reconcile local state given authoritative snapshot. Client-specific merge logic should be provided by caller.
  Future<void> reconcile(String sessionId, Map<String, dynamic> authoritative, {required FutureOr<void> Function(Map<String, dynamic>) apply}) async {
    // clear optimistic checkpoints and apply authoritative
    await _repo.clearSessionCheckpoint(sessionId);
    await apply(authoritative);
  }
}
