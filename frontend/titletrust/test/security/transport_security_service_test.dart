import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:titletrust/core/services/secure_storage_service.dart';
import 'package:titletrust/security/transport_security_service.dart';

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
  group('RequestSigningInterceptor', () {
    test('buildSignedHeaders is deterministic for same input', () {
      final first = RequestSigningInterceptor.buildSignedHeaders(
        secret: 'secret-value',
        method: 'POST',
        path: '/auth/login',
        body: {'username': 'user'},
        correlationId: 'corr-1',
        timestamp: '12345',
      );
      final second = RequestSigningInterceptor.buildSignedHeaders(
        secret: 'secret-value',
        method: 'POST',
        path: '/auth/login',
        body: {'username': 'user'},
        correlationId: 'corr-1',
        timestamp: '12345',
      );

      expect(first, second);
      expect(first['X-Request-Signed'], 'true');
      expect(first['X-Correlation-ID'], 'corr-1');
    });

    test('buildSignedHeaders changes when body changes', () {
      final first = RequestSigningInterceptor.buildSignedHeaders(
        secret: 'secret-value',
        method: 'POST',
        path: '/auth/login',
        body: {'username': 'user-1'},
        correlationId: 'corr-1',
        timestamp: '12345',
      );
      final second = RequestSigningInterceptor.buildSignedHeaders(
        secret: 'secret-value',
        method: 'POST',
        path: '/auth/login',
        body: {'username': 'user-2'},
        correlationId: 'corr-1',
        timestamp: '12345',
      );

      expect(first['X-Request-Signature'], isNot(second['X-Request-Signature']));
    });
  });

  group('TransportSecurityService', () {
    test('ensures and reuses a request secret', () async {
      final storage = InMemorySecureStorageService();
      final service = TransportSecurityService(storage);

      final firstSecret = await service.requestSecret();
      final secondSecret = await service.requestSecret();

      expect(firstSecret, isNotEmpty);
      expect(firstSecret, secondSecret);
    });

    test('rotates the request secret', () async {
      final storage = InMemorySecureStorageService();
      final service = TransportSecurityService(storage);

      final firstSecret = await service.requestSecret();
      final rotatedSecret = await service.rotateRequestSecret();

      expect(rotatedSecret, isNotEmpty);
      expect(rotatedSecret, isNot(firstSecret));
    });
  });
}
