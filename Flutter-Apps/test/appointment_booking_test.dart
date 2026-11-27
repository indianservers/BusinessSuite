import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/features/appointment_booking_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  final linked = ValueVariant<bool>({false, true});
  testWidgets('Native appointment checks the slot and retries one booking', (
    tester,
  ) async {
    const startsAt = '2026-12-01T09:00:00+00:00';
    const schedulePath = '/srm/service-checkout/appointments/23/schedule';
    final grouped = linked.currentValue!;
    final posts = <Json>[];
    var availabilityCalls = 0;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Branch'], '6');
          switch (request.path) {
            case schedulePath:
              expect(grouped, isTrue);
              if (request.method == 'GET') {
                return response({
                  'service_id': 3,
                  'appointment_revision': 4,
                  'occurrence_revision': 5,
                  'booking': {'eligibility_id': 8, 'duration_minutes': 30},
                  'additional_resource_ids': [12],
                });
              }
              posts.add(Map<String, dynamic>.of(request.data as Json));
              return response({
                'appointment': {
                  'id': 23,
                  'revision': 4,
                  'data': {'starts_at': '2026-12-01T08:00:00Z'},
                },
                'schedule': {
                  'appointment_revision': 5,
                  'booking': request.data['booking'],
                  'additional_resource_ids': [12],
                },
              });
            case '/srm/business/customers':
              return response({
                'items': [
                  {'id': 5, 'name': 'Aurora Retail'},
                ],
              });
            case '/catalog/items':
              expect(request.queryParameters['kind'], 'service');
              return response({
                'items': [
                  {'id': 3, 'name': 'Consultation'},
                ],
              });
            case '/srm/service-checkout/options':
              return response({
                'policy': {
                  'id': 7,
                  'revision': 2,
                  'default_duration_minutes': 30,
                },
                'specialists': [
                  {
                    'employee_id': 10,
                    'employee_name': 'Asha',
                    'eligibility_id': 8,
                    'eligibility_revision': 3,
                    'provider_resource_id': 11,
                    'timezone': 'UTC',
                  },
                ],
                'resources': [
                  {'id': 12, 'name': 'Room A', 'resource_type': 'room'},
                ],
              });
            case '/srm/service-checkout/options/availability':
              availabilityCalls++;
              expect(request.queryParameters['resource_ids'], [12]);
              expect(request.queryParameters['eligibility_id'], 8);
              if (availabilityCalls == 2) {
                expect(request.queryParameters['starts_at'], startsAt);
              }
              return response({
                'slots': [
                  {'starts_at': startsAt, 'label': '09:00'},
                  for (var index = 1; index <= 40; index++)
                    {'starts_at': startsAt, 'label': 'Other time $index'},
                ],
                'selection_available': true,
              });
            case '/srm/industry/appointments':
              expect(grouped, isFalse);
              posts.add(Map<String, dynamic>.of(request.data as Json));
              if (posts.length == 1) {
                throw DioException(
                  requestOptions: request,
                  type: DioExceptionType.connectionError,
                );
              }
              return response({'id': 23}, 201);
            default:
              fail('Unexpected request ${request.path}');
          }
        }),
    );
    Json? booked;
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () async {
                booked = await Navigator.of(context).push<Json>(
                  MaterialPageRoute(
                    builder: (_) => AppointmentBookingPage(
                      api: api,
                      headers: const {'X-Suite-Branch': '6'},
                      linkedAppointmentId: grouped ? 23 : null,
                    ),
                  ),
                );
              },
              child: const Text('Open booking'),
            ),
          ),
        ),
      ),
    );
    Future<void> tap(String label) async {
      final target = find.text(label).last;
      await tester.ensureVisible(target);
      await tester.tap(target);
      await tester.pumpAndSettle();
    }

    await tap('Open booking');
    if (!grouped) {
      await tap('Choose customer');
      await tap('Aurora Retail');
      await tap('Choose service');
      await tap('Consultation');
      await tester.tap(find.byType(DropdownButton<Json>));
      await tester.pumpAndSettle();
      await tap('Asha');
      await tap('Room A');
    }
    await tap('Check available times');
    await tap('09:00');
    final confirm = grouped ? 'Save new schedule' : 'Confirm appointment';
    expect(find.text(confirm).hitTestable(), findsOneWidget);
    await tap(confirm);
    expect(availabilityCalls, 2);
    if (grouped) {
      expect(posts.single['expected_appointment_revision'], 4);
      expect(posts.single['expected_occurrence_revision'], 5);
      expect(posts.single['additional_resource_ids'], [12]);
    } else {
      await tap('Retry confirmation');
      expect(posts, hasLength(2));
      expect(posts.last, posts.first);
      expect(posts.first['resource_ids'], [11, 12]);
    }
    expect(
      posts.first['booking'],
      containsPair('expected_eligibility_revision', 3),
    );
    expect(booked?['id'], 23);
    if (grouped) {
      expect(booked?['revision'], 5);
      expect(booked?['data']['starts_at'], startsAt);
    }
  }, variant: linked);
}
