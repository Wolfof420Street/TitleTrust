import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:titletrust/core/network/dio_client.dart';
import 'forensic_models.dart';

part 'forensic_repository.g.dart';

@riverpod
ForensicRepository forensicRepository(Ref ref) {
  return ForensicRepository(ref.watch(dioProvider));
}

class ForensicRepository {
  final Dio _dio;

  ForensicRepository(this._dio);

  Future<AuditResponse> uploadDocuments(List<XFile> files) async {
    final formData = FormData();

    for (var file in files) {
      formData.files.add(MapEntry(
        'files',
        await MultipartFile.fromFile(file.path, filename: file.name),
      ));
    }

    final response = await _dio.post(
      '/audit/forensic',
      data: formData,
    );

    return AuditResponse.fromJson(response.data);
  }
}
