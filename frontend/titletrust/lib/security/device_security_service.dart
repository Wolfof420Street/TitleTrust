import 'dart:io';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_auth/local_auth.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'package:titletrust/core/services/secure_storage_service.dart';

final deviceSecurityServiceProvider = Provider<DeviceSecurityService>((ref) {
  return DeviceSecurityService(ref.watch(secureStorageServiceProvider));
});

class DeviceIntegrityReport {
  final bool isPhysicalDevice;
  final bool supportsBiometrics;
  final bool requiresChallenge;
  final String deviceBinding;

  const DeviceIntegrityReport({
    required this.isPhysicalDevice,
    required this.supportsBiometrics,
    required this.requiresChallenge,
    required this.deviceBinding,
  });
}

class DeviceSecurityService {
  final SecureStorageService _storage;
  final LocalAuthentication _localAuth;
  final DeviceInfoPlugin _deviceInfo;

  static const String _deviceBindingKey = 'frontend_device_binding';
  static const String _biometricGateKey = 'frontend_biometric_gate';

  DeviceSecurityService(
    this._storage, {
    LocalAuthentication? localAuth,
    DeviceInfoPlugin? deviceInfo,
  })  : _localAuth = localAuth ?? LocalAuthentication(),
        _deviceInfo = deviceInfo ?? DeviceInfoPlugin();

  Future<bool> unlockWithBiometrics({String reason = 'Authenticate to continue'}) async {
    final canCheck = await _localAuth.canCheckBiometrics;
    final isSupported = await _localAuth.isDeviceSupported();
    if (!canCheck && !isSupported) {
      return false;
    }

    try {
      final authenticated = await _localAuth.authenticate(
        localizedReason: reason,
        options: const AuthenticationOptions(
          biometricOnly: true,
          stickyAuth: true,
          useErrorDialogs: true,
        ),
      );
      if (authenticated) {
        await _storage.write(_biometricGateKey, 'true');
      }
      return authenticated;
    } catch (_) {
      return false;
    }
  }

  Future<DeviceIntegrityReport> assessDeviceIntegrity() async {
    final binding = await getDeviceBinding();
    if (Platform.isAndroid) {
      final android = await _deviceInfo.androidInfo;
      return DeviceIntegrityReport(
        isPhysicalDevice: android.isPhysicalDevice,
        supportsBiometrics: await _localAuth.canCheckBiometrics,
        requiresChallenge: !android.isPhysicalDevice || kDebugMode,
        deviceBinding: binding,
      );
    }

    if (Platform.isIOS) {
      final ios = await _deviceInfo.iosInfo;
      return DeviceIntegrityReport(
        isPhysicalDevice: ios.isPhysicalDevice,
        supportsBiometrics: await _localAuth.canCheckBiometrics,
        requiresChallenge: !ios.isPhysicalDevice || kDebugMode,
        deviceBinding: binding,
      );
    }

    return DeviceIntegrityReport(
      isPhysicalDevice: true,
      supportsBiometrics: await _localAuth.canCheckBiometrics,
      requiresChallenge: kDebugMode,
      deviceBinding: binding,
    );
  }

  Future<String> getDeviceBinding() async {
    final stored = await _storage.read(_deviceBindingKey);
    if (stored != null && stored.isNotEmpty) {
      return stored;
    }

    final packageInfo = await PackageInfo.fromPlatform();
    final binding = await _buildBinding(packageInfo);
    await _storage.write(_deviceBindingKey, binding);
    return binding;
  }

  Future<void> clearSecureGate() async {
    await _storage.delete(_biometricGateKey);
  }

  Future<bool> isBiometricGateOpen() async {
    return (await _storage.read(_biometricGateKey)) == 'true';
  }

  Future<String> _buildBinding(PackageInfo packageInfo) async {
    final deviceId = Platform.localHostname;
    final platform = Platform.operatingSystem;
    final version = packageInfo.version;
    final buildNumber = packageInfo.buildNumber;
    return '$platform:$deviceId:$version:$buildNumber';
  }
}
