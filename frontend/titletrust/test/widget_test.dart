import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:titletrust/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const ProviderScope(child: TitleTrustApp(showOnboarding: false)));

    // Verify the app shell booted successfully without depending on auth state.
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
