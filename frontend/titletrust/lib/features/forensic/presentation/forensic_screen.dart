import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'forensic_controller.dart';
import '../../../core/ui/adaptive/verdict_card.dart';

class ForensicScreen extends ConsumerWidget {
  const ForensicScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(forensicControllerProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Forensic Document Audit')),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Upload your Title Deed, Green Card, and Sale Agreements for AI Analysis.',
                style: TextStyle(fontSize: 16),
              ),
              const SizedBox(height: 20),
              ElevatedButton.icon(
                onPressed: () => ref.read(forensicControllerProvider.notifier).submitDocuments(),
                icon: const Icon(Icons.upload_file),
                label: const Text('Select & Upload Documents'),
                style: ElevatedButton.styleFrom(padding: const EdgeInsets.all(16)),
              ),
              const SizedBox(height: 32),
              state.when(
                data: (response) {
                  if (response == null) {
                    return const Center(child: Text('No results yet. Upload documents to begin.'));
                  }
                  final isCritical = response.status == 'FLAGGED';
                  return AdaptiveVerdictCard(
                    isCritical: isCritical,
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Analysis Status: ${response.status}',
                            style: TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                              color: isCritical ? Colors.red : Colors.green,
                            ),
                          ),
                          const Divider(),
                          if (response.findings.isEmpty)
                            const Text('No anomalies detected. Documents appear clean.')
                          else
                            ...response.findings.map(
                              (finding) => Padding(
                                padding: const EdgeInsets.symmetric(vertical: 4),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Icon(Icons.warning, color: isCritical ? Colors.red : Colors.orange),
                                    const SizedBox(width: 8),
                                    Expanded(child: Text(finding, style: const TextStyle(fontWeight: FontWeight.w500))),
                                  ],
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  );
                },
                error: (err, stack) => Text('Error: $err', style: const TextStyle(color: Colors.red)),
                loading: () => const Center(child: CircularProgressIndicator()),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
