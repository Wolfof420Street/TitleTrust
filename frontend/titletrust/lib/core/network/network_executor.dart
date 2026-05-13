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
    final parsedResponseMessage = _extractResponseMessage(responseDetail);
    if (parsedResponseMessage != null && parsedResponseMessage.isNotEmpty) {
      return parsedResponseMessage;
    }
    if (error.type == DioExceptionType.connectionTimeout) {
      return "Connection timed out. Please try again.";
    }
    return error.message ?? "Unexpected network error.";
  }

  String? _extractResponseMessage(dynamic responseDetail) {
    if (responseDetail is Map) {
      final detail = responseDetail["detail"];
      if (detail is String) {
        return detail;
      }
      if (detail is List) {
        final messages = detail
            .map((entry) => _formatValidationError(entry))
            .whereType<String>()
            .where((message) => message.isNotEmpty)
            .toList(growable: false);
        if (messages.isNotEmpty) {
          return messages.join('; ');
        }
      }
      final message = responseDetail["message"];
      if (message is String && message.isNotEmpty) {
        return message;
      }
    }
    if (responseDetail is List) {
      final messages = responseDetail
          .map((entry) => _formatValidationError(entry))
          .whereType<String>()
          .where((message) => message.isNotEmpty)
          .toList(growable: false);
      if (messages.isNotEmpty) {
        return messages.join('; ');
      }
    }
    return null;
  }

  String? _formatValidationError(dynamic entry) {
    if (entry is Map) {
      final location = entry['loc'];
      final message = entry['msg'];
      final locationText = location is Iterable
          ? location.map((segment) => segment.toString()).join('.')
          : '';
      if (message is String && message.isNotEmpty) {
        if (locationText.isNotEmpty) {
          return '$locationText: $message';
        }
        return message;
      }
    }
    if (entry == null) {
      return null;
    }
    return entry.toString();
  }
}
