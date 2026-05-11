import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:titletrust/core/network/network_error.dart';
import 'package:titletrust/core/network/network_executor.dart';
import 'package:titletrust/core/network/dio_client.dart';
import 'forensic_job_response.dart';
import 'forensic_models.dart';

part 'forensic_repository.g.dart';

@riverpod
ForensicRepository forensicRepository(Ref ref) {
  return ForensicRepository(ref.watch(dioProvider));
}

class ForensicRepository {
  final Dio _dio;
  final NetworkExecutor _executor = const NetworkExecutor();

  ForensicRepository(this._dio);

  Future<AuditResponse> uploadDocuments(List<XFile> files) async {
    final formData = FormData();

    for (var file in files) {
      formData.files.add(MapEntry(
        'files',
        await MultipartFile.fromFile(file.path, filename: file.name),
      ));
    }

    final response = await _executor.run(() => _dio.post('/audit/forensic', data: formData));
    final accepted = AuditJobResponse.fromJson(Map<String, dynamic>.from(response.data as Map));
    return _pollForCompletion(accepted.jobId);
  }

  Future<AuditResponse> _pollForCompletion(String jobId) async {
    for (var attempt = 0; attempt < 60; attempt++) {
      final response = await _executor.run(() => _dio.get('/audit/jobs/$jobId'));
      final job = AuditJobResponse.fromJson(Map<String, dynamic>.from(response.data as Map));
      if (job.status == 'COMPLETED' && job.result != null) {
        return AuditResponse.fromJson(Map<String, dynamic>.from(job.result!));
      }
      if (job.status == 'FAILED' || job.status == 'CANCELLED') {
        throw NetworkError(job.error ?? 'Forensic analysis failed.');
      }
      await Future<void>.delayed(const Duration(seconds: 2));
    }
    throw const NetworkError('Forensic analysis timed out.');
  }
}
