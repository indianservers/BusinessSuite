import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/features/my_timesheets_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets('Employee creates a timesheet, logs work, and submits it', (
    tester,
  ) async {
    Json? sheet;
    final entries = <Json>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          switch ((request.method, request.path)) {
            case ('GET', '/timesheets/projects'):
              return response([
                {'id': 2, 'name': 'Warehouse rollout', 'status': 'Active'},
              ]);
            case ('GET', '/timesheets/'):
              expect(request.queryParameters['employee_id'], 27);
              return response([?sheet]);
            case ('POST', '/timesheets/'):
              final data = request.data as Json;
              expect(data['project_id'], 2);
              sheet = {
                ...data,
                'id': 12,
                'employee_id': 27,
                'status': 'Draft',
                'total_hours': '0',
                'entries': entries,
              };
              return response(sheet!, 201);
            case ('POST', '/timesheets/12/entries'):
              final data = request.data as Json;
              expect(data['task_name'], 'Counted inventory');
              expect(data['hours'], '8');
              expect(data['is_billable'], true);
              entries.add({...data, 'id': 31});
              sheet!['total_hours'] = '8';
              return response(entries.single, 201);
            case ('PUT', '/timesheets/12/submit'):
              expect(entries, hasLength(1));
              sheet!['status'] = 'Submitted';
              return response(sheet!);
            default:
              throw StateError('Unexpected request: ${request.path}');
          }
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: MyTimesheetsPage(api: api, employeeId: 27, canCreate: true),
      ),
    );
    await tester.pumpAndSettle();

    Future<void> tap(String label) async {
      final target = find.text(label).last;
      await tester.ensureVisible(target);
      await tester.tap(target);
      await tester.pumpAndSettle();
    }

    await tap('New timesheet');
    await tap('Project');
    await tap('Warehouse rollout');
    await tap('Create timesheet');
    await tap('Add entry');
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Task'),
      'Counted inventory',
    );
    await tap('Save entry');
    expect(find.text('Counted inventory'), findsOneWidget);
    await tap('Submit');
    expect(find.textContaining('Submitted · 8 h'), findsOneWidget);
    expect(find.text('Add entry'), findsNothing);
  });
}
