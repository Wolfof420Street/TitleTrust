import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:titletrust/core/network/dio_client.dart';
import 'geospatial_models.dart';

part 'geospatial_repository.g.dart';

@riverpod
GeospatialRepository geospatialRepository(Ref ref) {
  return GeospatialRepository(ref.watch(dioProvider));
}

class GeospatialRepository {
  final Dio _dio;

  GeospatialRepository(this._dio);

  Future<GeoCheck> verifySite(double lat, double lng, XFile file) async {
    final formData = FormData.fromMap({
      'lat': lat,
      'lng': lng,
      'file': await MultipartFile.fromFile(file.path, filename: file.name),
    });

    final response = await _dio.post(
      '/audit/geospatial',
      data: formData,
    );

    return GeoCheck.fromJson(response.data);
  }
}
