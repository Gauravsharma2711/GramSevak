/// Hierarchical District and Block Models for Farmer App
class DistrictItem {
  final int id;
  final String name;
  final String state;

  DistrictItem({
    required this.id,
    required this.name,
    required this.state,
  });

  factory DistrictItem.fromJson(Map<String, dynamic> json) {
    return DistrictItem(
      id: json['id'] as int? ?? 1,
      name: json['name'] as String? ?? 'Nashik',
      state: json['state'] as String? ?? 'Maharashtra',
    );
  }
}

class BlockItem {
  final int id;
  final int districtId;
  final String name;

  BlockItem({
    required this.id,
    required this.districtId,
    required this.name,
  });

  factory BlockItem.fromJson(Map<String, dynamic> json) {
    return BlockItem(
      id: json['id'] as int? ?? 101,
      districtId: json['district_id'] as int? ?? 1,
      name: json['name'] as String? ?? 'Baglan',
    );
  }
}
