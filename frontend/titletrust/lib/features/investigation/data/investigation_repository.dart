import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:titletrust/core/network/dio_client.dart';

// Domain Model for a Log Entry
class InvestigationLog {
  final String message;
  final String type;
  final DateTime? timestamp;

  InvestigationLog({
    required this.message,
    required this.type,
    this.timestamp,
  });

  factory InvestigationLog.fromMap(Map<String, dynamic> map) {
    return InvestigationLog(
      message: map['message'] ?? '',
      type: map['type'] ?? 'thought',
      // timestamp handling can be tricky with ArrayUnion/ServerTimestamp in simple maps,
      // often best to rely on client receive time or a proper subcollection if precise ordering needed.
      // Here we assume it might be missing or a Timestamp object.
      timestamp: map['timestamp'] is Timestamp ? (map['timestamp'] as Timestamp).toDate() : DateTime.now(),
    );
  }
}

// Domain Model for the Session State
class InvestigationSession {
  final String status;
  final List<InvestigationLog> logs;
  final int? riskScore;
  final String? auditConclusion;
  final List<dynamic>? findings;

  InvestigationSession({
    required this.status,
    required this.logs,
    this.riskScore,
    this.auditConclusion,
    this.findings,
  });
}

// ... (Rest of existing imports and classes up to InvestigationRepository)

// Repository Interface
abstract class InvestigationRepository {
  Stream<InvestigationSession> streamSessionLogs(String sessionId);
  Future<List<String>> getTitbits();
}

// Implementation
class InvestigationRepositoryImpl implements InvestigationRepository {
  final FirebaseFirestore _firestore;
  final Dio _dio;

  InvestigationRepositoryImpl(this._firestore, this._dio);

  @override
  Stream<InvestigationSession> streamSessionLogs(String sessionId) {
    return _firestore.collection('sessions').doc(sessionId).snapshots().map((snapshot) {
      final data = snapshot.data();
      if (data == null) {
        return InvestigationSession(status: 'INITIALIZING', logs: []);
      }

      final status = data['status'] as String? ?? 'RUNNING';
      final rawTrace = data['logs'] as List<dynamic>? ?? [];

      final logs = rawTrace.map((e) {
        if (e is Map<String, dynamic>) {
          return InvestigationLog.fromMap(e);
        }
        return InvestigationLog(message: e.toString(), type: 'unknown');
      }).toList();

      return InvestigationSession(
          status: status,
          logs: logs,
          riskScore: data['risk_score'] != null ? (data['risk_score'] as num).toInt() : null,
          auditConclusion: data['audit_conclusion'] as String?,
          findings: data['findings'] as List<dynamic>?);
    });
  }

  @override
  Future<List<String>> getTitbits() async {
    try {
      // Use relative path since baseUrl is configured in Dio client
      final response = await _dio.get('/audit/titbits');
      return List<String>.from(response.data['titbits']);
    } catch (e) {
      // Fallback for Hackathon stability / Offline mode
      return [
        "Did you know? A Green Card is the only true proof of ownership.",
        "Fraudsters using 'Air Subdivisions' are common in high-value zones.",
        "Section 26 of the Land Act protects innocent purchasers.",
        "Always do a 'Ground Truth' verification before paying.",
        "TitleTrust uses AI to cross-reference the Gazette Notice database."
      ];
    }
  }
}

// Providers
final investigationRepositoryProvider = Provider<InvestigationRepository>((ref) {
  final dio = ref.watch(dioProvider);
  return InvestigationRepositoryImpl(FirebaseFirestore.instance, dio);
});

final investigationSessionProvider = StreamProvider.family<InvestigationSession, String>((ref, sessionId) {
  final repository = ref.watch(investigationRepositoryProvider);
  return repository.streamSessionLogs(sessionId);
});

final titbitsProvider = FutureProvider<List<String>>((ref) async {
  final repository = ref.watch(investigationRepositoryProvider);
  return repository.getTitbits();
});
