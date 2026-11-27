import 'dart:convert';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/my_attendance_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore;

void main() {
  testWidgets(
    'Offline attendance opens saved history without allowing punches',
    (tester) async {
      const sqlite = MethodChannel('com.tekartik.sqflite');
      const scope = '["https://example.test/api/v1",5,7]';
      final messenger = tester.binding.defaultBinaryMessenger;
      databaseFactory = databaseFactorySqflitePlugin;
      final reads = <String>[];
      messenger.setMockMethodCallHandler(sqlite, (call) async {
        switch (call.method) {
          case 'getDatabasesPath':
            return '/test';
          case 'openDatabase':
            return {'id': 1};
          case 'execute':
            return null;
          case 'query':
            final args = call.arguments as Map;
            if ((args['sql'] as String).toUpperCase().contains(
              'USER_VERSION',
            )) {
              return [
                {'user_version': 3},
              ];
            }
            final key = (args['arguments'] as List).first as String;
            reads.add(key);
            final rows = switch (key
                .split(':')
                .where((part) => part.startsWith('/attendance/'))
                .single) {
              '/attendance/today' => [
                {'check_in': '2026-11-27T09:00:00Z'},
              ],
              '/attendance/my' => [
                {'date': '2026-11-26', 'status': 'Present'},
              ],
              '/attendance/summary/monthly' => [
                {'present': 4},
              ],
              _ => throw StateError(key),
            };
            return [
              {
                'saved_at': DateTime.now().millisecondsSinceEpoch,
                'rows': jsonEncode(rows),
              },
            ];
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
            fail('Offline attendance should read SQLite without API requests');
          }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: MyAttendancePage(api: api, cacheScope: scope, offline: true),
        ),
      );
      await tester.pumpAndSettle();
      expect(reads, hasLength(3));
      expect(reads.every((key) => key.startsWith('$scope:')), isTrue);
      expect(find.text('Checked in'), findsOneWidget);
      expect(find.text('Check Out'), findsNothing);
      expect(find.textContaining('Saved · Present 4'), findsOneWidget);
      expect(find.text('Saved attendance history'), findsOneWidget);
      expect(find.text('2026-11-26'), findsOneWidget);
    },
  );

}
