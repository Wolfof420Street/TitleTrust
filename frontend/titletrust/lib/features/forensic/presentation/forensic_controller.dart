import 'package:image_picker/image_picker.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../data/forensic_models.dart';
import '../data/forensic_repository.dart';

part 'forensic_controller.g.dart';

@riverpod
class ForensicController extends _$ForensicController {
  @override
  FutureOr<AuditResponse?> build() {
    return null;
  }

  Future<void> submitDocuments() async {
    final picker = ImagePicker();
    final List<XFile> images = await picker.pickMultiImage();

    if (images.isEmpty) return;

    state = const AsyncLoading();

    state = await AsyncValue.guard(() async {
      return ref.read(forensicRepositoryProvider).uploadDocuments(images);
    });
  }
}
