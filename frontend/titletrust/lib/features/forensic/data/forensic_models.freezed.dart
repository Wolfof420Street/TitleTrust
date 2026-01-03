// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'forensic_models.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

T _$identity<T>(T value) => value;

final _privateConstructorUsedError = UnsupportedError(
    'It seems like you constructed your class using `MyClass._()`. This constructor is only meant to be used by freezed and you are not supposed to need it nor use it.\nPlease check the documentation here for more information: https://github.com/rrousselGit/freezed#adding-getters-and-methods-to-our-models');

AuditResponse _$AuditResponseFromJson(Map<String, dynamic> json) {
  return _AuditResponse.fromJson(json);
}

/// @nodoc
mixin _$AuditResponse {
  @JsonKey(name: 'request_id')
  String get requestId => throw _privateConstructorUsedError;
  String get status => throw _privateConstructorUsedError;
  List<String> get findings => throw _privateConstructorUsedError;

  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;
  @JsonKey(ignore: true)
  $AuditResponseCopyWith<AuditResponse> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $AuditResponseCopyWith<$Res> {
  factory $AuditResponseCopyWith(
          AuditResponse value, $Res Function(AuditResponse) then) =
      _$AuditResponseCopyWithImpl<$Res, AuditResponse>;
  @useResult
  $Res call(
      {@JsonKey(name: 'request_id') String requestId,
      String status,
      List<String> findings});
}

/// @nodoc
class _$AuditResponseCopyWithImpl<$Res, $Val extends AuditResponse>
    implements $AuditResponseCopyWith<$Res> {
  _$AuditResponseCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? requestId = null,
    Object? status = null,
    Object? findings = null,
  }) {
    return _then(_value.copyWith(
      requestId: null == requestId
          ? _value.requestId
          : requestId // ignore: cast_nullable_to_non_nullable
              as String,
      status: null == status
          ? _value.status
          : status // ignore: cast_nullable_to_non_nullable
              as String,
      findings: null == findings
          ? _value.findings
          : findings // ignore: cast_nullable_to_non_nullable
              as List<String>,
    ) as $Val);
  }
}

/// @nodoc
abstract class _$$AuditResponseImplCopyWith<$Res>
    implements $AuditResponseCopyWith<$Res> {
  factory _$$AuditResponseImplCopyWith(
          _$AuditResponseImpl value, $Res Function(_$AuditResponseImpl) then) =
      __$$AuditResponseImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call(
      {@JsonKey(name: 'request_id') String requestId,
      String status,
      List<String> findings});
}

/// @nodoc
class __$$AuditResponseImplCopyWithImpl<$Res>
    extends _$AuditResponseCopyWithImpl<$Res, _$AuditResponseImpl>
    implements _$$AuditResponseImplCopyWith<$Res> {
  __$$AuditResponseImplCopyWithImpl(
      _$AuditResponseImpl _value, $Res Function(_$AuditResponseImpl) _then)
      : super(_value, _then);

  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? requestId = null,
    Object? status = null,
    Object? findings = null,
  }) {
    return _then(_$AuditResponseImpl(
      requestId: null == requestId
          ? _value.requestId
          : requestId // ignore: cast_nullable_to_non_nullable
              as String,
      status: null == status
          ? _value.status
          : status // ignore: cast_nullable_to_non_nullable
              as String,
      findings: null == findings
          ? _value._findings
          : findings // ignore: cast_nullable_to_non_nullable
              as List<String>,
    ));
  }
}

/// @nodoc
@JsonSerializable()
class _$AuditResponseImpl implements _AuditResponse {
  const _$AuditResponseImpl(
      {@JsonKey(name: 'request_id') required this.requestId,
      required this.status,
      final List<String> findings = const []})
      : _findings = findings;

  factory _$AuditResponseImpl.fromJson(Map<String, dynamic> json) =>
      _$$AuditResponseImplFromJson(json);

  @override
  @JsonKey(name: 'request_id')
  final String requestId;
  @override
  final String status;
  final List<String> _findings;
  @override
  @JsonKey()
  List<String> get findings {
    if (_findings is EqualUnmodifiableListView) return _findings;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_findings);
  }

  @override
  String toString() {
    return 'AuditResponse(requestId: $requestId, status: $status, findings: $findings)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$AuditResponseImpl &&
            (identical(other.requestId, requestId) ||
                other.requestId == requestId) &&
            (identical(other.status, status) || other.status == status) &&
            const DeepCollectionEquality().equals(other._findings, _findings));
  }

  @JsonKey(ignore: true)
  @override
  int get hashCode => Object.hash(runtimeType, requestId, status,
      const DeepCollectionEquality().hash(_findings));

  @JsonKey(ignore: true)
  @override
  @pragma('vm:prefer-inline')
  _$$AuditResponseImplCopyWith<_$AuditResponseImpl> get copyWith =>
      __$$AuditResponseImplCopyWithImpl<_$AuditResponseImpl>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$$AuditResponseImplToJson(
      this,
    );
  }
}

abstract class _AuditResponse implements AuditResponse {
  const factory _AuditResponse(
      {@JsonKey(name: 'request_id') required final String requestId,
      required final String status,
      final List<String> findings}) = _$AuditResponseImpl;

  factory _AuditResponse.fromJson(Map<String, dynamic> json) =
      _$AuditResponseImpl.fromJson;

  @override
  @JsonKey(name: 'request_id')
  String get requestId;
  @override
  String get status;
  @override
  List<String> get findings;
  @override
  @JsonKey(ignore: true)
  _$$AuditResponseImplCopyWith<_$AuditResponseImpl> get copyWith =>
      throw _privateConstructorUsedError;
}
