import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'auth_interceptor.dart';
import 'package:titletrust/core/services/secure_storage_service.dart';
import 'package:titletrust/security/transport_security_service.dart';

part 'dio_client.g.dart';

@Riverpod(keepAlive: true)
Dio dio(Ref ref) {
  final baseUrl = dotenv.env['API_BASE_URL'] ?? 'http://127.0.0.1:8000';

  final dio = Dio(
    BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 60),
      sendTimeout: const Duration(seconds: 60),
      headers: const {'Content-Type': 'application/json'},
      responseType: ResponseType.json,
      validateStatus: (status) => status != null && status >= 200 && status < 500,
    ),
  );

  if (!kReleaseMode) {
    dio.interceptors.add(
      LogInterceptor(
        requestBody: false,
        responseBody: false,
        requestHeader: false,
        responseHeader: false,
      ),
    );
  }

  dio.interceptors.add(AuthInterceptor());
  dio.interceptors.add(
    RequestSigningInterceptor(
      requestSecretProvider: () {
        final transport = TransportSecurityService(ref.read(secureStorageServiceProvider));
        return transport.requestSecret();
      },
      deviceSessionIdProvider: () {
        final storage = ref.read(secureStorageServiceProvider);
        return storage.read('device_session_id');
      },
    ),
  );
  return dio;
}
