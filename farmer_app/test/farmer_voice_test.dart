import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:farmer_app/models/farmer_forecast.dart';
import 'package:farmer_app/services/farmer_voice_service.dart';
import 'package:farmer_app/screens/advisory_detail_screen.dart';
import 'package:farmer_app/l10n/app_localizations.dart';

Widget createVoiceTestWidget(Widget child) {
  return MaterialApp(
    supportedLocales: AppLocalizations.supportedLocales,
    localizationsDelegates: const [
      AppLocalizations.delegate,
      DefaultMaterialLocalizations.delegate,
      DefaultWidgetsLocalizations.delegate,
    ],
    home: Scaffold(body: child),
  );
}

FarmerForecast createMockForecast({
  bool isApproved = true,
  String lang = 'en',
  String severity = 'HIGH',
}) {
  return FarmerForecast(
    panchayatName: 'Ajmer Saundane',
    blockName: 'Baglan',
    districtName: 'Nashik',
    forecastDate: '2026-09-30',
    rainfallMm: 42.5,
    rainfallCategory: 'Moderate Rain',
    severity: severity,
    advisoryStatus: isApproved ? 'APPROVED' : 'PENDING_OFFICER_REVIEW',
    language: lang,
    availableLanguages: ['en', 'mr', 'hi'],
    advisoryTitle: 'Immediate drainage and postpone spray operations',
    whatIsHappening: 'Continuous rainfall expected in Baglan Block over the next 24 hours.',
    whyItMatters: 'Excess standing water can damage onion nurseries and lead to root fungal rot.',
    recommendedActions: [
      'Open drainage channels at boundary lines to release excess water.',
      'Delay pesticide and herbicide spraying until skies clear.',
    ],
    timing: 'Effective immediately for next 36 hours.',
    warnings: [
      'Do not apply chemical fertilizers during heavy rainfall runoff.',
    ],
    advisoryPoints: [
      'Open drainage channels at boundary lines.',
      'Delay pesticide spraying.',
    ],
  );
}

void main() {
  group('Phase 6.4 — FarmerVoiceService Unit Tests', () {
    test('1. Speech text preparation cleans formatting and preserves metrics and severity', () {
      final service = FarmerVoiceService(engine: MockTtsEngine());
      final forecast = createMockForecast();

      final text = service.prepareSpeechText(forecast);

      // Verify essential metrics and guidance are preserved
      expect(text, contains('Ajmer Saundane'));
      expect(text, contains('42.5 millimeters'));
      expect(text, contains('Moderate Rain'));
      expect(text, contains('Severity level: HIGH'));
      expect(text, contains('Immediate drainage'));
      expect(text, contains('What is happening: Continuous rainfall'));
      expect(text, contains('Why it matters: Excess standing water'));
      expect(text, contains('Action 1: Open drainage channels'));
      expect(text, contains('Action 2: Delay pesticide'));
      expect(text, contains('Timing outlook: Effective immediately'));
      expect(text, contains('Warning: Do not apply chemical fertilizers'));

      // Ensure no raw markdown remains
      expect(text.contains('#'), isFalse);
      expect(text.contains('*'), isFalse);
    });

    test('2. Unapproved advisory is strictly rejected from speech preparation and playback', () async {
      final mockEngine = MockTtsEngine();
      final service = FarmerVoiceService(engine: mockEngine);
      final unapproved = createMockForecast(isApproved: false);

      // Speech preparation returns empty
      expect(service.prepareSpeechText(unapproved), isEmpty);

      // Playback returns false and does not speak
      final result = await service.playAdvisory(unapproved);
      expect(result, isFalse);
      expect(service.state, equals(VoiceState.error));
      expect(mockEngine.lastSpokenText, isNull);
    });

    test('3. Supported language maps correctly and triggers playback', () async {
      final mockEngine = MockTtsEngine(supportedLocales: ['en-IN', 'mr-IN', 'hi-IN']);
      final service = FarmerVoiceService(engine: mockEngine);
      final forecast = createMockForecast(lang: 'mr');

      final success = await service.playAdvisory(forecast, language: 'mr');

      expect(success, isTrue);
      expect(mockEngine.currentLanguage, equals('mr-IN'));
      expect(mockEngine.currentRate, equals(0.45)); // rural calibrated rate
      expect(service.state, equals(VoiceState.playing));
      expect(mockEngine.lastSpokenText, isNotNull);
    });

    test('4. Unsupported device language transitions safely to unsupportedLanguage state without crashing', () async {
      // Mock engine only supports English, missing Marathi
      final mockEngine = MockTtsEngine(supportedLocales: ['en-IN']);
      final service = FarmerVoiceService(engine: mockEngine);
      final forecast = createMockForecast(lang: 'mr');

      final success = await service.playAdvisory(forecast, language: 'mr');

      expect(success, isFalse);
      expect(service.state, equals(VoiceState.unsupportedLanguage));
      expect(mockEngine.lastSpokenText, isNull);
    });

    test('5. Playback lifecycle: pause, resume, stop, replay, completion', () async {
      final mockEngine = MockTtsEngine();
      final service = FarmerVoiceService(engine: mockEngine);
      final forecast = createMockForecast();

      // Play
      await service.playAdvisory(forecast);
      expect(service.state, equals(VoiceState.playing));

      // Pause
      await service.pause();
      expect(service.state, equals(VoiceState.paused));

      // Resume
      await service.resume();
      expect(service.state, equals(VoiceState.playing));

      // Stop
      await service.stop();
      expect(service.state, equals(VoiceState.stopped));

      // Replay
      await service.replay(forecast);
      expect(service.state, equals(VoiceState.playing));

      // Completion
      mockEngine.simulateCompletion();
      expect(service.state, equals(VoiceState.completed));
    });

    test('6. Engine runtime errors transition to error state safely', () async {
      final mockEngine = MockTtsEngine()..shouldFailSpeak = true;
      final service = FarmerVoiceService(engine: mockEngine);
      final forecast = createMockForecast();

      await service.playAdvisory(forecast);
      expect(service.state, equals(VoiceState.error));
    });
  });

  group('Phase 6.4 — AdvisoryDetailScreen Voice UI Widget Tests', () {
    testWidgets('7. Voice card renders with accessible Play button on approved advisory', (tester) async {
      final mockEngine = MockTtsEngine();
      final voiceService = FarmerVoiceService(engine: mockEngine);
      final forecast = createMockForecast(isApproved: true);

      await tester.pumpWidget(
        createVoiceTestWidget(
          AdvisoryDetailScreen(
            forecast: forecast,
            onRefresh: () {},
            currentLang: 'en',
            onLanguageChanged: (_) {},
            voiceService: voiceService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Header and initial state
      expect(find.text('Audio Advisory / व्हॉइस सल्ला'), findsOneWidget);
      expect(find.text('Listen'), findsOneWidget);

      // Verify touch target is at least 48x48
      final buttonFinder = find.widgetWithText(ElevatedButton, 'Listen');
      final size = tester.getSize(buttonFinder);
      expect(size.height, greaterThanOrEqualTo(48.0));
    });

    testWidgets('8. Tapping Listen enters playing state with waveform and pause/stop controls', (tester) async {
      final mockEngine = MockTtsEngine();
      final voiceService = FarmerVoiceService(engine: mockEngine);
      final forecast = createMockForecast(isApproved: true);

      await tester.pumpWidget(
        createVoiceTestWidget(
          AdvisoryDetailScreen(
            forecast: forecast,
            onRefresh: () {},
            currentLang: 'en',
            onLanguageChanged: (_) {},
            voiceService: voiceService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Tap Listen
      await tester.tap(find.text('Listen'));
      await tester.pump();

      // Should display listening subtitle and pause/stop icon buttons
      expect(find.text('Listening...'), findsOneWidget);
      expect(find.byIcon(Icons.pause), findsOneWidget);
      expect(find.byIcon(Icons.stop), findsOneWidget);

      // Tap Pause
      await tester.tap(find.byIcon(Icons.pause));
      await tester.pump();

      // Should transition to paused
      expect(find.text('Audio paused'), findsOneWidget);
      expect(find.byIcon(Icons.play_arrow), findsOneWidget);

      // Tap Resume
      await tester.tap(find.byIcon(Icons.play_arrow));
      await tester.pump();
      expect(find.text('Listening...'), findsOneWidget);

      // Tap Stop
      await tester.tap(find.byIcon(Icons.stop));
      await tester.pump();
      expect(find.text('Listen'), findsOneWidget);
    });

    testWidgets('9. Unsupported device language displays clear friendly notice while keeping written advisory visible', (tester) async {
      // Mock engine where Marathi is unsupported
      final mockEngine = MockTtsEngine(supportedLocales: ['en-IN']);
      final voiceService = FarmerVoiceService(engine: mockEngine);
      final forecast = createMockForecast(isApproved: true, lang: 'mr');

      await tester.pumpWidget(
        createVoiceTestWidget(
          AdvisoryDetailScreen(
            forecast: forecast,
            onRefresh: () {},
            currentLang: 'mr',
            onLanguageChanged: (_) {},
            voiceService: voiceService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Tap Listen
      await tester.tap(find.text('Listen'));
      await tester.pump();

      // Friendly fallback notice
      expect(find.text('Audio is not available for this language on your device.'), findsOneWidget);
      expect(find.text('Written guidance remains fully available below.'), findsOneWidget);

      // Crucial: Written advisory remains completely intact and visible
      expect(find.text('Immediate drainage and postpone spray operations'), findsOneWidget);
      expect(find.text('Continuous rainfall expected in Baglan Block over the next 24 hours.'), findsOneWidget);
    });
  });
}
