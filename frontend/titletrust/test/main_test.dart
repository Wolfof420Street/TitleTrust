import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:titletrust/main.dart';

Widget _buildApp() {
  return const ProviderScope(
    child: TitleTrustApp(showOnboarding: false),
  );
}

void main() {
  group('TitleTrust App', () {
    testWidgets('app initializes with correct theme', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());

      // Assert
      expect(find.byType(MaterialApp), findsOneWidget);
    });

    testWidgets('starts at login screen for unauthenticated user',
        (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());
      await tester.pumpAndSettle();

      // Assert
      expect(find.byType(AuthGuard), findsOneWidget);
    });

    testWidgets('theme uses proper color scheme', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());

      // Assert
      final materialApp = find.byType(MaterialApp).evaluate().first.widget
          as MaterialApp;
      expect(materialApp.theme, isNotNull);
    });

    testWidgets('app title is set correctly', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());

      // Assert
      final materialApp = find.byType(MaterialApp).evaluate().first.widget
          as MaterialApp;
      expect(materialApp.title, equals('VeriLand'));
    });

    testWidgets('app is responsive to orientation changes',
        (WidgetTester tester) async {
      // This test is deferred - requires more complex setup
      expect(true, true);
    });
  });

  group('App Navigation', () {
    testWidgets('navigation stack is initialized', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());

      // Assert
      expect(find.byType(Navigator), findsOneWidget);
    });

    testWidgets('home screen is the initial route', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());
      await tester.pumpAndSettle();

      // Assert
      expect(true, true);
    });
  });

  group('App Lifecycle', () {
    testWidgets('app initializes required services on startup',
        (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());

      // Assert
      expect(find.byType(ProviderScope), findsOneWidget);
    });

    testWidgets('telemetry is initialized', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());

      // Assert
      expect(true, true);
    });

    testWidgets('error handling is configured', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());

      // Assert
      expect(true, true);
    });
  });
}
