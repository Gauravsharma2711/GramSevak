import 'dart:async';
import 'package:flutter/material.dart';
import 'models/farmer_forecast.dart';
import 'models/panchayat_item.dart';
import 'models/notification_item.dart';
import 'repositories/farmer_repository.dart';
import 'services/farmer_notification_service.dart';
import 'services/farmer_preferences_service.dart';
import 'services/device_location_service.dart';
import 'theme/app_theme.dart';
import 'l10n/app_localizations.dart';
import 'widgets/farmer_scaffold.dart';
import 'widgets/panchayat_picker_sheet.dart';
import 'widgets/loading_state.dart';
import 'widgets/error_state.dart';
import 'screens/home_forecast_screen.dart';
import 'screens/forecast_detail_screen.dart';
import 'screens/advisory_detail_screen.dart';
import 'screens/farm_profile_screen.dart';
import 'screens/onboarding_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const GramSevakFarmerApp());
}

class GramSevakFarmerApp extends StatefulWidget {
  final bool showOnboardingInitially;
  final FarmerRepository? repository;
  final FarmerNotificationService? notificationService;
  final FarmerPreferencesService? preferencesService;
  final DeviceLocationService? locationService;

  const GramSevakFarmerApp({
    super.key,
    this.showOnboardingInitially = false,
    this.repository,
    this.notificationService,
    this.preferencesService,
    this.locationService,
  });

  @override
  State<GramSevakFarmerApp> createState() => _GramSevakFarmerAppState();
}

class _GramSevakFarmerAppState extends State<GramSevakFarmerApp> {
  Locale _locale = const Locale('en');

  void setLocale(String langCode) {
    setState(() {
      _locale = Locale(langCode);
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GramSevak — Farmer Advisory',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      locale: _locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      home: FarmerAppMainScreen(
        showOnboardingInitially: widget.showOnboardingInitially,
        onGlobalLanguageChanged: setLocale,
        repository: widget.repository,
        notificationService: widget.notificationService,
        preferencesService: widget.preferencesService,
        locationService: widget.locationService,
      ),
    );
  }
}

class FarmerAppMainScreen extends StatefulWidget {
  final bool showOnboardingInitially;
  final Function(String)? onGlobalLanguageChanged;
  final FarmerRepository? repository;
  final FarmerNotificationService? notificationService;
  final FarmerPreferencesService? preferencesService;
  final DeviceLocationService? locationService;

  const FarmerAppMainScreen({
    super.key,
    this.showOnboardingInitially = false,
    this.onGlobalLanguageChanged,
    this.repository,
    this.notificationService,
    this.preferencesService,
    this.locationService,
  });

  @override
  State<FarmerAppMainScreen> createState() => _FarmerAppMainScreenState();
}

class _FarmerAppMainScreenState extends State<FarmerAppMainScreen> {
  late final FarmerRepository _repository;
  late final FarmerNotificationService _notificationService;
  late final FarmerPreferencesService _preferencesService;
  late final DeviceLocationService _locationService;

  late bool _showOnboarding;
  int _selectedNavIndex = 0;
  String _selectedLang = 'en';
  int _selectedPanchayatId = 1001; // Pilot Village: Ajmer Saundane (Baglan)
  List<PanchayatItem> _panchayats = [];
  FarmerForecast? _forecast;
  List<FarmerNotification> _panchayatAlerts = [];
  PanchayatItem? _contextualPanchayat;
  bool _loading = true;
  String? _errorMessage;

  StreamSubscription<FarmerNotification>? _foregroundSub;
  StreamSubscription<FarmerNotification>? _openedSub;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? FarmerRepository();
    _notificationService = widget.notificationService ??
        FarmerNotificationService(repository: _repository);
    _preferencesService = widget.preferencesService ??
        FarmerPreferencesService(repository: _repository);
    _locationService = widget.locationService ?? DefaultDeviceLocationService();
    _showOnboarding = widget.showOnboardingInitially;
    _initNotifications();
    _loadInitialData();
  }

  void _initNotifications() {
    _foregroundSub =
        _notificationService.onForegroundNotification.listen((notification) {
      if (mounted) {
        setState(() {
          _panchayatAlerts.removeWhere((a) => a.eventId == notification.eventId);
          _panchayatAlerts.insert(0, notification);
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '${notification.title}: ${notification.message}',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            behavior: SnackBarBehavior.floating,
            backgroundColor: notification.severity == 'HIGH'
                ? const Color(0xFFB91C1C)
                : const Color(0xFFB45309),
            action: SnackBarAction(
              label: 'View',
              textColor: Colors.white,
              onPressed: () {
                setState(() => _selectedNavIndex = 2);
              },
            ),
          ),
        );
      }
    });

    _openedSub =
        _notificationService.onNotificationOpened.listen((notification) {
      if (mounted) {
        if (notification.panchayatId > 0 &&
            notification.panchayatId != _selectedPanchayatId) {
          setState(() {
            _selectedPanchayatId = notification.panchayatId;
            _selectedNavIndex = 2;
          });
          _reloadForecast();
        } else {
          setState(() => _selectedNavIndex = 2);
        }
      }
    });

    _syncDeviceNotifications();
  }

  Future<void> _syncDeviceNotifications() async {
    await _notificationService.requestPermission(grant: true);
    await _notificationService.syncDeviceToken(
      panchayatId: _selectedPanchayatId,
      lang: _selectedLang,
    );
  }

  @override
  void dispose() {
    _foregroundSub?.cancel();
    _openedSub?.cancel();
    super.dispose();
  }

  Future<void> _loadInitialData() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      // 1. Load preferences
      final prefs = await _preferencesService.loadPreferences();
      _selectedPanchayatId = prefs.panchayatId;
      _selectedLang = prefs.preferredLanguage;
      widget.onGlobalLanguageChanged?.call(_selectedLang);

      if (widget.showOnboardingInitially) {
        _showOnboarding = true;
      } else {
        _showOnboarding = !prefs.hasCompletedSetup;
      }

      // 2. Fetch panchayats, forecast, and alerts
      final panchayats = await _repository.getPanchayats();
      final forecast = await _repository.getFarmerForecast(
        panchayatId: _selectedPanchayatId,
        lang: _selectedLang,
      );
      final alerts = await _repository.getPanchayatAlerts(
        panchayatId: _selectedPanchayatId,
      );
      if (mounted) {
        setState(() {
          _panchayats = panchayats;
          _forecast = forecast;
          _panchayatAlerts = alerts;
          _loading = false;
        });
      }

      // 3. Optional contextual GPS detection (if returning farmer)
      if (!_showOnboarding) {
        _checkContextualGpsLocation();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _errorMessage =
              'Unable to connect to weather advisory service. Please check connection and try again.';
        });
      }
    }
  }

  Future<void> _checkContextualGpsLocation() async {
    try {
      final enabled = await _locationService.isLocationServiceEnabled();
      if (!enabled) return;

      final permission = await _locationService.checkPermission();
      if (permission != DeviceLocationPermission.granted) return;

      final coords = await _locationService.getCurrentCoordinates();
      if (coords == null) return;

      final result = await _repository.resolvePanchayatByLocation(
        latitude: coords.latitude,
        longitude: coords.longitude,
        gpsAccuracyMeters: coords.accuracyMeters,
      );

      if (result.matched && result.panchayat != null) {
        final detected = result.panchayat!.toPanchayatItem();
        // If detected differs from selected preferred Panchayat, show contextual banner
        if (detected.panchayatId != _selectedPanchayatId && mounted) {
          setState(() {
            _contextualPanchayat = detected;
          });
        }
      }
    } catch (_) {
      // Fail silently without disrupting preferred Panchayat experience
    }
  }

  Future<void> _reloadForecast() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final forecast = await _repository.getFarmerForecast(
        panchayatId: _selectedPanchayatId,
        lang: _selectedLang,
      );
      final alerts = await _repository.getPanchayatAlerts(
        panchayatId: _selectedPanchayatId,
      );
      _syncDeviceNotifications();
      if (mounted) {
        setState(() {
          _forecast = forecast;
          _panchayatAlerts = alerts;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _errorMessage = 'Unable to refresh forecast data.';
        });
      }
    }
  }

  void _onAcceptContextualPanchayat() async {
    if (_contextualPanchayat == null) return;
    final chosen = _contextualPanchayat!;
    setState(() {
      _selectedPanchayatId = chosen.panchayatId;
      _contextualPanchayat = null;
      if (!_panchayats.any((p) => p.panchayatId == chosen.panchayatId)) {
        _panchayats.insert(0, chosen);
      }
    });
    await _preferencesService.savePreferences(
      panchayatId: chosen.panchayatId,
      language: _selectedLang,
      panchayatName: chosen.panchayatName,
      blockName: chosen.blockName,
      districtName: chosen.districtName,
    );
    _reloadForecast();
  }

  void _onDismissContextualPanchayat() {
    setState(() {
      _contextualPanchayat = null;
    });
  }

  void _onLanguageChanged(String newLang) async {
    setState(() => _selectedLang = newLang);
    widget.onGlobalLanguageChanged?.call(newLang);
    await _preferencesService.savePreferences(
      panchayatId: _selectedPanchayatId,
      language: newLang,
    );
    _reloadForecast();
  }

  void _openPanchayatPicker() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => PanchayatPickerSheet(
        panchayats: _panchayats.isNotEmpty
            ? _panchayats
            : FarmerRepository.fallbackPanchayats,
        selectedPanchayatId: _selectedPanchayatId,
        onSelect: (panchayat) async {
          setState(() {
            _selectedPanchayatId = panchayat.panchayatId;
            _contextualPanchayat = null;
            if (!_panchayats
                .any((p) => p.panchayatId == panchayat.panchayatId)) {
              _panchayats.insert(0, panchayat);
            }
          });
          await _preferencesService.savePreferences(
            panchayatId: panchayat.panchayatId,
            language: _selectedLang,
            panchayatName: panchayat.panchayatName,
            blockName: panchayat.blockName,
            districtName: panchayat.districtName,
          );
          _reloadForecast();
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_showOnboarding) {
      return FarmerOnboardingScreen(
        panchayats: _panchayats.isNotEmpty
            ? _panchayats
            : FarmerRepository.fallbackPanchayats,
        initialPanchayatId: _selectedPanchayatId,
        currentLang: _selectedLang,
        onLanguageChanged: _onLanguageChanged,
        onCompleteOnboarding: (panchayat) async {
          setState(() {
            _showOnboarding = false;
            _selectedPanchayatId = panchayat.panchayatId;
            _contextualPanchayat = null;
            if (!_panchayats.any((p) => p.panchayatId == panchayat.panchayatId)) {
              _panchayats.insert(0, panchayat);
            }
          });
          await _preferencesService.savePreferences(
            panchayatId: panchayat.panchayatId,
            language: _selectedLang,
            panchayatName: panchayat.panchayatName,
            blockName: panchayat.blockName,
            districtName: panchayat.districtName,
          );
          _reloadForecast();
        },
      );
    }

    final currentP = _panchayats.firstWhere(
      (p) => p.panchayatId == _selectedPanchayatId,
      orElse: () => _panchayats.isNotEmpty
          ? _panchayats.first
          : FarmerRepository.fallbackPanchayats.first,
    );

    return FarmerScaffold(
      title: 'GramSevak',
      selectedPanchayatName: currentP.panchayatName,
      currentLang: _selectedLang,
      onLanguageChanged: _onLanguageChanged,
      onSelectPanchayat: _openPanchayatPicker,
      selectedNavIndex: _selectedNavIndex,
      onNavIndexChanged: (index) {
        setState(() => _selectedNavIndex = index);
      },
      body: _buildCurrentBody(currentP),
    );
  }

  Widget _buildCurrentBody(PanchayatItem currentP) {
    if (_loading && _forecast == null) {
      return const FarmerLoadingState();
    }

    if (_errorMessage != null && _forecast == null) {
      return FarmerErrorState(
        message: _errorMessage!,
        onRetry: _loadInitialData,
      );
    }

    final activeForecast = _forecast ??
        FarmerForecast(
          panchayatName: currentP.panchayatName,
          blockName: currentP.blockName,
          districtName: currentP.districtName,
          forecastDate: '2026-09-09',
          rainfallMm: 0.0,
          rainfallCategory: 'No rainfall',
          severity: 'LOW',
          advisoryTitle: null,
          advisoryPoints: const [],
          advisoryStatus: 'NO_APPROVED_ADVISORY',
          language: _selectedLang,
          availableLanguages: const ['en', 'mr', 'hi'],
          languageStatus: null,
        );

    switch (_selectedNavIndex) {
      case 0:
        return HomeForecastScreen(
          forecast: activeForecast,
          onRefresh: _reloadForecast,
          onSwitchPanchayat: _openPanchayatPicker,
          alerts: _panchayatAlerts,
          contextualPanchayat: _contextualPanchayat,
          onAcceptContextualPanchayat: _onAcceptContextualPanchayat,
          onDismissContextualPanchayat: _onDismissContextualPanchayat,
          onViewForecastDetails: () {
            setState(() => _selectedNavIndex = 1);
          },
          onViewAdvisoryDetails: () {
            setState(() => _selectedNavIndex = 2);
          },
        );
      case 1:
        return ForecastDetailScreen(
          forecast: activeForecast,
          onRefresh: _reloadForecast,
          onSwitchPanchayat: _openPanchayatPicker,
        );
      case 2:
        return AdvisoryDetailScreen(
          forecast: activeForecast,
          onRefresh: _reloadForecast,
          currentLang: _selectedLang,
          onLanguageChanged: _onLanguageChanged,
        );
      case 3:
      default:
        return FarmProfileScreen(
          forecast: activeForecast,
          currentPanchayat: currentP,
          onChangePanchayat: _openPanchayatPicker,
          currentLang: _selectedLang,
          onLanguageChanged: _onLanguageChanged,
          onOpenOnboarding: () {
            setState(() => _showOnboarding = true);
          },
        );
    }
  }
}

