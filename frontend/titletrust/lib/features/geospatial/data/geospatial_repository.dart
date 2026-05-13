import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:titletrust/core/network/dio_client.dart';
import 'package:titletrust/core/network/network_error.dart';
import 'package:titletrust/core/network/network_executor.dart';
import 'geospatial_job_response.dart';
import 'geospatial_models.dart';

part 'geospatial_repository.g.dart';

@riverpod
GeospatialRepository geospatialRepository(Ref ref) {
  return GeospatialRepository(ref.watch(dioProvider));
}

class GeospatialRepository {
  final Dio _dio;
  final NetworkExecutor _executor = const NetworkExecutor();

  GeospatialRepository(this._dio);

  Future<GeoCheck> verifySite(double lat, double lng, XFile file) async {
    final formData = FormData.fromMap({
      'lat': lat,
      'lng': lng,
      'file': await MultipartFile.fromFile(file.path, filename: file.name),
    });

    final response = await _executor.run(() => _dio.post('/audit/geospatial', data: formData));
    final accepted = GeoCheckJobResponse.fromJson(Map<String, dynamic>.from(response.data as Map));
    return _pollForCompletion(accepted.jobId);
  }

  Future<GeoCheckJobResponse> cancelJob(String jobId) async {
    final response = await _executor.run(() => _dio.post('/audit/jobs/$jobId/cancel'));
    return GeoCheckJobResponse.fromJson(Map<String, dynamic>.from(response.data as Map));
  }

  Future<GeoCheck> _pollForCompletion(String jobId) async {
    for (var attempt = 0; attempt < 60; attempt++) {
      final response = await _executor.run(() => _dio.get('/audit/jobs/$jobId'));
      final job = GeoCheckJobResponse.fromJson(Map<String, dynamic>.from(response.data as Map));
      if (job.status == 'COMPLETED' && job.result != null) {
        return GeoCheck.fromJson(Map<String, dynamic>.from(job.result!));
      }
      if (job.status == 'FAILED' || job.status == 'CANCELLED') {
        throw NetworkError(job.error ?? 'Geospatial verification failed.');
      }
      await Future<void>.delayed(const Duration(seconds: 2));
    }
    throw const NetworkError('Geospatial verification timed out.');
  }
}
