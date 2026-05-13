import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:titletrust/core/network/network_error.dart';
import 'package:titletrust/core/network/network_executor.dart';

void main() {
  group('NetworkExecutor', () {
    test('surfaces standard FastAPI detail strings', () async {
      final executor = NetworkExecutor();
      final requestOptions = RequestOptions(path: '/audit/tick');

      final future = executor.run(() async {
        throw DioException(
          requestOptions: requestOptions,
          response: Response<dynamic>(
            requestOptions: requestOptions,
            statusCode: 401,
            data: {'detail': 'Missing authentication token'},
          ),
          type: DioExceptionType.badResponse,
        );
      });

      await expectLater(
        future,
        throwsA(
          isA<NetworkError>().having(
            (error) => error.message,
            'message',
            'Missing authentication token',
          ),
        ),
      );
    });

    test('surfaces FastAPI 422 validation arrays', () async {
      final executor = NetworkExecutor();
      final requestOptions = RequestOptions(path: '/audit/start');

      final future = executor.run(() async {
        throw DioException(
          requestOptions: requestOptions,
          response: Response<dynamic>(
            requestOptions: requestOptions,
            statusCode: 422,
            data: {
              'detail': [
                {
                  'loc': ['body', 'file'],
                  'msg': 'Field required',
                  'type': 'missing',
                },
                {
                  'loc': ['body', 'lat'],
                  'msg': 'Input should be less than or equal to 90',
                  'type': 'less_than_equal',
                },
              ],
            },
          ),
          type: DioExceptionType.badResponse,
        );
      });

      await expectLater(
        future,
        throwsA(
          isA<NetworkError>().having(
            (error) => error.message,
            'message',
            contains('body.file: Field required'),
          ),
        ),
      );
    });
  });
}
