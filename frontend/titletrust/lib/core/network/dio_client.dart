import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'auth_interceptor.dart';

part 'dio_client.g.dart';

@Riverpod(keepAlive: true)
Dio dio(Ref ref) {
  final baseUrl = dotenv.env['API_BASE_URL'] ?? 'http://127.0.0.1:8000';

  final dio = Dio(
    BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 120),
      receiveTimeout: const Duration(seconds: 120),
      headers: {
        'Content-Type': 'application/json',
      },
    ),
  );

  dio.interceptors.add(LogInterceptor(responseBody: true, requestBody: true));
  dio.interceptors.add(AuthInterceptor());

  return dio;
}
