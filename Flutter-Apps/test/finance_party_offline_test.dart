import 'dart:convert';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/finance_party_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore;

void main() {
  testWidgets(
    'Finance loads saved outstanding bills without contacting the API',
    (tester) async {
      const scope = '["https://example.test/api/v1",5,7]';
      const channel = MethodChannel('com.tekartik.sqflite');
      final messenger = tester.binding.defaultBinaryMessenger;
      databaseFactory = databaseFactorySqflitePlugin;
      var reads = 0;
      messenger.setMockMethodCallHandler(channel, (call) async {
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
            reads++;
            expect(
              (args['arguments'] as List).first,
              '$scope:/fam/parties/4/outstanding:6',
            );
            return [
              {
                'saved_at': DateTime.now().millisecondsSinceEpoch,
                'rows': jsonEncode([
                  {
                    'openBills': 1,
                    'outstanding': '75.00',
                    'items': [
                      {
                        'bill_number': 'B-22',
                        'due_date': '2026-12-15',
                        'outstanding_amount': '75.00',
                      },
                    ],
                  },
                ]),
              },
            ];
          default:
            fail('Unexpected SQLite method ${call.method}');
        }
      });
      addTearDown(() {
        messenger.setMockMethodCallHandler(channel, null);
        databaseFactory = null;
      });
      final api = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            fail('Offline Finance made a request to ${request.path}');
          }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: FinancePartyPage(
            api: api,
            id: 4,
            cacheScope: scope,
            offline: true,
            scopeHeaders: const {'X-Suite-Branch': '6'},
            summary: const {'legal_name': 'Saved party'},
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('View outstanding bills'));
      await tester.pumpAndSettle();
      expect(find.text('Saved outstanding bills'), findsOneWidget);
      expect(find.text('B-22'), findsOneWidget);
      expect(find.text('Due 2026-12-15'), findsOneWidget);
      expect(reads, 1);
    },
  );
}
