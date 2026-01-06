import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/theme/app_theme.dart';
import 'core/ui/adaptive/adaptive_app_bar.dart';
import 'core/ui/adaptive/adaptive_scaffold.dart';
import 'features/forensic/presentation/forensic_screen.dart';
import 'features/geospatial/presentation/geospatial_screen.dart';
import 'features/onboarding/presentation/onboarding_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: ".env");
  final prefs = await SharedPreferences.getInstance();
  final text = prefs.getBool('has_seen_onboarding');
  final showOnboarding = text == null || !text;

  runApp(ProviderScope(child: TitleTrustApp(showOnboarding: showOnboarding)));
}

class TitleTrustApp extends StatelessWidget {
  final bool showOnboarding;

  const TitleTrustApp({super.key, required this.showOnboarding});

  @override
  Widget build(BuildContext context) {
    if (Platform.isIOS) {
      return CupertinoApp(
        title: 'TitleTrust',
        theme: AppTheme.iosTheme,
        home: showOnboarding ? const OnboardingScreen() : const HomeScreen(),
        debugShowCheckedModeBanner: false,
      );
    } else {
      return MaterialApp(
        title: 'TitleTrust',
        theme: AppTheme.androidTheme,
        darkTheme: AppTheme.androidDarkTheme,
        home: showOnboarding ? const OnboardingScreen() : const HomeScreen(),
        debugShowCheckedModeBanner: false,
      );
    }
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return AdaptiveScaffold(
      appBar: const AdaptiveAppBar(title: 'TitleTrust Agent'),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _FeatureCard(
              title: "Forensic Document Audit",
              icon: Icons.manage_search,
              color: Colors.blue.shade100,
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ForensicScreen())),
            ),
            const SizedBox(height: 24),
            _FeatureCard(
              title: "Geospatial Reality Check",
              icon: Icons.satellite_alt,
              color: Colors.green.shade100,
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const GeospatialScreen())),
            ),
          ],
        ),
      ),
    );
  }
}

class _FeatureCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const _FeatureCard({
    required this.title,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 300,
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(16),
          boxShadow: const [BoxShadow(color: Colors.black12, blurRadius: 10, offset: Offset(0, 4))],
        ),
        child: Column(
          children: [
            Icon(icon, size: 48, color: Colors.black87),
            const SizedBox(height: 16),
            Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.black87)),
          ],
        ),
      ),
    );
  }
}
