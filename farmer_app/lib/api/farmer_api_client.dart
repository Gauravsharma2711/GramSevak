import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

/// Exception thrown when the Farmer API request fails or returns an error.
class FarmerApiException implements Exception {
  final String message;
  final int? statusCode;

  FarmerApiException(this.message, [this.statusCode]);

  @override
  String toString() => 'FarmerApiException: $message (HTTP $statusCode)';
}

/// Centralized HTTP API Client for GramSevak Farmer Mobile App.
///
/// Communicates with FastAPI backend (`/api/v1/farmer/*` and `/api/v1/panchayats`).
/// - No hardcoded secrets or API tokens.
/// - Configurable base URL with safe local and emulator fallbacks.
/// - Centralized timeout and structured error parsing.
class FarmerApiClient {
  /// Base API URL configurable via dart-define or default deployed Render FastAPI address
  static const String defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://gramsevak-backend-512883913933.asia-south1.run.app/api/v1',
  );

  final String baseUrl;
  final http.Client _httpClient;
  final Duration timeoutDuration;

  FarmerApiClient({
    String? baseUrl,
    http.Client? httpClient,
    this.timeoutDuration = const Duration(seconds: 15),
  })  : baseUrl = baseUrl ?? defaultBaseUrl,
        _httpClient = httpClient ?? http.Client();

  /// Generic GET request with timeout and error extraction
  Future<dynamic> get(String endpoint,
      {Map<String, String>? queryParams}) async {
    Uri uri = Uri.parse('$baseUrl$endpoint');
    if (queryParams != null && queryParams.isNotEmpty) {
      uri = uri.replace(queryParameters: queryParams);
    }

    try {
      final response = await _httpClient.get(
        uri,
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      ).timeout(timeoutDuration);

      if (response.statusCode >= 200 && response.statusCode < 300) {
        final decoded = jsonDecode(utf8.decode(response.bodyBytes));
        return decoded;
      } else if (response.statusCode == 404) {
        String notFoundMsg =
            'Requested weather information is not currently available.';
        try {
          final errBody = jsonDecode(utf8.decode(response.bodyBytes));
          if (errBody is Map && errBody['detail'] != null) {
            notFoundMsg = errBody['detail'].toString();
          }
        } catch (_) {}
        throw FarmerApiException(notFoundMsg, 404);
      } else {
        String errorMsg = 'Server error (${response.statusCode})';
        try {
          final errBody = jsonDecode(utf8.decode(response.bodyBytes));
          if (errBody is Map && errBody['detail'] != null) {
            errorMsg = errBody['detail'].toString();
          }
        } catch (_) {}
        throw FarmerApiException(errorMsg, response.statusCode);
      }
    } on SocketException catch (e) {
      throw FarmerApiException(
          'Unable to reach GramSevak server. Please check your network connection: ${e.message}');
    } on TimeoutException {
      throw FarmerApiException('Weather request timed out. Please try again.');
    } on FormatException catch (e) {
      throw FarmerApiException(
          'Invalid response from weather service: ${e.message}');
    } catch (e) {
      if (e is FarmerApiException) rethrow;
      throw FarmerApiException('Unexpected network error: $e');
    }
  }

  /// Generic POST request with JSON payload, timeout, and structured error extraction
  Future<dynamic> post(
    String endpoint, {
    Map<String, dynamic>? body,
  }) async {
    final Uri uri = Uri.parse('$baseUrl$endpoint');

    try {
      final response = await _httpClient
          .post(
            uri,
            headers: {
              'Accept': 'application/json',
              'Content-Type': 'application/json',
            },
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(timeoutDuration);

      if (response.statusCode >= 200 && response.statusCode < 300) {
        final decoded = jsonDecode(utf8.decode(response.bodyBytes));
        return decoded;
      } else {
        String errorMsg = 'Server error (${response.statusCode})';
        try {
          final errBody = jsonDecode(utf8.decode(response.bodyBytes));
          if (errBody is Map && errBody['detail'] != null) {
            errorMsg = errBody['detail'].toString();
          }
        } catch (_) {}
        throw FarmerApiException(errorMsg, response.statusCode);
      }
    } on SocketException catch (e) {
      throw FarmerApiException(
          'Unable to reach GramSevak server. Please check your network connection: ${e.message}');
    } on TimeoutException {
      throw FarmerApiException('Location request timed out. Please try again.');
    } on FormatException catch (e) {
      throw FarmerApiException('Invalid response from server: ${e.message}');
    } catch (e) {
      if (e is FarmerApiException) rethrow;
      throw FarmerApiException('Unexpected network error: $e');
    }
  }

  /// Close underlying HTTP client
  void dispose() {
    _httpClient.close();
  }
}
