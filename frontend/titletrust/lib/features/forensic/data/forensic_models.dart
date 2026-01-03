// ignore_for_file: invalid_annotation_target
import 'package:freezed_annotation/freezed_annotation.dart';

part 'forensic_models.freezed.dart';
part 'forensic_models.g.dart';

@freezed
class AuditResponse with _$AuditResponse {
  const factory AuditResponse({
    @JsonKey(name: 'request_id') required String requestId,
    required String status,
    @Default([]) List<String> findings,
  }) = _AuditResponse;

  factory AuditResponse.fromJson(Map<String, dynamic> json) => _$AuditResponseFromJson(json);
}
