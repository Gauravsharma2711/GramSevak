import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:farmer_app/models/farmer_forecast.dart';
import 'package:farmer_app/screens/advisory_detail_screen.dart';
import 'package:farmer_app/screens/home_forecast_screen.dart';
import 'package:farmer_app/l10n/app_localizations.dart';

class _TestMaterialLocalizationsDelegate extends LocalizationsDelegate<MaterialLocalizations> {
  const _TestMaterialLocalizationsDelegate();
  @override
  bool isSupported(Locale locale) => true;
  @override
  Future<MaterialLocalizations> load(Locale locale) =>
      DefaultMaterialLocalizations.load(const Locale('en'));
  @override
  bool shouldReload(_TestMaterialLocalizationsDelegate old) => false;
}

class _TestCupertinoLocalizationsDelegate extends LocalizationsDelegate<CupertinoLocalizations> {
  const _TestCupertinoLocalizationsDelegate();
  @override
  bool isSupported(Locale locale) => true;
  @override
  Future<CupertinoLocalizations> load(Locale locale) =>
      DefaultCupertinoLocalizations.load(const Locale('en'));
  @override
  bool shouldReload(_TestCupertinoLocalizationsDelegate old) => false;
}

void main() {
  final approvedForecastEn = FarmerForecast(
    panchayatName: 'Ajmer Saundane',
    blockName: 'Baglan',
    districtName: 'Nashik',
    forecastDate: '2026-09-10',
    rainfallMm: 24.5,
    rainfallCategory: 'Moderate rainfall',
    severity: 'MODERATE',
    advisoryTitle: 'Moderate Rainfall Advisory - Clean Drainage and Halt Irrigation',
    advisoryPoints: const [
      'Suspend all surface irrigation.',
      'Clean field drainage channels.',
    ],
    advisoryStatus: 'APPROVED',
    language: 'en',
    availableLanguages: const ['en', 'mr', 'hi'],
    summary: 'Moderate Rainfall Advisory - Clean Drainage and Halt Irrigation',
    whatIsHappening: '24.5 mm moderate rainfall predicted across the Panchayat.',
    whyItMatters: 'Rainfall satisfies crop water demands; water stagnation in heavy soils may cause root damage.',
    recommendedActions: const [
      'Suspend all surface irrigation.',
      'Clean field drainage channels.',
    ],
    timing: 'Next 24 to 48 hours',
    warnings: const [
      'Do not apply nitrogenous fertilizers prior to rainfall.',
    ],
    advisoryVersion: 2,
    approvedAt: '2026-09-20T14:30:00Z',
  );

  final approvedForecastMr = FarmerForecast(
    panchayatName: 'अजमेर सौंदाणे',
    blockName: 'बागलाण',
    districtName: 'नाशिक',
    forecastDate: '2026-09-10',
    rainfallMm: 24.5,
    rainfallCategory: 'मध्यम पाऊस',
    severity: 'MODERATE',
    advisoryTitle: 'मध्यम पाऊस सल्ला - पाण्याचा निचरा करा व सिंचन थांबवा',
    advisoryPoints: const [
      'सर्व प्रकारचे वरचे सिंचन तात्काळ थांबवा.',
      'शेतातील पाटाचे चर स्वच्छ करा.',
    ],
    advisoryStatus: 'APPROVED',
    language: 'mr',
    availableLanguages: const ['en', 'mr', 'hi'],
    summary: 'मध्यम पाऊस सल्ला - पाण्याचा निचरा करा व सिंचन थांबवा',
    whatIsHappening: 'पंचायत कार्यक्षेत्रात 24.5 मिमी मध्यम स्वरूपाचा पाऊस अपेक्षित आहे.',
    whyItMatters: 'पावसामुळे पिकाची पाण्याची गरज पूर्ण होते; परंतु भारी जमिनीत पाणी साचल्यास मुळे कुजण्याचा धोका संभवतो.',
    recommendedActions: const [
      'सर्व प्रकारचे वरचे सिंचन तात्काळ थांबवा.',
      'शेतातील पाटाचे चर स्वच्छ करा.',
    ],
    timing: 'पुढील २४ ते ४८ तास',
    warnings: const [
      'पावसापूर्वी युरिया किंवा नत्रयुक्त खते देणे टाळा.',
    ],
    advisoryVersion: 2,
    approvedAt: '2026-09-20T14:30:00Z',
  );

  final approvedForecastHi = FarmerForecast(
    panchayatName: 'अजमेर सौंदाने',
    blockName: 'बागलाण',
    districtName: 'नासिक',
    forecastDate: '2026-09-10',
    rainfallMm: 24.5,
    rainfallCategory: 'मध्यम बारिश',
    severity: 'MODERATE',
    advisoryTitle: 'मध्यम वर्षा कृषि परामर्श - जल निकासी साफ करें और सिंचाई रोकें',
    advisoryPoints: const [
      'सभी प्रकार की सतही सिंचाई तुरंत रोक दें।',
      'खेत की जलनिकासी नालियों को साफ करें।',
    ],
    advisoryStatus: 'APPROVED',
    language: 'hi',
    availableLanguages: const ['en', 'mr', 'hi'],
    summary: 'मध्यम वर्षा कृषि परामर्श - जल निकासी साफ करें और सिंचाई रोकें',
    whatIsHappening: 'पंचायत क्षेत्र में 24.5 मिमी मध्यम वर्षा का पूर्वानुमान है।',
    whyItMatters: 'वर्षा से फसलों की पानी की मांग पूरी होती है; भारी मिट्टी में जलभराव से जड़ गलन की संभावना रहती है।',
    recommendedActions: const [
      'सभी प्रकार की सतही सिंचाई तुरंत रोक दें।',
      'खेत की जलनिकासी नालियों को साफ करें।',
    ],
    timing: 'अगले 24 से 48 घंटे',
    warnings: const [
      'बारिश से पहले यूरिया या नाइट्रोजन उर्वरक डालने से बचें।',
    ],
    advisoryVersion: 2,
    approvedAt: '2026-09-20T14:30:00Z',
  );

  final unapprovedForecast = FarmerForecast(
    panchayatName: 'Akhatwade',
    blockName: 'Baglan',
    districtName: 'Nashik',
    forecastDate: '2026-09-10',
    rainfallMm: 14.0,
    rainfallCategory: 'Moderate rainfall',
    severity: 'MODERATE',
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
        _TestMaterialLocalizationsDelegate(),
        _TestCupertinoLocalizationsDelegate(),
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: child),
    );
  }

  group('Phase 5.7 Farmer Advisory Integration & Multilingual Tests', () {
    testWidgets('1. Approved advisory renders 3-tier structure (what, why, actions, timing, warnings)',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          AdvisoryDetailScreen(
            forecast: approvedForecastEn,
            onRefresh: () {},
            currentLang: 'en',
            onLanguageChanged: (_) {},
          ),
          locale: const Locale('en'),
        ),
      );
      await tester.pumpAndSettle();

      // Tier 1: What is happening
      expect(find.text('What is happening?'), findsOneWidget);
      expect(find.text('24.5 mm moderate rainfall predicted across the Panchayat.'), findsOneWidget);

      // Tier 2: Why it matters
      expect(find.text('Why it matters for your field'), findsOneWidget);
      expect(find.text('Rainfall satisfies crop water demands; water stagnation in heavy soils may cause root damage.'), findsOneWidget);

      // Tier 3: Recommended actions
      expect(find.text('What you can do (Recommended Actions)'), findsOneWidget);
      expect(find.text('Suspend all surface irrigation.'), findsOneWidget);
      expect(find.text('Clean field drainage channels.'), findsOneWidget);

      // Timing & Warnings
      expect(find.text('Timing & Validity'), findsOneWidget);
      expect(find.text('Next 24 to 48 hours'), findsOneWidget);
      expect(find.text('Important Operational Warnings'), findsOneWidget);
      expect(find.text('• Do not apply nitrogenous fertilizers prior to rainfall.'), findsOneWidget);

      // Version badge & Officer verification
      expect(find.text('v2'), findsOneWidget);
      expect(find.byIcon(Icons.verified), findsOneWidget);
      expect(find.byIcon(Icons.verified_user), findsOneWidget);
    });

    testWidgets('2. Unapproved / NO_APPROVED_ADVISORY renders clean empty state without draft content',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          AdvisoryDetailScreen(
            forecast: unapprovedForecast,
            onRefresh: () {},
            currentLang: 'en',
            onLanguageChanged: (_) {},
          ),
          locale: const Locale('en'),
        ),
      );
      await tester.pumpAndSettle();

      // Clean empty state
      expect(find.text('Advisory Under Officer Review'), findsOneWidget);
      expect(find.byIcon(Icons.hourglass_empty), findsOneWidget);
      expect(find.text('Try Again'), findsOneWidget);

      // Internal diagnostics / draft text should NOT appear
      expect(find.text('Draft Unverified Model Guidance'), findsNothing);
      expect(find.text('Draft advice that should remain hidden.'), findsNothing);
      expect(find.text('What is happening?'), findsNothing);
      expect(find.text('GENERATED'), findsNothing);
      expect(find.text('VALIDATION_FAILED'), findsNothing);
    });

    testWidgets('3. Marathi advisory renders accurately with numerical rainfall preserved',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          AdvisoryDetailScreen(
            forecast: approvedForecastMr,
            onRefresh: () {},
            currentLang: 'mr',
            onLanguageChanged: (_) {},
          ),
          locale: const Locale('mr'),
        ),
      );
      await tester.pumpAndSettle();

      // Marathi headers
      expect(find.text('काय घडत आहे?'), findsOneWidget);
      expect(find.text('पंचायत कार्यक्षेत्रात 24.5 मिमी मध्यम स्वरूपाचा पाऊस अपेक्षित आहे.'), findsOneWidget);

      expect(find.text('तुमच्या शेतासाठी हे का महत्त्वाचे आहे'), findsOneWidget);
      expect(find.text('तुम्ही काय करू शकता (शिफारस केलेल्या कृती)'), findsOneWidget);
      expect(find.text('वेळ आणि वैधता'), findsOneWidget);
      expect(find.text('पुढील २४ ते ४८ तास'), findsOneWidget);
      expect(find.text('महत्त्वाच्या शेती सूचना'), findsOneWidget);
      expect(find.text('• पावसापूर्वी युरिया किंवा नत्रयुक्त खते देणे टाळा.'), findsOneWidget);

      // Numerical rainfall preserved
      expect(approvedForecastMr.rainfallMm, equals(24.5));
    });

    testWidgets('4. Hindi advisory renders accurately with numerical rainfall preserved',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          AdvisoryDetailScreen(
            forecast: approvedForecastHi,
            onRefresh: () {},
            currentLang: 'hi',
            onLanguageChanged: (_) {},
          ),
          locale: const Locale('hi'),
        ),
      );
      await tester.pumpAndSettle();

      // Hindi headers
      expect(find.text('क्या हो रहा है?'), findsOneWidget);
      expect(find.text('पंचायत क्षेत्र में 24.5 मिमी मध्यम वर्षा का पूर्वानुमान है।'), findsOneWidget);

      expect(find.text('आपके खेत के लिए यह क्यों महत्वपूर्ण है'), findsOneWidget);
      expect(find.text('आप क्या कर सकते हैं (अनुशंसित कार्रवाई)'), findsOneWidget);
      expect(find.text('समय और वैधता'), findsOneWidget);
      expect(find.text('अगले 24 से 48 घंटे'), findsOneWidget);
      expect(find.text('महत्वपूर्ण कृषि सावधानियां'), findsOneWidget);
      expect(find.text('• बारिश से पहले यूरिया या नाइट्रोजन उर्वरक डालने से बचें।'), findsOneWidget);

      // Numerical rainfall preserved
      expect(approvedForecastHi.rainfallMm, equals(24.5));
    });

    testWidgets('5. HomeForecastScreen shows approved advisory preview card and triggers navigation',
        (tester) async {
      bool navigated = false;
      await tester.pumpWidget(
        createTestWidget(
          HomeForecastScreen(
            forecast: approvedForecastEn,
            onRefresh: () {},
            onSwitchPanchayat: () {},
            onViewAdvisoryDetails: () {
              navigated = true;
            },
          ),
          locale: const Locale('en'),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Agricultural Advisory'), findsOneWidget);
      expect(find.text('Moderate Rainfall Advisory - Clean Drainage and Halt Irrigation'), findsOneWidget);
      expect(find.text('View All Advice →'), findsOneWidget);

      // Tap on View All Advice
      await tester.tap(find.text('View All Advice →'));
      await tester.pumpAndSettle();

      expect(navigated, isTrue);
    });

    testWidgets('6. HomeForecastScreen shows pending notice when advisory is not approved',
        (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          HomeForecastScreen(
            forecast: unapprovedForecast,
            onRefresh: () {},
            onSwitchPanchayat: () {},
          ),
          locale: const Locale('en'),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Agricultural Advisory'), findsOneWidget);
      expect(find.text('Advisory Under Officer Review'), findsOneWidget);
      expect(find.byIcon(Icons.hourglass_empty), findsOneWidget);
    });

    test('7. FarmerForecast model serialization preserves 3-tier fields safely', () {
      final json = {
        'panchayat_name': 'Dindori',
        'block_name': 'Dindori',
        'district_name': 'Nashik',
        'forecast_date': '2026-09-12',
        'rainfall_mm': 35.0,
        'rainfall_category': 'Moderate rainfall',
        'severity': 'MODERATE',
        'advisory_status': 'APPROVED',
        'language': 'en',
        'available_languages': ['en', 'mr', 'hi'],
        'summary': 'Moderate Rainfall Alert',
        'what_is_happening': '35.0 mm moderate rainfall predicted.',
        'why_it_matters': 'Protects vegetative onion crops.',
        'recommended_actions': ['Drain excess water.', 'Stop spraying.'],
        'timing': 'Next 24 hours',
        'warnings': ['Avoid water stagnation.'],
        'advisory_version': 1,
        'approved_at': '2026-09-12T10:00:00Z',
      };

      final forecast = FarmerForecast.fromJson(json);

      expect(forecast.panchayatName, equals('Dindori'));
      expect(forecast.rainfallMm, equals(35.0));
      expect(forecast.isApproved, isTrue);
      expect(forecast.summary, equals('Moderate Rainfall Alert'));
      expect(forecast.whatIsHappening, equals('35.0 mm moderate rainfall predicted.'));
      expect(forecast.whyItMatters, equals('Protects vegetative onion crops.'));
      expect(forecast.recommendedActions.length, equals(2));
      expect(forecast.timing, equals('Next 24 hours'));
      expect(forecast.warnings.first, equals('Avoid water stagnation.'));
      expect(forecast.advisoryVersion, equals(1));
      expect(forecast.approvedAt, equals('2026-09-12T10:00:00Z'));
    });
  });
}
