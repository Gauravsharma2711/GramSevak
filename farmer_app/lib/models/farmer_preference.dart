/// Farmer Preferences Data Model (Phase 6.3).
///
/// Encapsulates the farmer's personalization settings:
/// - Preferred Gram Panchayat ID (Authoritative)
/// - Preferred Language (en, mr, hi)
/// - Authoritative administrative spatial metadata (Panchayat, Block, District)
/// - Onboarding setup completion state
class FarmerPreferences {
  final String farmerId;
  final int panchayatId;
  final String preferredLanguage;
  final String panchayatName;
  final String blockName;
  final String districtName;
  final DateTime updatedAt;
  final bool hasCompletedSetup;

  const FarmerPreferences({
    required this.farmerId,
    required this.panchayatId,
    required this.preferredLanguage,
    required this.panchayatName,
    required this.blockName,
    required this.districtName,
    required this.updatedAt,
    this.hasCompletedSetup = true,
  });

  /// Factory for a newly installed app before first setup
  factory FarmerPreferences.defaultPreferences({
    String? farmerId,
    int? defaultPanchayatId,
    String? defaultLang,
  }) {
    return FarmerPreferences(
      farmerId: farmerId ?? 'farmer_device_default',
      panchayatId: defaultPanchayatId ?? 1001,
      preferredLanguage: defaultLang ?? 'en',
      panchayatName: 'Ajmer Saundane',
      blockName: 'Baglan',
      districtName: 'Nashik',
      updatedAt: DateTime.now(),
      hasCompletedSetup: false,
    );
  }

  factory FarmerPreferences.fromJson(Map<String, dynamic> json) {
    return FarmerPreferences(
      farmerId: json['farmer_id'] as String? ?? 'farmer_unknown',
      panchayatId: (json['panchayat_id'] as num?)?.toInt() ?? 1001,
      preferredLanguage: json['preferred_language'] as String? ?? 'en',
      panchayatName: json['panchayat_name'] as String? ?? 'Ajmer Saundane',
      blockName: json['block_name'] as String? ?? 'Baglan',
      districtName: json['district_name'] as String? ?? 'Nashik',
      updatedAt: json['updated_at'] != null
          ? DateTime.tryParse(json['updated_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      hasCompletedSetup: json['has_completed_setup'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'farmer_id': farmerId,
      'panchayat_id': panchayatId,
      'preferred_language': preferredLanguage,
      'panchayat_name': panchayatName,
      'block_name': blockName,
      'district_name': districtName,
      'updated_at': updatedAt.toIso8601String(),
      'has_completed_setup': hasCompletedSetup,
    };
  }

  FarmerPreferences copyWith({
    String? farmerId,
    int? panchayatId,
    String? preferredLanguage,
    String? panchayatName,
    String? blockName,
    String? districtName,
    DateTime? updatedAt,
    bool? hasCompletedSetup,
  }) {
    return FarmerPreferences(
      farmerId: farmerId ?? this.farmerId,
      panchayatId: panchayatId ?? this.panchayatId,
      preferredLanguage: preferredLanguage ?? this.preferredLanguage,
      panchayatName: panchayatName ?? this.panchayatName,
      blockName: blockName ?? this.blockName,
      districtName: districtName ?? this.districtName,
      updatedAt: updatedAt ?? this.updatedAt,
      hasCompletedSetup: hasCompletedSetup ?? this.hasCompletedSetup,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is FarmerPreferences &&
          runtimeType == other.runtimeType &&
          farmerId == other.farmerId &&
          panchayatId == other.panchayatId &&
          preferredLanguage == other.preferredLanguage &&
          hasCompletedSetup == other.hasCompletedSetup;

  @override
  int get hashCode =>
      farmerId.hashCode ^
      panchayatId.hashCode ^
      preferredLanguage.hashCode ^
      hasCompletedSetup.hashCode;
}
