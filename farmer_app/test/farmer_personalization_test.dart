import 'package:flutter_test/flutter_test.dart';

import 'package:farmer_app/main.dart';
import 'package:farmer_app/models/farmer_forecast.dart';
import 'package:farmer_app/models/panchayat_item.dart';
import 'package:farmer_app/models/location_resolution.dart';
import 'package:farmer_app/models/farmer_preference.dart';
import 'package:farmer_app/models/notification_item.dart';
import 'package:farmer_app/repositories/farmer_repository.dart';
import 'package:farmer_app/services/farmer_preferences_service.dart';
import 'package:farmer_app/services/device_location_service.dart';

// ---------------------------------------------------------------------------
// Stubs for Phase 6.3 Personalization Testing
// ---------------------------------------------------------------------------

class _StubFarmerRepository extends FarmerRepository {
  FarmerPreferences? savedPreferences;
  int updateCallCount = 0;
  bool shouldFailNetwork = false;

  final List<PanchayatItem> mockPanchayats = [
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
      lgdCode: 182598,
      panchayatName: 'Akhatwade',
      blockName: 'Baglan',
      districtName: 'Nashik',
      latitude: 20.6908,
      longitude: 74.2045,
      elevationM: 595.0,
    ),
  ];

  @override
  Future<List<PanchayatItem>> getPanchayats({String? search, String? blockName}) async {
    return mockPanchayats;
  }

  @override
  Future<FarmerForecast> getFarmerForecast({
    required int panchayatId,
    String lang = 'en',
    String? forecastDate,
  }) async {
    final p = mockPanchayats.firstWhere(
      (m) => m.panchayatId == panchayatId,
      orElse: () => mockPanchayats.first,
    );
    return FarmerForecast(
      panchayatName: p.panchayatName,
      blockName: p.blockName,
      districtName: p.districtName,
      forecastDate: '2026-09-09',
      rainfallMm: 12.5,
      rainfallCategory: 'Light rain',
      severity: 'LOW',
      advisoryTitle: 'Verified Advisory for ${p.panchayatName}',
      advisoryPoints: ['Irrigate lightly in the morning'],
      advisoryStatus: 'APPROVED',
      language: lang,
      availableLanguages: const ['en', 'mr', 'hi'],
      languageStatus: 'VERIFIED_PRIMARY',
    );
  }

  @override
  Future<List<FarmerNotification>> getPanchayatAlerts({
    required int panchayatId,
    int limit = 10,
  }) async {
    return [];
  }

  @override
  Future<FarmerPreferences?> getFarmerPreferences({required String farmerId}) async {
    if (shouldFailNetwork) throw Exception('Network offline');
    return savedPreferences;
  }

  @override
  Future<FarmerPreferences> updateFarmerPreferences({
    required String farmerId,
    required int panchayatId,
    required String language,
  }) async {
    updateCallCount++;
    if (shouldFailNetwork) throw Exception('Network offline');

    final p = mockPanchayats.firstWhere(
      (m) => m.panchayatId == panchayatId,
      orElse: () => mockPanchayats.first,
    );
    savedPreferences = FarmerPreferences(
      farmerId: farmerId,
      panchayatId: panchayatId,
      preferredLanguage: language,
      panchayatName: p.panchayatName,
      blockName: p.blockName,
      districtName: p.districtName,
      updatedAt: DateTime.now(),
      hasCompletedSetup: true,
    );
    return savedPreferences!;
  }

  @override
  Future<bool> registerDeviceToken({
    required String deviceToken,
    required int panchayatId,
    String platform = 'android',
    String languagePreference = 'en',
  }) async {
    return true;
  }

  @override
  Future<LocationResolutionResponse> resolvePanchayatByLocation({
    required double latitude,
    required double longitude,
    double? gpsAccuracyMeters,
  }) async {
    // If coords are near Akhatwade (20.6908, 74.2045)
    if ((latitude - 20.6908).abs() < 0.01) {
      return const LocationResolutionResponse(
        matched: true,
        status: LocationResolutionStatus.matched,
        message: 'Successfully resolved',
        panchayat: ResolvedPanchayat(
          id: 1002,
          lgdCode: 182598,
          name: 'Akhatwade',
          blockName: 'Baglan',
          districtName: 'Nashik',
          latitude: 20.6908,
          longitude: 74.2045,
          elevationM: 595.0,
        ),
      );
    }
    // Default to Ajmer Saundane
    return const LocationResolutionResponse(
      matched: true,
      status: LocationResolutionStatus.matched,
      message: 'Successfully resolved',
      panchayat: ResolvedPanchayat(
        id: 1001,
        lgdCode: 182597,
        name: 'Ajmer Saundane',
        blockName: 'Baglan',
        districtName: 'Nashik',
        latitude: 20.6385,
        longitude: 74.1201,
        elevationM: 585.0,
      ),
    );
  }
}

class _StubLocationService implements DeviceLocationService {
  bool serviceEnabled = true;
  DeviceLocationPermission permission = DeviceLocationPermission.granted;
  DeviceCoordinates? coordinates = const DeviceCoordinates(latitude: 20.6385, longitude: 74.1201);

  @override
  Future<bool> isLocationServiceEnabled() async => serviceEnabled;

  @override
  Future<DeviceLocationPermission> checkPermission() async => permission;

  @override
  Future<DeviceLocationPermission> requestPermission() async => permission;

  @override
  Future<DeviceCoordinates?> getCurrentCoordinates() async => coordinates;
}

// ---------------------------------------------------------------------------
// Unit & Widget Tests
// ---------------------------------------------------------------------------

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Phase 6.3 Farmer Personalization Service Tests', () {
    test('Default preferences generated for first-time farmer with hasCompletedSetup = false', () {
      final service = FarmerPreferencesService(farmerId: 'farmer_unit_01');
      final defaults = service.loadPreferences();

      expect(defaults, completion(isA<FarmerPreferences>()));
      defaults.then((p) {
        expect(p.farmerId, 'farmer_unit_01');
        expect(p.hasCompletedSetup, false);
        expect(p.panchayatId, 1001);
        expect(p.preferredLanguage, 'en');
      });
    });

    test('Saving preferences updates local state and marks hasCompletedSetup = true', () async {
      final repo = _StubFarmerRepository();
      final service = FarmerPreferencesService(repository: repo, farmerId: 'farmer_unit_02');

      final saved = await service.savePreferences(
        panchayatId: 1002,
        language: 'mr',
        panchayatName: 'Akhatwade',
        blockName: 'Baglan',
        districtName: 'Nashik',
      );

      expect(saved.hasCompletedSetup, true);
      expect(saved.panchayatId, 1002);
      expect(saved.preferredLanguage, 'mr');
      expect(repo.updateCallCount, 1);
    });

    test('Offline resilience: savePreferences retains local preference when network fails', () async {
      final repo = _StubFarmerRepository()..shouldFailNetwork = true;
      final service = FarmerPreferencesService(repository: repo, farmerId: 'farmer_unit_offline');

      final saved = await service.savePreferences(
        panchayatId: 1002,
        language: 'hi',
        panchayatName: 'Akhatwade',
        blockName: 'Baglan',
        districtName: 'Nashik',
      );

      // Should still succeed locally
      expect(saved.hasCompletedSetup, true);
      expect(saved.panchayatId, 1002);
      expect(saved.preferredLanguage, 'hi');
    });

    test('Contextual GPS detection does NOT overwrite preferred default', () {
      final service = FarmerPreferencesService(farmerId: 'farmer_unit_ctx');
      final detected = PanchayatItem(
        panchayatId: 1008,
        lgdCode: 182604,
        panchayatName: 'Mulher',
        blockName: 'Baglan',
        districtName: 'Nashik',
        latitude: 20.7512,
        longitude: 74.0321,
        elevationM: 720.0,
      );

      service.setContextualPanchayat(detected);
      expect(service.contextualPanchayat?.panchayatId, 1008);
      // Preferred Panchayat remains default (1001)
      expect(service.currentPreferences?.panchayatId ?? 1001, 1001);

      service.clearContextualPanchayat();
      expect(service.contextualPanchayat, isNull);
    });
  });

  group('Phase 6.3 Farmer App Personalization Widget Tests', () {
    testWidgets('First-time farmer sees onboarding setup flow', (tester) async {
      final repo = _StubFarmerRepository();
      final prefService = FarmerPreferencesService(
        repository: repo,
        farmerId: 'new_farmer_01',
        initialPreferences: FarmerPreferences.defaultPreferences(farmerId: 'new_farmer_01'),
      );

      await tester.pumpWidget(
        GramSevakFarmerApp(
          repository: repo,
          preferencesService: prefService,
          showOnboardingInitially: true,
        ),
      );
      await tester.pumpAndSettle();

      // Onboarding title / welcome visual rendered
      expect(find.text('GramSevak'), findsWidgets);
      expect(find.text('Skip'), findsOneWidget);
    });

    testWidgets('Returning farmer opens directly to saved Panchayat without onboarding', (tester) async {
      final repo = _StubFarmerRepository();
      final saved = FarmerPreferences(
        farmerId: 'returning_farmer_01',
        panchayatId: 1002,
        preferredLanguage: 'en',
        panchayatName: 'Akhatwade',
        blockName: 'Baglan',
        districtName: 'Nashik',
        updatedAt: DateTime.now(),
        hasCompletedSetup: true,
      );
      final prefService = FarmerPreferencesService(
        repository: repo,
        farmerId: 'returning_farmer_01',
        initialPreferences: saved,
      );

      await tester.pumpWidget(
        GramSevakFarmerApp(
          repository: repo,
          preferencesService: prefService,
          showOnboardingInitially: false,
        ),
      );
      await tester.pumpAndSettle();

      // Direct to HomeForecastScreen showing Akhatwade
      expect(find.text('Akhatwade'), findsWidgets);
      expect(find.text('Baglan Block, Nashik'), findsOneWidget);
      expect(find.text('Skip'), findsNothing);
    });

    testWidgets('GPS resolves to same Panchayat: runs normally without contextual prompt', (tester) async {
      final repo = _StubFarmerRepository();
      final locService = _StubLocationService()
        ..coordinates = const DeviceCoordinates(latitude: 20.6385, longitude: 74.1201); // Ajmer Saundane

      final saved = FarmerPreferences(
        farmerId: 'farmer_same_gps',
        panchayatId: 1001,
        preferredLanguage: 'en',
        panchayatName: 'Ajmer Saundane',
        blockName: 'Baglan',
        districtName: 'Nashik',
        updatedAt: DateTime.now(),
        hasCompletedSetup: true,
      );
      final prefService = FarmerPreferencesService(
        repository: repo,
        farmerId: 'farmer_same_gps',
        initialPreferences: saved,
      );

      await tester.pumpWidget(
        GramSevakFarmerApp(
          repository: repo,
          preferencesService: prefService,
          locationService: locService,
        ),
      );
      await tester.pumpAndSettle();

      // Should show Ajmer Saundane
      expect(find.text('Ajmer Saundane'), findsWidgets);
      // Contextual switch banner should NOT appear
      expect(find.textContaining('Detected near'), findsNothing);
    });

    testWidgets('GPS resolves to different Panchayat: displays contextual banner without silent overwrite', (tester) async {
      final repo = _StubFarmerRepository();
      // GPS coords near Akhatwade (1002)
      final locService = _StubLocationService()
        ..coordinates = const DeviceCoordinates(latitude: 20.6908, longitude: 74.2045);

      // Preferred Panchayat is Ajmer Saundane (1001)
      final saved = FarmerPreferences(
        farmerId: 'farmer_diff_gps',
        panchayatId: 1001,
        preferredLanguage: 'en',
        panchayatName: 'Ajmer Saundane',
        blockName: 'Baglan',
        districtName: 'Nashik',
        updatedAt: DateTime.now(),
        hasCompletedSetup: true,
      );
      final prefService = FarmerPreferencesService(
        repository: repo,
        farmerId: 'farmer_diff_gps',
        initialPreferences: saved,
      );

      await tester.pumpWidget(
        GramSevakFarmerApp(
          repository: repo,
          preferencesService: prefService,
          locationService: locService,
        ),
      );
      await tester.pumpAndSettle();

      // Preferred Panchayat still shown as primary title
      expect(find.text('Ajmer Saundane'), findsWidgets);

      // Contextual banner appears
      expect(find.text('Detected near Akhatwade'), findsOneWidget);
      expect(find.text('Switch'), findsOneWidget);

      // Farmer taps Switch -> context changes to Akhatwade
      await tester.tap(find.text('Switch'));
      await tester.pumpAndSettle();

      expect(find.text('Akhatwade'), findsWidgets);
      expect(find.text('Detected near Akhatwade'), findsNothing);
    });

    testWidgets('GPS denied or disabled retains preferred Panchayat smoothly', (tester) async {
      final repo = _StubFarmerRepository();
      final locService = _StubLocationService()
        ..serviceEnabled = false
        ..permission = DeviceLocationPermission.denied;

      final saved = FarmerPreferences(
        farmerId: 'farmer_denied_gps',
        panchayatId: 1001,
        preferredLanguage: 'en',
        panchayatName: 'Ajmer Saundane',
        blockName: 'Baglan',
        districtName: 'Nashik',
        updatedAt: DateTime.now(),
        hasCompletedSetup: true,
      );
      final prefService = FarmerPreferencesService(
        repository: repo,
        farmerId: 'farmer_denied_gps',
        initialPreferences: saved,
      );

      await tester.pumpWidget(
        GramSevakFarmerApp(
          repository: repo,
          preferencesService: prefService,
          locationService: locService,
        ),
      );
      await tester.pumpAndSettle();

      // Continues normally with Ajmer Saundane
      expect(find.text('Ajmer Saundane'), findsWidgets);
      expect(find.textContaining('Detected near'), findsNothing);
    });
  });
}
