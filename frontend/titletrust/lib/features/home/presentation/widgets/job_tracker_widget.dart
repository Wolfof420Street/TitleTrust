import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:titletrust/core/services/job_state_service.dart';
import 'package:titletrust/features/investigation/presentation/investigation_screen.dart';

class JobTrackerWidget extends ConsumerWidget {
  const JobTrackerWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final jobState = ref.watch(jobStateServiceProvider);

    return FutureBuilder<String?>(
      future: jobState.getActiveJobId(),
      builder: (context, snapshot) {
        if (!snapshot.hasData || snapshot.data == null) {
          return const SizedBox.shrink();
        }

        final jobId = snapshot.data!;

        return StreamBuilder<DocumentSnapshot>(
          stream: FirebaseFirestore.instance.collection('sessions').doc(jobId).snapshots(),
          builder: (context, streamSnapshot) {
            if (streamSnapshot.hasError || !streamSnapshot.hasData || !streamSnapshot.data!.exists) {
              return const SizedBox.shrink();
            }

            final data = streamSnapshot.data!.data() as Map<String, dynamic>;
            final status = data['status'] ?? 'UNKNOWN';
            final memoryList = (data['memory'] as List?)?.cast<String>() ?? [];
            final lastThought = memoryList.isNotEmpty ? memoryList.last : "Initializing Agent...";

            final isRunning = status == 'RUNNING' || status == 'SLEEPING';
            final isCompleted = status == 'COMPLETED';

            return _ModernJobTracker(
              isCompleted: isCompleted,
              isRunning: isRunning,
              lastThought: lastThought,
              jobId: jobId,
            );
          },
        );
      },
    );
  }
}

class _ModernJobTracker extends StatefulWidget {
  final bool isCompleted;
  final bool isRunning;
  final String lastThought;
  final String jobId;

  const _ModernJobTracker({
    required this.isCompleted,
    required this.isRunning,
    required this.lastThought,
    required this.jobId,
  });

  @override
  State<_ModernJobTracker> createState() => _ModernJobTrackerState();
}

class _ModernJobTrackerState extends State<_ModernJobTracker> with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);
    
    _pulseAnimation = Tween<double>(begin: 0.9, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: widget.isCompleted
              ? [Colors.green.shade400, Colors.green.shade600]
              : [Colors.blue.shade400, Colors.blue.shade600],
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: (widget.isCompleted ? Colors.green : Colors.blue).withOpacity(0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: Stack(
          children: [
            // Glassmorphic overlay
            Positioned.fill(
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      Colors.white.withOpacity(0.25),
                      Colors.white.withOpacity(0.05),
                    ],
                  ),
                ),
              ),
            ),
            // Animated background pattern for running state
            if (widget.isRunning && !widget.isCompleted)
              Positioned.fill(
                child: AnimatedBuilder(
                  animation: _pulseController,
                  builder: (context, child) {
                    return CustomPaint(
                      painter: _CircuitPainter(
                        animationValue: _pulseController.value,
                      ),
                    );
                  },
                ),
              ),
            // Content
            Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Header
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.25),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(
                          widget.isCompleted ? Icons.check_circle_outline : Icons.auto_awesome,
                          color: Colors.white,
                          size: 24,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              widget.isCompleted ? "Audit Complete" : "Agent Active",
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 18,
                                color: Colors.white,
                                letterSpacing: -0.3,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              widget.isCompleted ? "Results ready to view" : "Processing investigation",
                              style: TextStyle(
                                fontSize: 13,
                                color: Colors.white.withOpacity(0.85),
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ],
                        ),
                      ),
                      if (widget.isRunning && !widget.isCompleted)
                        AnimatedBuilder(
                          animation: _pulseAnimation,
                          builder: (context, child) {
                            return Transform.scale(
                              scale: _pulseAnimation.value,
                              child: Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Colors.white.withOpacity(0.25),
                                  shape: BoxShape.circle,
                                ),
                                child: const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
                    ],
                  ),

                  // Thoughts Console (for running state)
                  if (!widget.isCompleted) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: Colors.white.withOpacity(0.2),
                          width: 1,
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.psychology_outlined,
                                size: 16,
                                color: Colors.white.withOpacity(0.9),
                              ),
                              const SizedBox(width: 8),
                              Text(
                                "Agent Thoughts",
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.white.withOpacity(0.9),
                                  letterSpacing: 0.5,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Text(
                            widget.lastThought,
                            style: const TextStyle(
                              fontFamily: 'Courier',
                              fontSize: 13,
                              color: Colors.white,
                              height: 1.4,
                            ),
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                  ],

                  // View Report / Progress Button (Always visible now)
                  const SizedBox(height: 16),
                  Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            Colors.white.withOpacity(0.3),
                            Colors.white.withOpacity(0.15),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Material(
                        color: Colors.transparent,
                        child: InkWell(
                          onTap: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => InvestigationScreen(sessionId: widget.jobId),
                              ),
                            );
                          },
                          borderRadius: BorderRadius.circular(16),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  widget.isCompleted ? Icons.description_outlined : Icons.visibility_outlined,
                                  color: Colors.white,
                                  size: 20,
                                ),
                                const SizedBox(width: 12),
                                Text(
                                  widget.isCompleted ? "View Full Report" : "View Live Progress",
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 16,
                                    fontWeight: FontWeight.w700,
                                    letterSpacing: -0.2,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Icon(
                                  Icons.arrow_forward,
                                  color: Colors.white.withOpacity(0.9),
                                  size: 18,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// Custom painter for animated circuit-like background pattern
class _CircuitPainter extends CustomPainter {
  final double animationValue;

  _CircuitPainter({required this.animationValue});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withOpacity(0.1)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    final path = Path();
    
    // Create animated flowing lines
    final offset = animationValue * 50;
    
    for (var i = 0; i < 5; i++) {
      final y = (size.height / 5) * i + offset;
      path.moveTo(0, y % size.height);
      path.lineTo(size.width * 0.3, y % size.height);
      
      path.moveTo(size.width * 0.7, y % size.height);
      path.lineTo(size.width, y % size.height);
    }

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_CircuitPainter oldDelegate) {
    return oldDelegate.animationValue != animationValue;
  }
}