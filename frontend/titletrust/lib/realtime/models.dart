import 'dart:convert';

enum RealtimeConnectionState {
  disconnected,
  connecting,
  reconnecting,
  replaying,
  synchronized,
  recovering,
  degraded,
  stale,
}

class RealtimeTimelineEntry {
  final String id;
  final String title;
  final String message;
  final String kind;
  final int? sequenceId;
  final String? sessionId;
  final String? streamOffset;
  final String? originInstanceId;
  final DateTime timestamp;
  final bool authoritative;

  const RealtimeTimelineEntry({
    required this.id,
    required this.title,
    required this.message,
    required this.kind,
    required this.timestamp,
    this.sequenceId,
    this.sessionId,
    this.streamOffset,
    this.originInstanceId,
    this.authoritative = false,
  });
}

class RealtimeDiagnostics {
  final int reconnectAttempts;
  final int replayRecoveries;
  final int sequenceGaps;
  final int duplicateEvents;
  final Duration? averageReplayDuration;
  final String? latestStreamOffset;
  final int? subscriberLagSeconds;

  const RealtimeDiagnostics({
    required this.reconnectAttempts,
    required this.replayRecoveries,
    required this.sequenceGaps,
    required this.duplicateEvents,
    this.averageReplayDuration,
    this.latestStreamOffset,
    this.subscriberLagSeconds,
  });
}

class RealtimeEventEnvelope {
  final String eventId;
  final String eventType;
  final int? sequenceId;
  final String? sessionId;
  final String? originInstanceId;
  final String? streamOffset;
  final int ts;
  final Map<String, dynamic>? payload;

  RealtimeEventEnvelope({
    required this.eventId,
    required this.eventType,
    this.sequenceId,
    this.sessionId,
    this.originInstanceId,
    this.streamOffset,
    required this.ts,
    this.payload,
  });

  factory RealtimeEventEnvelope.fromJson(Map<String, dynamic> json) {
    return RealtimeEventEnvelope(
      eventId: json['event_id']?.toString() ?? json['id'] ?? '',
      eventType: json['event_type'] ?? '',
      sequenceId: json['sequence_id'] is int ? json['sequence_id'] : (json['sequence_id'] != null ? int.tryParse(json['sequence_id'].toString()) : null),
      sessionId: json['session_id']?.toString(),
      originInstanceId: json['origin_instance_id']?.toString(),
      streamOffset: json['stream_offset']?.toString(),
      ts: json['ts'] is int ? json['ts'] : (json['ts'] != null ? (json['ts'] as num).toInt() : DateTime.now().millisecondsSinceEpoch),
      payload: json['payload'] is Map ? Map<String, dynamic>.from(json['payload']) : (json['payload'] == null ? null : jsonDecode(json['payload'].toString()) as Map<String, dynamic>?),
    );
  }

  factory RealtimeEventEnvelope.fromData(String data) {
    final Map<String, dynamic> map = json.decode(data) as Map<String, dynamic>;
    return RealtimeEventEnvelope.fromJson(map);
  }
}
