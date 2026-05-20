import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:titletrust/features/investigation/data/investigation_repository.dart';

import 'package:titletrust/features/investigation/presentation/investigation_report_view.dart';
import 'package:titletrust/realtime/models.dart';
import 'package:titletrust/realtime/realtime_controller.dart';

class InvestigationScreen extends ConsumerStatefulWidget {
  final String sessionId;

  const InvestigationScreen({super.key, required this.sessionId});

  @override
  ConsumerState<InvestigationScreen> createState() => _InvestigationScreenState();
}

class _InvestigationScreenState extends ConsumerState<InvestigationScreen> with WidgetsBindingObserver {
  StreamSubscription? _connectivitySub;
  bool _networkAvailable = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _bootstrapRealtime();
    _connectivitySub = Connectivity().onConnectivityChanged.listen(_handleConnectivityChange);
    _seedConnectivity();
  }

  Future<void> _bootstrapRealtime() async {
    await Future<void>.delayed(Duration.zero);
    if (!mounted) {
      return;
    }
    await ref.read(realtimeControllerProvider(widget.sessionId).notifier).handleAppResumed();
  }

  Future<void> _seedConnectivity() async {
    try {
      final result = await Connectivity().checkConnectivity();
      _handleConnectivityChange(result);
    } catch (_) {}
  }

  void _handleConnectivityChange(dynamic result) {
    final offline = _isOffline(result);
    if (offline == !_networkAvailable) {
      return;
    }
    setState(() {
      _networkAvailable = !offline;
    });
    final controller = ref.read(realtimeControllerProvider(widget.sessionId).notifier);
    if (offline) {
      unawaited(controller.handleAppPaused());
    } else {
      unawaited(controller.handleAppResumed());
    }
  }

  bool _isOffline(dynamic result) {
    if (result == null) {
      return true;
    }
    if (result is ConnectivityResult) {
      return result == ConnectivityResult.none;
    }
    if (result is List<ConnectivityResult>) {
      return result.contains(ConnectivityResult.none) || result.isEmpty;
    }
    if (result is Iterable) {
      return result.isEmpty || result.contains(ConnectivityResult.none);
    }
    return false;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final controller = ref.read(realtimeControllerProvider(widget.sessionId).notifier);
    if (state == AppLifecycleState.paused || state == AppLifecycleState.inactive || state == AppLifecycleState.detached) {
      unawaited(controller.handleAppPaused());
    } else if (state == AppLifecycleState.resumed) {
      unawaited(controller.handleAppResumed());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_connectivitySub?.cancel());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ref = this.ref;
    final sessionAsync = ref.watch(investigationSessionProvider(widget.sessionId));
    final realtimeState = ref.watch(realtimeControllerProvider(widget.sessionId));

    return Scaffold(
      backgroundColor: Colors.black, // Matrix style background
      appBar: AppBar(
        backgroundColor: Colors.black,
        title: const Text(
          "MARATHON AGENT: RUNNING",
          style: TextStyle(color: Colors.greenAccent, fontFamily: "Courier"),
        ),
        iconTheme: const IconThemeData(color: Colors.greenAccent),
      ),
      body: sessionAsync.when(
        loading: () => const Center(child: CircularProgressIndicator(color: Colors.greenAccent)),
        error: (err, stack) => Center(child: Text("Connection Lost: $err", style: const TextStyle(color: Colors.red))),
        data: (session) {
          final status = session.status;
          final logs = session.logs;
          final isCompleted = status == "COMPLETED";
          final realtimeLabel = _labelForConnectionState(realtimeState.connectionState);
          final realtimeColor = _colorForConnectionState(realtimeState.connectionState);

          return Column(
            children: [
              // Header Status
              Container(
                padding: const EdgeInsets.all(16),
                width: double.infinity,
                decoration: BoxDecoration(
                  border: Border(bottom: BorderSide(color: Colors.greenAccent.withOpacity(0.5))),
                ),
                child: Row(
                  children: [
                    Icon(isCompleted ? Icons.check_circle : Icons.sync,
                        color: isCompleted ? Colors.green : Colors.yellowAccent),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            "STATUS: $status",
                            style: const TextStyle(
                              color: Colors.greenAccent,
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              fontFamily: "Courier",
                            ),
                          ),
                          const SizedBox(height: 4),
                          Wrap(
                            spacing: 8,
                            runSpacing: 6,
                            children: [
                              _StatusChip(label: realtimeLabel, color: realtimeColor),
                              _StatusChip(label: _networkAvailable ? 'network online' : 'network offline', color: _networkAvailable ? Colors.greenAccent : Colors.redAccent),
                              if (realtimeState.isRecovering) const _StatusChip(label: 'recovering', color: Colors.orangeAccent),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              // Agent Thinking Process (Hero Section)
              if (!isCompleted) ...[
                Expanded(
                  flex: 2,
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: Colors.black,
                      border: Border.all(color: Colors.greenAccent.withOpacity(0.5)),
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.greenAccent.withOpacity(0.1),
                          blurRadius: 20,
                          offset: const Offset(0, 0),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation<Color>(Colors.greenAccent),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Text(
                              "AGENT ${status == 'SLEEPING' ? 'SLEEPING' : 'THINKING'}...",
                              style: const TextStyle(
                                color: Colors.greenAccent,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                fontFamily: "Courier",
                                letterSpacing: 1.2,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Expanded(
                          child: SingleChildScrollView(
                            reverse: true,
                            child: Text(
                              logs.isNotEmpty ? logs.last.message : "Initializing neural pathways...",
                              style: TextStyle(
                                color: Colors.greenAccent.withOpacity(0.9),
                                fontFamily: "Courier",
                                fontSize: 16,
                                height: 1.5,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],

              Expanded(
                flex: 3,
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: Colors.black,
                    border: !isCompleted ? Border(top: BorderSide(color: Colors.greenAccent.withOpacity(0.2))) : null,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (realtimeState.timeline.isNotEmpty)
                        Container(
                          margin: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.04),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: Colors.white.withOpacity(0.08)),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  const Icon(Icons.play_circle_outline, color: Colors.cyanAccent, size: 18),
                                  const SizedBox(width: 8),
                                  Text('LIVE REALTIME', style: TextStyle(color: Colors.white.withOpacity(0.8), fontFamily: 'Courier', fontWeight: FontWeight.bold)),
                                  const Spacer(),
                                  Text('seq ${realtimeState.lastSequenceId ?? '-'}', style: TextStyle(color: Colors.white.withOpacity(0.5), fontFamily: 'Courier')),
                                ],
                              ),
                              const SizedBox(height: 10),
                              SizedBox(
                                height: 120,
                                child: ListView.separated(
                                  itemCount: realtimeState.timeline.length > 5 ? 5 : realtimeState.timeline.length,
                                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                                  itemBuilder: (context, index) {
                                    final item = realtimeState.timeline[realtimeState.timeline.length - 1 - index];
                                    return _TimelineItemTile(item: item);
                                  },
                                ),
                              ),
                            ],
                          ),
                        ),
                      if (realtimeState.warnings.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                          child: Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: realtimeState.warnings.take(3).map((warning) {
                              return Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                decoration: BoxDecoration(
                                  color: Colors.orangeAccent.withOpacity(0.12),
                                  borderRadius: BorderRadius.circular(999),
                                  border: Border.all(color: Colors.orangeAccent.withOpacity(0.35)),
                                ),
                                child: Text(warning, style: const TextStyle(color: Colors.orangeAccent, fontSize: 12, fontFamily: 'Courier')),
                              );
                            }).toList(),
                          ),
                        ),
                      const SizedBox(height: 8),
                      Expanded(
                        child: ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: logs.length,
                          reverse: true,
                          itemBuilder: (context, index) {
                            final log = logs[index];
                            final message = log.message;
                            final type = log.type;

                            Color textColor = Colors.green;
                            if (type == "error") textColor = Colors.redAccent;
                            if (type == "action") textColor = Colors.cyanAccent;
                            if (type == "success") textColor = Colors.white;

                            return Padding(
                              padding: const EdgeInsets.only(bottom: 8.0),
                              child: Text(
                                "> $message",
                                style: TextStyle(
                                  color: textColor,
                                  fontFamily: "Courier",
                                  fontSize: 14,
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // Final Verdict Card (Visible only when complete)
              if (isCompleted)
                Container(
                  color: Colors.greenAccent.withOpacity(0.1),
                  padding: const EdgeInsets.all(20),
                  child: SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.greenAccent,
                        foregroundColor: Colors.black,
                      ),
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => InvestigationReportView(
                              session: session,
                              onClose: () => Navigator.pop(context),
                            ),
                          ),
                        );
                      },
                      child: const Text("VIEW FINAL REPORT"),
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  String _labelForConnectionState(RealtimeConnectionState state) {
    switch (state) {
      case RealtimeConnectionState.connecting:
        return 'connected';
      case RealtimeConnectionState.reconnecting:
        return 'reconnecting';
      case RealtimeConnectionState.replaying:
        return 'replaying';
      case RealtimeConnectionState.recovering:
        return 'recovering';
      case RealtimeConnectionState.degraded:
        return 'degraded';
      case RealtimeConnectionState.stale:
        return 'stale';
      case RealtimeConnectionState.synchronized:
        return 'connected';
      case RealtimeConnectionState.disconnected:
        return 'offline';
    }
  }

  Color _colorForConnectionState(RealtimeConnectionState state) {
    switch (state) {
      case RealtimeConnectionState.synchronized:
      case RealtimeConnectionState.connecting:
        return Colors.greenAccent;
      case RealtimeConnectionState.replaying:
        return Colors.cyanAccent;
      case RealtimeConnectionState.reconnecting:
        return Colors.orangeAccent;
      case RealtimeConnectionState.recovering:
        return Colors.amberAccent;
      case RealtimeConnectionState.degraded:
        return Colors.redAccent;
      case RealtimeConnectionState.stale:
      case RealtimeConnectionState.disconnected:
        return Colors.white54;
    }
  }
}

class _StatusChip extends StatelessWidget {
  final String label;
  final Color color;

  const _StatusChip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 11, fontFamily: 'Courier', fontWeight: FontWeight.bold)),
    );
  }
}

class _TimelineItemTile extends StatelessWidget {
  final RealtimeTimelineEntry item;

  const _TimelineItemTile({required this.item});

  @override
  Widget build(BuildContext context) {
    final accent = _colorForKind(item.kind);
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: accent.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: accent.withOpacity(0.18)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(_iconForKind(item.kind), color: accent, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(item.title, style: TextStyle(color: Colors.white.withOpacity(0.92), fontFamily: 'Courier', fontWeight: FontWeight.bold, fontSize: 12)),
                const SizedBox(height: 2),
                Text(item.message, maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(color: Colors.white.withOpacity(0.65), fontFamily: 'Courier', fontSize: 11)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  IconData _iconForKind(String kind) {
    switch (kind) {
      case 'evidence':
        return Icons.science_outlined;
      case 'security':
        return Icons.shield_outlined;
      case 'geospatial':
        return Icons.public_outlined;
      case 'job':
        return Icons.task_alt_outlined;
      default:
        return Icons.auto_awesome_outlined;
    }
  }

  Color _colorForKind(String kind) {
    switch (kind) {
      case 'evidence':
        return Colors.cyanAccent;
      case 'security':
        return Colors.orangeAccent;
      case 'geospatial':
        return Colors.greenAccent;
      case 'job':
        return Colors.blueAccent;
      default:
        return Colors.white70;
    }
  }
}
