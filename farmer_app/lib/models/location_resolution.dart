import 'panchayat_item.dart';

/// Status codes matching backend LocationResolutionStatus
enum LocationResolutionStatus {
  matched,
  noMatch,
  boundaryUnavailable,
  ambiguousMatch,
  accuracyTooLow,
  error,
}

/// Authoritative Gram Panchayat administrative hierarchy details resolved from coordinates.
class ResolvedPanchayat {
  final int id;
  final int lgdCode;
  final String name;
  final int? districtId;
  final String? districtName;
  final int? blockId;
  final String? blockName;
  final double latitude;
  final double longitude;
  final double elevationM;

  const ResolvedPanchayat({
    required this.id,
    required this.lgdCode,
    required this.name,
    this.districtId,
    this.districtName,
    this.blockId,
    this.blockName,
    this.latitude = 20.6,
    this.longitude = 74.1,
    this.elevationM = 550.0,
  });

  factory ResolvedPanchayat.fromJson(Map<String, dynamic> json) {
    return ResolvedPanchayat(
      id: json['id'] as int,
      lgdCode: json['lgd_code'] as int,
      name: json['name'] as String,
      districtId: json['district_id'] as int?,
      districtName: json['district_name'] as String?,
      blockId: json['block_id'] as int?,
      blockName: json['block_name'] as String?,
      latitude: (json['latitude'] as num?)?.toDouble() ?? 20.6,
      longitude: (json['longitude'] as num?)?.toDouble() ?? 74.1,
      elevationM: (json['elevation_m'] as num?)?.toDouble() ?? 550.0,
    );
  }

  /// Converts resolved panchayat to standard PanchayatItem for UI state compatibility
  PanchayatItem toPanchayatItem() {
    return PanchayatItem(
      panchayatId: id,
      lgdCode: lgdCode,
      panchayatName: name,
      blockName: blockName ?? 'Block',
      districtName: districtName ?? 'District',
      latitude: latitude,
      longitude: longitude,
      elevationM: elevationM,
    );
  }
}

/// Standardized response wrapper for GPS-based Panchayat resolution.
class LocationResolutionResponse {
  final bool matched;
  final LocationResolutionStatus status;
  final String message;
  final ResolvedPanchayat? panchayat;
  final String? accuracyWarning;

  const LocationResolutionResponse({
    required this.matched,
    required this.status,
    required this.message,
    this.panchayat,
    this.accuracyWarning,
  });

  factory LocationResolutionResponse.fromJson(Map<String, dynamic> json) {
    final statusStr = json['status'] as String? ?? 'NO_MATCH';
    LocationResolutionStatus parsedStatus;
    switch (statusStr) {
      case 'MATCHED':
        parsedStatus = LocationResolutionStatus.matched;
        break;
      case 'BOUNDARY_DATA_UNAVAILABLE':
        parsedStatus = LocationResolutionStatus.boundaryUnavailable;
        break;
      case 'AMBIGUOUS_MATCH':
        parsedStatus = LocationResolutionStatus.ambiguousMatch;
        break;
      case 'ACCURACY_TOO_LOW':
        parsedStatus = LocationResolutionStatus.accuracyTooLow;
        break;
      case 'NO_MATCH':
      default:
        parsedStatus = LocationResolutionStatus.noMatch;
        break;
    }

    return LocationResolutionResponse(
      matched: json['matched'] as bool? ?? false,
      status: parsedStatus,
      message: json['message'] as String? ?? '',
      panchayat: json['panchayat'] != null
          ? ResolvedPanchayat.fromJson(json['panchayat'] as Map<String, dynamic>)
          : null,
      accuracyWarning: json['accuracy_warning'] as String?,
    );
  }

  factory LocationResolutionResponse.error(String message) {
    return LocationResolutionResponse(
      matched: false,
      status: LocationResolutionStatus.error,
      message: message,
      panchayat: null,
    );
  }
}
