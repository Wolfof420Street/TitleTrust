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

class InvestigationTickResponse {
  final String status;
  final String agentStatus;

  const InvestigationTickResponse({
    required this.status,
    required this.agentStatus,
  });

  factory InvestigationTickResponse.fromJson(Map<String, dynamic> json) {
    return InvestigationTickResponse(
      status: json['status'] as String? ?? 'UNKNOWN',
      agentStatus: json['agent_status'] as String? ?? 'UNKNOWN',
    );
  }
}

class InvestigationSessionStatusResponse {
  final String sessionId;
  final String? status;
  final Map<String, dynamic> progress;
  final int totalSteps;
  final String? lastThought;
  final String? error;
  final List<dynamic> findings;
  final String? auditConclusion;

  const InvestigationSessionStatusResponse({
    required this.sessionId,
    required this.status,
    required this.progress,
    required this.totalSteps,
    required this.lastThought,
    required this.error,
    required this.findings,
    required this.auditConclusion,
  });

  factory InvestigationSessionStatusResponse.fromJson(Map<String, dynamic> json) {
    return InvestigationSessionStatusResponse(
      sessionId: json['session_id'] as String,
      status: json['status'] as String?,
      progress: json['progress'] is Map ? Map<String, dynamic>.from(json['progress'] as Map) : <String, dynamic>{},
      totalSteps: (json['total_steps'] as num?)?.toInt() ?? 0,
      lastThought: json['last_thought'] as String?,
      error: json['error'] as String?,
      findings: json['findings'] is List ? List<dynamic>.from(json['findings'] as List) : <dynamic>[],
      auditConclusion: json['audit_conclusion'] as String?,
    );
  }
}

class InvestigationRetryResponse {
  final String sessionId;
  final String status;
  final String message;

  const InvestigationRetryResponse({
    required this.sessionId,
    required this.status,
    required this.message,
  });

  factory InvestigationRetryResponse.fromJson(Map<String, dynamic> json) {
    return InvestigationRetryResponse(
      sessionId: json['session_id'] as String,
      status: json['status'] as String? ?? 'UNKNOWN',
      message: json['message'] as String? ?? '',
    );
  }
}
