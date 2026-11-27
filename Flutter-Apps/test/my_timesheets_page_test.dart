import 'dart:convert';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/features/my_timesheets_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets('Saved timesheets open without API requests or edit actions', (
    tester,
  ) async {
    const scope = '["https://example.test/api/v1",5,7]';
    const sqlite = MethodChannel('com.tekartik.sqflite');
    final messenger = tester.binding.defaultBinaryMessenger;
    databaseFactory = databaseFactorySqflitePlugin;
    final reads = <String>[];
    messenger.setMockMethodCallHandler(sqlite, (call) async {
      switch (call.method) {
        case 'getDatabasesPath':
          return '/test';
        case 'openDatabase':
          return {'id': 1};
        case 'query':
          final args = call.arguments as Map;
          final sql = args['sql'] as String;
          if (sql.toUpperCase().contains('USER_VERSION')) {
            return [
              {'user_version': 3},
            ];
          }
          final key = (args['arguments'] as List).first as String;
          reads.add(key);
          return [
            {
              'saved_at': DateTime.now().millisecondsSinceEpoch,
              'rows': jsonEncode([
                {
                  'projects': [
                    {'id': 2, 'name': 'Warehouse rollout'},
                  ],
                  'sheets': [
                    {
                      'id': 12,
                      'project_id': 2,
                      'period_start': '2026-11-23',
                      'period_end': '2026-11-29',
                      'status': 'Draft',
                      'total_hours': '8',
                      'entries': [
                        {
                          'task_name': 'Counted inventory',
                          'work_date': '2026-11-27',
                          'is_billable': true,
                          'hours': '8',
                        },
                      ],
                    },
                  ],
                },
              ]),
            },
          ];
        case 'execute':
          return null;
        default:
          fail('Unexpected SQLite method: ${call.method}');
      }
    });
    addTearDown(() {
      messenger.setMockMethodCallHandler(sqlite, null);
      databaseFactory = null;
    });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((_) async {
          fail('Offline timesheets should read SQLite without an API request');
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: MyTimesheetsPage(
          api: api,
          employeeId: 27,
          canCreate: true,
          cacheScope: scope,
          offline: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(reads, ['$scope:my-timesheets:27']);
    expect(find.text('Saved timesheets'), findsOneWidget);
    await tester.tap(find.text('Warehouse rollout'));
    await tester.pumpAndSettle();
    expect(find.text('Counted inventory'), findsOneWidget);
    expect(find.text('New timesheet'), findsNothing);
    expect(find.text('Add entry'), findsNothing);
    expect(find.text('Submit'), findsNothing);
  });

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
    await tester.tap(find.byTooltip('Refresh timesheets'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Submitted · 8 h'), findsOneWidget);
  });
}
