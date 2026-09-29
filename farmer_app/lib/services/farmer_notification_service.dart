import 'dart:async';
import '../models/notification_item.dart';
import '../repositories/farmer_repository.dart';

/// Notification permission states for the farmer app
enum NotificationPermissionStatus {
  granted,
  denied,
  undetermined,
}

/// Service managing device push notification lifecycle, token registration,
/// and foreground/background event dispatching for Panchayat weather alerts.
class FarmerNotificationService {
  final FarmerRepository _repository;
  
  NotificationPermissionStatus _permissionStatus = NotificationPermissionStatus.undetermined;
  final String _deviceToken;
  int? _registeredPanchayatId;

  final StreamController<FarmerNotification> _foregroundController =
      StreamController<FarmerNotification>.broadcast();
  final StreamController<FarmerNotification> _openedController =
      StreamController<FarmerNotification>.broadcast();

  FarmerNotificationService({
    FarmerRepository? repository,
    String? initialToken,
    NotificationPermissionStatus? initialPermission,
  })  : _repository = repository ?? FarmerRepository(),
        _deviceToken = initialToken ?? 'mock_farmer_device_token_demo',
        _permissionStatus = initialPermission ?? NotificationPermissionStatus.undetermined;

  /// Current notification permission status
  NotificationPermissionStatus get permissionStatus => _permissionStatus;

  /// Device token for push dispatch
  String get deviceToken => _deviceToken;

  /// Currently registered Panchayat ID for this device
  int? get registeredPanchayatId => _registeredPanchayatId;

  /// Stream of notifications received while the app is active in the foreground
  Stream<FarmerNotification> get onForegroundNotification => _foregroundController.stream;

  /// Stream of notifications opened/clicked by the farmer to navigate to relevant context
  Stream<FarmerNotification> get onNotificationOpened => _openedController.stream;

  /// Request push notification permissions with farmer context
  Future<NotificationPermissionStatus> requestPermission({bool grant = true}) async {
    _permissionStatus = grant
        ? NotificationPermissionStatus.granted
        : NotificationPermissionStatus.denied;
    return _permissionStatus;
  }

  /// Register the device token with the backend scoped to the farmer's active Panchayat
  Future<bool> syncDeviceToken({
    required int panchayatId,
    String platform = 'android',
    String lang = 'en',
  }) async {
    // Only register if permission is granted
    if (_permissionStatus != NotificationPermissionStatus.granted) {
      return false;
    }

    try {
      final success = await _repository.registerDeviceToken(
        deviceToken: _deviceToken,
        panchayatId: panchayatId,
        platform: platform,
        languagePreference: lang,
      );
      if (success) {
        _registeredPanchayatId = panchayatId;
      }
      return success;
    } catch (_) {
      return false;
    }
  }

  /// Handle an incoming notification when app is in the foreground
  void handleForegroundMessage(Map<String, dynamic> rawPayload) {
    try {
      final notification = FarmerNotification.fromJson(rawPayload);
      _foregroundController.add(notification);
    } catch (_) {
      // Ignore malformed payloads safely
    }
  }

  /// Handle notification opened/clicked event (e.g. from system tray or banner)
  void handleNotificationOpened(Map<String, dynamic> rawPayload) {
    try {
      final notification = FarmerNotification.fromJson(rawPayload);
      _openedController.add(notification);
    } catch (_) {
      // Ignore malformed payloads safely
    }
  }

  /// Process background notification payload safely without crashing or exposing IDs
  FarmerNotification? handleBackgroundMessage(Map<String, dynamic> rawPayload) {
    try {
      return FarmerNotification.fromJson(rawPayload);
    } catch (_) {
      return null;
    }
  }

  /// Clean up stream controllers
  void dispose() {
    _foregroundController.close();
    _openedController.close();
  }
}
