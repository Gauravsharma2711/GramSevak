import 'package:flutter/material.dart';
import 'models/farmer_forecast.dart';
import 'models/panchayat_item.dart';
import 'repositories/farmer_repository.dart';
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

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const GramSevakFarmerApp());
}

class GramSevakFarmerApp extends StatefulWidget {
  const GramSevakFarmerApp({super.key});

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
        onGlobalLanguageChanged: setLocale,
      ),
    );
  }
}

class FarmerAppMainScreen extends StatefulWidget {
  final Function(String)? onGlobalLanguageChanged;

  const FarmerAppMainScreen({
    super.key,
    this.onGlobalLanguageChanged,
  });

  @override
  State<FarmerAppMainScreen> createState() => _FarmerAppMainScreenState();
}

class _FarmerAppMainScreenState extends State<FarmerAppMainScreen> {
  final FarmerRepository _repository = FarmerRepository();

  int _selectedNavIndex = 0;
  String _selectedLang = 'en';
  int _selectedPanchayatId = 1001; // Pilot Village: Ajmer Saundane (Baglan)
  List<PanchayatItem> _panchayats = [];
  FarmerForecast? _forecast;
  bool _loading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadInitialData();
  }

  Future<void> _loadInitialData() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final panchayats = await _repository.getPanchayats();
      final forecast = await _repository.getFarmerForecast(
        panchayatId: _selectedPanchayatId,
        lang: _selectedLang,
      );
      if (mounted) {
        setState(() {
          _panchayats = panchayats;
          _forecast = forecast;
          _loading = false;
        });
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
      if (mounted) {
        setState(() {
          _forecast = forecast;
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

  void _onLanguageChanged(String newLang) {
    setState(() => _selectedLang = newLang);
    widget.onGlobalLanguageChanged?.call(newLang);
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
        onSelect: (panchayat) {
          setState(() {
            _selectedPanchayatId = panchayat.panchayatId;
            if (!_panchayats
                .any((p) => p.panchayatId == panchayat.panchayatId)) {
              _panchayats.insert(0, panchayat);
            }
          });
          _reloadForecast();
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
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
        );
    }
  }
}
