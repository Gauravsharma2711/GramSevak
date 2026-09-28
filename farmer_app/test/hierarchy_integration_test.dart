import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:farmer_app/api/farmer_api_client.dart';
import 'package:farmer_app/models/hierarchy_models.dart';
import 'package:farmer_app/models/panchayat_item.dart';
import 'package:farmer_app/repositories/farmer_repository.dart';
import 'package:farmer_app/widgets/panchayat_picker_sheet.dart';
import 'package:farmer_app/l10n/app_localizations.dart';

void main() {
  group('1. Hierarchy Model Layer Tests', () {
    test('DistrictItem and DistrictPagination parse backend envelope correctly',
        () {
      final json = {
        'total': 36,
        'page': 1,
        'page_size': 20,
        'total_pages': 2,
        'items': [
          {'id': 1, 'name': 'Nashik', 'code': 'NSK', 'state': 'Maharashtra'},
          {'id': 4, 'name': 'Pune', 'code': 'PUN', 'state': 'Maharashtra'},
        ],
      };

      final paginated = DistrictPagination.fromJson(json);
      expect(paginated.total, 36);
      expect(paginated.page, 1);
      expect(paginated.pageSize, 20);
      expect(paginated.totalPages, 2);
      expect(paginated.items.length, 2);
      expect(paginated.items[0].name, 'Nashik');
      expect(paginated.items[0].code, 'NSK');
      expect(paginated.items[1].name, 'Pune');
    });

    test('BlockItem and BlockPagination parse backend envelope correctly', () {
      final json = {
        'total': 15,
        'page': 1,
        'page_size': 20,
        'total_pages': 1,
        'items': [
          {'id': 1, 'district_id': 1, 'name': 'Baglan', 'code': 'BAG'},
          {'id': 2, 'district_id': 1, 'name': 'Dindori', 'code': 'DIN'},
        ],
      };

      final paginated = BlockPagination.fromJson(json);
      expect(paginated.total, 15);
      expect(paginated.items.length, 2);
      expect(paginated.items[0].name, 'Baglan');
      expect(paginated.items[0].districtId, 1);
      expect(paginated.items[1].name, 'Dindori');
    });

    test(
        'PanchayatItem and PanchayatPagination parse backend envelope correctly',
        () {
      final json = {
        'total': 132,
        'page': 1,
        'page_size': 50,
        'total_pages': 3,
        'items': [
          {
            'id': 1001,
            'lgd_code': 182597,
            'panchayat_code': 'MH-NAS-BAG-001',
            'name': 'Ajmer Saundane',
            'block_id': 1,
            'district_id': 1,
            'latitude': 20.6385,
            'longitude': 74.1201,
            'elevation_m': 585.0,
          },
        ],
      };

      final paginated = PanchayatPagination.fromJson(
        json,
        blockName: 'Baglan',
        districtName: 'Nashik',
      );
      expect(paginated.total, 132);
      expect(paginated.totalPages, 3);
      expect(paginated.items.length, 1);

      final p = paginated.items[0];
      expect(p.panchayatId, 1001);
      expect(p.panchayatName, 'Ajmer Saundane');
      expect(p.lgdCode, 182597);
      expect(p.blockName, 'Baglan');
      expect(p.districtName, 'Nashik');
      expect(p.elevationM, 585.0);
    });

    test('Single Panchayat detail endpoint with nested lineage parses cleanly',
        () {
      final json = {
        'id': 1001,
        'lgd_code': 182597,
        'name': 'Ajmer Saundane',
        'block_id': 1,
        'district_id': 1,
        'latitude': 20.6385,
        'longitude': 74.1201,
        'elevation_m': 585.0,
        'district': {'id': 1, 'name': 'Nashik', 'state': 'Maharashtra'},
        'block': {'id': 1, 'district_id': 1, 'name': 'Baglan'},
      };

      final p = PanchayatItem.fromJson(json);
      expect(p.panchayatId, 1001);
      expect(p.panchayatName, 'Ajmer Saundane');
      expect(p.blockName, 'Baglan');
      expect(p.districtName, 'Nashik');
    });

    test('Models handle missing or malformed fields safely without crashing',
        () {
      final district = DistrictItem.fromJson({});
      expect(district.id, 0);
      expect(district.name, '');

      final block = BlockItem.fromJson({});
      expect(block.id, 0);
      expect(block.name, '');

      final panchayat = PanchayatItem.fromJson({});
      expect(panchayat.panchayatId, 0);
      expect(panchayat.panchayatName, 'Unknown');
      expect(panchayat.blockName, 'Block');
      expect(panchayat.districtName, 'District');
    });
  });

  group('2. Repository Layer Tests with Mock HTTP Client', () {
    test('getDistricts passes pagination & search params and parses response',
        () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, endsWith('/districts'));
        expect(request.url.queryParameters['page'], '2');
        expect(request.url.queryParameters['page_size'], '20');
        expect(request.url.queryParameters['search'], 'Pun');

        final body = jsonEncode({
          'total': 1,
          'page': 2,
          'page_size': 20,
          'total_pages': 2,
          'items': [
            {'id': 4, 'name': 'Pune', 'code': 'PUN', 'state': 'Maharashtra'},
          ],
        });
        return http.Response(body, 200,
            headers: {'content-type': 'application/json'});
      });

      final apiClient = FarmerApiClient(httpClient: mockClient);
      final repo = FarmerRepository(apiClient: apiClient);

      final result =
          await repo.getDistricts(page: 2, pageSize: 20, search: 'Pun');
      expect(result.total, 1);
      expect(result.items.first.name, 'Pune');
    });

    test('getDistrictBlocks scopes query to districtId and parses blocks',
        () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, endsWith('/districts/4/blocks'));
        expect(request.url.queryParameters['page'], '1');
        expect(request.url.queryParameters['search'], 'Hav');

        final body = jsonEncode({
          'total': 1,
          'page': 1,
          'page_size': 20,
          'total_pages': 1,
          'items': [
            {'id': 401, 'district_id': 4, 'name': 'Haveli', 'code': 'HAV'},
          ],
        });
        return http.Response(body, 200,
            headers: {'content-type': 'application/json'});
      });

      final apiClient = FarmerApiClient(httpClient: mockClient);
      final repo = FarmerRepository(apiClient: apiClient);

      final result = await repo.getDistrictBlocks(4, page: 1, search: 'Hav');
      expect(result.total, 1);
      expect(result.items.first.name, 'Haveli');
      expect(result.items.first.districtId, 4);
    });

    test('getBlockPanchayats scopes query to blockId and parses Panchayats',
        () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, endsWith('/blocks/1/panchayats'));
        expect(request.url.queryParameters['page'], '1');
        expect(request.url.queryParameters['page_size'], '50');

        final body = jsonEncode({
          'total': 132,
          'page': 1,
          'page_size': 50,
          'total_pages': 3,
          'items': [
            {
              'id': 1001,
              'lgd_code': 182597,
              'name': 'Ajmer Saundane',
              'block_id': 1,
              'district_id': 1,
              'latitude': 20.6385,
              'longitude': 74.1201,
              'elevation_m': 585.0,
            }
          ],
        });
        return http.Response(body, 200,
            headers: {'content-type': 'application/json'});
      });

      final apiClient = FarmerApiClient(httpClient: mockClient);
      final repo = FarmerRepository(apiClient: apiClient);

      final result = await repo.getBlockPanchayats(1,
          page: 1, pageSize: 50, blockName: 'Baglan', districtName: 'Nashik');
      expect(result.total, 132);
      expect(result.items.first.panchayatName, 'Ajmer Saundane');
    });

    test('getPanchayatById fetches single record correctly', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, endsWith('/panchayats/1001'));
        final body = jsonEncode({
          'id': 1001,
          'lgd_code': 182597,
          'name': 'Ajmer Saundane',
          'block_id': 1,
          'district_id': 1,
          'latitude': 20.6385,
          'longitude': 74.1201,
          'elevation_m': 585.0,
          'block': {'id': 1, 'name': 'Baglan'},
          'district': {'id': 1, 'name': 'Nashik'},
        });
        return http.Response(body, 200,
            headers: {'content-type': 'application/json'});
      });

      final apiClient = FarmerApiClient(httpClient: mockClient);
      final repo = FarmerRepository(apiClient: apiClient);

      final p = await repo.getPanchayatById(1001);
      expect(p.panchayatId, 1001);
      expect(p.panchayatName, 'Ajmer Saundane');
      expect(p.blockName, 'Baglan');
    });

    test('API errors throw FarmerApiException with status code', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
            jsonEncode({'detail': 'Panchayat not found'}), 404);
      });

      final apiClient = FarmerApiClient(httpClient: mockClient);
      final repo = FarmerRepository(apiClient: apiClient);

      expect(
        () async => await repo.getPanchayatById(9999),
        throwsA(isA<FarmerApiException>()
            .having((e) => e.statusCode, 'statusCode', 404)),
      );
    });
  });

  group('3. PanchayatPickerSheet UI & Progressive Flow Tests', () {
    late FarmerRepository mockRepo;

    setUp(() {
      final mockClient = MockClient((request) async {
        final path = request.url.path;

        if (path.endsWith('/districts')) {
          final search = request.url.queryParameters['search'];
          final items = [
            {'id': 1, 'name': 'Nashik', 'state': 'Maharashtra'},
            {'id': 4, 'name': 'Pune', 'state': 'Maharashtra'},
          ]
              .where((d) =>
                  search == null ||
                  d['name']!
                      .toString()
                      .toLowerCase()
                      .contains(search.toLowerCase()))
              .toList();

          return http.Response(
            jsonEncode({
              'total': items.length,
              'page': int.parse(request.url.queryParameters['page'] ?? '1'),
              'page_size': 20,
              'total_pages': 1,
              'items': items,
            }),
            200,
          );
        }

        if (path.contains('/districts/1/blocks')) {
          final items = [
            {'id': 1, 'district_id': 1, 'name': 'Baglan'},
            {'id': 2, 'district_id': 1, 'name': 'Dindori'},
          ];
          return http.Response(
            jsonEncode({
              'total': items.length,
              'page': 1,
              'page_size': 20,
              'total_pages': 1,
              'items': items,
            }),
            200,
          );
        }

        if (path.contains('/districts/4/blocks')) {
          final items = [
            {'id': 401, 'district_id': 4, 'name': 'Haveli'},
          ];
          return http.Response(
            jsonEncode({
              'total': items.length,
              'page': 1,
              'page_size': 20,
              'total_pages': 1,
              'items': items,
            }),
            200,
          );
        }

        if (path.contains('/blocks/1/panchayats')) {
          final items = [
            {
              'id': 1001,
              'lgd_code': 182597,
              'name': 'Ajmer Saundane',
              'block_id': 1,
              'district_id': 1,
              'latitude': 20.6385,
              'longitude': 74.1201,
              'elevation_m': 585.0,
            },
          ];
          return http.Response(
            jsonEncode({
              'total': items.length,
              'page': 1,
              'page_size': 50,
              'total_pages': 1,
              'items': items,
            }),
            200,
          );
        }

        return http.Response('Not Found', 404);
      });

      mockRepo =
          FarmerRepository(apiClient: FarmerApiClient(httpClient: mockClient));
    });

    testWidgets(
        'Full 3-step progressive navigation: District -> Block -> Panchayat -> Select',
        (tester) async {
      PanchayatItem? selectedItem;

      await tester.pumpWidget(
        MaterialApp(
          localizationsDelegates: const [
            AppLocalizations.delegate,
            DefaultMaterialLocalizations.delegate,
            DefaultWidgetsLocalizations.delegate,
          ],
          home: Scaffold(
            body: PanchayatPickerSheet(
              repository: mockRepo,
              onSelect: (p) {
                selectedItem = p;
              },
            ),
          ),
        ),
      );

      // Step 1: District list loads
      await tester.pumpAndSettle();
      expect(find.text('Nashik District'), findsOneWidget);
      expect(find.text('Pune District'), findsOneWidget);

      // Farmer taps Nashik District
      await tester.tap(find.text('Nashik District'));
      await tester.pumpAndSettle();

      // Step 2: Block list for Nashik loads
      expect(find.text('Baglan'), findsOneWidget);
      expect(find.text('Dindori'), findsOneWidget);
      expect(find.text('Haveli'), findsNothing); // Pune blocks are not shown

      // Farmer taps Baglan Block
      await tester.tap(find.text('Baglan'));
      await tester.pumpAndSettle();

      // Step 3: Panchayats for Baglan load
      expect(find.text('Ajmer Saundane'), findsOneWidget);
      expect(find.text('LGD 182597'), findsOneWidget);

      // Farmer taps Ajmer Saundane
      await tester.tap(find.text('Ajmer Saundane'));
      await tester.pumpAndSettle();

      expect(selectedItem, isNotNull);
      expect(selectedItem!.panchayatId, 1001);
      expect(selectedItem!.panchayatName, 'Ajmer Saundane');
    });

    testWidgets(
        'Switching district via breadcrumb resets block and panchayat state',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          localizationsDelegates: const [
            AppLocalizations.delegate,
            DefaultMaterialLocalizations.delegate,
            DefaultWidgetsLocalizations.delegate,
          ],
          home: Scaffold(
            body: PanchayatPickerSheet(
              repository: mockRepo,
              onSelect: (_) {},
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Select Nashik -> Baglan -> Village
      await tester.tap(find.text('Nashik District'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Baglan'));
      await tester.pumpAndSettle();
      expect(find.text('Ajmer Saundane'), findsOneWidget);

      // Tap Step 1 Breadcrumb
      await tester.tap(find.text('1. Nashik'));
      await tester.pumpAndSettle();
      expect(find.text('Nashik District'), findsOneWidget);
      expect(find.text('Pune District'), findsOneWidget);

      // Select Pune District
      await tester.tap(find.text('Pune District'));
      await tester.pumpAndSettle();

      // Verified: Baglan and Ajmer Saundane are cleared, Pune blocks are shown
      expect(find.text('Haveli'), findsOneWidget);
      expect(find.text('Baglan'), findsNothing);
      expect(find.text('Ajmer Saundane'), findsNothing);
    });

    testWidgets('Search input filters districts server-side with debouncing',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          localizationsDelegates: const [
            AppLocalizations.delegate,
            DefaultMaterialLocalizations.delegate,
            DefaultWidgetsLocalizations.delegate,
          ],
          home: Scaffold(
            body: PanchayatPickerSheet(
              repository: mockRepo,
              onSelect: (_) {},
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();
      expect(find.text('Nashik District'), findsOneWidget);
      expect(find.text('Pune District'), findsOneWidget);

      // Enter search 'Pun'
      await tester.enterText(find.byType(TextField), 'Pun');
      await tester.pump(const Duration(milliseconds: 300));
      await tester.pumpAndSettle();

      expect(find.text('Pune District'), findsOneWidget);
      expect(find.text('Nashik District'), findsNothing);
    });

    testWidgets('Error state renders retry button that recovers on success',
        (tester) async {
      bool shouldFail = true;
      final flakyClient = MockClient((request) async {
        if (shouldFail) {
          return http.Response('Server Error', 500);
        }
        return http.Response(
          jsonEncode({
            'total': 1,
            'page': 1,
            'page_size': 20,
            'total_pages': 1,
            'items': [
              {'id': 1, 'name': 'Nashik', 'state': 'Maharashtra'},
            ],
          }),
          200,
        );
      });

      final flakyRepo =
          FarmerRepository(apiClient: FarmerApiClient(httpClient: flakyClient));

      await tester.pumpWidget(
        MaterialApp(
          localizationsDelegates: const [
            AppLocalizations.delegate,
            DefaultMaterialLocalizations.delegate,
            DefaultWidgetsLocalizations.delegate,
          ],
          home: Scaffold(
            body: PanchayatPickerSheet(
              repository: flakyRepo,
              onSelect: (_) {},
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();
      expect(find.text('Unable to load districts.'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);

      // Recover and tap Retry
      shouldFail = false;
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();

      expect(find.text('Nashik District'), findsOneWidget);
      expect(find.text('Unable to load districts.'), findsNothing);
    });
  });
}
