import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:titletrust/core/network/dio_client.dart';
import 'package:titletrust/core/network/network_error.dart';
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
  static const String _frontendRequestSecretKey = 'frontend_request_secret';

  DeviceSessionService(this._dio, this._storage, this._transportSecurity, this._executor);

  Future<void> register() async {
    var sessionId = await _storage.read(_deviceSessionIdKey);
    if (sessionId == null || sessionId.isEmpty) {
      sessionId = _generateUuidV4();
      await _storage.write(_deviceSessionIdKey, sessionId);
    }
    final requestSecret = await _transportSecurity.requestSecret();
    final packageInfo = await PackageInfo.fromPlatform();
    final appVersion = '${packageInfo.version}+${packageInfo.buildNumber}';

    String deviceId;
    try {
      deviceId = Platform.localHostname;
      if (deviceId.isEmpty) deviceId = sessionId;
    } catch (_) {
      deviceId = sessionId;
    }

    await _executor.run(
      () => _dio.post(
        '/auth/device-sessions',
        data: {
          'session_id': sessionId,
          'device_id': deviceId,
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
        options: Options(
          extra: {
            RequestSigningInterceptor.requestSecretOverrideKey: newSecret,
          },
        ),
      ),
    );
    await _storage.write(_frontendRequestSecretKey, newSecret);
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
    await _storage.delete(_frontendRequestSecretKey);
  }

  Future<List<Map<String, dynamic>>> listActiveSessions() async {
    final response = await _executor.run(() => _dio.get('/auth/device-sessions'));
    final data = response.data;
    if (data is Map && data['sessions'] is List) {
      return (data['sessions'] as List)
          .map((entry) {
            if (entry is Map) {
              return Map<String, dynamic>.from(entry);
            }
            throw const FormatException('Invalid device session entry');
          })
          .toList(growable: false);
    }
    throw const NetworkError('Unexpected device session list response.');
  }

  String _generateUuidV4() {
    // Generate 16 random bytes and format as UUID v4
    final rnd = Random.secure();
    final bytes = List<int>.generate(16, (_) => rnd.nextInt(256));
    // Set variant and version bits per RFC 4122
    bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant
    String hex(int i) => bytes[i].toRadixString(16).padLeft(2, '0');
    final parts = [
      List.generate(4, (i) => hex(i)).join(),
      List.generate(2, (i) => hex(i + 4)).join(),
      List.generate(2, (i) => hex(i + 6)).join(),
      List.generate(2, (i) => hex(i + 8)).join(),
      List.generate(6, (i) => hex(i + 10)).join(),
    ];
    return parts.join('-');
  }
}
