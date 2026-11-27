import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/crm_follow_ups_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets('CRM searches follow-ups and completes one through the API', (
    tester,
  ) async {
    var status = 'Due';
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
    await tester.tap(find.text('Mark complete').last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextField, 'Notes'),
      'Renewal confirmed',
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save action'));
    await tester.pumpAndSettle();
    expect(searches, ['', 'maintenance', 'maintenance']);
    expect(find.text('Paper supplier · Completed'), findsOneWidget);
  });
}
