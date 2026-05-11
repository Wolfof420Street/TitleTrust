class InvestigationStartResponse {
  final String sessionId;
  final String status;
  final String message;

  const InvestigationStartResponse({
    required this.sessionId,
    required this.status,
    required this.message,
  });

  factory InvestigationStartResponse.fromJson(Map<String, dynamic> json) {
    return InvestigationStartResponse(
      sessionId: json['session_id'] as String,
      status: json['status'] as String? ?? 'UNKNOWN',
      message: json['message'] as String? ?? '',
    );
  }
}
