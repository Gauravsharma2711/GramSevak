import 'dart:async';

/// Status of device location permission.
enum DeviceLocationPermission {
  granted,
  denied,
  permanentlyDenied,
}

/// Simple value object holding latitude, longitude, and optional horizontal accuracy.
class DeviceCoordinates {
  final double latitude;
  final double longitude;
  final double? accuracyMeters;

  const DeviceCoordinates({
    required this.latitude,
    required this.longitude,
    this.accuracyMeters,
  });

  @override
  String toString() =>
      'DeviceCoordinates(lat: $latitude, lng: $longitude, accuracy: ${accuracyMeters}m)';
}

/// Abstract contract for device location services in the GramSevak mobile app.
///
/// Ensures modularity, platform independence, and deterministic unit/widget testing
/// without binding the entire UI to platform plugins.
abstract class DeviceLocationService {
  /// Checks whether hardware GPS / location services are enabled on the device.
  Future<bool> isLocationServiceEnabled();

  /// Checks current location permission status without prompting.
  Future<DeviceLocationPermission> checkPermission();

  /// Requests location permission from the farmer.
  Future<DeviceLocationPermission> requestPermission();

  /// Acquires current device GPS coordinates. Returns null if unavailable or timed out.
  Future<DeviceCoordinates?> getCurrentCoordinates();
}

/// Default implementation of DeviceLocationService.
/// Supports programmatic overrides for testing and configurable platform fallback.
class DefaultDeviceLocationService implements DeviceLocationService {
  bool _serviceEnabled;
  DeviceLocationPermission _permission;
  DeviceCoordinates? _simulatedCoordinates;

  DefaultDeviceLocationService({
    bool serviceEnabled = true,
    DeviceLocationPermission permission = DeviceLocationPermission.denied,
    DeviceCoordinates? initialCoordinates,
  })  : _serviceEnabled = serviceEnabled,
        _permission = permission,
        _simulatedCoordinates = initialCoordinates;

  @override
  Future<bool> isLocationServiceEnabled() async {
    return _serviceEnabled;
  }

  @override
  Future<DeviceLocationPermission> checkPermission() async {
    return _permission;
  }

  @override
  Future<DeviceLocationPermission> requestPermission() async {
    // If permanently denied, asking cannot grant it directly without system settings
    if (_permission == DeviceLocationPermission.permanentlyDenied) {
      return DeviceLocationPermission.permanentlyDenied;
    }
    // Simulate user granting or denying
    if (_permission == DeviceLocationPermission.denied) {
      _permission = DeviceLocationPermission.granted;
    }
    return _permission;
  }

  @override
  Future<DeviceCoordinates?> getCurrentCoordinates() async {
    if (!_serviceEnabled) return null;
    if (_permission != DeviceLocationPermission.granted) return null;
    return _simulatedCoordinates;
  }

  // Test / simulation helpers
  void setServiceEnabled(bool enabled) => _serviceEnabled = enabled;
  void setPermission(DeviceLocationPermission perm) => _permission = perm;
  void setCoordinates(DeviceCoordinates? coords) =>
      _simulatedCoordinates = coords;
}
