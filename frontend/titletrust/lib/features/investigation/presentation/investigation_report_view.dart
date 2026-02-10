import 'package:flutter/material.dart';
import 'package:titletrust/features/investigation/data/investigation_repository.dart';

class InvestigationReportView extends StatelessWidget {
  final InvestigationSession session;
  final VoidCallback onClose;

  const InvestigationReportView({
    super.key,
    required this.session,
    required this.onClose,
  });

  @override
  Widget build(BuildContext context) {
    // 1. Calculate Colors based on Risk Score
    final riskScore = session.riskScore ?? 0;
    final isHighRisk = riskScore > 70;
    final isMediumRisk = riskScore > 30 && riskScore <= 70;

    // Gradient Colors
    final Color primaryColor =
        isHighRisk ? const Color(0xFFFF5252) : (isMediumRisk ? Colors.amber : const Color(0xFF69F0AE));
    const Color backgroundColor = Colors.black;

    return Scaffold(
      backgroundColor: backgroundColor,
      body: CustomScrollView(
        slivers: [
          // 2. Sliver App Bar with Risk Gauge Background
          SliverAppBar(
            backgroundColor: backgroundColor,
            expandedHeight: 300,
            pinned: true,
            leading: IconButton(
              icon: const Icon(Icons.close, color: Colors.white),
              onPressed: onClose,
            ),
            flexibleSpace: FlexibleSpaceBar(
              background: Stack(
                alignment: Alignment.center,
                children: [
                  // Animated Gradient Mesh (Simplified for now)
                  Container(
                    decoration: BoxDecoration(
                        gradient: RadialGradient(
                      colors: [primaryColor.withOpacity(0.3), Colors.black],
                      radius: 1.2,
                    )),
                  ),
                  // Risk Score Display
                  Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const SizedBox(height: 50),
                      Text("RISK SCORE",
                          style: TextStyle(color: Colors.white.withOpacity(0.6), letterSpacing: 2, fontSize: 14)),
                      const SizedBox(height: 10),
                      Stack(
                        alignment: Alignment.center,
                        children: [
                          SizedBox(
                            width: 150,
                            height: 150,
                            child: CircularProgressIndicator(
                              value: riskScore / 100,
                              strokeWidth: 10,
                              backgroundColor: Colors.white10,
                              valueColor: AlwaysStoppedAnimation<Color>(primaryColor),
                            ),
                          ),
                          Text(
                            "$riskScore",
                            style: TextStyle(
                                color: primaryColor, fontSize: 64, fontWeight: FontWeight.bold, fontFamily: "Outfit"),
                          ),
                        ],
                      )
                    ],
                  )
                ],
              ),
              title: Text("AUDIT CONCLUSION",
                  style: TextStyle(color: Colors.white.withOpacity(0.9), letterSpacing: 1.5, fontSize: 16)),
              centerTitle: true,
            ),
          ),

          // 3. Conclusion Summary
          SliverToBoxAdapter(
            child: Container(
              margin: const EdgeInsets.all(20),
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.1),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white.withOpacity(0.1)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.gavel, color: primaryColor),
                      const SizedBox(width: 15),
                      const Text("VERDICT",
                          style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                    ],
                  ),
                  const SizedBox(height: 15),
                  Text(
                    session.auditConclusion ?? "No conclusion provided.",
                    style: const TextStyle(color: Colors.white70, fontSize: 16, height: 1.6),
                  )
                ],
              ),
            ),
          ),

          // 4. Detailed Findings Header
          const SliverPadding(
            padding: EdgeInsets.symmetric(horizontal: 20, vertical: 10),
            sliver: SliverToBoxAdapter(
              child: Text("KEY FINDINGS",
                  style: TextStyle(color: Colors.white54, fontSize: 14, letterSpacing: 2, fontWeight: FontWeight.bold)),
            ),
          ),

          // 5. Findings List
          SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) {
                final finding = session.findings![index];

                String category = 'Anomaly';
                String description = '';
                String evidence = '';

                // Robust Handling for unknown JSON structures
                if (finding is Map) {
                  category = (finding['anomaly_type'] ?? finding['category'] ?? 'Anomaly').toString();
                  // Fallbacks for various agent output styles
                  description = (finding['description'] ?? finding['details'] ?? finding['finding'] ?? '').toString();
                  evidence = (finding['evidence'] ?? finding['reasoning'] ?? '').toString();
                } else if (finding is String) {
                  description = finding;
                } else {
                  description = finding.toString();
                }

                return Container(
                  margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                      color: const Color(0xFF1E1E1E),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: Colors.white.withOpacity(0.05)),
                      boxShadow: [
                        BoxShadow(color: Colors.black.withOpacity(0.5), blurRadius: 10, offset: const Offset(0, 5))
                      ]),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Badge
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.blueGrey.withOpacity(0.3),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(category.toUpperCase(),
                            style:
                                const TextStyle(color: Colors.cyanAccent, fontSize: 10, fontWeight: FontWeight.bold)),
                      ),
                      const SizedBox(height: 12),
                      Text(description,
                          style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 12),
                      // Evidence Block
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                            color: Colors.black.withOpacity(0.3),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: Colors.white.withOpacity(0.05))),
                        child: Text(
                          "EVIDENCE: $evidence",
                          style: TextStyle(
                              color: Colors.white.withOpacity(0.5), fontSize: 12, fontFamily: "Courier", height: 1.4),
                        ),
                      )
                    ],
                  ),
                );
              },
              childCount: session.findings?.length ?? 0,
            ),
          ),

          // Bottom Spacing
          const SliverPadding(padding: EdgeInsets.only(bottom: 100)),
        ],
      ),
    );
  }
}
