// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'geospatial_models.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

T _$identity<T>(T value) => value;

final _privateConstructorUsedError = UnsupportedError(
    'It seems like you constructed your class using `MyClass._()`. This constructor is only meant to be used by freezed and you are not supposed to need it nor use it.\nPlease check the documentation here for more information: https://github.com/rrousselGit/freezed#adding-getters-and-methods-to-our-models');

GeoCheck _$GeoCheckFromJson(Map<String, dynamic> json) {
  return _GeoCheck.fromJson(json);
}

/// @nodoc
mixin _$GeoCheck {
  @JsonKey(name: 'check_id')
  String get checkId => throw _privateConstructorUsedError;
  @JsonKey(name: 'risk_level')
  String get riskLevel => throw _privateConstructorUsedError;
  @JsonKey(name: 'satellite_analysis_result')
  String get satelliteAnalysisResult => throw _privateConstructorUsedError;

  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;
  @JsonKey(ignore: true)
  $GeoCheckCopyWith<GeoCheck> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $GeoCheckCopyWith<$Res> {
  factory $GeoCheckCopyWith(GeoCheck value, $Res Function(GeoCheck) then) =
      _$GeoCheckCopyWithImpl<$Res, GeoCheck>;
  @useResult
  $Res call(
      {@JsonKey(name: 'check_id') String checkId,
      @JsonKey(name: 'risk_level') String riskLevel,
      @JsonKey(name: 'satellite_analysis_result')
      String satelliteAnalysisResult});
}

/// @nodoc
class _$GeoCheckCopyWithImpl<$Res, $Val extends GeoCheck>
    implements $GeoCheckCopyWith<$Res> {
  _$GeoCheckCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? checkId = null,
    Object? riskLevel = null,
    Object? satelliteAnalysisResult = null,
  }) {
    return _then(_value.copyWith(
      checkId: null == checkId
          ? _value.checkId
          : checkId // ignore: cast_nullable_to_non_nullable
              as String,
      riskLevel: null == riskLevel
          ? _value.riskLevel
          : riskLevel // ignore: cast_nullable_to_non_nullable
              as String,
      satelliteAnalysisResult: null == satelliteAnalysisResult
          ? _value.satelliteAnalysisResult
          : satelliteAnalysisResult // ignore: cast_nullable_to_non_nullable
              as String,
    ) as $Val);
  }
}

/// @nodoc
abstract class _$$GeoCheckImplCopyWith<$Res>
    implements $GeoCheckCopyWith<$Res> {
  factory _$$GeoCheckImplCopyWith(
          _$GeoCheckImpl value, $Res Function(_$GeoCheckImpl) then) =
      __$$GeoCheckImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call(
      {@JsonKey(name: 'check_id') String checkId,
      @JsonKey(name: 'risk_level') String riskLevel,
      @JsonKey(name: 'satellite_analysis_result')
      String satelliteAnalysisResult});
}

/// @nodoc
class __$$GeoCheckImplCopyWithImpl<$Res>
    extends _$GeoCheckCopyWithImpl<$Res, _$GeoCheckImpl>
    implements _$$GeoCheckImplCopyWith<$Res> {
  __$$GeoCheckImplCopyWithImpl(
      _$GeoCheckImpl _value, $Res Function(_$GeoCheckImpl) _then)
      : super(_value, _then);

  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? checkId = null,
    Object? riskLevel = null,
    Object? satelliteAnalysisResult = null,
  }) {
    return _then(_$GeoCheckImpl(
      checkId: null == checkId
          ? _value.checkId
          : checkId // ignore: cast_nullable_to_non_nullable
              as String,
      riskLevel: null == riskLevel
          ? _value.riskLevel
          : riskLevel // ignore: cast_nullable_to_non_nullable
              as String,
      satelliteAnalysisResult: null == satelliteAnalysisResult
          ? _value.satelliteAnalysisResult
          : satelliteAnalysisResult // ignore: cast_nullable_to_non_nullable
              as String,
    ));
  }
}

/// @nodoc
@JsonSerializable()
class _$GeoCheckImpl implements _GeoCheck {
  const _$GeoCheckImpl(
      {@JsonKey(name: 'check_id') required this.checkId,
      @JsonKey(name: 'risk_level') required this.riskLevel,
      @JsonKey(name: 'satellite_analysis_result')
      required this.satelliteAnalysisResult});

  factory _$GeoCheckImpl.fromJson(Map<String, dynamic> json) =>
      _$$GeoCheckImplFromJson(json);

  @override
  @JsonKey(name: 'check_id')
  final String checkId;
  @override
  @JsonKey(name: 'risk_level')
  final String riskLevel;
  @override
  @JsonKey(name: 'satellite_analysis_result')
  final String satelliteAnalysisResult;

  @override
  String toString() {
    return 'GeoCheck(checkId: $checkId, riskLevel: $riskLevel, satelliteAnalysisResult: $satelliteAnalysisResult)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$GeoCheckImpl &&
            (identical(other.checkId, checkId) || other.checkId == checkId) &&
            (identical(other.riskLevel, riskLevel) ||
                other.riskLevel == riskLevel) &&
            (identical(
                    other.satelliteAnalysisResult, satelliteAnalysisResult) ||
                other.satelliteAnalysisResult == satelliteAnalysisResult));
  }

  @JsonKey(ignore: true)
  @override
  int get hashCode =>
      Object.hash(runtimeType, checkId, riskLevel, satelliteAnalysisResult);

  @JsonKey(ignore: true)
  @override
  @pragma('vm:prefer-inline')
  _$$GeoCheckImplCopyWith<_$GeoCheckImpl> get copyWith =>
      __$$GeoCheckImplCopyWithImpl<_$GeoCheckImpl>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$$GeoCheckImplToJson(
      this,
    );
  }
}

abstract class _GeoCheck implements GeoCheck {
  const factory _GeoCheck(
      {@JsonKey(name: 'check_id') required final String checkId,
      @JsonKey(name: 'risk_level') required final String riskLevel,
      @JsonKey(name: 'satellite_analysis_result')
      required final String satelliteAnalysisResult}) = _$GeoCheckImpl;

  factory _GeoCheck.fromJson(Map<String, dynamic> json) =
      _$GeoCheckImpl.fromJson;

  @override
  @JsonKey(name: 'check_id')
  String get checkId;
  @override
  @JsonKey(name: 'risk_level')
  String get riskLevel;
  @override
  @JsonKey(name: 'satellite_analysis_result')
  String get satelliteAnalysisResult;
  @override
  @JsonKey(ignore: true)
  _$$GeoCheckImplCopyWith<_$GeoCheckImpl> get copyWith =>
      throw _privateConstructorUsedError;
}
