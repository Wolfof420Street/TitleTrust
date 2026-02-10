import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:titletrust/features/investigation/data/investigation_repository.dart';

import 'package:titletrust/features/investigation/presentation/investigation_report_view.dart';

class InvestigationScreen extends ConsumerWidget {
  final String sessionId;

  const InvestigationScreen({super.key, required this.sessionId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessionAsync = ref.watch(investigationSessionProvider(sessionId));

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
                    Text(
                      "STATUS: $status",
                      style: const TextStyle(
                        color: Colors.greenAccent,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        fontFamily: "Courier",
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

              // Matrix Log Stream
              Expanded(
                flex: 3,
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: Colors.black,
                    border: !isCompleted ? Border(top: BorderSide(color: Colors.greenAccent.withOpacity(0.2))) : null,
                  ),
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: logs.length,
                    reverse: true,
                    itemBuilder: (context, index) {
                      final log = logs[index];
                      final message = log.message;
                      final type = log.type;

                      Color textColor = Colors.green; // Default Matrix Green
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
}
