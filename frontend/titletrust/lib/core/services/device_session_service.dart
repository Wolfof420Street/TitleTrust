import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:titletrust/core/network/dio_client.dart';
import 'package:titletrust/core/network/network_executor.dart';
import 'package:titletrust/core/services/secure_storage_service.dart';
import 'package:titletrust/security/transport_security_service.dart';

final deviceSessionServiceProvider = Provider<DeviceSessionService>((ref) {
  return DeviceSessionService(
    ref.watch(dioProvider),
    ref.watch(secureStorageServiceProvider),
    ref.watch(transportSecurityServiceProvider),
    const NetworkExecutor(),
  );
});

class DeviceSessionService {
  final Dio _dio;
  final SecureStorageService _storage;
  final TransportSecurityService _transportSecurity;
  final NetworkExecutor _executor;
  static const String _deviceSessionIdKey = 'device_session_id';

  DeviceSessionService(this._dio, this._storage, this._transportSecurity, this._executor);

  Future<void> register() async {
    var sessionId = await _storage.read(_deviceSessionIdKey);
    sessionId ??= '${Platform.operatingSystem}-${DateTime.now().millisecondsSinceEpoch}';
    await _storage.write(_deviceSessionIdKey, sessionId);
    final requestSecret = await _transportSecurity.requestSecret();
    final packageInfo = await PackageInfo.fromPlatform();
    final appVersion = '${packageInfo.version}+${packageInfo.buildNumber}';

    await _executor.run(
      () => _dio.post(
        '/auth/device-sessions',
        data: {
          'session_id': sessionId,
          'device_id': Platform.localHostname,
          'platform': Platform.operatingSystem,
          'app_version': appVersion,
          'request_secret': requestSecret,
        },
      ),
    );
  }

  Future<void> rotateSigningSecret() async {
    final sessionId = await _storage.read(_deviceSessionIdKey);
    if (sessionId == null || sessionId.isEmpty) {
      await register();
      return;
    }

    // Generate new secret without persisting it yet
    final newSecret = _generateRandomSecret();
    final packageInfo = await PackageInfo.fromPlatform();
    final appVersion = '${packageInfo.version}+${packageInfo.buildNumber}';

    try {
      // POST is signed with the currently persisted old secret
      // The request carries the new secret we want the server to expect next time
      await _executor.run(
        () => _dio.post(
          '/auth/device-sessions',
          data: {
            'session_id': sessionId,
            'device_id': Platform.localHostname,
            'platform': Platform.operatingSystem,
            'app_version': appVersion,
            'request_secret': newSecret,
          },
        ),
      );
      // Only persist new secret after successful POST
      await _storage.write('frontend_request_secret', newSecret);
    } catch (e) {
      // On failure, the old secret remains persisted and can be reused for retry
      rethrow;
    }
  }

  String _generateRandomSecret() {
    try {
      final random = Random.secure();
      final values = List<int>.generate(32, (i) => random.nextInt(256));
      return base64UrlEncode(values);
    } on UnsupportedError catch (e) {
      throw Exception('Random.secure() unavailable on this platform: $e');
    }
  }

  Future<void> revoke() async {
    final sessionId = await _storage.read(_deviceSessionIdKey);
    if (sessionId == null || sessionId.isEmpty) {
      return;
    }
    await _executor.run(() => _dio.post('/auth/device-sessions/$sessionId/revoke'));
    await _storage.delete(_deviceSessionIdKey);
    // Also delete the request secret so the client cannot reuse the signing key
    await _storage.delete('frontend_request_secret');
  }
}
