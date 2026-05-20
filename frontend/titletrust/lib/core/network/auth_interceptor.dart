import 'dart:developer' as developer;

import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';

class AuthInterceptor extends Interceptor {
  @override
  Future<void> onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final user = FirebaseAuth.instance.currentUser;

    if (user != null) {
      try {
        final token = await user.getIdToken(false);
        if (token != null && token.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $token';
        }
      } catch (e, stackTrace) {
        developer.log(
          'AuthInterceptor token fetch failed',
          error: e,
          stackTrace: stackTrace,
          name: 'titletrust.auth',
        );
      }
    }

    handler.next(options);
  }
}
