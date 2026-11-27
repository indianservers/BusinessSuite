import 'dart:convert';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/my_leave_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore;

void main() {
  testWidgets('Saved leave balances and requests are available offline', (
    tester,
  ) async {
    const scope = '["https://example.test/api/v1",5,7]';
    const sqlite = MethodChannel('com.tekartik.sqflite');
    final messenger = tester.binding.defaultBinaryMessenger;
    final keys = <String>[];
    databaseFactory = databaseFactorySqflitePlugin;
    messenger.setMockMethodCallHandler(sqlite, (call) async {
      switch (call.method) {
        case 'getDatabasesPath':
          return '/test';
        case 'openDatabase':
          return {'id': 1};
        case 'execute':
          return null;
        case 'query':
          final query = call.arguments as Map;
          if ((query['sql'] as String).toUpperCase().contains('USER_VERSION')) {
            return [
              {'user_version': 3},
            ];
          }
          final key = (query['arguments'] as List).first as String;
          keys.add(key);
          return [
            {
              'saved_at': DateTime.now().millisecondsSinceEpoch,
              'rows': jsonEncode([
                {
                  'leave_type': {'name': 'Annual leave'},
                  if (key.contains('/leave/balance')) ...{
                    'available': 8,
                    'used': 2,
                    'pending': 1,
                  } else ...{
                    'id': 15,
                    'from_date': '2026-11-30',
                    'to_date': '2026-11-30',
                    'days_count': 1,
                    'status': 'Pending',
                  },
                },
              ]),
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
        ..httpClientAdapter = FakeAdapter((_) async {
          fail('Saved leave must open without a network request');
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: MyLeavePage(api: api, cacheScope: scope, offline: true),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      keys,
      unorderedEquals([
        '$scope:/leave/balance:${DateTime.now().year}',
        '$scope:/leave/my-requests:1',
      ]),
    );
    expect(find.text('Saved leave balances'), findsOneWidget);
    expect(find.text('8 days available'), findsOneWidget);
    expect(find.text('Saved leave requests'), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Apply for leave'),
          )
          .onPressed,
      isNull,
    );
    await tester.tap(find.text('Pending'));
    await tester.pumpAndSettle();
    expect(find.text('1 days · Pending'), findsOneWidget);
    expect(find.text('Cancel request'), findsNothing);
  });
}
