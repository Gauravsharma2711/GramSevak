import 'dart:async';
import '../models/farmer_preference.dart';
import '../models/panchayat_item.dart';
import '../repositories/farmer_repository.dart';

/// Farmer Personalization & Preferences Service (Phase 6.3).
///
/// Features:
/// - Remembers farmer's preferred Panchayat ID and language
/// - Distinguishes between Preferred Panchayat (saved default) and Contextual GPS Panchayat (temporary detected)
/// - Resilient to offline and rural network failures with local caching
/// - Safe synchronization with FastAPI backend (`/api/v1/farmer/preferences`)
class FarmerPreferencesService {
  final FarmerRepository _repository;
  final String _farmerId;

  FarmerPreferences? _currentPreferences;
  PanchayatItem? _contextualPanchayat;

  // Stream for notifying UI of preference changes
  final _preferencesController = StreamController<FarmerPreferences>.broadcast();
  Stream<FarmerPreferences> get onPreferencesChanged => _preferencesController.stream;

  FarmerPreferencesService({
    FarmerRepository? repository,
    String? farmerId,
    FarmerPreferences? initialPreferences,
  })  : _repository = repository ?? FarmerRepository(),
        _farmerId = farmerId ?? 'farmer_device_pilot_01',
        _currentPreferences = initialPreferences;

  String get farmerId => _farmerId;
  FarmerPreferences? get currentPreferences => _currentPreferences;
  PanchayatItem? get contextualPanchayat => _contextualPanchayat;

  /// Loads saved farmer preferences with local offline fallback and backend sync
  Future<FarmerPreferences> loadPreferences() async {
    if (_currentPreferences != null && _currentPreferences!.hasCompletedSetup) {
      // In the background attempt to sync with backend without blocking UI
      _syncFromBackendSilently();
      return _currentPreferences!;
    }

    try {
      final remotePrefs = await _repository.getFarmerPreferences(farmerId: _farmerId);
      if (remotePrefs != null) {
        _currentPreferences = remotePrefs.copyWith(hasCompletedSetup: true);
        _preferencesController.add(_currentPreferences!);
        return _currentPreferences!;
      }
    } catch (_) {
      // Network offline: fall back to local/default
    }

    // Default unconfigured preferences for first-time farmer
    _currentPreferences ??= FarmerPreferences.defaultPreferences(
      farmerId: _farmerId,
      defaultPanchayatId: 1001,
      defaultLang: 'en',
    );
    return _currentPreferences!;
  }

  Future<void> _syncFromBackendSilently() async {
    try {
      final remotePrefs = await _repository.getFarmerPreferences(farmerId: _farmerId);
      if (remotePrefs != null) {
        _currentPreferences = remotePrefs.copyWith(hasCompletedSetup: true);
        _preferencesController.add(_currentPreferences!);
      }
    } catch (_) {}
  }

  /// Saves the preferred Panchayat and language locally and syncs to backend
  Future<FarmerPreferences> savePreferences({
    required int panchayatId,
    required String language,
    String? panchayatName,
    String? blockName,
    String? districtName,
  }) async {
    // 1. Immediately update local state for instant, offline-first UI response
    final resolvedPanchayatName = panchayatName ?? _currentPreferences?.panchayatName ?? 'Ajmer Saundane';
    final resolvedBlockName = blockName ?? _currentPreferences?.blockName ?? 'Baglan';
    final resolvedDistrictName = districtName ?? _currentPreferences?.districtName ?? 'Nashik';

    final updated = FarmerPreferences(
      farmerId: _farmerId,
      panchayatId: panchayatId,
      preferredLanguage: language,
      panchayatName: resolvedPanchayatName,
      blockName: resolvedBlockName,
      districtName: resolvedDistrictName,
      updatedAt: DateTime.now(),
      hasCompletedSetup: true,
    );

    _currentPreferences = updated;
    _preferencesController.add(updated);

    // 2. Synchronize with backend
    try {
      final savedRemote = await _repository.updateFarmerPreferences(
        farmerId: _farmerId,
        panchayatId: panchayatId,
        language: language,
      );
      _currentPreferences = savedRemote.copyWith(hasCompletedSetup: true);
      _preferencesController.add(_currentPreferences!);
      return _currentPreferences!;
    } catch (_) {
      // If server unreachable, local state remains authoritative for rural offline use
      return updated;
    }
  }

  /// Sets contextual GPS-detected Panchayat without modifying the preferred default
  void setContextualPanchayat(PanchayatItem? detectedPanchayat) {
    _contextualPanchayat = detectedPanchayat;
  }

  /// Clears temporary contextual location
  void clearContextualPanchayat() {
    _contextualPanchayat = null;
  }

  /// Resets setup state (e.g. for re-testing onboarding)
  void clearPreferences() {
    _currentPreferences = FarmerPreferences.defaultPreferences(farmerId: _farmerId);
    _contextualPanchayat = null;
  }

  void dispose() {
    _preferencesController.close();
  }
}
