import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:farmer_app/api/farmer_api_client.dart';
import 'package:farmer_app/models/panchayat_item.dart';
import 'package:farmer_app/models/location_resolution.dart';
import 'package:farmer_app/repositories/farmer_repository.dart';
import 'package:farmer_app/services/device_location_service.dart';
import 'package:farmer_app/widgets/panchayat_picker_sheet.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Phase 6.1 Location Resolution Domain & Service Tests', () {
    test('LocationResolutionResponse parses valid matched payload', () {
      final json = {
        'matched': true,
        'status': 'MATCHED',
        'message': 'Resolved to Ajmer Saundane Gram Panchayat (Baglan, Nashik).',
        'panchayat': {
          'id': 1001,
          'lgd_code': 182597,
          'name': 'Ajmer Saundane',
          'district_id': 1,
          'district_name': 'Nashik',
          'block_id': 4,
          'block_name': 'Baglan',
          'latitude': 20.6385,
          'longitude': 74.1201,
          'elevation_m': 585.0,
        },
        'accuracy_warning': null,
      };

      final response = LocationResolutionResponse.fromJson(json);

      expect(response.matched, isTrue);
      expect(response.status, equals(LocationResolutionStatus.matched));
      expect(response.panchayat, isNotNull);
      expect(response.panchayat!.id, equals(1001));
      expect(response.panchayat!.name, equals('Ajmer Saundane'));
      expect(response.panchayat!.blockName, equals('Baglan'));
      expect(response.panchayat!.districtName, equals('Nashik'));

      final pItem = response.panchayat!.toPanchayatItem();
      expect(pItem.panchayatId, equals(1001));
      expect(pItem.panchayatName, equals('Ajmer Saundane'));
      expect(pItem.blockName, equals('Baglan'));
      expect(pItem.districtName, equals('Nashik'));
      expect(pItem.latitude, equals(20.6385));
    });

    test('LocationResolutionResponse parses noMatch and boundaryUnavailable', () {
      final noMatchJson = {
        'matched': false,
        'status': 'NO_MATCH',
        'message': 'No Gram Panchayat boundary found matching your current location.',
        'panchayat': null,
        'accuracy_warning': null,
      };

      final noMatchRes = LocationResolutionResponse.fromJson(noMatchJson);
      expect(noMatchRes.matched, isFalse);
      expect(noMatchRes.status, equals(LocationResolutionStatus.noMatch));
      expect(noMatchRes.panchayat, isNull);

      final unavailJson = {
        'matched': false,
        'status': 'BOUNDARY_DATA_UNAVAILABLE',
        'message': 'Authoritative Panchayat boundary datasets are currently being ingested.',
        'panchayat': null,
        'accuracy_warning': null,
      };

      final unavailRes = LocationResolutionResponse.fromJson(unavailJson);
      expect(unavailRes.matched, isFalse);
      expect(unavailRes.status, equals(LocationResolutionStatus.boundaryUnavailable));
    });

    test('LocationResolutionResponse parses low accuracy and ambiguous match', () {
      final lowAccJson = {
        'matched': false,
        'status': 'ACCURACY_TOO_LOW',
        'message': 'GPS accuracy is too low to determine village.',
        'panchayat': null,
        'accuracy_warning': 'Low accuracy radius: ±3000m',
      };
      final lowAccRes = LocationResolutionResponse.fromJson(lowAccJson);
      expect(lowAccRes.status, equals(LocationResolutionStatus.accuracyTooLow));
      expect(lowAccRes.accuracyWarning, contains('3000m'));

      final ambigJson = {
        'matched': false,
        'status': 'AMBIGUOUS_MATCH',
        'message': 'Coordinates fall in boundary zone.',
        'panchayat': null,
        'accuracy_warning': 'Multiple adjacent boundaries matched.',
      };
      final ambigRes = LocationResolutionResponse.fromJson(ambigJson);
      expect(ambigRes.status, equals(LocationResolutionStatus.ambiguousMatch));
    });
  });

  group('Phase 6.1 PanchayatPickerSheet Location Integration Tests', () {
    late DefaultDeviceLocationService mockLocationService;

    setUp(() {
      mockLocationService = DefaultDeviceLocationService(
        serviceEnabled: true,
        permission: DeviceLocationPermission.granted,
        initialCoordinates: const DeviceCoordinates(
          latitude: 20.6385,
          longitude: 74.1201,
          accuracyMeters: 15.0,
        ),
      );
    });

    Widget createTestWidget({
      required Function(PanchayatItem) onSelect,
      required FarmerRepository repository,
      DeviceLocationService? locationService,
    }) {
      return MaterialApp(
        home: Scaffold(
          body: PanchayatPickerSheet(
            panchayats: FarmerRepository.fallbackPanchayats,
            selectedPanchayatId: 1001,
            onSelect: onSelect,
            repository: repository,
            locationService: locationService ?? mockLocationService,
          ),
        ),
      );
    }

    testWidgets('1. GPS Quick-Detect button is rendered and GPS is optional',
        (tester) async {
      await tester.pumpWidget(createTestWidget(
        onSelect: (_) {},
        repository: FarmerRepository(),
      ));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('use_gps_location_button')), findsOneWidget);
      expect(find.text('Auto-Detect Village via GPS'), findsOneWidget);
      // Verify manual search and manual District step remain fully visible as fallback
      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('1. District'), findsOneWidget);
    });

    testWidgets('2. Permission denied handled gracefully without crash',
        (tester) async {
      mockLocationService.setPermission(DeviceLocationPermission.denied);

      // Create a service where requesting permission returns denied
      final deniedLocationService = _StubLocationService(
        serviceEnabled: true,
        requestPermissionResult: DeviceLocationPermission.denied,
      );

      await tester.pumpWidget(createTestWidget(
        onSelect: (_) {},
        repository: FarmerRepository(),
        locationService: deniedLocationService,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('use_gps_location_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('gps_feedback_banner')), findsOneWidget);
      expect(
        find.textContaining('Location permission was denied'),
        findsOneWidget,
      );
      // Manual selection remains accessible
      expect(find.text('1. District'), findsOneWidget);
    });

    testWidgets('3. Permanently denied permission handled safely',
        (tester) async {
      final permDeniedService = _StubLocationService(
        serviceEnabled: true,
        requestPermissionResult: DeviceLocationPermission.permanentlyDenied,
      );

      await tester.pumpWidget(createTestWidget(
        onSelect: (_) {},
        repository: FarmerRepository(),
        locationService: permDeniedService,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('use_gps_location_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('gps_feedback_banner')), findsOneWidget);
      expect(
        find.textContaining('permanently denied'),
        findsOneWidget,
      );
    });

    testWidgets('4. GPS disabled handled safely', (tester) async {
      final gpsDisabledService = _StubLocationService(
        serviceEnabled: false,
        requestPermissionResult: DeviceLocationPermission.granted,
      );

      await tester.pumpWidget(createTestWidget(
        onSelect: (_) {},
        repository: FarmerRepository(),
        locationService: gpsDisabledService,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('use_gps_location_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('gps_feedback_banner')), findsOneWidget);
      expect(
        find.textContaining('GPS is turned off'),
        findsOneWidget,
      );
    });

    testWidgets('5. Backend successful resolution selects Panchayat and closes sheet',
        (tester) async {
      PanchayatItem? selectedResult;

      final mockClient = MockClient((request) async {
        if (request.url.path.contains('resolve-panchayat')) {
          return http.Response(
            jsonEncode({
              'matched': true,
              'status': 'MATCHED',
              'message': 'Resolved to Ajmer Saundane Gram Panchayat (Baglan, Nashik).',
              'panchayat': {
                'id': 1001,
                'lgd_code': 182597,
                'name': 'Ajmer Saundane',
                'district_id': 1,
                'district_name': 'Nashik',
                'block_id': 4,
                'block_name': 'Baglan',
                'latitude': 20.6385,
                'longitude': 74.1201,
                'elevation_m': 585.0,
              },
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final repo = FarmerRepository(
        apiClient: FarmerApiClient(httpClient: mockClient),
      );

      await tester.pumpWidget(createTestWidget(
        onSelect: (p) => selectedResult = p,
        repository: repo,
        locationService: mockLocationService,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('use_gps_location_button')));
      await tester.pumpAndSettle();

      expect(selectedResult, isNotNull);
      expect(selectedResult!.panchayatId, equals(1001));
      expect(selectedResult!.panchayatName, equals('Ajmer Saundane'));
      expect(selectedResult!.blockName, equals('Baglan'));
      expect(selectedResult!.districtName, equals('Nashik'));
    });

    testWidgets('6. Backend no-match displays feedback banner and preserves manual picker',
        (tester) async {
      final mockClient = MockClient((request) async {
        if (request.url.path.contains('resolve-panchayat')) {
          return http.Response(
            jsonEncode({
              'matched': false,
              'status': 'BOUNDARY_DATA_UNAVAILABLE',
              'message': 'Authoritative Panchayat boundary datasets are currently being ingested.',
              'panchayat': null,
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final repo = FarmerRepository(
        apiClient: FarmerApiClient(httpClient: mockClient),
      );

      await tester.pumpWidget(createTestWidget(
        onSelect: (_) {},
        repository: repo,
        locationService: mockLocationService,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('use_gps_location_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('gps_feedback_banner')), findsOneWidget);
      expect(
        find.textContaining('datasets are currently being ingested'),
        findsOneWidget,
      );
      // Manual selection remains active
      expect(find.text('1. District'), findsOneWidget);
    });

    testWidgets('7. Backend failure displays safe fallback error', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response('Server Error', 500);
      });

      final repo = FarmerRepository(
        apiClient: FarmerApiClient(httpClient: mockClient),
      );

      await tester.pumpWidget(createTestWidget(
        onSelect: (_) {},
        repository: repo,
        locationService: mockLocationService,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('use_gps_location_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('gps_feedback_banner')), findsOneWidget);
      expect(
        find.textContaining('select your village manually below'),
        findsOneWidget,
      );
    });
  });
}

class _StubLocationService implements DeviceLocationService {
  final bool serviceEnabled;
  final DeviceLocationPermission requestPermissionResult;
  final DeviceCoordinates? coordinates = null;

  _StubLocationService({
    required this.serviceEnabled,
    required this.requestPermissionResult,
  });

  @override
  Future<bool> isLocationServiceEnabled() async => serviceEnabled;

  @override
  Future<DeviceLocationPermission> checkPermission() async =>
      requestPermissionResult;

  @override
  Future<DeviceLocationPermission> requestPermission() async =>
      requestPermissionResult;

  @override
  Future<DeviceCoordinates?> getCurrentCoordinates() async => coordinates;
}
