import 'package:flutter_test/flutter_test.dart';
import 'package:farmer_app/main.dart';
import 'package:farmer_app/models/farmer_preference.dart';
import 'package:farmer_app/services/farmer_preferences_service.dart';

void main() {
  testWidgets('GramSevak Farmer App renders onboarding for new farmer', (WidgetTester tester) async {
    await tester.pumpWidget(const GramSevakFarmerApp());
    await tester.pumpAndSettle();

    // Verify onboarding elements appear
    expect(find.text('GramSevak'), findsWidgets);
  });

  testWidgets('GramSevak Farmer App renders home shell for returning farmer', (WidgetTester tester) async {
    final prefsService = FarmerPreferencesService(
      initialPreferences: FarmerPreferences(
        farmerId: 'farmer-test',
        panchayatId: 1001,
        panchayatName: 'Ajmer Saundane',
        blockName: 'Baglan',
        districtName: 'Nashik',
        preferredLanguage: 'en',
        updatedAt: DateTime.now(),
        hasCompletedSetup: true,
      ),
    );

    await tester.pumpWidget(GramSevakFarmerApp(
      preferencesService: prefsService,
    ));
    await tester.pumpAndSettle();

    // Verify that the title and key branding elements appear.
    expect(find.text('GramSevak'), findsWidgets);
    expect(find.text('Forecast'), findsWidgets);
    expect(find.text('Advisory'), findsWidgets);
    expect(find.text('Profile'), findsOneWidget);
  });
}
