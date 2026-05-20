import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'realtime_controller.dart';

class RealtimeDebugOverlay extends ConsumerWidget {
  final String sessionId;
  const RealtimeDebugOverlay({super.key, required this.sessionId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(realtimeControllerProvider(sessionId));
    return Card(
      color: Colors.black.withOpacity(0.6),
      child: Padding(
        padding: const EdgeInsets.all(8.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Realtime Debug', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            Text('Session: $sessionId', style: const TextStyle(color: Colors.white70)),
            const SizedBox(height: 6),
            Text('Connection: ${state.connectionState.name}', style: const TextStyle(color: Colors.white70)),
            Text('Last sequence: ${state.lastSequenceId ?? '-'}', style: const TextStyle(color: Colors.white70)),
            Text('Stream offset: ${state.latestStreamOffset ?? '-'}', style: const TextStyle(color: Colors.white70)),
            Text('Reconnects: ${state.diagnostics.reconnectAttempts}', style: const TextStyle(color: Colors.white70)),
            Text('Replay recoveries: ${state.diagnostics.replayRecoveries}', style: const TextStyle(color: Colors.white70)),
            Text('Sequence gaps: ${state.diagnostics.sequenceGaps}', style: const TextStyle(color: Colors.white70)),
            Text('Duplicate events: ${state.diagnostics.duplicateEvents}', style: const TextStyle(color: Colors.white70)),
            Text('Subscriber lag: ${state.diagnostics.subscriberLagSeconds ?? '-'}s', style: const TextStyle(color: Colors.white70)),
          ],
        ),
      ),
    );
  }
}
