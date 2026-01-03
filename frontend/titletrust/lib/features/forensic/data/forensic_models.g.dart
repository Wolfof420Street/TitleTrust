// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'forensic_models.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_$AuditResponseImpl _$$AuditResponseImplFromJson(Map<String, dynamic> json) =>
    _$AuditResponseImpl(
      requestId: json['request_id'] as String,
      status: json['status'] as String,
      findings: (json['findings'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          const [],
    );

Map<String, dynamic> _$$AuditResponseImplToJson(_$AuditResponseImpl instance) =>
    <String, dynamic>{
      'request_id': instance.requestId,
      'status': instance.status,
      'findings': instance.findings,
    };
