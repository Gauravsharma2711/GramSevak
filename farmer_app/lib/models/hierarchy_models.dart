import 'panchayat_item.dart';

/// Hierarchical District Model for Farmer App
class DistrictItem {
  final int id;
  final String name;
  final String? code;
  final String state;

  DistrictItem({
    required this.id,
    required this.name,
    this.code,
    required this.state,
  });

  factory DistrictItem.fromJson(Map<String, dynamic> json) {
    return DistrictItem(
      id: json['id'] as int? ?? 0,
      name: json['name'] as String? ?? '',
      code: json['code'] as String?,
      state: json['state'] as String? ?? 'Maharashtra',
    );
  }
}

/// Paginated District response container
class DistrictPagination {
  final int total;
  final int page;
  final int pageSize;
  final int totalPages;
  final List<DistrictItem> items;

  DistrictPagination({
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
    required this.items,
  });

  factory DistrictPagination.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return DistrictPagination(
      total: json['total'] as int? ?? rawItems.length,
      page: json['page'] as int? ?? 1,
      pageSize: json['page_size'] as int? ?? 20,
      totalPages: json['total_pages'] as int? ?? 1,
      items: rawItems
          .map((e) => DistrictItem.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

/// Hierarchical Block Model for Farmer App
class BlockItem {
  final int id;
  final int districtId;
  final String name;
  final String? code;

  BlockItem({
    required this.id,
    required this.districtId,
    required this.name,
    this.code,
  });

  factory BlockItem.fromJson(Map<String, dynamic> json) {
    return BlockItem(
      id: json['id'] as int? ?? 0,
      districtId: json['district_id'] as int? ?? 0,
      name: json['name'] as String? ?? '',
      code: json['code'] as String?,
    );
  }
}

/// Paginated Block response container
class BlockPagination {
  final int total;
  final int page;
  final int pageSize;
  final int totalPages;
  final List<BlockItem> items;

  BlockPagination({
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
    required this.items,
  });

  factory BlockPagination.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return BlockPagination(
      total: json['total'] as int? ?? rawItems.length,
      page: json['page'] as int? ?? 1,
      pageSize: json['page_size'] as int? ?? 20,
      totalPages: json['total_pages'] as int? ?? 1,
      items: rawItems
          .map((e) => BlockItem.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

/// Paginated Panchayat response container
class PanchayatPagination {
  final int total;
  final int page;
  final int pageSize;
  final int totalPages;
  final List<PanchayatItem> items;

  PanchayatPagination({
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
    required this.items,
  });

  factory PanchayatPagination.fromJson(
    Map<String, dynamic> json, {
    String? blockName,
    String? districtName,
  }) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return PanchayatPagination(
      total: json['total'] as int? ?? rawItems.length,
      page: json['page'] as int? ?? 1,
      pageSize: json['page_size'] as int? ?? 50,
      totalPages: json['total_pages'] as int? ?? 1,
      items: rawItems.map((e) {
        final m = e as Map<String, dynamic>;
        return PanchayatItem(
          panchayatId: (m['id'] ?? m['panchayat_id']) as int? ?? 0,
          lgdCode: m['lgd_code'] as int? ?? 0,
          panchayatName:
              (m['name'] ?? m['panchayat_name']) as String? ?? 'Panchayat',
          blockName: blockName ??
              (m['block'] is Map
                  ? m['block']['name']
                  : m['block_name']?.toString()) ??
              'Block',
          districtName: districtName ??
              (m['district'] is Map
                  ? m['district']['name']
                  : m['district_name']?.toString()) ??
              'District',
          latitude: (m['latitude'] as num?)?.toDouble() ?? 20.0,
          longitude: (m['longitude'] as num?)?.toDouble() ?? 74.0,
          elevationM: (m['elevation_m'] as num?)?.toDouble() ?? 550.0,
        );
      }).toList(),
    );
  }
}
