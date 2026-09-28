/// Data model for Panchayat Metadata
class PanchayatItem {
  final int panchayatId;
  final int lgdCode;
  final String panchayatName;
  final String blockName;
  final String districtName;
  final double latitude;
  final double longitude;
  final double elevationM;

  PanchayatItem({
    required this.panchayatId,
    required this.lgdCode,
    required this.panchayatName,
    required this.blockName,
    required this.districtName,
    required this.latitude,
    required this.longitude,
    required this.elevationM,
  });

  factory PanchayatItem.fromJson(Map<String, dynamic> json) {
    return PanchayatItem(
      panchayatId: (json['id'] ?? json['panchayat_id']) as int? ?? 0,
      lgdCode: json['lgd_code'] as int? ?? 0,
      panchayatName:
          (json['name'] ?? json['panchayat_name']) as String? ?? 'Unknown',
      blockName: (json['block'] is Map
              ? json['block']['name']
              : json['block_name']) as String? ??
          'Block',
      districtName: (json['district'] is Map
              ? json['district']['name']
              : json['district_name']) as String? ??
          'District',
      latitude: (json['latitude'] as num?)?.toDouble() ?? 20.6,
      longitude: (json['longitude'] as num?)?.toDouble() ?? 74.1,
      elevationM: (json['elevation_m'] as num?)?.toDouble() ?? 550.0,
    );
  }
}
