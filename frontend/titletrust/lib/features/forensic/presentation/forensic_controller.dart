import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
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
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['pdf', 'jpg', 'jpeg', 'png'],
    );

    if (result == null || result.files.isEmpty) return;

    // Convert PlatformFile to XFile for repository compatibility
    final List<XFile> files = result.files.where((f) => f.path != null).map((f) => XFile(f.path!)).toList();

    state = const AsyncLoading();

    state = await AsyncValue.guard(() async {
      return ref.read(forensicRepositoryProvider).uploadDocuments(files);
    });
  }
}
