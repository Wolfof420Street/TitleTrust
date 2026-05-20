import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:titletrust/main.dart';

void main() {
  group('Onboarding and Sign-In Integration Test', () {
    testWidgets('user can see login screen',
        (WidgetTester tester) async {
      // Arrange
      await tester.pumpWidget(
        const ProviderScope(
          child: TitleTrustApp(showOnboarding: false),
        ),
      );

      // Act
      await tester.pumpAndSettle();

      // Assert
      expect(find.text('TitleTrust Agent'), findsOneWidget);
      expect(find.text('Secure Forensic Land Audit'), findsOneWidget);
    });

    testWidgets('sign-in button is visible',
        (WidgetTester tester) async {
      // Arrange
      await tester.pumpWidget(
        const ProviderScope(
          child: TitleTrustApp(showOnboarding: false),
        ),
      );
      await tester.pumpAndSettle();

      // Assert
      final button = find.byType(ElevatedButton);
      expect(button, findsOneWidget);
    });

    testWidgets('UI elements are visible on default screen',
        (WidgetTester tester) async {
      // Arrange
      await tester.pumpWidget(
        const ProviderScope(
          child: TitleTrustApp(showOnboarding: false),
        ),
      );
      await tester.pumpAndSettle();

      // Assert - icon, title, button should all be visible
      expect(find.byIcon(Icons.security), findsOneWidget);
      expect(find.text('TitleTrust Agent'), findsOneWidget);
      expect(find.byType(ElevatedButton), findsOneWidget);
    });

    testWidgets('all required security elements are rendered',
        (WidgetTester tester) async {
      // Arrange
      await tester.pumpWidget(
        const ProviderScope(
          child: TitleTrustApp(showOnboarding: false),
        ),
      );
      await tester.pumpAndSettle();

      // Assert
      expect(find.byIcon(Icons.security), findsOneWidget);
      expect(find.byIcon(Icons.login), findsOneWidget);
      expect(find.byType(ElevatedButton), findsOneWidget);
    });
  });
}
