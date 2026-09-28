import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:farmer_app/models/farmer_forecast.dart';
import 'package:farmer_app/models/panchayat_item.dart';
import 'package:farmer_app/screens/home_forecast_screen.dart';
import 'package:farmer_app/screens/onboarding_screen.dart';
import 'package:farmer_app/l10n/app_localizations.dart';
import 'package:farmer_app/theme/app_theme.dart';
import 'package:farmer_app/widgets/agricultural_illustrations.dart';
import 'package:farmer_app/widgets/weather_hero_card.dart';
import 'package:farmer_app/widgets/advisory_card.dart';

void main() {
  group('Phase 4.4 Farmer Onboarding & Home Experience Tests', () {
    final testPanchayats = <PanchayatItem>[
      PanchayatItem(
        panchayatId: 1001,
        lgdCode: 182597,
        panchayatName: 'Ajmer Saundane',
        blockName: 'Baglan',
        districtName: 'Nashik',
        latitude: 20.6385,
        longitude: 74.1201,
        elevationM: 585.0,
      ),
      PanchayatItem(
        panchayatId: 1002,
        lgdCode: 182600,
        panchayatName: 'Mulher',
        blockName: 'Baglan',
        districtName: 'Nashik',
        latitude: 20.75,
        longitude: 74.05,
        elevationM: 710.0,
      ),
    ];

    final sampleForecast = FarmerForecast(
      panchayatName: 'Ajmer Saundane',
      blockName: 'Baglan',
      districtName: 'Nashik',
      forecastDate: '2026-09-09',
      rainfallMm: 14.5,
      rainfallCategory: 'MODERATE_RAIN',
      severity: 'MEDIUM',
      advisoryTitle: 'Postpone Pesticide Spraying — Moderate Showers',
      advisoryPoints: const [
        'Expected 14.5 mm rainfall between 2:00 PM and 6:00 PM.',
        'Ensure drainage outlets are open in low-lying vegetable plots.',
      ],
      advisoryStatus: 'APPROVED',
      language: 'en',
      availableLanguages: const ['en', 'mr', 'hi'],
      languageStatus: 'ACTIVE',
    );

    testWidgets('1. Onboarding displays welcome story and advances through 3 steps',
        (tester) async {
      PanchayatItem? completedPanchayat;

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            DefaultMaterialLocalizations.delegate,
            DefaultWidgetsLocalizations.delegate,
          ],
          home: FarmerOnboardingScreen(
            panchayats: testPanchayats,
            initialPanchayatId: 1001,
            currentLang: 'en',
            onLanguageChanged: (_) {},
            onCompleteOnboarding: (p) => completedPanchayat = p,
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Step 1: Welcome Screen
      expect(find.text('GramSevak'), findsOneWidget);
      expect(find.text('Village-Level Weather & Farm Guidance'), findsOneWidget);
      expect(find.byType(AgriSunFieldIllustration), findsOneWidget);

      // Tap Next to Step 2
      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();

      // Step 2: Why Location Matters
      expect(find.text('Weather Changes Every 5 km'), findsOneWidget);
      expect(find.byType(TopographyRainIllustration), findsOneWidget);

      // Tap Next to Step 3
      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();

      // Step 3: Location Selection
      expect(find.text('Select Your Gram Panchayat'), findsOneWidget);
      expect(find.text('Ajmer Saundane'), findsOneWidget);
      expect(find.text('Baglan Block • Nashik'), findsOneWidget);
      expect(find.text('Choose Gram Panchayat'), findsOneWidget);

      // Tap Get Started button to complete onboarding
      await tester.tap(find.text('Open My Farm Dashboard'));
      await tester.pumpAndSettle();

      expect(completedPanchayat, isNotNull);
      expect(completedPanchayat!.panchayatId, 1001);
    });

    testWidgets('2. Skip button directly jumps to Step 3 Location Selection',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            DefaultMaterialLocalizations.delegate,
            DefaultWidgetsLocalizations.delegate,
          ],
          home: FarmerOnboardingScreen(
            panchayats: testPanchayats,
            initialPanchayatId: 1001,
            currentLang: 'en',
            onLanguageChanged: (_) {},
            onCompleteOnboarding: (_) {},
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Tap Skip on Step 1
      await tester.tap(find.text('Skip'));
      await tester.pumpAndSettle();

      // Should be on Step 3
      expect(find.text('Select Your Gram Panchayat'), findsOneWidget);
      expect(find.text('Open My Farm Dashboard'), findsOneWidget);
    });

    testWidgets('3. HomeForecastScreen renders restrained typography and audio playback',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            DefaultMaterialLocalizations.delegate,
            DefaultWidgetsLocalizations.delegate,
          ],
          home: Scaffold(
            body: HomeForecastScreen(
              forecast: sampleForecast,
              onRefresh: () {},
              onSwitchPanchayat: () {},
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Location Header
      expect(find.text('Ajmer Saundane'), findsOneWidget);
      expect(find.text('Baglan Block, Nashik'), findsOneWidget);
      expect(find.text('Change Village'), findsOneWidget);

      // Hero Weather Card (restrained 30px metric)
      expect(find.byType(WeatherHeroCard), findsOneWidget);
      expect(find.text('14.5'), findsOneWidget);
      expect(find.text('mm'), findsOneWidget);
      expect(find.text('Moderate Rain'), findsOneWidget);

      // Key Operations
      expect(find.text('Postpone'), findsOneWidget);
      expect(find.text('MEDIUM'), findsOneWidget);

      // Hero Advisory Card & Audio Button
      expect(find.byType(AdvisoryCard), findsOneWidget);
      expect(find.text('Officer Verified Advisory'), findsOneWidget);
      expect(find.text('Postpone Pesticide Spraying — Moderate Showers'), findsOneWidget);
      expect(find.text('Listen'), findsOneWidget);

      // Tap Audio Listen button
      await tester.tap(find.text('Listen'));
      await tester.pump(const Duration(milliseconds: 100));

      // Audio waveform illustration active during playback
      expect(find.byType(AudioWaveformIllustration), findsOneWidget);
      expect(find.text('Listening...'), findsOneWidget);

      // Settle audio playback timer
      await tester.pump(const Duration(seconds: 4));
      await tester.pumpAndSettle();
    });
  });
}
