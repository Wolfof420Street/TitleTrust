import 'package:camera/camera.dart';
import 'package:geolocator/geolocator.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../data/geospatial_models.dart';
import '../data/geospatial_repository.dart';

part 'geospatial_controller.g.dart';

@riverpod
class GeospatialController extends _$GeospatialController {
  @override
  FutureOr<GeoCheck?> build() {
    return null;
  }

  Future<void> performVerification(XFile imageFile) async {
    state = const AsyncLoading();

    state = await AsyncValue.guard(() async {
      // 1. Get Location
      // Check permissions (omitted for brevity, assume granted or handled by UI)
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      // 2. Upload
      return ref.read(geospatialRepositoryProvider).verifySite(position.latitude, position.longitude, imageFile);
    });
  }
}
