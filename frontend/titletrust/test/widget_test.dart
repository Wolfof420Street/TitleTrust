import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:titletrust/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const ProviderScope(child: TitleTrustApp(showOnboarding: false)));

    // Verify that our app title is present (Home Screen)
    expect(find.text('TitleTrust Agent'), findsOneWidget);
  });
}
