import 'dart:convert';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/finance_chart_page.dart';
import 'package:business_suite_mobile/features/finance_party_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets(
    'Finance chart browses ledger groups and searches the shared list',
    (tester) async {
      var requests = 0;
      final api = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            expect(request.path, '/fam/chart-of-accounts');
            expect(request.headers['X-Suite-Branch'], '6');
            requests++;
            return response({
              'groups': [
                {
                  'id': 1,
                  'group_name': 'Current assets',
                  'nature': 'asset',
                  'system_group': true,
                },
                {'id': 2, 'group_name': 'Expenses', 'nature': 'expense'},
              ],
              'ledgers': [
                {
                  'ledger_group_id': 1,
                  'ledger_code': 'A001',
                  'ledger_name': 'Bank account',
                  'active': true,
                },
                {
                  'ledger_group_id': 2,
                  'ledger_code': 'E001',
                  'ledger_name': 'Office supplies',
                  'active': false,
                },
              ],
            });
          }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: FinanceChartPage(
            api: api,
            scopeHeaders: const {'X-Suite-Branch': '6'},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Bank account'), findsOneWidget);
      expect(find.text('Office supplies'), findsOneWidget);
      expect(find.text('Inactive'), findsOneWidget);
      await tester.tap(find.text('Ledger groups (2)'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Current assets'));
      await tester.pumpAndSettle();
      expect(find.text('Office supplies'), findsNothing);
      await tester.enterText(find.byType(TextField), 'a001');
      await tester.pumpAndSettle();
      expect(find.text('Bank account'), findsOneWidget);
      expect(requests, 1);
    },
  );

  testWidgets(
    'Finance loads saved details, bills, and statements without contacting the API',
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
            expect((args['arguments'] as List).first, switch (reads) {
              1 => '$scope:/fam/parties/4:6',
              2 => '$scope:/fam/parties/4/outstanding:6',
              _ => '$scope:/fam/parties/4/statement:6',
            });
            return [
              {
                'saved_at': DateTime.now().millisecondsSinceEpoch,
                'rows': jsonEncode([
                  {
                    'legal_name': 'Saved party record',
                    'payment_terms_days': 30,
                    'contacts': [
                      {'name': 'Accounts desk'},
                    ],
                    'openBills': 1,
                    'outstanding': '75.00',
                    'party': {'legal_name': 'Saved party'},
                    'billReferences': [
                      {'id': 1, 'bill_number': 'B-22', 'status': 'Open'},
                      {'id': 2, 'bill_number': 'R-7', 'status': 'Closed'},
                    ],
                    'allocations': [
                      {
                        'from_bill_reference_id': 2,
                        'to_bill_reference_id': 1,
                        'allocated_amount': '25.00',
                      },
                    ],
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
      expect(find.text('Saved party details'), findsOneWidget);
      expect(find.text('Saved party record'), findsOneWidget);
      expect(find.text('Accounts desk'), findsOneWidget);
      await tester.tap(find.text('View outstanding bills'));
      await tester.pumpAndSettle();
      expect(find.text('Saved outstanding bills'), findsOneWidget);
      expect(find.text('B-22'), findsOneWidget);
      expect(find.text('Due 2026-12-15'), findsOneWidget);
      expect(reads, 2);
      await tester.tap(find.text('View statement'));
      await tester.pumpAndSettle();
      expect(find.text('Saved statement'), findsOneWidget);
      expect(find.text('B-22 · Open'), findsOneWidget);
      expect(find.text('R-7 → B-22'), findsOneWidget);
      expect(reads, 3);
    },
  );
}
