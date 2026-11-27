import 'dart:async';
import 'dart:convert';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/crm_follow_ups_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets(
    'Saved follow-ups open offline and disappear when access is denied',
    (tester) async {
      const sqlite = MethodChannel('com.tekartik.sqflite');
      const scope = '["https://example.test/api/v1",5,7]';
      const row = {'id': 9, 'title': 'Check delivery', 'status': 'Due'};
      final refresh = Completer<ResponseBody>();
      var requests = 0;
      final messenger = tester.binding.defaultBinaryMessenger;
      databaseFactory = databaseFactorySqflitePlugin;
      messenger.setMockMethodCallHandler(sqlite, (call) async {
        switch (call.method) {
          case 'getDatabasesPath':
            return '/test';
          case 'openDatabase':
            return {'id': 1};
          case 'execute':
            return null;
          case 'update':
            return 1;
          case 'query':
            final query = call.arguments as Map;
            if ((query['sql'] as String).toUpperCase().contains(
              'USER_VERSION',
            )) {
              return [
                {'user_version': 3},
              ];
            }
            final key = (query['arguments'] as List).first;
            final record = switch (key) {
              '$scope:follow-ups:::1:/follow-ups:6' => {
                'items': [row],
                'total': 1,
              },
              '$scope:/follow-ups/9:6' => {
                ...row,
                'activities': [
                  {'action': 'contact', 'actor_name': 'Sales coordinator'},
                ],
              },
              _ => throw StateError('Unexpected SQLite key $key'),
            };
            return [
              {
                'saved_at': DateTime.now().millisecondsSinceEpoch,
                'rows': jsonEncode([record]),
              },
            ];
          default:
            fail('Unexpected SQLite method ${call.method}');
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
          ..httpClientAdapter = FakeAdapter((request) async {
            requests++;
            expect(request.path, '/follow-ups');
            return refresh.future;
          }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: CrmFollowUpsPage(
            api: api,
            headers: const {'X-Suite-Branch': '6'},
            cacheScope: scope,
            offline: true,
            canEdit: true,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Check delivery'));
      await tester.pumpAndSettle();
      expect(find.text('Saved activity history'), findsOneWidget);
      expect(find.text('contact'), findsOneWidget);
      expect(find.text('Sales coordinator'), findsOneWidget);
      expect(find.text('Save action'), findsNothing);
      expect(requests, 0);
      await tester.tap(find.text('Close'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Refresh follow-ups'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(requests, 1);
      expect(find.text('Check delivery'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      refresh.complete(response({'detail': 'Follow-up access revoked'}, 403));
      await tester.pumpAndSettle();
      expect(find.text('Check delivery'), findsNothing);
      expect(find.textContaining('Follow-up access revoked'), findsOneWidget);
    },
  );

  testWidgets('CRM schedules a customer follow-up with a date and time', (
    tester,
  ) async {
    Map? created;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Branch'], '6');
          switch ((request.method, request.path)) {
            case ('GET', '/follow-ups'):
              return response({
                'items': [
                  if (created != null) {'id': 9, ...created!, 'status': 'Due'},
                ],
                'total': created == null ? 0 : 1,
              });
            case ('GET', '/follow-ups/options'):
              return response({
                'customers': [
                  {'id': 5, 'name': 'Paper supplier'},
                ],
              });
            case ('POST', '/follow-ups'):
              created = request.data as Map;
              return response({'id': 9}, 201);
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
          canEdit: false,
          canCreate: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('New follow-up'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Customer'), 'Paper');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Paper supplier').last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextField, 'Purpose / next action'),
      'Check delivery',
    );
    await tester.pumpAndSettle();
    expect(created, isNull);
    Future<void> tap(String label) async {
      final target = find.text(label).last;
      await tester.ensureVisible(target);
      await tester.tap(target);
      await tester.pumpAndSettle();
    }

    await tap('Choose due date and time');
    await tap('OK');
    await tap('OK');
    await tap('Schedule follow-up');
    expect(created, {
      'customer_id': 5,
      'title': 'Check delivery',
      'required': true,
      'type': 'date',
      'due_at': endsWith('Z'),
      'priority': 'Normal',
      'contact_method': 'Call',
      'notes': '',
    });
    expect(find.text('Check delivery'), findsOneWidget);
  });

  testWidgets('CRM can reassign with assign permission alone', (tester) async {
    var assignee = 'Original owner';
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Branch'], '6');
          final row = {
            'id': 12,
            'title': 'Renew maintenance',
            'status': 'Due',
            'assigned_to': assignee,
            'assigned_user_id': 3,
          };
          switch ((request.method, request.path)) {
            case ('GET', '/follow-ups'):
              return response({
                'items': [row],
                'total': 1,
              });
            case ('GET', '/follow-ups/12'):
              return response(row);
            case ('GET', '/follow-ups/options'):
              return response({
                'employees': [
                  {'id': 3, 'name': 'Original owner'},
                  {'id': 7, 'name': 'New owner'},
                ],
              });
            case ('POST', '/follow-ups/12/actions'):
              expect(request.data, {
                'action': 'assign',
                'notes': 'Handover agreed',
                'assigned_user_id': 7,
              });
              assignee = 'New owner';
              return response({...row, 'assigned_to': assignee});
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
          canEdit: false,
          canAssign: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    Future<void> tap(String label) async {
      await tester.tap(find.text(label).last);
      await tester.pumpAndSettle();
    }

    await tap('Renew maintenance');
    expect(find.text('Reassign'), findsOneWidget);
    expect(find.text('Add comment'), findsNothing);
    await tap('Load assignees');
    await tester.tap(find.byType(DropdownButton<int>));
    await tester.pumpAndSettle();
    expect(find.text('Original owner'), findsNothing);
    await tap('New owner');
    await tester.enterText(
      find.widgetWithText(TextField, 'Notes'),
      'Handover agreed',
    );
    await tester.pumpAndSettle();
    await tap('Save action');
    expect(find.text('Due · New owner'), findsOneWidget);
  });

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
