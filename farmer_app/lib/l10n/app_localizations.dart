import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// GramSevak Universal Farmer Localization Architecture
/// Provides structured, fallback-safe UI keys for English, Marathi (मराठी), and Hindi (हिन्दी).
/// Advisory content is NOT machine-translated; it is supplied directly by agromet specialists.
class AppLocalizations {
  final Locale locale;

  AppLocalizations(this.locale);

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations) ??
        AppLocalizations(const Locale('en'));
  }

  static const List<Locale> supportedLocales = [
    Locale('en', ''), // English (Primary baseline)
    Locale('mr', ''), // Marathi (मराठी)
    Locale('hi', ''), // Hindi (हिन्दी)
  ];

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  String get _lang => locale.languageCode;

  // Base lookup with guaranteed fallback to English
  String _lookup(String key) {
    if (_lang == 'mr') {
      return _marathiStrings[key] ?? _englishStrings[key] ?? key;
    } else if (_lang == 'hi') {
      return _hindiStrings[key] ?? _englishStrings[key] ?? key;
    }
    return _englishStrings[key] ?? key;
  }

  // --- UI LOCALIZATION KEYS ---

  // Navigation & Branding
  String get appName => 'GramSevak';
  String get navHome => _lookup('nav_home');
  String get navForecast => _lookup('nav_forecast');
  String get navAdvisory => _lookup('nav_advisory');
  String get navProfile => _lookup('nav_profile');

  // Location & Header
  String get changeVillage => _lookup('change_village');
  String get selectVillage => _lookup('select_village');
  String get searchVillage => _lookup('search_village');
  String get registeredVillage => _lookup('registered_village');
  String get preferredLanguage => _lookup('preferred_language');
  String get kisanAccount => _lookup('kisan_account');

  // Weather & Forecast
  String get todaysForecast => _lookup('todays_forecast');
  String get panchayatRainfall => _lookup('panchayat_rainfall');
  String get tomorrow => _lookup('tomorrow');
  String get forecastDetails => _lookup('forecast_details');
  String get view24HourBreakdown => _lookup('view_24h_breakdown');
  String get timeOfDayOutlook => _lookup('time_of_day_outlook');

  // IMD Rainfall Categories
  String get categoryLightRain => _lookup('cat_light_rain');
  String get categoryModerateRain => _lookup('cat_moderate_rain');
  String get categoryHeavyRain => _lookup('cat_heavy_rain');
  String get categoryNoRain => _lookup('cat_no_rain');

  // Agricultural Operations & Windows
  String get operationalGuidance => _lookup('operational_guidance');
  String get sprayingWindow => _lookup('spraying_window');
  String get safeWindow => _lookup('safe_window');
  String get postpone => _lookup('postpone');
  String get rainRiskLevel => _lookup('rain_risk_level');
  String get fieldTillage => _lookup('field_tillage');
  String get fieldDrainage => _lookup('field_drainage');
  String get permitted => _lookup('permitted');
  String get delay => _lookup('delay');
  String get openTrenches => _lookup('open_trenches');
  String get normal => _lookup('normal');

  // Advisory & Officer Review
  String get agriculturalAdvisory => _lookup('agricultural_advisory');
  String get officerVerifiedAdvisory => _lookup('officer_verified_advisory');
  String get advisoryUnderReview => _lookup('advisory_under_review');
  String get advisoryUnderReviewDesc => _lookup('advisory_under_review_desc');
  String get viewAllAdvice => _lookup('view_all_advice');
  String get actionableGuidance => _lookup('actionable_guidance');
  String get verifiedByOfficer => _lookup('verified_by_officer');

  // 3-Tier Advisory Experience
  String get whatIsHappening => _lookup('what_is_happening');
  String get whyItMatters => _lookup('why_it_matters');
  String get whatYouCanDo => _lookup('what_you_can_do');
  String get recommendedAction => _lookup('recommended_action');
  String get timingOutlook => _lookup('timing_outlook');
  String get imdRainfallScale => _lookup('imd_rainfall_scale');
  String get alertHighRain => _lookup('alert_high_rain');
  String get alertHighRainDesc => _lookup('alert_high_rain_desc');
  String get primaryForecastDay => _lookup('primary_forecast_day');
  String get hourlyBreakdown => _lookup('hourly_breakdown');
  String get forecastBasis => _lookup('forecast_basis');

  // Voice Audio & Helpline
  String get audioAdvisory => _lookup('audio_advisory');
  String get tapToListen => _lookup('tap_to_listen');
  String get listenAudio => _lookup('listen_audio');
  String get listeningAudio => _lookup('listening_audio');
  String get kisanCallCentre => _lookup('kisan_call_centre');
  String get kisanCallCentreSub => _lookup('kisan_call_centre_sub');

  // States
  String get tryAgain => _lookup('try_again');
  String get connectionError => _lookup('connection_error');
  String get connectionErrorMessage => _lookup('connection_error_msg');
  String get noForecastTitle => _lookup('no_forecast_title');
  String get noForecastDescription => _lookup('no_forecast_desc');

  // Onboarding
  String get onboardingWelcomeTitle => _lookup('onboarding_welcome_title');
  String get onboardingWelcomeSub => _lookup('onboarding_welcome_sub');
  String get onboardingLocationTitle => _lookup('onboarding_location_title');
  String get onboardingLocationSub => _lookup('onboarding_location_sub');
  String get onboardingSelectionTitle => _lookup('onboarding_selection_title');
  String get onboardingSelectionSub => _lookup('onboarding_selection_sub');
  String get btnChooseVillage => _lookup('btn_choose_village');
  String get btnUseDemoVillage => _lookup('btn_use_demo_village');
  String get btnGetStarted => _lookup('btn_get_started');
  String get btnNext => _lookup('btn_next');
  String get btnSkip => _lookup('btn_skip');

  // --- LOCALIZED DICTIONARIES ---

  static const Map<String, String> _englishStrings = {
    'nav_home': 'Home',
    'nav_forecast': 'Forecast',
    'nav_advisory': 'Advisory',
    'nav_profile': 'Profile',
    'change_village': 'Change Village',
    'select_village': 'Select Your Gram Panchayat',
    'search_village': 'Search village, block, PIN...',
    'registered_village': 'Registered Village',
    'preferred_language': 'Preferred Language / भाषा निवडा',
    'kisan_account': 'Kisan Farm Account',
    'todays_forecast': "Today's / Next Forecast",
    'panchayat_rainfall': 'Panchayat 24-Hour Rainfall',
    'tomorrow': 'Tomorrow',
    'forecast_details': 'Forecast Details',
    'view_24h_breakdown': 'View 24-Hour Breakdown',
    'time_of_day_outlook': 'Time-of-Day Outlook',
    'cat_light_rain': 'Light Rain',
    'cat_moderate_rain': 'Moderate Rain',
    'cat_heavy_rain': 'Heavy Rain',
    'cat_no_rain': 'No Rain / Clear',
    'operational_guidance': 'Field Operational Guidance',
    'spraying_window': 'Spraying Window',
    'safe_window': 'Safe Window',
    'postpone': 'Postpone',
    'rain_risk_level': 'Rain Risk Level',
    'field_tillage': 'Field Tillage',
    'field_drainage': 'Field Drainage',
    'permitted': 'Permitted',
    'delay': 'Delay',
    'open_trenches': 'Open Trenches',
    'normal': 'Normal',
    'agricultural_advisory': 'Agricultural Advisory',
    'officer_verified_advisory': 'Officer Verified Advisory',
    'advisory_under_review': 'Advisory Under Officer Review',
    'advisory_under_review_desc':
        'Our agromet specialist is currently reviewing downscaled forecasts. Verified advice will appear shortly.',
    'view_all_advice': 'View All Advice →',
    'actionable_guidance': 'Actionable Guidance for Farmers:',
    'verified_by_officer':
        'Verified by Agricultural Extension Officer • District Agromet Unit',
    'what_is_happening': 'What is happening?',
    'why_it_matters': 'Why it matters for your field',
    'what_you_can_do': 'What you can do (Recommended Actions)',
    'recommended_action': 'Recommended Action',
    'timing_outlook': 'Timing & Validity',
    'imd_rainfall_scale': 'IMD Rainfall Classification',
    'alert_high_rain': 'Heavy Rain Weather Advisory',
    'alert_high_rain_desc':
        'High rainfall predicted for this Gram Panchayat. Clear drainage channels and secure harvested produce.',
    'primary_forecast_day': 'Primary Forecast',
    'hourly_breakdown': 'Time-of-Day Outlook',
    'forecast_basis': 'Downscaled Weather Basis',
    'audio_advisory': 'Audio Advisory / व्हॉइस सल्ला',
    'tap_to_listen': 'Tap to listen to verified guidance',
    'listen_audio': 'Listen',
    'listening_audio': 'Listening...',
    'kisan_call_centre': 'Kisan Call Centre (Toll Free)',
    'kisan_call_centre_sub':
        'Call 1800-180-1551 for direct agronomist support',
    'try_again': 'Try Again',
    'connection_error': 'Unable to Load Forecast',
    'connection_error_msg':
        'Please check your mobile connection or try refreshing the forecast.',
    'no_forecast_title': 'No Forecast Available',
    'no_forecast_desc':
        'No weather forecast recorded for this village yet.',
    'onboarding_welcome_title': 'Village-Level Weather & Farm Guidance',
    'onboarding_welcome_sub':
        'Accurate micro-climate forecasts downscaled specifically to your Gram Panchayat.',
    'onboarding_location_title': 'Weather Changes Every 5 km',
    'onboarding_location_sub':
        'Mountain ridges and valleys have different rainfall. Choose your exact Gram Panchayat for village-level guidance.',
    'onboarding_selection_title': 'Select Your Gram Panchayat',
    'onboarding_selection_sub':
        'Choose your District, Block, and Village to receive verified agro-advisory.',
    'btn_choose_village': 'Choose Gram Panchayat',
    'btn_use_demo_village': 'Start with Pilot Village (Ajmer Saundane)',
    'btn_get_started': 'Open My Farm Dashboard',
    'btn_next': 'Next',
    'btn_skip': 'Skip',
  };

  static const Map<String, String> _marathiStrings = {
    'nav_home': 'मुख्य',
    'nav_forecast': 'अंदाज',
    'nav_advisory': 'सल्ला',
    'nav_profile': 'प्रोफाइल',
    'change_village': 'गाव बदला',
    'select_village': 'तुमची ग्रामपंचायत निवडा',
    'search_village': 'गाव किंवा तालुका शोधा...',
    'registered_village': 'नोंदणीकृत गाव',
    'preferred_language': 'पसंतीची भाषा निवडा',
    'kisan_account': 'शेतकरी खाते',
    'todays_forecast': 'आजचा / पुढील अंदाज',
    'panchayat_rainfall': 'पंचायत २४-तास पाऊस',
    'tomorrow': 'उद्या',
    'forecast_details': 'हवामान तपशील',
    'view_24h_breakdown': '२४ तासांचा तपशील पहा',
    'time_of_day_outlook': 'वेळेनुसार हवामान अंदाज',
    'cat_light_rain': 'हलका पाऊस',
    'cat_moderate_rain': 'मध्यम पाऊस',
    'cat_heavy_rain': 'मुसळधार पाऊस',
    'cat_no_rain': 'पाऊस नाही / कोरडे',
    'operational_guidance': 'शेती कामांचे नियोजन',
    'spraying_window': 'फवारणी वेळ',
    'safe_window': 'सुरक्षित वेळ',
    'postpone': 'पुढे ढकला',
    'rain_risk_level': 'पाऊस जोखीम पातळी',
    'field_tillage': 'शेती मशागत',
    'field_drainage': 'पाण्याचा निचरा',
    'permitted': 'अनुकूल',
    'delay': 'थांबवा',
    'open_trenches': 'चर खणा',
    'normal': 'सामान्य',
    'agricultural_advisory': 'कृषी सल्ला',
    'officer_verified_advisory': 'अधिकारी प्रमाणित सल्ला',
    'advisory_under_review': 'सल्ला अधिकारी तपासणी अंतर्गत आहे',
    'advisory_under_review_desc':
        'कृषी तज्ज्ञ सध्या हवामान अंदाजाची पडताळणी करत आहेत. प्रमाणित सल्ला लवकरच दिसेल.',
    'view_all_advice': 'सर्व सल्ला पहा →',
    'actionable_guidance': 'शेतकऱ्यांसाठी कृषी सूचना:',
    'verified_by_officer':
        'कृषी विस्तार अधिकाऱ्यांद्वारे प्रमाणित • जिल्हा कृषी हवामान केंद्र',
    'what_is_happening': 'काय घडत आहे?',
    'why_it_matters': 'तुमच्या शेतासाठी हे का महत्त्वाचे आहे',
    'what_you_can_do': 'तुम्ही काय करू शकता (शिफारस केलेल्या कृती)',
    'recommended_action': 'शिफारस केलेली मुख्य कृती',
    'timing_outlook': 'वेळ आणि वैधता',
    'imd_rainfall_scale': 'IMD पर्जन्यमान वर्गीकरण',
    'alert_high_rain': 'मुसळधार पाऊस सतर्कता सूचना',
    'alert_high_rain_desc':
        'या ग्रामपंचायतीसाठी मुसळधार पावसाचा अंदाज आहे. पाण्याचा निचरा करा व काढणी केलेला माल सुरक्षित ठेवा.',
    'primary_forecast_day': 'मुख्य अंदाज',
    'hourly_breakdown': 'वेळेनुसार हवामान अंदाज',
    'forecast_basis': 'हवामान अंदाजाचा आधार',
    'audio_advisory': 'व्हॉइस सल्ला',
    'tap_to_listen': 'प्रमाणित सल्ला ऐकण्यासाठी टॅप करा',
    'listen_audio': 'ऐका',
    'listening_audio': 'सुरू आहे...',
    'kisan_call_centre': 'किसान कॉल सेंटर (टोल फ्री)',
    'kisan_call_centre_sub':
        'थेट कृषी तज्ञांच्या मदतीसाठी १८००-१८०-१५५१ वर कॉल करा',
    'try_again': 'पुन्हा प्रयत्न करा',
    'connection_error': 'अंदाज लोड करणे शक्य नाही',
    'connection_error_msg':
        'कृपया इंटरनेट तपासा किंवा रिफ्रेश करा.',
    'no_forecast_title': 'अंदाज उपलब्ध नाही',
    'no_forecast_desc':
        'या गावासाठी हवामान अंदाज उपलब्ध नाही.',
    'onboarding_welcome_title': 'गाव पातळीवरील हवामान व कृषी सल्ला',
    'onboarding_welcome_sub':
        'तुमच्या शेतासाठी अचूक ग्रामपंचायत पातळीवरील हवामान अंदाज.',
    'onboarding_location_title': 'दर ५ किमीवर हवामान बदलते',
    'onboarding_location_sub':
        'डोंगराळ आणि सपाट भागात पाऊस वेगवेगळा असतो. योग्य निर्णय घेण्यासाठी तुमची ग्रामपंचायत निवडा.',
    'onboarding_selection_title': 'तुमची ग्रामपंचायत निवडा',
    'onboarding_selection_sub':
        'प्रमाणित कृषी सल्ला मिळवण्यासाठी जिल्हा, तालुका आणि गाव निवडा.',
    'btn_choose_village': 'ग्रामपंचायत निवडा',
    'btn_use_demo_village': 'पायलट गावापासून सुरू करा (अजमेर सौंदाणे)',
    'btn_get_started': 'माझे शेत डॅशबोर्ड उघडा',
    'btn_next': 'पुढे',
    'btn_skip': 'वगळा',
  };

  static const Map<String, String> _hindiStrings = {
    'nav_home': 'होम',
    'nav_forecast': 'पूर्वानुमान',
    'nav_advisory': 'सलाह',
    'nav_profile': 'प्रोफाइल',
    'change_village': 'गांव बदलें',
    'select_village': 'अपनी ग्राम पंचायत चुनें',
    'search_village': 'गांव या ब्लॉक खोजें...',
    'registered_village': 'पंजीकृत गांव',
    'preferred_language': 'पसंदीदा भाषा चुनें',
    'kisan_account': 'किसान खाता',
    'todays_forecast': 'आज का / अगला पूर्वानुमान',
    'panchayat_rainfall': 'पंचायत 24-घंटे वर्षा',
    'tomorrow': 'कल',
    'forecast_details': 'पूर्वानुमान विवरण',
    'view_24h_breakdown': '24 घंटे का विवरण देखें',
    'time_of_day_outlook': 'समयानुसार मौसम पूर्वानुमान',
    'cat_light_rain': 'हल्की बारिश',
    'cat_moderate_rain': 'मध्यम बारिश',
    'cat_heavy_rain': 'भारी बारिश',
    'cat_no_rain': 'बारिश नहीं / साफ',
    'operational_guidance': 'कृषि कार्यों का मार्गदर्शन',
    'spraying_window': 'छिड़काव समय',
    'safe_window': 'सुरक्षित समय',
    'postpone': 'स्थगित करें',
    'rain_risk_level': 'वर्षा जोखिम स्तर',
    'field_tillage': 'खेत जुताई',
    'field_drainage': 'जल निकासी',
    'permitted': 'अनुमति',
    'delay': 'टालें',
    'open_trenches': 'नालियां बनाएं',
    'normal': 'सामान्य',
    'agricultural_advisory': 'कृषि सलाह',
    'officer_verified_advisory': 'अधिकारी सत्यापित सलाह',
    'advisory_under_review': 'सलाह अधिकारी समीक्षाधीन है',
    'advisory_under_review_desc':
        'कृषि विशेषज्ञ वर्तमान में मौसम पूर्वानुमान की समीक्षा कर रहे हैं। सत्यापित सलाह जल्द प्रदर्शित होगी।',
    'view_all_advice': 'पूरी सलाह देखें →',
    'actionable_guidance': 'किसानों के लिए आवश्यक निर्देश:',
    'verified_by_officer':
        'कृषि विस्तार अधिकारी द्वारा सत्यापित • जिला कृषि मौसम केंद्र',
    'what_is_happening': 'क्या हो रहा है?',
    'why_it_matters': 'आपके खेत के लिए यह क्यों महत्वपूर्ण है',
    'what_you_can_do': 'आप क्या कर सकते हैं (अनुशंसित कार्रवाई)',
    'recommended_action': 'अनुशंसित मुख्य कार्रवाई',
    'timing_outlook': 'समय और वैधता',
    'imd_rainfall_scale': 'IMD वर्षा वर्गीकरण',
    'alert_high_rain': 'भारी वर्षा मौसम चेतावनी',
    'alert_high_rain_desc':
        'इस ग्राम पंचायत के लिए भारी वर्षा का पूर्वानुमान है। जल निकासी की व्यवस्था करें और फसल सुरक्षित रखें।',
    'primary_forecast_day': 'मुख्य पूर्वानुमान',
    'hourly_breakdown': 'समयानुसार मौसम पूर्वानुमान',
    'forecast_basis': 'मौसम पूर्वानुमान का आधार',
    'audio_advisory': 'ऑडियो सलाह',
    'tap_to_listen': 'सत्यापित सलाह सुनने के लिए टैप करें',
    'listen_audio': 'सुनें',
    'listening_audio': 'चल रहा है...',
    'kisan_call_centre': 'किसान कॉल सेंटर (टोल फ्री)',
    'kisan_call_centre_sub':
        'कृषि विशेषज्ञ सहायता के लिए 1800-180-1551 पर कॉल करें',
    'try_again': 'पुनः प्रयास करें',
    'connection_error': 'पूर्वानुमान लोड करने में असमर्थ',
    'connection_error_msg':
        'कृपया इंटरनेट जांचें या रीफ्रेश करें।',
    'no_forecast_title': 'पूर्वानुमान उपलब्ध नहीं',
    'no_forecast_desc':
        'इस गांव के लिए पूर्वानुमान उपलब्ध नहीं है।',
    'onboarding_welcome_title': 'ग्राम पंचायत स्तर का मौसम व कृषि सलाह',
    'onboarding_welcome_sub':
        'आपके खेत के लिए अति-स्थानीय मौसम पूर्वानुमान और प्रमाणित कृषि सलाह।',
    'onboarding_location_title': 'हर 5 किमी पर मौसम बदलता है',
    'onboarding_location_sub':
        'पहाड़ी और घाटी क्षेत्रों में वर्षा भिन्न होती है। सटीक निर्णयों के लिए अपनी पंचायत चुनें।',
    'onboarding_selection_title': 'अपनी ग्राम पंचायत चुनें',
    'onboarding_selection_sub':
        'प्रमाणित कृषि सलाह प्राप्त करने के लिए जिला, ब्लॉक और गांव चुनें।',
    'btn_choose_village': 'ग्राम पंचायत चुनें',
    'btn_use_demo_village': 'पायलट गांव से शुरू करें (अजमेर सौंदाने)',
    'btn_get_started': 'मेरा खेत डैशबोर्ड खोलें',
    'btn_next': 'आगे बढ़ें',
    'btn_skip': 'छोड़ें',
  };
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) {
    return ['en', 'mr', 'hi'].contains(locale.languageCode);
  }

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(AppLocalizations(locale));
  }

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}
