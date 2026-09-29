/// Data model representing a farmer-safe location alert or push notification.
class FarmerNotification {
  final int eventId;
  final int advisoryId;
  final int advisoryVersion;
  final int panchayatId;
  final String alertCategory;
  final String severity;
  final String title;
  final String message;
  final String publishedAt;
  final String? deepLink;

  const FarmerNotification({
    required this.eventId,
    required this.advisoryId,
    required this.advisoryVersion,
    required this.panchayatId,
    required this.alertCategory,
    required this.severity,
    required this.title,
    required this.message,
    required this.publishedAt,
    this.deepLink,
  });

  factory FarmerNotification.fromJson(Map<String, dynamic> json) {
    return FarmerNotification(
      eventId: (json['event_id'] as num?)?.toInt() ?? 0,
      advisoryId: (json['advisory_id'] as num?)?.toInt() ?? 0,
      advisoryVersion: (json['advisory_version'] as num?)?.toInt() ?? 1,
      panchayatId: (json['panchayat_id'] as num?)?.toInt() ?? 0,
      alertCategory: json['alert_category'] as String? ?? 'WEATHER_ADVISORY',
      severity: json['severity'] as String? ?? 'LOW',
      title: json['title'] as String? ?? 'Weather Advisory',
      message: json['message'] as String? ?? '',
      publishedAt: json['published_at'] as String? ?? '',
      deepLink: json['deep_link'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'event_id': eventId,
        'advisory_id': advisoryId,
        'advisory_version': advisoryVersion,
        'panchayat_id': panchayatId,
        'alert_category': alertCategory,
        'severity': severity,
        'title': title,
        'message': message,
        'published_at': publishedAt,
        'deep_link': deepLink,
      };
}
