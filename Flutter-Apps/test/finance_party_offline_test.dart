import 'dart:convert';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/finance_chart_page.dart';
import 'package:business_suite_mobile/features/finance_vouchers_page.dart';
import 'package:business_suite_mobile/features/finance_party_page.dart';
import 'package:business_suite_mobile/features/inventory_finance_report_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets('Stock Ledger pages and searches the shared inventory report', (
    tester,
  ) async {
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.path, '/srm/inventory/reports');
          expect(request.headers['X-Suite-Branch'], '6');
          expect(request.queryParameters['report'], 'ledger');
          expect(request.queryParameters['per_page'], 25);
          final page = request.queryParameters['page'];
          final search = request.queryParameters['search'];
          return response({
            'total': search == null ? 26 : 1,
            'items': [
              {
                'movement_number': search == 'cable'
                    ? 'Cable delivery'
                    : 'Movement $page',
                'opening_quantity': 8,
                'quantity_in': 3,
                'closing_quantity': 11,
              },
            ],
          });
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: InventoryFinanceReportPage(
          api: api,
          report: InventoryFinanceReport.stockLedger,
          scopeHeaders: const {'X-Suite-Branch': '6'},
          cacheScope: null,
          offline: false,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Movement 1'), findsOneWidget);
    expect(find.textContaining('Closing: 11'), findsOneWidget);
    await tester.tap(find.text('Next page'));
    await tester.pumpAndSettle();
    expect(find.text('Movement 2'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'cable');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();
    expect(find.text('Page 1'), findsOneWidget);
    expect(find.text('Cable delivery'), findsOneWidget);
  });

  testWidgets('Finance creates and edits a voucher draft with active ledgers', (
    tester,
  ) async {
    var created = false;
    var edited = false;
    final voucher = <String, dynamic>{
      'id': 7,
      'voucher_number': 'V-007',
      'status': 'draft',
    };
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Branch'], '6');
          switch ((request.method, request.path)) {
            case ('GET', '/fam/vouchers'):
              return response({
                'items': [if (created) voucher],
              });
            case ('GET', '/fam/voucher-types'):
              return response({
                'items': [
                  {'id': 2, 'voucher_type_name': 'Journal', 'active': true},
                ],
              });
            case ('GET', '/fam/ledgers'):
              return response({
                'items': [
                  {'id': 8, 'ledger_name': 'Bank', 'active': true},
                  {'id': 9, 'ledger_name': 'Sales', 'active': true},
                  {'id': 10, 'ledger_name': 'Inactive ledger', 'active': false},
                ],
              });
            case ('POST', '/fam/vouchers'):
              expect(request.data, {
                'voucher_type_id': 2,
                'voucher_date': matches(RegExp(r'^\d{4}-\d{2}-\d{2}$')),
                'lines': [
                  {
                    'ledger_id': 8,
                    'debit_amount': '250.00',
                    'credit_amount': '0',
                    'cost_center_id': 42,
                    'narration': 'Bank deposit',
                  },
                  {
                    'ledger_id': 9,
                    'debit_amount': '0',
                    'credit_amount': '250.00',
                  },
                ],
              });
              created = true;
              voucher.addAll(request.data as Map<String, dynamic>);
              voucher['branch_id'] = 6;
              voucher['financial_year_id'] = 4;
              voucher['accounting_period_id'] = 5;
              (voucher['lines'][0] as Map<String, dynamic>)['party_id'] = 12;
              return response(voucher, 201);
            case ('PUT', '/fam/vouchers/7'):
              final payload = request.data as Map<String, dynamic>;
              expect(payload['reference_number'], 'REF-7');
              expect(payload['branch_id'], 6);
              expect(payload['financial_year_id'], 4);
              expect(payload['accounting_period_id'], 5);
              expect(payload['lines'], voucher['lines']);
              edited = true;
              voucher.addAll(payload);
              return response(voucher);
            case ('GET', '/fam/vouchers/7'):
              return response(voucher);
            default:
              throw StateError(request.path);
          }
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: FinanceVouchersPage(
          api: api,
          canCreate: true,
          canEdit: true,
          scopeHeaders: const {'X-Suite-Branch': '6'},
        ),
      ),
    );
    await tester.pumpAndSettle();
    Future<void> tap(Finder finder) async {
      await tester.ensureVisible(finder);
      await tester.tap(finder);
      await tester.pumpAndSettle();
    }

    await tap(find.text('New voucher'));
    await tap(
      find.widgetWithText(DropdownButtonFormField<int>, 'Voucher type'),
    );
    await tap(find.text('Journal').last);
    await tap(find.widgetWithText(DropdownButtonFormField<int>, 'Ledger 1'));
    expect(find.text('Inactive ledger'), findsNothing);
    await tap(find.text('Bank').last);
    await tap(find.widgetWithText(DropdownButtonFormField<int>, 'Ledger 2'));
    await tap(find.text('Sales').last);
    for (final label in ['Amount 1', 'Amount 2']) {
      final field = find.widgetWithText(TextFormField, label);
      await tester.ensureVisible(field);
      await tester.enterText(field, '250.00');
    }
    for (final (label, value) in [
      ('Cost center 1', '42'),
      ('Line narration 1', 'Bank deposit'),
    ]) {
      final field = find.widgetWithText(TextFormField, label);
      await tester.ensureVisible(field);
      await tester.enterText(field, value);
    }
    await tester.pumpAndSettle();
    expect(find.text('Debit 250.00 · Credit 250.00'), findsOneWidget);
    expect(find.text('Difference 0.00'), findsOneWidget);
    await tap(find.text('Save voucher draft'));
    expect(created, isTrue);
    expect(find.text('V-007'), findsOneWidget);
    await tap(find.text('Edit draft'));
    expect(find.text('Bank deposit'), findsOneWidget);
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Reference number'),
      'REF-7',
    );
    await tap(find.text('Save voucher draft'));
    expect(edited, isTrue);
    expect(find.text('REF-7'), findsOneWidget);
  });

  testWidgets('Finance confirms posting, reversal, and cancellation', (
    tester,
  ) async {
    final paths = <String>[];
    final voucher = {
      'id': 7,
      'voucher_number': 'V-007',
      'voucher_date': '2026-11-27',
      'status': 'draft',
      'total_debit': '250.00',
      'total_credit': '250.00',
      'source_module': 'fam',
    };
    final reversal = {
      ...voucher,
      'id': 11,
      'voucher_number': 'REV-V-007',
      'reversed_voucher_id': 7,
    };
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Branch'], '6');
          paths.add(request.path);
          if (request.path == '/fam/vouchers/7/post') {
            expect(request.method, 'POST');
            voucher['status'] = 'posted';
            return response(voucher);
          }
          if (request.path == '/fam/vouchers/7/reverse') {
            expect(request.method, 'POST');
            voucher['status'] = 'reversed';
            voucher['reversed_voucher_id'] = 11;
            return response(reversal, 201);
          }
          if (request.path == '/fam/vouchers/11/cancel') {
            expect(request.method, 'POST');
            expect(request.data, {'reason': 'Incorrect reversal'});
            reversal['status'] = 'cancelled';
            reversal['cancellation_reason'] = 'Incorrect reversal';
            return response(reversal);
          }
          return switch (request.path) {
            '/fam/vouchers' => response({
              'items': [voucher],
            }),
            '/fam/vouchers/7' => response({
              ...voucher,
              'lines': [
                {
                  'ledger_id': 8,
                  'debit_amount': '250.00',
                  'credit_amount': '0.00',
                },
                {
                  'ledger_id': 9,
                  'debit_amount': '0.00',
                  'credit_amount': '250.00',
                },
              ],
            }),
            '/fam/vouchers/11' => response(reversal),
            _ => throw StateError(request.path),
          };
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: FinanceVouchersPage(
          api: api,
          canPost: true,
          canCancel: true,
          canReverse: true,
          scopeHeaders: const {'X-Suite-Branch': '6'},
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'missing');
    await tester.pumpAndSettle();
    expect(find.text('No matching vouchers'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'v-007');
    await tester.pumpAndSettle();
    await tester.tap(find.text('V-007'));
    await tester.pumpAndSettle();
    expect(find.text('Ledger #8'), findsOneWidget);
    expect(find.text('Debit 250.00\nCredit 0.00'), findsOneWidget);
    expect(paths, ['/fam/vouchers', '/fam/vouchers/7']);
    await tester.tap(find.text('Post voucher'));
    await tester.pumpAndSettle();
    expect(paths, ['/fam/vouchers', '/fam/vouchers/7']);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(paths, ['/fam/vouchers', '/fam/vouchers/7']);
    await tester.tap(find.text('Post voucher'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm posting'));
    await tester.pumpAndSettle();
    expect(paths.where((path) => path.endsWith('/post')), hasLength(1));
    expect(find.text('2026-11-27 · posted'), findsOneWidget);
    expect(find.text('Post voucher'), findsNothing);
    await tester.tap(find.text('Reverse voucher'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm reversal'));
    await tester.pumpAndSettle();
    expect(find.text('2026-11-27 · reversed'), findsOneWidget);
    await tester.tap(find.text('Linked voucher'));
    await tester.pumpAndSettle();
    expect(find.text('2026-11-27 · draft'), findsOneWidget);
    await tester.tap(find.text('Cancel voucher'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm cancellation'));
    await tester.pumpAndSettle();
    expect(paths, isNot(contains('/fam/vouchers/11/cancel')));
    await tester.enterText(find.byType(TextField), 'Incorrect reversal');
    await tester.tap(find.text('Confirm cancellation'));
    await tester.pumpAndSettle();
    expect(find.text('2026-11-27 · cancelled'), findsOneWidget);
    expect(find.text('Incorrect reversal'), findsOneWidget);
  });

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
