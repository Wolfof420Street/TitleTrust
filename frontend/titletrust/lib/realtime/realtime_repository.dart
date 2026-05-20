import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class RealtimeRepository {
  static const _lastEventKeyPrefix = 'realtime.last_event.';
  static const _seqKeyPrefix = 'realtime.last_seq.';
  static const _snapshotKeyPrefix = 'realtime.snapshot.';
  static const _checkpointKeyPrefix = 'realtime.checkpoint.';

  Future<void> persistLastEventId(String sessionId, String eventId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('$_lastEventKeyPrefix$sessionId', eventId);
  }

  Future<String?> getLastEventId(String sessionId) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('$_lastEventKeyPrefix$sessionId');
  }

  Future<void> persistLatestSequence(String sessionId, int seq) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('$_seqKeyPrefix$sessionId', seq);
  }

  Future<int?> getLatestSequence(String sessionId) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt('$_seqKeyPrefix$sessionId');
  }

  Future<void> clearSessionCheckpoint(String sessionId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('$_lastEventKeyPrefix$sessionId');
    await prefs.remove('$_seqKeyPrefix$sessionId');
    await prefs.remove('$_checkpointKeyPrefix$sessionId');
  }

  Future<void> persistRecoveredSnapshot(String sessionId, Map<String, dynamic> snapshot) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('$_snapshotKeyPrefix$sessionId', jsonEncode(snapshot));
  }

  Future<Map<String, dynamic>?> getRecoveredSnapshot(String sessionId) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('$_snapshotKeyPrefix$sessionId');
    if (raw == null || raw.isEmpty) return null;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) return decoded;
      if (decoded is Map) return Map<String, dynamic>.from(decoded);
    } catch (_) {}
    return null;
  }

  Future<void> persistCheckpoint(String sessionId, Map<String, dynamic> checkpoint) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('$_checkpointKeyPrefix$sessionId', jsonEncode(checkpoint));
  }

  Future<Map<String, dynamic>?> getCheckpoint(String sessionId) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('$_checkpointKeyPrefix$sessionId');
    if (raw == null || raw.isEmpty) return null;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) return decoded;
      if (decoded is Map) return Map<String, dynamic>.from(decoded);
    } catch (_) {}
    return null;
  }
}
