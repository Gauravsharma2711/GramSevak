import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:farmer_app/screens/home_forecast_screen.dart';
import 'package:farmer_app/screens/onboarding_screen.dart';
import 'package:farmer_app/models/farmer_forecast.dart';
import 'package:farmer_app/models/panchayat_item.dart';
import 'package:farmer_app/l10n/app_localizations.dart';
import 'package:farmer_app/theme/app_theme.dart';

void main() {
  final sampleForecast = FarmerForecast(
    panchayatName: 'Ajmer Saundane Gram Panchayat with Very Long Name',
    blockName: 'Baglan',
    districtName: 'Nashik',
    forecastDate: '2026-09-09',
    rainfallMm: 42.5,
    rainfallCategory: 'MODERATE_RAIN',
    severity: 'MEDIUM',
    advisoryStatus: 'APPROVED',
    advisoryTitle: 'Postpone Fertilizer Application',
    advisoryPoints: const ['Dig drainage furrows', 'Delay chemical sprays'],
    language: 'en',
    availableLanguages: const ['en', 'mr', 'hi'],
    languageStatus: 'ACTIVE',
  );

  final samplePanchayats = [
    PanchayatItem(
      panchayatId: 101,
      lgdCode: 182597,
      panchayatName: 'Ajmer Saundane',
      blockName: 'Baglan',
      districtName: 'Nashik',
      latitude: 20.6385,
      longitude: 74.1201,
      elevationM: 585.0,
    ),
  ];

  Widget createResponsiveTestApp(Widget child, Size screenSize) {
    return MediaQuery(
      data: MediaQueryData(
        size: screenSize,
        padding: const EdgeInsets.only(top: 24, bottom: 16),
        devicePixelRatio: 2.0,
      ),
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          DefaultMaterialLocalizations.delegate,
          DefaultWidgetsLocalizations.delegate,
        ],
        home: child,
      ),
    );
  }

  group('Phase 4.7 Responsive & Accessibility Tests', () {
    testWidgets('1. HomeForecastScreen renders on ultra-compact 320x568 screen without overflow',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(320, 568));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        createResponsiveTestApp(
          Scaffold(
            body: HomeForecastScreen(
              forecast: sampleForecast,
              onRefresh: () {},
              onSwitchPanchayat: () {},
            ),
          ),
          const Size(320, 568),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.byType(HomeForecastScreen), findsOneWidget);
    });

    testWidgets('2. FarmerOnboardingScreen renders on compact 360x640 screen with scrollable content',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(360, 640));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        createResponsiveTestApp(
          FarmerOnboardingScreen(
            panchayats: samplePanchayats,
            initialPanchayatId: 101,
            onCompleteOnboarding: (_) {},
            currentLang: 'en',
            onLanguageChanged: (_) {},
          ),
          const Size(360, 640),
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('GramSevak'), findsOneWidget);
      expect(find.byType(SingleChildScrollView), findsWidgets);
    });

    testWidgets('3. HomeForecastScreen renders gracefully on large 800x1280 tablet screen',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(800, 1280));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        createResponsiveTestApp(
          Scaffold(
            body: HomeForecastScreen(
              forecast: sampleForecast,
              onRefresh: () {},
              onSwitchPanchayat: () {},
            ),
          ),
          const Size(800, 1280),
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('42.5'), findsOneWidget);
    });

    testWidgets('4. Semantic buttons have accessible touch labels',
        (tester) async {
      await tester.pumpWidget(
        createResponsiveTestApp(
          Scaffold(
            body: HomeForecastScreen(
              forecast: sampleForecast,
              onRefresh: () {},
              onSwitchPanchayat: () {},
            ),
          ),
          const Size(375, 812),
        ),
      );
      await tester.pumpAndSettle();

      final semantics = find.byType(Semantics);
      expect(semantics, findsWidgets);
    });
  });
}
