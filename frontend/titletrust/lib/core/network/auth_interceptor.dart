import 'dart:developer' as developer;
import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';

class AuthInterceptor extends Interceptor {
  @override
  Future<void> onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final user = FirebaseAuth.instance.currentUser;

    if (user != null) {
      try {
        final token = await user.getIdToken();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
      } catch (e, stackTrace) {
        // Log error but proceed without token if fetching fails
        developer.log(
          "AuthInterceptor: Failed to get token",
          error: e,
          stackTrace: stackTrace,
        );
      }
    }

    return super.onRequest(options, handler);
  }
}
