import 'dart:async';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:titletrust/features/investigation/data/investigation_repository.dart';

class TitbitsWidget extends ConsumerStatefulWidget {
  const TitbitsWidget({super.key});

  @override
  ConsumerState<TitbitsWidget> createState() => _TitbitsWidgetState();
}

class _TitbitsWidgetState extends ConsumerState<TitbitsWidget> {
  int _currentIndex = 0;
  Timer? _timer;
  List<String> _facts = [];

  @override
  void initState() {
    super.initState();
    // Cycle facts every 6 seconds
    _timer = Timer.periodic(const Duration(seconds: 6), (timer) {
      if (_facts.isNotEmpty) {
        setState(() {
          _currentIndex = (_currentIndex + 1) % _facts.length;
        });
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Use the provider from the repository
    final asyncTitbits = ref.watch(titbitsProvider);

    return asyncTitbits.when(
      data: (facts) {
        _facts = facts;
        if (_facts.isEmpty) return const SizedBox.shrink();

        return ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10), // Glassmorphism
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.1),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.white.withOpacity(0.2)),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.lightbulb_outline, color: Colors.amberAccent, size: 20),
                      const SizedBox(width: 8),
                      Text("DID YOU KNOW?",
                          style: TextStyle(
                              color: Colors.amberAccent.withOpacity(0.8),
                              fontWeight: FontWeight.bold,
                              letterSpacing: 1.2)),
                    ],
                  ),
                  const SizedBox(height: 12),
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 500),
                    transitionBuilder: (Widget child, Animation<double> animation) {
                      return FadeTransition(
                          opacity: animation,
                          child: SlideTransition(
                            position: Tween<Offset>(begin: const Offset(0.0, 0.2), end: Offset.zero).animate(animation),
                            child: child,
                          ));
                    },
                    child: Text(
                      _facts[_currentIndex],
                      key: ValueKey<int>(_currentIndex),
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        height: 1.4,
                        fontFamily: "Outfit", // or default
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  // Progress Indicator dots
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(_facts.length, (index) {
                      return AnimatedContainer(
                        duration: const Duration(milliseconds: 300),
                        margin: const EdgeInsets.symmetric(horizontal: 3),
                        height: 4,
                        width: _currentIndex == index ? 24 : 8,
                        decoration: BoxDecoration(
                          color: _currentIndex == index ? Colors.amberAccent : Colors.white.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(2),
                        ),
                      );
                    }),
                  )
                ],
              ),
            ),
          ),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}
