class GeoCheckJobResponse {
  final String jobId;
  final String status;
  final String jobType;
  final Map<String, dynamic>? result;
  final String? error;

  const GeoCheckJobResponse({
    required this.jobId,
    required this.status,
    required this.jobType,
    this.result,
    this.error,
  });

  factory GeoCheckJobResponse.fromJson(Map<String, dynamic> json) {
    return GeoCheckJobResponse(
      jobId: json['job_id'] as String,
      status: json['status'] as String? ?? 'UNKNOWN',
      jobType: json['job_type'] as String? ?? 'unknown',
      result: json['result'] is Map<String, dynamic>
          ? json['result'] as Map<String, dynamic>
          : (json['result'] is Map ? Map<String, dynamic>.from(json['result'] as Map) : null),
      error: json['error'] as String?,
    );
  }
}
