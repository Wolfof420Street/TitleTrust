import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:titletrust/core/network/network_executor.dart';
import 'package:titletrust/core/network/dio_client.dart';
import 'package:titletrust/features/investigation/data/marathon_models.dart';

class MarathonService {
  final Dio _dio;
  final NetworkExecutor _executor;

  MarathonService(this._dio, this._executor);

  Future<InvestigationStartResponse> startInvestigation(File file) async {
    final fileName = file.path.split('/').last;
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(file.path, filename: fileName),
    });
    final response = await _executor.run(() => _dio.post('/audit/start', data: formData));
    return InvestigationStartResponse.fromJson(Map<String, dynamic>.from(response.data as Map));
  }

  Future<InvestigationStartResponse> startInvestigationFromStorage({
    required String objectPath,
    required String originalFilename,
  }) async {
    final response = await _executor.run(
      () => _dio.post(
        '/audit/start/from-storage',
        data: {
          'object_path': objectPath,
          'original_filename': originalFilename,
        },
      ),
    );
    return InvestigationStartResponse.fromJson(Map<String, dynamic>.from(response.data as Map));
  }

  Future<InvestigationTickResponse> tickSession(String sessionId) async {
    final response = await _executor.run(
      () => _dio.post(
        '/audit/tick',
        data: {'session_id': sessionId},
      ),
    );
    return InvestigationTickResponse.fromJson(Map<String, dynamic>.from(response.data as Map));
  }

  Future<InvestigationSessionStatusResponse> getSessionStatus(String sessionId) async {
    final response = await _executor.run(() => _dio.get('/audit/status/$sessionId'));
    return InvestigationSessionStatusResponse.fromJson(Map<String, dynamic>.from(response.data as Map));
  }

  Future<InvestigationRetryResponse> retrySession(String sessionId) async {
    final response = await _executor.run(() => _dio.post('/audit/retry/$sessionId'));
    return InvestigationRetryResponse.fromJson(Map<String, dynamic>.from(response.data as Map));
  }
}

final marathonServiceProvider = Provider<MarathonService>((ref) {
  final dio = ref.watch(dioProvider);
  return MarathonService(dio, const NetworkExecutor());
});
