import 'dart:ui';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/ui/adaptive/adaptive_scaffold.dart';
import '../../../main.dart'; // To navigate to HomeScreen

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  final List<Map<String, String>> _pages = [
    {'title': 'Welcome to TitleTrust', 'body': 'Secure your property with AI-driven forensic analysis.'},
    {'title': 'Forensic Audit', 'body': 'Detect anomalies in Title Deeds and Sale Agreements instantly.'},
    {'title': 'Geospatial Check', 'body': 'Verify land boundaries with satellite data.'},
  ];

  Future<void> _completeOnboarding() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('has_seen_onboarding', true);

    if (mounted) {
      final isIOS = Theme.of(context).platform == TargetPlatform.iOS;
      Navigator.of(context).pushReplacement(
        isIOS
            ? CupertinoPageRoute(builder: (_) => const AuthGuard())
            : MaterialPageRoute(builder: (_) => const AuthGuard()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isIOS = Theme.of(context).platform == TargetPlatform.iOS;
    return AdaptiveScaffold(
      body: Stack(
        children: [
          PageView.builder(
            controller: _pageController,
            onPageChanged: (index) => setState(() => _currentPage = index),
            itemCount: _pages.length,
            itemBuilder: (context, index) {
              final page = _pages[index];
              return Padding(
                padding: const EdgeInsets.all(32.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Placeholder for illustration
                    Container(
                      height: 200,
                      width: 200,
                      color: Colors.grey.shade200,
                      child: Icon(
                        index == 0
                            ? Icons.security
                            : index == 1
                                ? Icons.manage_search
                                : Icons.satellite_alt,
                        size: 80,
                        color: Colors.blueGrey,
                      ),
                    ),
                    const SizedBox(height: 32),
                    Text(
                      page['title']!,
                      style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      page['body']!,
                      style: Theme.of(context).textTheme.bodyLarge,
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              );
            },
          ),
          if (isIOS) _buildIOSControls() else _buildAndroidControls(),
        ],
      ),
    );
  }

  Widget _buildAndroidControls() {
    return Positioned(
      bottom: 0,
      left: 0,
      right: 0,
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            // Dots
            Row(
              children: List.generate(
                _pages.length,
                (index) => Container(
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _currentPage == index ? Theme.of(context).colorScheme.primary : Colors.grey.shade400,
                  ),
                ),
              ),
            ),
            // Skip / Done
            TextButton(
              onPressed: _completeOnboarding,
              child: Text(_currentPage == _pages.length - 1 ? 'GET STARTED' : 'SKIP'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildIOSControls() {
    return Positioned(
      bottom: 0,
      left: 0,
      right: 0,
      child: ClipRRect(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            color: CupertinoColors.systemBackground.resolveFrom(context).withOpacity(0.5),
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(
                    _pages.length,
                    (index) => Container(
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _currentPage == index ? CupertinoColors.activeBlue : CupertinoColors.systemGrey,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: CupertinoButton.filled(
                    onPressed: _completeOnboarding,
                    child: Text(_currentPage == _pages.length - 1 ? 'Get Started' : 'Skip'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
