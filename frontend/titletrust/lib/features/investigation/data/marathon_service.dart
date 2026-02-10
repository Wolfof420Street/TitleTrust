import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:titletrust/core/network/dio_client.dart';

class MarathonService {
  final Dio _dio;

  MarathonService(this._dio);

  Future<String> startInvestigation(File file) async {
    final fileName = file.path.split('/').last;
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(file.path, filename: fileName),
    });

    try {
      // Endpoint /audit/start returns { session_id: "...", status: "..." }
      final response = await _dio.post('/audit/start', data: formData);

      if (response.statusCode == 200) {
        return response.data['session_id'];
      } else {
        throw Exception("Failed to start investigation: ${response.statusMessage}");
      }
    } on DioException catch (e) {
      throw Exception("Network Error: ${e.message}");
    }
  }
}

final marathonServiceProvider = Provider<MarathonService>((ref) {
  final dio = ref.watch(dioProvider);
  return MarathonService(dio);
});
