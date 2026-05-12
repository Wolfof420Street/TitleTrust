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
    testWidgets('app initializes with MaterialApp', (WidgetTester tester) async {
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

    testWidgets('theme is configured', (WidgetTester tester) async {
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
  });

  group('App Navigation', () {
    testWidgets('navigation stack is initialized', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());

      // Assert
      expect(find.byType(Navigator), findsOneWidget);
    });
  });

  group('App Lifecycle', () {
    testWidgets('renders ProviderScope on startup',
        (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(_buildApp());

      // Assert
      expect(find.byType(ProviderScope), findsOneWidget);
    });
  });
}
