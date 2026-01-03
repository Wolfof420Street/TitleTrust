// ignore_for_file: invalid_annotation_target
import 'package:freezed_annotation/freezed_annotation.dart';

part 'geospatial_models.freezed.dart';
part 'geospatial_models.g.dart';

@freezed
class GeoCheck with _$GeoCheck {
  const factory GeoCheck({
    @JsonKey(name: 'check_id') required String checkId,
    @JsonKey(name: 'risk_level') required String riskLevel,
    @JsonKey(name: 'satellite_analysis_result') required String satelliteAnalysisResult,
  }) = _GeoCheck;

  factory GeoCheck.fromJson(Map<String, dynamic> json) => _$GeoCheckFromJson(json);
}
