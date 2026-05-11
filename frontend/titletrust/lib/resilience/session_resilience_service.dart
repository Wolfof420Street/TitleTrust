import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:titletrust/core/services/secure_storage_service.dart';

final sessionResilienceServiceProvider = Provider<SessionResilienceService>((ref) {
  return SessionResilienceService(ref.watch(secureStorageServiceProvider));
});

class SessionResilienceService {
  final SecureStorageService _storage;
  final StreamController<bool> _logoutController = StreamController<bool>.broadcast();

  static const String _sessionTokenKey = 'frontend_session_token';
  static const String _sessionExpiresAtKey = 'frontend_session_expires_at';
  static const String _lastKnownUserKey = 'frontend_last_known_user';

  SessionResilienceService(this._storage);

  Stream<bool> get forcedLogoutStream => _logoutController.stream;

  Future<void> persistSession({required String token, required String expiresAt, String? userId}) async {
    await _storage.write(_sessionTokenKey, token);
    await _storage.write(_sessionExpiresAtKey, expiresAt);
    if (userId != null && userId.isNotEmpty) {
      await _storage.write(_lastKnownUserKey, userId);
    }
  }

  Future<({String? token, String? expiresAt, String? userId})> restoreSession() async {
    final token = await _storage.read(_sessionTokenKey);
    final expiresAt = await _storage.read(_sessionExpiresAtKey);
    final userId = await _storage.read(_lastKnownUserKey);
    return (token: token, expiresAt: expiresAt, userId: userId);
  }

  Future<void> clearSession() async {
    await _storage.delete(_sessionTokenKey);
    await _storage.delete(_sessionExpiresAtKey);
    await _storage.delete(_lastKnownUserKey);
    _logoutController.add(true);
  }

  Future<bool> isSessionExpired() async {
    final expiresAt = await _storage.read(_sessionExpiresAtKey);
    if (expiresAt == null || expiresAt.isEmpty) {
      return true;
    }
    final parsed = DateTime.tryParse(expiresAt);
    if (parsed == null) {
      return true;
    }
    return DateTime.now().toUtc().isAfter(parsed.toUtc());
  }

  Future<void> propagateForcedLogout() async {
    await clearSession();
  }

  Future<void> rememberCurrentUser(String userId) async {
    await _storage.write(_lastKnownUserKey, userId);
  }

  void dispose() {
    _logoutController.close();
  }
}
