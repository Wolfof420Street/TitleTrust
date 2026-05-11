import 'dart:async';
import 'dart:developer' as developer;

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:sentry_flutter/sentry_flutter.dart';

class FrontendTelemetryService {
  bool _initialized = false;

  Future<void> initialize() async {
    if (_initialized) {
      return;
    }

    final packageInfo = await PackageInfo.fromPlatform();
    final appVersion = '${packageInfo.version}+${packageInfo.buildNumber}';
    FlutterError.onError = (details) {
      FirebaseCrashlytics.instance.recordFlutterFatalError(details);
      developer.log('Flutter error', error: details.exception, stackTrace: details.stack, name: 'titletrust.telemetry');
    };

    PlatformDispatcher.instance.onError = (error, stack) {
      FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
      developer.log('Platform error', error: error, stackTrace: stack, name: 'titletrust.telemetry');
      return true;
    };

    _initialized = true;
    developer.log('Frontend telemetry initialized ($appVersion)', name: 'titletrust.telemetry');
  }

  Future<void> recordStartupTiming(Duration duration) async {
    developer.log(
      'startup_timing',
      name: 'titletrust.telemetry',
      error: {'startup_ms': duration.inMilliseconds},
    );
    await FirebaseCrashlytics.instance.setCustomKey('startup_ms', duration.inMilliseconds);
  }

  Future<void> recordNetworkQuality() async {
    final connectivity = await Connectivity().checkConnectivity();
    await FirebaseCrashlytics.instance.setCustomKey('connectivity', connectivity.first.name);
    developer.log('network_quality', name: 'titletrust.telemetry', error: {'connectivity': connectivity.first.name});
  }

  Future<void> setCorrelationId(String correlationId) async {
    await FirebaseCrashlytics.instance.setCustomKey('correlation_id', correlationId);
  }

  Future<void> reportHandledError(Object error, StackTrace stackTrace, {String? context}) async {
    await FirebaseCrashlytics.instance.recordError(error, stackTrace, reason: context, fatal: false);
    await Sentry.captureException(error, stackTrace: stackTrace, hint: Hint.withMap({'context': context ?? 'unknown'}));
  }
}
