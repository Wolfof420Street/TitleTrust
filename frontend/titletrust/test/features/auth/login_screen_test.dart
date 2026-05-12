import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:titletrust/features/auth/presentation/login_screen.dart';


void main() {
  group('LoginScreen Widget Tests', () {
    testWidgets('displays TitleTrust branding text',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: ProviderScope(child: LoginScreen()),
        ),
      );

      expect(find.text('TitleTrust Agent'), findsOneWidget);
      expect(find.text('Secure Forensic Land Audit'), findsOneWidget);
    });

    testWidgets('displays security icon', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: ProviderScope(child: LoginScreen()),
        ),
      );

      expect(find.byIcon(Icons.security), findsOneWidget);
    });

    testWidgets('displays sign-in button with Google icon',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: ProviderScope(child: LoginScreen()),
        ),
      );

      expect(find.text('Sign in with Google'), findsOneWidget);
      expect(find.byIcon(Icons.login), findsOneWidget);
    });

    testWidgets('renders LoginScreen with Scaffold structure',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: ProviderScope(child: LoginScreen()),
        ),
      );

      expect(find.byType(Scaffold), findsOneWidget);
      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets('layout elements are visible',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: ProviderScope(child: LoginScreen()),
        ),
      );

      // Key elements should be visible
      expect(find.byIcon(Icons.security), findsOneWidget);
      expect(find.text('TitleTrust Agent'), findsOneWidget);
    });
  });
}
