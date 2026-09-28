import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:farmer_app/widgets/agricultural_illustrations.dart';
import 'package:farmer_app/widgets/empty_state.dart';
import 'package:farmer_app/widgets/error_state.dart';

void main() {
  group('Phase 4.6 Visual Interactions & Agricultural Illustrations Tests', () {
    testWidgets('1. Agricultural illustrations render cleanly using CustomPaint',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                AgriSunFieldIllustration(size: 100),
                TopographyRainIllustration(size: 100),
                CropSproutIllustration(size: 100),
                WeatherConditionIllustration(rainfallMm: 0.0, size: 50),
                WeatherConditionIllustration(rainfallMm: 12.0, size: 50),
                WeatherConditionIllustration(rainfallMm: 75.0, size: 50),
                RainfallGaugeIllustration(rainfallMm: 35.0),
              ],
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byType(AgriSunFieldIllustration), findsOneWidget);
      expect(find.byType(TopographyRainIllustration), findsOneWidget);
      expect(find.byType(CropSproutIllustration), findsOneWidget);
      expect(find.byType(RainfallGaugeIllustration), findsOneWidget);
      expect(find.text('Moderate (7.6-64.4mm)'), findsOneWidget);
    });

    testWidgets('2. WeatherAlertPulseIllustration respects reduced-motion preferences',
        (tester) async {
      // Test when disableAnimations is TRUE
      await tester.pumpWidget(
        const MediaQuery(
          data: MediaQueryData(disableAnimations: true),
          child: MaterialApp(
            home: Scaffold(
              body: WeatherAlertPulseIllustration(
                icon: Icons.warning_amber_rounded,
                size: 36,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
      // Transform.scale should not be present within the illustration when animations are disabled
      expect(
        find.descendant(
          of: find.byType(WeatherAlertPulseIllustration),
          matching: find.byType(Transform),
        ),
        findsNothing,
      );
    });

    testWidgets('3. FarmerEmptyState renders CropSproutIllustration as default visual',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: FarmerEmptyState(
              title: 'No Forecast Available',
              description: 'Select your Gram Panchayat to view rainfall downscaling.',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('No Forecast Available'), findsOneWidget);
      expect(find.byType(CropSproutIllustration), findsOneWidget);
    });

    testWidgets('4. FarmerErrorState displays error visual and responds to retry interaction',
        (tester) async {
      bool retried = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FarmerErrorState(
              title: 'Offline Mode',
              message: 'Check connection and tap retry.',
              onRetry: () {
                retried = true;
              },
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Offline Mode'), findsOneWidget);
      expect(find.byIcon(Icons.wifi_off_rounded), findsOneWidget);

      await tester.tap(find.text('Try Again / पुन्हा प्रयत्न करा'));
      await tester.pumpAndSettle();

      expect(retried, isTrue);
    });
  });
}
