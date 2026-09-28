import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:farmer_app/models/farmer_forecast.dart';
import 'package:farmer_app/screens/forecast_detail_screen.dart';
import 'package:farmer_app/screens/advisory_detail_screen.dart';
import 'package:farmer_app/widgets/agricultural_illustrations.dart';
import 'package:farmer_app/l10n/app_localizations.dart';

void main() {
  final approvedForecast = FarmerForecast(
    panchayatName: 'Ajmer Saundane',
    blockName: 'Baglan',
    districtName: 'Nashik',
    forecastDate: '2026-09-10',
    rainfallMm: 24.5,
    rainfallCategory: 'Moderate rainfall',
    severity: 'MODERATE',
    advisoryTitle: 'Verified Moderate Rainfall Guidance for Grapes & Onions',
    advisoryPoints: const [
      'Suspend foliar sprays until weather clears.',
      'Inspect field drainage trenches for sediment blockage.',
    ],
    advisoryStatus: 'APPROVED',
    language: 'en',
    availableLanguages: const ['en', 'mr', 'hi'],
  );

  final heavyRainForecast = FarmerForecast(
    panchayatName: 'Mulher',
    blockName: 'Baglan',
    districtName: 'Nashik',
    forecastDate: '2026-09-10',
    rainfallMm: 72.0,
    rainfallCategory: 'Heavy rainfall',
    severity: 'HIGH',
    advisoryTitle: 'Heavy Inundation Precaution Advisory',
    advisoryPoints: const [
      'Open emergency drainage trenches immediately.',
      'Shift harvested produce to elevated platforms.',
    ],
    advisoryStatus: 'APPROVED',
    language: 'en',
    availableLanguages: const ['en', 'mr', 'hi'],
  );

  final unapprovedForecast = FarmerForecast(
    panchayatName: 'Akhatwade',
    blockName: 'Baglan',
    districtName: 'Nashik',
    forecastDate: '2026-09-10',
    rainfallMm: 12.0,
    rainfallCategory: 'Moderate rainfall',
    severity: 'LOW',
    advisoryTitle: 'Draft Unverified Model Guidance',
    advisoryPoints: const ['Draft advice that should remain hidden.'],
    advisoryStatus: 'NO_APPROVED_ADVISORY',
    language: 'en',
    availableLanguages: const ['en', 'mr', 'hi'],
  );

  Widget createTestWidget(Widget child, {Locale locale = const Locale('en')}) {
    return MaterialApp(
      locale: locale,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: child),
    );
  }

  group('Phase 4.5 Weather Experience & Forecast Presentation Tests', () {
    testWidgets('1. ForecastDetailScreen renders Panchayat, rainfall, gauge, and weather visual',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          ForecastDetailScreen(
            forecast: approvedForecast,
            onRefresh: () {},
            onSwitchPanchayat: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Verified Panchayat Header
      expect(find.text('Ajmer Saundane'), findsOneWidget);
      expect(find.text('Baglan Block, Nashik'), findsOneWidget);

      // Rainfall Display & Units
      expect(find.text('24.5'), findsOneWidget);
      expect(find.text('mm'), findsOneWidget);

      // Weather Condition Illustration & Gauge
      expect(find.byType(WeatherConditionIllustration), findsOneWidget);
      expect(find.byType(RainfallGaugeIllustration), findsOneWidget);

      // Operational Guidance Tiles
      expect(find.text('Field Operational Guidance'), findsOneWidget);
      expect(find.text('Spraying Window'), findsOneWidget);
      expect(find.text('Field Drainage'), findsOneWidget);
    });

    testWidgets('2. ForecastDetailScreen renders Heavy Rain Alert banner when rainfall is high',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          ForecastDetailScreen(
            forecast: heavyRainForecast,
            onRefresh: () {},
            onSwitchPanchayat: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Heavy Rain Weather Advisory'), findsOneWidget);
      expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
    });

    testWidgets('3. ForecastDetailScreen switches between Overview and Time-of-Day Outlook tabs',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          ForecastDetailScreen(
            forecast: approvedForecast,
            onRefresh: () {},
            onSwitchPanchayat: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Switch to Time-of-Day tab
      await tester.tap(find.text('Time-of-Day Outlook'));
      await tester.pumpAndSettle();

      expect(find.text('Morning (06:00 - 12:00)'), findsOneWidget);
      expect(find.text('Afternoon (12:00 - 18:00)'), findsOneWidget);
      expect(find.text('Evening & Night (18:00+)'), findsOneWidget);
    });
  });

  group('Phase 4.5 Advisory Experience Tests (3-Tier Structure)', () {
    testWidgets('4. AdvisoryDetailScreen presents What is happening -> Why it matters -> What you can do',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          AdvisoryDetailScreen(
            forecast: approvedForecast,
            onRefresh: () {},
            currentLang: 'en',
            onLanguageChanged: (_) {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Main Recommendation Callout
      expect(find.text('Recommended Action'), findsOneWidget);
      expect(
        find.text('Verified Moderate Rainfall Guidance for Grapes & Onions'),
        findsOneWidget,
      );

      // 3-Tier Headings
      expect(find.text('What is happening?'), findsOneWidget);
      expect(find.text('Why it matters for your field'), findsOneWidget);
      expect(find.text('What you can do (Recommended Actions)'), findsOneWidget);

      // Actionable Guidance Points
      expect(find.text('Suspend foliar sprays until weather clears.'), findsOneWidget);
      expect(
        find.text('Inspect field drainage trenches for sediment blockage.'),
        findsOneWidget,
      );

      // Officer Verification Seal
      expect(find.byIcon(Icons.verified_user), findsOneWidget);
      expect(find.byIcon(Icons.verified), findsOneWidget);

      // Audio Read-Aloud Voice Card
      expect(find.text('Listen'), findsOneWidget);
    });

    testWidgets('5. AdvisoryDetailScreen audio button activates audio animation waveform',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          AdvisoryDetailScreen(
            forecast: approvedForecast,
            onRefresh: () {},
            currentLang: 'en',
            onLanguageChanged: (_) {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Tap Listen button
      await tester.tap(find.text('Listen'));
      await tester.pump();

      // Should show listening status
      expect(find.text('Listening...'), findsOneWidget);
      expect(find.byType(AudioWaveformIllustration), findsOneWidget);

      // Advance timer so pending timer completes cleanly
      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('6. AdvisoryDetailScreen renders clean pending review state when unapproved',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          AdvisoryDetailScreen(
            forecast: unapprovedForecast,
            onRefresh: () {},
            currentLang: 'en',
            onLanguageChanged: (_) {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Must hide raw draft advice
      expect(find.text('Draft Unverified Model Guidance'), findsNothing);
      expect(find.text('Draft advice that should remain hidden.'), findsNothing);

      // Must show official under-review message
      expect(find.text('Advisory Under Officer Review'), findsOneWidget);
      expect(find.byIcon(Icons.hourglass_empty), findsOneWidget);
      expect(find.text('Try Again'), findsOneWidget);
    });
  });
}
