import '../api/farmer_api_client.dart';
import '../models/farmer_forecast.dart';
import '../models/panchayat_item.dart';
import '../models/hierarchy_models.dart';

/// Repository layer mediating weather forecast & advisory data retrieval for farmers.
class FarmerRepository {
  final FarmerApiClient _apiClient;

  FarmerRepository({FarmerApiClient? apiClient})
      : _apiClient = apiClient ?? FarmerApiClient();

  /// Static list of pilot Nashik Panchayats for offline resilience
  static final List<PanchayatItem> fallbackPanchayats = [
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
    PanchayatItem(
      panchayatId: 1008,
      lgdCode: 182604,
      panchayatName: 'Mulher',
      blockName: 'Baglan',
      districtName: 'Nashik',
      latitude: 20.7512,
      longitude: 74.0321,
      elevationM: 720.0,
    ),
    PanchayatItem(
      panchayatId: 1005,
      lgdCode: 182601,
      panchayatName: 'Ambasan',
      blockName: 'Baglan',
      districtName: 'Nashik',
      latitude: 20.7121,
      longitude: 74.3659,
      elevationM: 565.0,
    ),
  ];

  /// Retrieve available Gram Panchayats from live backend API with fallback
  Future<List<PanchayatItem>> getPanchayats(
      {String? search, String? blockName}) async {
    final Map<String, String> queryParams = {
      'page': '1',
      'page_size': '50',
    };
    if (search != null && search.isNotEmpty) {
      queryParams['search'] = search;
    }
    if (blockName != null && blockName.isNotEmpty) {
      queryParams['block_name'] = blockName;
    }

    try {
      final data =
          await _apiClient.get('/panchayats', queryParams: queryParams);
      if (data is Map && data['items'] is List) {
        final List<dynamic> rawItems = data['items'];
        final items = rawItems
            .map((e) => PanchayatItem.fromJson(e as Map<String, dynamic>))
            .toList();
        if (items.isNotEmpty) return items;
      }
    } catch (_) {
      // Graceful fallback to pilot records during local testing or network offline
    }
    return fallbackPanchayats;
  }

  /// Retrieve all administrative districts with server-side pagination and search
  Future<DistrictPagination> getDistricts({
    int page = 1,
    int pageSize = 20,
    String? search,
  }) async {
    final Map<String, String> queryParams = {
      'page': page.toString(),
      'page_size': pageSize.toString(),
    };
    if (search != null && search.trim().isNotEmpty) {
      queryParams['search'] = search.trim();
    }

    try {
      final data = await _apiClient.get('/districts', queryParams: queryParams);
      if (data is Map<String, dynamic>) {
        return DistrictPagination.fromJson(data);
      } else if (data is List) {
        final items = data
            .map((e) => DistrictItem.fromJson(e as Map<String, dynamic>))
            .toList();
        return DistrictPagination(
          total: items.length,
          page: page,
          pageSize: pageSize,
          totalPages: 1,
          items: items,
        );
      }
    } catch (_) {
      rethrow;
    }
    throw FarmerApiException('Invalid response format for districts');
  }

  /// Retrieve all blocks within a district with server-side pagination and search
  Future<BlockPagination> getDistrictBlocks(
    int districtId, {
    int page = 1,
    int pageSize = 20,
    String? search,
  }) async {
    final Map<String, String> queryParams = {
      'page': page.toString(),
      'page_size': pageSize.toString(),
    };
    if (search != null && search.trim().isNotEmpty) {
      queryParams['search'] = search.trim();
    }

    try {
      final data = await _apiClient.get('/districts/$districtId/blocks',
          queryParams: queryParams);
      if (data is Map<String, dynamic>) {
        return BlockPagination.fromJson(data);
      } else if (data is List) {
        final items = data
            .map((e) => BlockItem.fromJson(e as Map<String, dynamic>))
            .toList();
        return BlockPagination(
          total: items.length,
          page: page,
          pageSize: pageSize,
          totalPages: 1,
          items: items,
        );
      }
    } catch (_) {
      rethrow;
    }
    throw FarmerApiException('Invalid response format for blocks');
  }

  /// Retrieve Panchayats within a block with server-side search and pagination
  Future<PanchayatPagination> getBlockPanchayats(
    int blockId, {
    int page = 1,
    int pageSize = 50,
    String? search,
    String? blockName,
    String? districtName,
  }) async {
    final Map<String, String> queryParams = {
      'page': page.toString(),
      'page_size': pageSize.toString(),
    };
    if (search != null && search.trim().isNotEmpty) {
      queryParams['search'] = search.trim();
    }

    try {
      final data = await _apiClient.get('/blocks/$blockId/panchayats',
          queryParams: queryParams);
      if (data is Map<String, dynamic>) {
        return PanchayatPagination.fromJson(data,
            blockName: blockName, districtName: districtName);
      }
    } catch (_) {
      rethrow;
    }
    throw FarmerApiException('Invalid response format for Panchayats');
  }

  /// Retrieve single Panchayat detail by ID (GET /api/v1/panchayats/{id})
  Future<PanchayatItem> getPanchayatById(int panchayatId) async {
    try {
      final data = await _apiClient.get('/panchayats/$panchayatId');
      if (data is Map<String, dynamic>) {
        return PanchayatItem.fromJson(data);
      }
    } catch (_) {
      rethrow;
    }
    throw FarmerApiException(
        'Invalid response format for Panchayat $panchayatId');
  }

  // Aliases conforming to Section 3: API / NETWORK LAYER
  Future<DistrictPagination> listDistricts(
          {int page = 1, int pageSize = 20, String? search}) =>
      getDistricts(page: page, pageSize: pageSize, search: search);

  Future<BlockPagination> listBlocks(int districtId,
          {int page = 1, int pageSize = 20, String? search}) =>
      getDistrictBlocks(districtId,
          page: page, pageSize: pageSize, search: search);

  Future<PanchayatPagination> listPanchayats(int blockId,
          {int page = 1,
          int pageSize = 50,
          String? search,
          String? blockName,
          String? districtName}) =>
      getBlockPanchayats(blockId,
          page: page,
          pageSize: pageSize,
          search: search,
          blockName: blockName,
          districtName: districtName);

  Future<PanchayatItem> getPanchayat(int panchayatId) =>
      getPanchayatById(panchayatId);

  /// Retrieve high-resolution downscaled weather forecast and approved advisory for a Panchayat
  Future<FarmerForecast> getFarmerForecast({
    required int panchayatId,
    String lang = 'en',
    String? forecastDate,
  }) async {
    final Map<String, String> queryParams = {
      'lang': lang,
    };
    if (forecastDate != null && forecastDate.isNotEmpty) {
      queryParams['forecast_date'] = forecastDate;
    }

    try {
      final data = await _apiClient.get('/farmer/panchayat/$panchayatId',
          queryParams: queryParams);
      if (data is Map<String, dynamic>) {
        return FarmerForecast.fromJson(data);
      }
    } catch (e) {
      if (e is FarmerApiException && e.statusCode == 404) {
        // No forecast found in database for this Panchayat/date -> construct clean unapproved forecast
        final matchedP = fallbackPanchayats.firstWhere(
          (p) => p.panchayatId == panchayatId,
          orElse: () => fallbackPanchayats.first,
        );
        return FarmerForecast(
          panchayatName: matchedP.panchayatName,
          blockName: matchedP.blockName,
          districtName: matchedP.districtName,
          forecastDate: forecastDate ?? '2026-09-09',
          rainfallMm: 0.0,
          rainfallCategory: 'No forecast data',
          severity: 'LOW',
          advisoryTitle: null,
          advisoryPoints: const [],
          advisoryStatus: 'NO_APPROVED_ADVISORY',
          language: lang,
          availableLanguages: const ['en', 'mr', 'hi'],
          languageStatus: null,
        );
      }
      rethrow;
    }

    throw FarmerApiException('Invalid response format from weather server');
  }
}
