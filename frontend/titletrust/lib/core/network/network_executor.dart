import 'dart:async';

import 'package:dio/dio.dart';

import 'network_error.dart';

class NetworkExecutor {
  const NetworkExecutor();

  Future<T> run<T>(Future<T> Function() action) async {
    var attempts = 0;
    while (true) {
      attempts += 1;
      try {
        return await action();
      } on DioException catch (error) {
        final statusCode = error.response?.statusCode;
        final retryable = statusCode == null || statusCode >= 500 || error.type == DioExceptionType.connectionTimeout;
        if (attempts < 3 && retryable) {
          await Future<void>.delayed(Duration(milliseconds: 250 * attempts));
          continue;
        }

        throw NetworkError(
          _messageFrom(error),
          statusCode: statusCode,
        );
      } catch (error) {
        throw NetworkError(error.toString());
      }
    }
  }

  String _messageFrom(DioException error) {
    final responseDetail = error.response?.data;
    if (responseDetail is Map && responseDetail["detail"] is String) {
      return responseDetail["detail"] as String;
    }
    if (error.type == DioExceptionType.connectionTimeout) {
      return "Connection timed out. Please try again.";
    }
    return error.message ?? "Unexpected network error.";
  }
}
