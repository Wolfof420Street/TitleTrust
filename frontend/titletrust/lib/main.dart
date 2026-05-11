import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sentry_flutter/sentry_flutter.dart';

import 'core/theme/app_theme.dart';
import 'core/ui/adaptive/adaptive_app_bar.dart';
import 'core/ui/adaptive/adaptive_scaffold.dart';
import 'features/forensic/presentation/forensic_screen.dart';
import 'features/geospatial/presentation/geospatial_screen.dart';
import 'features/investigation/presentation/marathon_start_screen.dart';
import 'features/onboarding/presentation/onboarding_screen.dart';

import 'package:firebase_core/firebase_core.dart';

import 'features/auth/presentation/auth_controller.dart';
import 'features/auth/presentation/login_screen.dart';
import 'core/services/notification_service.dart';
import 'features/home/presentation/widgets/job_tracker_widget.dart';
import 'package:titletrust/security/transport_security_service.dart';
import 'package:titletrust/telemetry/frontend_telemetry_service.dart';
import 'package:titletrust/core/services/secure_storage_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final telemetry = FrontendTelemetryService();
  try {
    await dotenv.load(fileName: ".env");
  } catch (e) {
    debugPrint("Warning: .env file not found or invalid. Using defaults.");
  }

  try {
    await Firebase.initializeApp();
  } catch (e) {
    debugPrint("Firebase init failed: $e");
  }

  final prefs = await SharedPreferences.getInstance();
  final hasSeenOnboarding = prefs.getBool('has_seen_onboarding');
  final showOnboarding = hasSeenOnboarding == null || !hasSeenOnboarding;

  try {
    await NotificationService().initialize();
  } catch (e) {
    debugPrint("Notification init error: $e");
  }

  try {
    await telemetry.initialize();
    await telemetry.recordNetworkQuality();
    await telemetry.recordStartupTiming(const Duration(milliseconds: 0));
  } catch (e) {
    debugPrint("Telemetry init error: $e");
  }

  try {
    final transportSecurity = TransportSecurityService(const SecureStorageService(FlutterSecureStorage()));
    transportSecurity.installCertificatePinning(
      allowedFingerprints: {
        if (dotenv.env['API_CERT_FINGERPRINTS'] != null)
          ...dotenv.env['API_CERT_FINGERPRINTS']!
              .split(',')
              .map((value) => value.trim())
              .where((value) => value.isNotEmpty),
      },
    );
    await transportSecurity.ensureRequestSecret();
  } catch (e) {
    debugPrint("Transport security init error: $e");
  }

  final app = ProviderScope(child: TitleTrustApp(showOnboarding: showOnboarding));
  const sentryDsn = String.fromEnvironment('SENTRY_DSN', defaultValue: '');
  if (sentryDsn.isNotEmpty) {
    await SentryFlutter.init(
      (options) {
        options.dsn = sentryDsn;
        options.tracesSampleRate = 0.2;
        options.enableAutoSessionTracking = true;
        options.environment = const String.fromEnvironment('APP_ENV', defaultValue: 'development');
      },
      appRunner: () => runApp(app),
    );
  } else {
    runApp(app);
  }
}

class TitleTrustApp extends StatelessWidget {
  final bool showOnboarding;

  const TitleTrustApp({super.key, required this.showOnboarding});

  @override
  Widget build(BuildContext context) {
    final Widget homeWidget = showOnboarding ? const OnboardingScreen() : const AuthGuard();

    if (Platform.isIOS) {
      return CupertinoApp(
        title: 'VeriLand',
        theme: AppTheme.iosTheme,
        home: homeWidget,
        debugShowCheckedModeBanner: false,
      );
    } else {
      return MaterialApp(
        title: 'VeriLand',
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
      error: (_, __) => const Scaffold(
        body: Center(child: Text("Authentication unavailable. Please retry.")),
      ),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return AdaptiveScaffold(
      appBar: const AdaptiveAppBar(title: 'TitleTrust Agent'),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Colors.blue.shade50,
              Colors.purple.shade50,
              Colors.pink.shade50,
            ],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            physics: const BouncingScrollPhysics(),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const JobTrackerWidget(),
                  const SizedBox(height: 32),
                  Text(
                    'Intelligence Suite',
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.w800,
                      color: Colors.grey.shade800,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'AI-powered property verification',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey.shade600,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 24),
                  _FeatureCard(
                    title: "Forensic Document Audit",
                    subtitle: "Deep analysis of property documents",
                    icon: Icons.manage_search,
                    gradient: LinearGradient(
                      colors: [Colors.blue.shade400, Colors.blue.shade600],
                    ),
                    onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ForensicScreen())),
                  ),
                  const SizedBox(height: 16),
                  _FeatureCard(
                    title: "Autonomous Due Diligence",
                    subtitle: "Automated investigation workflows",
                    icon: Icons.auto_mode,
                    gradient: LinearGradient(
                      colors: [Colors.purple.shade400, Colors.purple.shade600],
                    ),
                    onTap: () =>
                        Navigator.push(context, MaterialPageRoute(builder: (_) => const MarathonStartScreen())),
                  ),
                  const SizedBox(height: 16),
                  _FeatureCard(
                    title: "Geospatial Reality Check",
                    subtitle: "Satellite verification & mapping",
                    icon: Icons.satellite_alt,
                    gradient: LinearGradient(
                      colors: [Colors.green.shade400, Colors.green.shade600],
                    ),
                    onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const GeospatialScreen())),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _FeatureCard extends StatefulWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final Gradient gradient;
  final VoidCallback onTap;

  const _FeatureCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.gradient,
    required this.onTap,
  });

  @override
  State<_FeatureCard> createState() => _FeatureCardState();
}

class _FeatureCardState extends State<_FeatureCard> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 150),
      vsync: this,
    );
    _scaleAnimation = Tween<double>(begin: 1.0, end: 0.95).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) {
        _controller.forward();
      },
      onTapUp: (_) {
        _controller.reverse();
        widget.onTap();
      },
      onTapCancel: () {
        _controller.reverse();
      },
      child: AnimatedBuilder(
        animation: _scaleAnimation,
        builder: (context, child) {
          return Transform.scale(
            scale: _scaleAnimation.value,
            child: Container(
              decoration: BoxDecoration(
                gradient: widget.gradient,
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: widget.gradient.colors.first.withOpacity(0.3),
                    blurRadius: 20,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(20),
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
                              Colors.white.withOpacity(0.2),
                              Colors.white.withOpacity(0.05),
                            ],
                          ),
                        ),
                      ),
                    ),
                    // Content
                    Padding(
                      padding: const EdgeInsets.all(24),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: Colors.white.withOpacity(0.25),
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: Icon(
                              widget.icon,
                              size: 32,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(width: 20),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  widget.title,
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.white,
                                    letterSpacing: -0.3,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  widget.subtitle,
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: Colors.white.withOpacity(0.9),
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Icon(
                            Icons.arrow_forward_ios,
                            color: Colors.white.withOpacity(0.8),
                            size: 18,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
