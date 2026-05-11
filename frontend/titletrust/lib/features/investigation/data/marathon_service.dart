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
}

final marathonServiceProvider = Provider<MarathonService>((ref) {
  final dio = ref.watch(dioProvider);
  return MarathonService(dio, const NetworkExecutor());
});
