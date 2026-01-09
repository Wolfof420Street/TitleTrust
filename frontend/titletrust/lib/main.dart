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

import 'package:firebase_core/firebase_core.dart';

import 'features/auth/presentation/auth_controller.dart';
import 'features/auth/presentation/login_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await dotenv.load(fileName: ".env");
  } catch (e) {
    debugPrint("Warning: .env file not found or invalid. Using defaults.");
  }

  await Firebase.initializeApp();

  final prefs = await SharedPreferences.getInstance();
  final hasSeenOnboarding = prefs.getBool('has_seen_onboarding');
  final showOnboarding = hasSeenOnboarding == null || !hasSeenOnboarding;

  runApp(ProviderScope(child: TitleTrustApp(showOnboarding: showOnboarding)));
}

class TitleTrustApp extends StatelessWidget {
  final bool showOnboarding;

  const TitleTrustApp({super.key, required this.showOnboarding});

  @override
  Widget build(BuildContext context) {
    // If onboarding is needed, show it. Otherwise, show AuthGuard.
    final Widget homeWidget = showOnboarding ? const OnboardingScreen() : const AuthGuard();

    if (Platform.isIOS) {
      return CupertinoApp(
        title: 'TitleTrust',
        theme: AppTheme.iosTheme,
        home: homeWidget,
        debugShowCheckedModeBanner: false,
      );
    } else {
      return MaterialApp(
        title: 'TitleTrust',
        theme: AppTheme.androidTheme,
        darkTheme: AppTheme.androidDarkTheme,
        home: homeWidget,
        debugShowCheckedModeBanner: false,
      );
    }
  }
}

class AuthGuard extends ConsumerWidget {
  const AuthGuard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authStateProvider);

    return authState.when(
      data: (user) => user != null ? const HomeScreen() : const LoginScreen(),
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (err, stack) => Scaffold(body: Center(child: Text("Error: $err"))),
    );
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
