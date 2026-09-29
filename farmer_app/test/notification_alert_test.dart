import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:farmer_app/api/farmer_api_client.dart';
import 'package:farmer_app/models/farmer_forecast.dart';
import 'package:farmer_app/models/notification_item.dart';
import 'package:farmer_app/repositories/farmer_repository.dart';
import 'package:farmer_app/screens/home_forecast_screen.dart';
import 'package:farmer_app/services/farmer_notification_service.dart';

void main() {
  group('Phase 6.2 — Farmer Notification & Location Alerts Service Tests', () {
    test('Notification permission granted transitions status correctly', () async {
      final service = FarmerNotificationService(initialToken: 'test_token_123');
      expect(service.permissionStatus, NotificationPermissionStatus.undetermined);

      final status = await service.requestPermission(grant: true);
      expect(status, NotificationPermissionStatus.granted);
      expect(service.permissionStatus, NotificationPermissionStatus.granted);
      expect(service.deviceToken, 'test_token_123');
      service.dispose();
    });

    test('Notification permission denied prevents token sync', () async {
      final mockClient = MockClient((request) async {
        return http.Response(jsonEncode({'status': 'registered'}), 200);
      });
      final repo = FarmerRepository(apiClient: FarmerApiClient(httpClient: mockClient));
      final service = FarmerNotificationService(repository: repo);

      final status = await service.requestPermission(grant: false);
      expect(status, NotificationPermissionStatus.denied);

      final synced = await service.syncDeviceToken(panchayatId: 1001);
      expect(synced, isFalse);
      expect(service.registeredPanchayatId, isNull);
      service.dispose();
    });

    test('Device token registration sends correct payload to backend', () async {
      Map<String, dynamic>? recordedBody;
      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/farmer/device-token')) {
          recordedBody = jsonDecode(request.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({
              'status': 'registered',
              'device_token': recordedBody!['device_token'],
              'panchayat_id': recordedBody!['panchayat_id'],
            }),
            200,
          );
        }
        return http.Response('Not Found', 404);
      });

      final repo = FarmerRepository(apiClient: FarmerApiClient(httpClient: mockClient));
      final service = FarmerNotificationService(
        repository: repo,
        initialToken: 'fcm_token_device_abc',
        initialPermission: NotificationPermissionStatus.granted,
      );

      final synced = await service.syncDeviceToken(
        panchayatId: 1008,
        platform: 'android',
        lang: 'mr',
      );

      expect(synced, isTrue);
      expect(service.registeredPanchayatId, 1008);
      expect(recordedBody?['device_token'], 'fcm_token_device_abc');
      expect(recordedBody?['panchayat_id'], 1008);
      expect(recordedBody?['platform'], 'android');
      expect(recordedBody?['language_preference'], 'mr');
      service.dispose();
    });

    test('Foreground notification stream receives and parses payload', () async {
      final service = FarmerNotificationService();
      final notifications = <FarmerNotification>[];
      final sub = service.onForegroundNotification.listen(notifications.add);

      final rawPayload = {
        'event_id': 42,
        'advisory_id': 101,
        'advisory_version': 2,
        'panchayat_id': 1001,
        'alert_category': 'HEAVY_RAINFALL',
        'severity': 'HIGH',
        'title': 'Heavy Rainfall Alert',
        'message': 'Expected heavy rain over 65mm in next 24 hours.',
        'published_at': '2026-09-29T10:00:00Z',
        'deep_link': 'gramsevak://advisory/101',
      };

      service.handleForegroundMessage(rawPayload);
      await Future.delayed(const Duration(milliseconds: 10));

      expect(notifications.length, 1);
      final item = notifications.first;
      expect(item.eventId, 42);
      expect(item.alertCategory, 'HEAVY_RAINFALL');
      expect(item.severity, 'HIGH');
      expect(item.title, 'Heavy Rainfall Alert');
      expect(item.message, contains('65mm'));

      await sub.cancel();
      service.dispose();
    });

    test('Background message handler parses payload safely', () {
      final service = FarmerNotificationService();
      final parsed = service.handleBackgroundMessage({
        'event_id': 55,
        'advisory_id': 102,
        'advisory_version': 1,
        'panchayat_id': 1002,
        'alert_category': 'PEST_RISK',
        'severity': 'MEDIUM',
        'title': 'Pest Warning',
        'message': 'High humidity increases downy mildew risk.',
        'published_at': '2026-09-29T11:00:00Z',
      });

      expect(parsed, isNotNull);
      expect(parsed?.eventId, 55);
      expect(parsed?.title, 'Pest Warning');
      expect(parsed?.severity, 'MEDIUM');
      service.dispose();
    });

    test('Notification opened stream receives event for navigation', () async {
      final service = FarmerNotificationService();
      final openedEvents = <FarmerNotification>[];
      final sub = service.onNotificationOpened.listen(openedEvents.add);

      service.handleNotificationOpened({
        'event_id': 77,
        'advisory_id': 105,
        'advisory_version': 1,
        'panchayat_id': 1008,
        'alert_category': 'WEATHER_ALERT',
        'severity': 'HIGH',
        'title': 'Thunderstorm Advisory',
        'message': 'Secure harvested crops immediately.',
        'published_at': '2026-09-29T12:00:00Z',
      });
      await Future.delayed(const Duration(milliseconds: 10));

      expect(openedEvents.length, 1);
      expect(openedEvents.first.panchayatId, 1008);
      expect(openedEvents.first.title, 'Thunderstorm Advisory');

      await sub.cancel();
      service.dispose();
    });

    test('Malformed or invalid deep link context is handled safely without throwing', () {
      final service = FarmerNotificationService();
      // Should not throw on empty/corrupt payload
      final result = service.handleBackgroundMessage({'invalid_key': 123});
      expect(result, isNotNull);
      expect(result?.title, 'Weather Advisory');
      expect(result?.advisoryId, 0);

      service.handleForegroundMessage({});
      service.handleNotificationOpened({});
      service.dispose();
    });
  });

  group('Phase 6.2 — Widget Alert Presentation & Manual Selection Tests', () {
    testWidgets('HomeForecastScreen displays farmer-safe alert banner when alerts present', (tester) async {
      final forecast = FarmerForecast(
        panchayatName: 'Ajmer Saundane',
        blockName: 'Baglan',
        districtName: 'Nashik',
        forecastDate: '2026-09-29',
        rainfallMm: 45.0,
        rainfallCategory: 'Heavy Rain',
        severity: 'HIGH',
        advisoryTitle: 'Heavy Rainfall Alert',
        advisoryPoints: ['Drain water from low-lying fields.'],
        advisoryStatus: 'APPROVED',
        language: 'en',
        availableLanguages: const ['en', 'mr', 'hi'],
      );

      const alert = FarmerNotification(
        eventId: 10,
        advisoryId: 101,
        advisoryVersion: 1,
        panchayatId: 1001,
        alertCategory: 'HEAVY_RAINFALL',
        severity: 'HIGH',
        title: 'High Rain Warning',
        message: 'Avoid pesticide spray. Ensure channel drainage.',
        publishedAt: '2026-09-29T10:00:00Z',
      );

      bool advisoryOpened = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: HomeForecastScreen(
              forecast: forecast,
              onRefresh: () {},
              onSwitchPanchayat: () {},
              alerts: const [alert],
              onViewAdvisoryDetails: () {
                advisoryOpened = true;
              },
            ),
          ),
        ),
      );

      // Verify alert banner is rendered with farmer safe title and message
      expect(find.text('High Rain Warning'), findsOneWidget);
      expect(find.text('Avoid pesticide spray. Ensure channel drainage.'), findsOneWidget);
      expect(find.text('HIGH'), findsWidgets);

      // Tap alert banner -> triggers onViewAdvisoryDetails
      await tester.tap(find.text('High Rain Warning'));
      await tester.pumpAndSettle();

      expect(advisoryOpened, isTrue);
    });

    testWidgets('Manual Panchayat selection flow remains completely functional', (tester) async {
      bool switchClicked = false;
      final forecast = FarmerForecast(
        panchayatName: 'Mulher',
        blockName: 'Baglan',
        districtName: 'Nashik',
        forecastDate: '2026-09-29',
        rainfallMm: 2.0,
        rainfallCategory: 'Light Rain',
        severity: 'LOW',
        advisoryTitle: null,
        advisoryPoints: [],
        advisoryStatus: 'APPROVED',
        language: 'en',
        availableLanguages: const ['en', 'mr', 'hi'],
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: HomeForecastScreen(
              forecast: forecast,
              onRefresh: () {},
              onSwitchPanchayat: () {
                switchClicked = true;
              },
              alerts: const [],
            ),
          ),
        ),
      );

      expect(find.text('Mulher'), findsOneWidget);
      expect(find.text('Change Village'), findsOneWidget);

      await tester.tap(find.text('Change Village'));
      await tester.pumpAndSettle();

      expect(switchClicked, isTrue);
    });
  });
}
