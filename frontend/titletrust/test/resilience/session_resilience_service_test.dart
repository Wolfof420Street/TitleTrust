import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:titletrust/core/services/secure_storage_service.dart';
import 'package:titletrust/resilience/session_resilience_service.dart';

class InMemorySecureStorageService extends SecureStorageService {
  final Map<String, String> _values = {};

  InMemorySecureStorageService() : super(const FlutterSecureStorage());

  @override
  Future<void> write(String key, String value) async {
    _values[key] = value;
  }

  @override
  Future<String?> read(String key) async {
    return _values[key];
  }

  @override
  Future<void> delete(String key) async {
    _values.remove(key);
  }
}

void main() {
  group('SessionResilienceService', () {
    test('persists and restores a session', () async {
      final storage = InMemorySecureStorageService();
      final service = SessionResilienceService(storage);

      await service.persistSession(
        token: 'token-123',
        expiresAt: '2026-05-11T00:00:00Z',
        userId: 'user-1',
      );

      final restored = await service.restoreSession();
      expect(restored.token, 'token-123');
      expect(restored.expiresAt, '2026-05-11T00:00:00Z');
      expect(restored.userId, 'user-1');
    });

    test('clears session and emits logout', () async {
      final storage = InMemorySecureStorageService();
      final service = SessionResilienceService(storage);
      final events = <bool>[];
      final subscription = service.forcedLogoutStream.listen(events.add);

      await service.persistSession(
        token: 'token-123',
        expiresAt: '2026-05-11T00:00:00Z',
        userId: 'user-1',
      );
      await service.clearSession();

      final restored = await service.restoreSession();
      expect(restored.token, isNull);
      expect(events, [true]);

      await subscription.cancel();
    });

    test('reports expired sessions', () async {
      final storage = InMemorySecureStorageService();
      final service = SessionResilienceService(storage);

      await service.persistSession(
        token: 'token-123',
        expiresAt: '2000-01-01T00:00:00Z',
      );

      expect(await service.isSessionExpired(), isTrue);
    });
  });
}
