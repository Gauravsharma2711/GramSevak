/// Data model strictly matching backend `FarmerForecastResponse` schema
/// (`/api/v1/farmer/panchayat/{id}`).
///
/// Contains downscaled rainfall prediction paired with verified agronomic guidance.
/// Zero internal model hyperparameters, database IDs, or sensitive officer metadata.
class FarmerForecast {
  final String panchayatName;
  final String blockName;
  final String districtName;
  final String forecastDate;
  final double rainfallMm;
  final String rainfallCategory;
  final String severity; // 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'
  final String? advisoryTitle;
  final List<String> advisoryPoints;
  final String advisoryStatus; // 'APPROVED' or 'NO_APPROVED_ADVISORY'
  final String language;
  final List<String> availableLanguages;
  final String? languageStatus;

  FarmerForecast({
    required this.panchayatName,
    required this.blockName,
    required this.districtName,
    required this.forecastDate,
    required this.rainfallMm,
    required this.rainfallCategory,
    required this.severity,
    this.advisoryTitle,
    required this.advisoryPoints,
    required this.advisoryStatus,
    required this.language,
    required this.availableLanguages,
    this.languageStatus,
  });

  /// True ONLY when the advisory has been explicitly reviewed and approved by an extension officer.
  bool get isApproved => advisoryStatus == 'APPROVED';

  /// True if actionable advisory points exist and status is approved.
  bool get hasActionableAdvice => isApproved && advisoryPoints.isNotEmpty;

  /// Safe factory constructor converting raw backend JSON to immutable FarmerForecast
  factory FarmerForecast.fromJson(Map<String, dynamic> json) {
    // 1. Sanitize rainfall value (ensure non-negative and handle nulls/NaN safely)
    double rawRainfall = 0.0;
    if (json['rainfall_mm'] != null) {
      final numVal = json['rainfall_mm'];
      if (numVal is num && !numVal.isNaN && !numVal.isInfinite) {
        rawRainfall = numVal.toDouble().clamp(0.0, 9999.0);
      }
    }

    // 2. Parse advisory points safely
    final List<String> points = [];
    if (json['advisory_points'] is List) {
      for (final item in (json['advisory_points'] as List)) {
        if (item != null && item.toString().trim().isNotEmpty) {
          points.add(item.toString().trim());
        }
      }
    }

    // 3. Parse available languages
    final List<String> languages = [];
    if (json['available_languages'] is List) {
      for (final l in (json['available_languages'] as List)) {
        if (l != null) languages.add(l.toString());
      }
    }
    if (languages.isEmpty) {
      languages.addAll(['en', 'mr', 'hi']);
    }

    return FarmerForecast(
      panchayatName: json['panchayat_name'] as String? ?? 'Gram Panchayat',
      blockName: json['block_name'] as String? ?? 'Block',
      districtName: json['district_name'] as String? ?? 'District',
      forecastDate: json['forecast_date']?.toString() ?? '2026-09-09',
      rainfallMm: rawRainfall,
      rainfallCategory: json['rainfall_category'] as String? ?? 'No rainfall',
      severity: json['severity'] as String? ?? 'LOW',
      advisoryTitle: json['advisory_title'] as String?,
      advisoryPoints: points,
      advisoryStatus:
          json['advisory_status'] as String? ?? 'NO_APPROVED_ADVISORY',
      language: json['language'] as String? ?? 'en',
      availableLanguages: languages,
      languageStatus: json['language_status'] as String?,
    );
  }

  /// Create a copy with optional modifications
  FarmerForecast copyWith({
    String? panchayatName,
    String? blockName,
    String? districtName,
    String? forecastDate,
    double? rainfallMm,
    String? rainfallCategory,
    String? severity,
    String? advisoryTitle,
    List<String>? advisoryPoints,
    String? advisoryStatus,
    String? language,
    List<String>? availableLanguages,
    String? languageStatus,
  }) {
    return FarmerForecast(
      panchayatName: panchayatName ?? this.panchayatName,
      blockName: blockName ?? this.blockName,
      districtName: districtName ?? this.districtName,
      forecastDate: forecastDate ?? this.forecastDate,
      rainfallMm: rainfallMm ?? this.rainfallMm,
      rainfallCategory: rainfallCategory ?? this.rainfallCategory,
      severity: severity ?? this.severity,
      advisoryTitle: advisoryTitle ?? this.advisoryTitle,
      advisoryPoints: advisoryPoints ?? this.advisoryPoints,
      advisoryStatus: advisoryStatus ?? this.advisoryStatus,
      language: language ?? this.language,
      availableLanguages: availableLanguages ?? this.availableLanguages,
      languageStatus: languageStatus ?? this.languageStatus,
    );
  }
}
