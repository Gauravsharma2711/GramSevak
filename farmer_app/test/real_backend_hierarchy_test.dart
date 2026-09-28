import 'package:flutter_test/flutter_test.dart';
import 'package:farmer_app/api/farmer_api_client.dart';
import 'package:farmer_app/repositories/farmer_repository.dart';

void main() {
  group('Real Backend Hierarchy Integration Verification', () {
    late FarmerRepository repo;

    setUp(() {
      // Configure client pointing to active backend instance on port 7560
      final client = FarmerApiClient(
        baseUrl: 'http://127.0.0.1:7560/api/v1',
        timeoutDuration: const Duration(seconds: 30),
      );
      repo = FarmerRepository(apiClient: client);
    });

    test('1. Loads Districts from real database including Nashik and Pune',
        () async {
      final districts = await repo.getDistricts(page: 1, pageSize: 20);
      expect(districts.total, greaterThanOrEqualTo(2));
      expect(districts.items.any((d) => d.name == 'Nashik'), isTrue);
      expect(districts.items.any((d) => d.name == 'Pune'), isTrue);
    });

    test('2. Loads Blocks for Nashik District (15 blocks)', () async {
      final districts = await repo.getDistricts();
      final nashik = districts.items.firstWhere((d) => d.name == 'Nashik');

      final blocks =
          await repo.getDistrictBlocks(nashik.id, page: 1, pageSize: 20);
      expect(blocks.total, 15);
      expect(blocks.items.any((b) => b.name == 'Baglan'), isTrue);
      expect(blocks.items.every((b) => b.districtId == nashik.id), isTrue);
    });

    test('3. Loads Blocks for Pune District with strict isolation from Nashik',
        () async {
      final districts = await repo.getDistricts();
      final pune = districts.items.firstWhere((d) => d.name == 'Pune');

      final blocks =
          await repo.getDistrictBlocks(pune.id, page: 1, pageSize: 20);
      expect(blocks.total, greaterThanOrEqualTo(10));
      expect(
          blocks.items.any((b) => b.name == 'Haveli' || b.name == 'Ambegaon'),
          isTrue);
      // Ensure no Nashik blocks leak into Pune
      expect(blocks.items.any((b) => b.name == 'Baglan'), isFalse);
    });

    test('4. Loads Baglan Panchayats with server-side pagination (132 total)',
        () async {
      final panchayats =
          await repo.getBlockPanchayats(1, page: 1, pageSize: 50);
      expect(panchayats.total, 132);
      expect(panchayats.totalPages, 3);
      expect(panchayats.items.length, 50);
    });

    test('5. Server-side search on Panchayats matches "Ajme"', () async {
      final searchResult = await repo.getBlockPanchayats(1,
          search: 'Ajme', page: 1, pageSize: 50);
      expect(searchResult.total, greaterThanOrEqualTo(1));
      expect(searchResult.items.first.panchayatName, 'Ajmer Saundane');
    });

    test('6. Single Panchayat detail endpoint resolves full parent lineage',
        () async {
      final p = await repo.getPanchayatById(1001);
      expect(p.panchayatId, 1001);
      expect(p.panchayatName, 'Ajmer Saundane');
      expect(p.blockName, 'Baglan');
      expect(p.districtName, 'Nashik');
    });

    test('7. Downscaled forecast loads for selected Panchayat 1001', () async {
      final forecast = await repo.getFarmerForecast(panchayatId: 1001);
      expect(forecast.panchayatName, 'Ajmer Saundane');
      expect(forecast.blockName, 'Baglan');
      expect(forecast.districtName, 'Nashik');
      expect(forecast.rainfallMm, greaterThanOrEqualTo(0.0));
    });
  });
}
