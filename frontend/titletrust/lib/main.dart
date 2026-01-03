import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'features/forensic/presentation/forensic_screen.dart';
import 'features/geospatial/presentation/geospatial_screen.dart';

void main() {
  runApp(const ProviderScope(child: TitleTrustApp()));
}

class TitleTrustApp extends StatelessWidget {
  const TitleTrustApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TitleTrust',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1A73E8)),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('TitleTrust Agent')),
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
            Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }
}
