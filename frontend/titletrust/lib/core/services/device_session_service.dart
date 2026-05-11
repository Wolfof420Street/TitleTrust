import 'dart:io';

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

    // Read current secret before generating new one
    final currentSecret = await _transportSecurity.requestSecret();
    // Generate new secret without persisting yet
    await _transportSecurity.clearRequestSecret();
    await _transportSecurity.ensureRequestSecret();
    final newSecret = await _transportSecurity.requestSecret();
    final packageInfo = await PackageInfo.fromPlatform();
    final appVersion = '${packageInfo.version}+${packageInfo.buildNumber}';

    try {
      // Only persist new secret after successful POST
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
    } catch (e) {
      // Rollback to previous secret on failure
      await _storage.write('frontend_request_secret', currentSecret);
      rethrow;
    }
  }

  Future<void> revoke() async {
    final sessionId = await _storage.read(_deviceSessionIdKey);
    if (sessionId == null || sessionId.isEmpty) {
      return;
    }
    await _executor.run(() => _dio.post('/auth/device-sessions/$sessionId/revoke'));
    await _storage.delete(_deviceSessionIdKey);
  }
}
