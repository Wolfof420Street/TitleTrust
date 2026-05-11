import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:titletrust/core/services/secure_storage_service.dart';

final transportSecurityServiceProvider = Provider<TransportSecurityService>((ref) {
  return TransportSecurityService(ref.watch(secureStorageServiceProvider));
});

class TransportSecurityService {
  final SecureStorageService _storage;

  static const String _requestSecretKey = 'frontend_request_secret';

  TransportSecurityService(this._storage);

  Future<void> ensureRequestSecret() async {
    final existing = await _storage.read(_requestSecretKey);
    if (existing != null && existing.isNotEmpty) {
      return;
    }
    final secret = base64UrlEncode(
      utf8.encode('${DateTime.now().microsecondsSinceEpoch}:${Platform.localHostname}:$kDebugMode'),
    );
    await _storage.write(_requestSecretKey, secret);
  }

  Future<String> requestSecret() async {
    await ensureRequestSecret();
    return (await _storage.read(_requestSecretKey))!;
  }

  Future<void> clearRequestSecret() async {
    await _storage.delete(_requestSecretKey);
  }

  void installCertificatePinning({Set<String> allowedFingerprints = const {}}) {
    if (allowedFingerprints.isEmpty) {
      return;
    }

    HttpOverrides.global = _PinnedHttpOverrides(allowedFingerprints);
  }

  RequestSigningInterceptor buildRequestSigningInterceptor() {
    return RequestSigningInterceptor(requestSecretProvider: requestSecret);
  }
}

class RequestSigningInterceptor extends Interceptor {
  final Future<String> Function() requestSecretProvider;

  RequestSigningInterceptor({required this.requestSecretProvider});

  @override
  Future<void> onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final secret = await requestSecretProvider();
    final signedHeaders = buildSignedHeaders(
      secret: secret,
      method: options.method,
      path: options.path,
      body: options.data,
      correlationId: options.headers['X-Correlation-ID']?.toString(),
    );
    options.headers.addAll(signedHeaders);
    handler.next(options);
  }

  static Map<String, String> buildSignedHeaders({
    required String secret,
    required String method,
    required String path,
    dynamic body,
    String? correlationId,
    String? timestamp,
  }) {
    final resolvedTimestamp = timestamp ?? DateTime.now().toUtc().millisecondsSinceEpoch.toString();
    final resolvedCorrelationId = correlationId ?? _generateCorrelationId();
    final bodyHash = _hashBody(body);
    final signaturePayload = '$method\n$path\n$resolvedTimestamp\n$resolvedCorrelationId\n$bodyHash';
    final signature = Hmac(sha256, utf8.encode(secret)).convert(utf8.encode(signaturePayload)).bytes;

    return {
      'X-Correlation-ID': resolvedCorrelationId,
      'X-Request-Timestamp': resolvedTimestamp,
      'X-Request-Signature': base64UrlEncode(signature),
      'X-Request-Signed': 'true',
    };
  }

  static String _hashBody(dynamic body) {
    if (body == null) {
      return sha256.convert(utf8.encode('')).toString();
    }
    if (body is String) {
      return sha256.convert(utf8.encode(body)).toString();
    }
    return sha256.convert(utf8.encode(jsonEncode(body))).toString();
  }

  static String _generateCorrelationId() {
    return base64UrlEncode(utf8.encode('${DateTime.now().microsecondsSinceEpoch}:${Platform.localHostname}'));
  }
}

class _PinnedHttpOverrides extends HttpOverrides {
  final Set<String> allowedFingerprints;

  _PinnedHttpOverrides(this.allowedFingerprints);

  @override
  HttpClient createHttpClient(SecurityContext? context) {
    final client = super.createHttpClient(context);
    client.badCertificateCallback = (X509Certificate cert, String host, int port) {
      final fingerprint = sha256.convert(cert.der).toString();
      return allowedFingerprints.contains(fingerprint) || allowedFingerprints.contains(fingerprint.toUpperCase());
    };
    return client;
  }
}
