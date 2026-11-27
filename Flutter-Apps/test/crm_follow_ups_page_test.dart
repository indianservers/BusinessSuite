import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/crm_follow_ups_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets('CRM searches, reschedules, and completes a follow-up', (
    tester,
  ) async {
    var status = 'Due';
    var due = '2026-11-27T10:30:00Z';
    final searches = <String>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Branch'], '6');
          final row = {
            'id': 12,
            'title': 'Renew maintenance',
            'customer_name': 'Paper supplier',
            'status': status,
            'due_at': due,
          };
          switch ((request.method, request.path)) {
            case ('GET', '/follow-ups'):
              searches.add(request.queryParameters['search'] as String);
              return response({
                'items': [row],
                'total': 1,
              });
            case ('GET', '/follow-ups/12'):
              return response({...row, 'activities': []});
            case ('POST', '/follow-ups/12/actions'):
              final data = request.data as Map;
              if (data['action'] == 'reschedule') {
                expect(data['notes'], 'Customer requested a new time');
                final current = DateTime.parse(due).toLocal();
                expect(
                  data['due_at'],
                  DateTime(
                    current.year,
                    current.month,
                    28,
                    current.hour,
                    current.minute,
                  ).toUtc().toIso8601String(),
                );
                due = data['due_at'] as String;
                status = 'Rescheduled';
                return response({...row, 'status': status, 'due_at': due});
              }
              expect(request.data, {
                'action': 'complete',
                'notes': 'Renewal confirmed',
              });
              status = 'Completed';
              return response({...row, 'status': status});
            default:
              throw StateError('Unexpected request: ${request.path}');
          }
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmFollowUpsPage(
          api: api,
          headers: const {'X-Suite-Branch': '6'},
          cacheScope: null,
          offline: false,
          canEdit: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'maintenance');
    await tester.tap(find.byTooltip('Search'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Renew maintenance'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Add comment'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Reschedule').last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextField, 'Notes'),
      'Customer requested a new time',
    );
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Save action'),
          )
          .onPressed,
      isNull,
    );
    await tester.tap(find.text('Choose due date and time'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('28').last);
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save action'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Rescheduled'), findsOneWidget);
    await tester.tap(find.text('Renew maintenance'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Add comment'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Mark complete').last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextField, 'Notes'),
      'Renewal confirmed',
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save action'));
    await tester.pumpAndSettle();
    expect(searches, ['', 'maintenance', 'maintenance', 'maintenance']);
    expect(find.textContaining('Completed'), findsOneWidget);
  });
}
