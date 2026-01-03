// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'geospatial_models.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_$GeoCheckImpl _$$GeoCheckImplFromJson(Map<String, dynamic> json) =>
    _$GeoCheckImpl(
      checkId: json['check_id'] as String,
      riskLevel: json['risk_level'] as String,
      satelliteAnalysisResult: json['satellite_analysis_result'] as String,
    );

Map<String, dynamic> _$$GeoCheckImplToJson(_$GeoCheckImpl instance) =>
    <String, dynamic>{
      'check_id': instance.checkId,
      'risk_level': instance.riskLevel,
      'satellite_analysis_result': instance.satelliteAnalysisResult,
    };
