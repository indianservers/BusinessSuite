import 'dart:async';
import 'dart:convert';

import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/crm_offline_edits.dart';
import 'package:business_suite_mobile/core/inventory_offline_creates.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/core/notes_offline_cache.dart';
import 'package:business_suite_mobile/core/sales_order_drafts.dart';
import 'package:business_suite_mobile/features/crm_lead_page.dart';
import 'package:business_suite_mobile/features/crm_contact_page.dart';
import 'package:business_suite_mobile/features/crm_deal_page.dart';
import 'package:business_suite_mobile/features/crm_quotation_page.dart';
import 'package:business_suite_mobile/features/crm_quotation_line_page.dart';
import 'package:business_suite_mobile/features/crm_new_lead_page.dart';
import 'package:business_suite_mobile/features/company_profile_panel.dart';
import 'package:business_suite_mobile/features/branch_settings_panel.dart';
import 'package:business_suite_mobile/features/branch_membership_page.dart';
import 'package:business_suite_mobile/features/lead_sources_panel.dart';
import 'package:business_suite_mobile/features/starter_values_panel.dart';
import 'package:business_suite_mobile/features/gst_invoice_page.dart';
import 'package:business_suite_mobile/features/inventory_warehouse_form.dart';
import 'package:business_suite_mobile/features/inventory_tracking_form.dart';
import 'package:business_suite_mobile/features/inventory_procurement_page.dart';
import 'package:business_suite_mobile/features/inventory_purchase_order_form.dart';
import 'package:business_suite_mobile/features/my_attendance_page.dart';
import 'package:business_suite_mobile/features/my_leave_page.dart';
import 'package:business_suite_mobile/features/my_payslips_page.dart';
import 'package:business_suite_mobile/features/my_roster_page.dart';
import 'package:business_suite_mobile/features/notes_page.dart';
import 'package:business_suite_mobile/features/finance_party_page.dart';
import 'package:business_suite_mobile/features/business_defaults_panel.dart';
import 'package:business_suite_mobile/features/sales_order_page.dart';
import 'package:business_suite_mobile/features/sales_order_drafts_page.dart';
import 'package:business_suite_mobile/features/suite_dashboard.dart';
import 'package:business_suite_mobile/main.dart';
import 'package:dio/dio.dart';
import 'package:flutter/services.dart';
import 'package:sqflite/sqflite.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void mockUnavailableSqlite(WidgetTester tester) {
  const sqlite = MethodChannel('com.tekartik.sqflite');
  final messenger = tester.binding.defaultBinaryMessenger;
  databaseFactory = databaseFactorySqflitePlugin;
  messenger.setMockMethodCallHandler(sqlite, (call) async {
    expect(call.method, 'getDatabasesPath');
    throw PlatformException(code: 'cache_unavailable');
  });
  addTearDown(() {
    messenger.setMockMethodCallHandler(sqlite, null);
    databaseFactory = null;
  });
}

void main() {
  testWidgets('My Payslips opens history and sends a query for that record', (
    tester,
  ) async {
    RequestOptions? sent;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          switch (request.path) {
            case '/payroll/my-payslips':
              return response([
                {
                  'id': 71,
                  'month': 4,
                  'year': 2024,
                  'net_salary': '20000',
                  'currency': 'INR',
                  'financial_year': '2024–25',
                },
              ]);
            case '/payroll/payslip':
              expect(
                request.queryParameters.containsKey('employee_id'),
                isFalse,
              );
              if (request.queryParameters['year'] != 2024) {
                return response({'detail': 'Payslip not found'}, 404);
              }
              expect(request.queryParameters['month'], 4);
              return response({
                'payroll_record_id': 71,
                'net_salary': '20000',
                'currency': 'INR',
                'payroll_status': 'Locked',
              });
            case '/payroll/payslip-queries':
              sent = request;
              return response({'id': 12}, 201);
            default:
              throw StateError('Unexpected request: ${request.path}');
          }
        }),
    );
    await tester.pumpWidget(MaterialApp(home: MyPayslipsPage(api: api)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Available payslips'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('April 2024'));
    await tester.pumpAndSettle();
    expect(find.text('Net pay · April 2024'), findsOneWidget);
    expect(find.text('Download PDF'), findsOneWidget);
    final question = find.byType(TextField);
    await tester.ensureVisible(question);
    await tester.enterText(question, 'Please check the adjustment.');
    await tester.pumpAndSettle();
    final send = find.text('Send query to Payroll');
    await tester.ensureVisible(send);
    await tester.tap(send);
    await tester.pumpAndSettle();
    expect(sent?.method, 'POST');
    expect(sent?.data, {
      'payroll_record_id': 71,
      'subject': 'Payslip query: April 2024',
      'description': 'Please check the adjustment.',
      'priority': 'Medium',
    });
    expect(find.text('Payslip query sent to Payroll.'), findsOneWidget);
  });

  testWidgets('My Roster loads only my shifts from the web roster API', (
    tester,
  ) async {
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.path, '/hrms/shift-roster');
          expect(request.queryParameters['employeeId'], 27);
          final from = DateTime.parse(
            request.queryParameters['from'] as String,
          );
          final to = DateTime.parse(request.queryParameters['to'] as String);
          expect(
            DateTime.utc(
              to.year,
              to.month,
              to.day,
            ).difference(DateTime.utc(from.year, from.month, from.day)).inDays,
            7,
          );
          return response({
            'rosters': [
              {
                'employeeId': 27,
                'rosterDate': '2026-11-27',
                'shift': {'name': 'Morning', 'code': 'AM'},
                'status': 'published',
              },
              {'employeeId': 27, 'rosterDate': '2026-11-28'},
              {
                'employeeId': 28,
                'shift': {'name': 'Someone else’s shift'},
              },
            ],
          });
        }),
    );
    final user = SessionUser.fromJson({
      'id': 2,
      'email': 'employee@example.test',
      'employee_id': 27,
    });
    await tester.pumpWidget(
      MaterialApp(
        home: MyRosterPage(api: api, employeeId: user.employeeId),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Morning'), findsOneWidget);
    expect(find.text('2026-11-27 · AM'), findsOneWidget);
    expect(find.text('Weekly Off'), findsOneWidget);
    expect(find.text('Someone else’s shift'), findsNothing);
  });

  test(
    'Queued purchase drafts preserve retry identity and replace rejections',
    () async {
      FlutterSecureStorage.setMockInitialValues({});
      const base = 'https://example.test/api/v1';
      final drafts = SalesOrderDrafts.purchaseOrders('["$base",5,7]');
      const operation = '08992dd0-1223-4fad-aafe-c47922d7bb8c';
      final payload = {
        'vendor_id': 22,
        'vendor_name': 'Supplier',
        'lines': [
          {'product_id': 3, 'warehouse_id': 6, 'quantity': '2'},
        ],
      };
      await drafts.save(operation, payload, branch: '6');
      final requests = <RequestOptions>[];
      final api = ApiClient(
        baseUrl: base,
        store: MemoryStore(),
        transport: Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            requests.add(request);
            return switch (requests.length) {
              1 => response({}, 503),
              2 => response({'detail': 'Invalid quantity'}, 422),
              _ => response({'id': 9, 'status': 'draft'}, 201),
            };
          }),
      );
      await api.acceptTokens({'access_token': 'a', 'refresh_token': 'b'});
      await drafts.sync(api);
      expect(await drafts.entries(), hasLength(1));
      await drafts.sync(api);
      expect((await drafts.entries()).single['status'], 422);
      expect(requests, hasLength(2));
      for (final request in requests) {
        expect(
          request.path,
          '/srm/procurement/purchase-orders/drafts/offline-create',
        );
        expect(request.headers['X-Suite-Organization'], '7');
        expect(request.headers['X-Suite-Branch'], '6');
        expect(request.headers['X-Offline-Operation'], operation);
        expect(request.data, payload);
      }
      const replacement = '6a52216b-a4e1-4e4a-980d-ea178e9512cd';
      final corrected = {
        ...payload,
        'lines': [
          {'product_id': 3, 'warehouse_id': 6, 'quantity': '1'},
        ],
      };
      await drafts.save(
        replacement,
        corrected,
        branch: '6',
        replaceRejected: operation,
      );
      expect((await drafts.entries()).single['operation'], replacement);
      await drafts.sync(api);
      expect(await drafts.entries(), isEmpty);
      expect(requests.last.headers['X-Offline-Operation'], replacement);
      expect(requests.last.headers['X-Suite-Branch'], '6');
      expect(requests.last.data, corrected);
    },
  );

  testWidgets('A rejected purchase draft reopens with its saved selections', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    addTearDown(() => FlutterSecureStorage.setMockInitialValues({}));
    mockUnavailableSqlite(tester);
    const base = 'https://example.test/api/v1';
    const scope = '["$base",5,7]';
    final drafts = SalesOrderDrafts.purchaseOrders(scope);
    await drafts.save('rejected-operation', {
      'vendor_id': 22,
      'vendor_name': 'Saved supplier',
      'expected_date': '2026-12-02',
      'notes': 'Original delivery instructions',
      'lines': [
        {
          'product_id': 3,
          'warehouse_id': 6,
          'quantity': '2',
          'unit_price': '12.50',
        },
      ],
    }, branch: '6');
    final api = ApiClient(
      baseUrl: base,
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.path == '/srm/inventory/warehouses') {
            expect(request.headers['X-Suite-Branch'], '6');
            return response({
              'items': [
                {'id': 6, 'warehouse_name': 'Saved warehouse'},
              ],
            });
          }
          expect(
            request.path,
            '/srm/procurement/purchase-orders/drafts/offline-create',
          );
          return response({'detail': 'Quantity needs correction'}, 422);
        }),
    );
    await tester.runAsync(() async {
      await api.acceptTokens({'access_token': 'a', 'refresh_token': 'b'});
      await drafts.sync(api);
    });
    await tester.pumpWidget(
      MaterialApp(
        home: SalesOrderDraftsPage(
          api: api,
          drafts: drafts,
          correctPurchaseDraft: (draft) => InventoryPurchaseOrderForm(
            api: api,
            scopeHeaders: {'X-Suite-Branch': draft['branch'] as String},
            cacheScope: scope,
            rejectedDraft: draft,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Saved supplier'));
    await tester.pumpAndSettle();
    expect(find.text('Correct purchase order draft'), findsOneWidget);
    expect(find.text('Product #3'), findsOneWidget);
    expect(find.text('Saved warehouse'), findsOneWidget);
    expect(find.text('Expected date · 2026-12-02'), findsOneWidget);
    final notes = find.widgetWithText(TextFormField, 'Notes');
    expect(find.text('Original delivery instructions'), findsOneWidget);
    await tester.ensureVisible(notes);
    await tester.enterText(notes, 'Deliver to receiving');
    final quantity = find.widgetWithText(TextFormField, 'Order quantity');
    await tester.ensureVisible(quantity);
    await tester.enterText(quantity, '1');
    final save = find.text('Save corrected draft');
    await tester.ensureVisible(save);
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(find.text('Awaiting sync'), findsOneWidget);
    final entry = (await drafts.entries()).single;
    expect(entry['operation'], isNot('rejected-operation'));
    expect(entry['branch'], '6');
    expect(entry['payload']['expected_date'], '2026-12-02');
    expect(entry['payload']['notes'], 'Deliver to receiving');
    expect(entry['payload']['lines'], [
      {
        'product_id': 3,
        'warehouse_id': 6,
        'quantity': '1',
        'unit_price': '12.50',
        'tax_amount': '0',
      },
    ]);
  });

  testWidgets('Purchase order cancellation records a reason and refreshes', (
    tester,
  ) async {
    const document = '/srm/documents/purchase-orders/72';
    final version = 'a' * 64;
    RequestOptions? cancelled;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          switch (request.path) {
            case document:
              return response({'version': version, 'editable': false});
            case '$document/cancel':
              expect(request.method, 'POST');
              cancelled = request;
              return response({
                'record': {'id': 72, 'status': 'cancelled'},
              });
            case '/srm/procurement/purchase-orders/72':
              return response({
                'id': 72,
                'po_number': 'PO-72',
                'status': cancelled == null ? 'ordered' : 'cancelled',
              });
            default:
              throw StateError('Unexpected request: ${request.path}');
          }
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: InventoryProcurementPage(
          api: api,
          kind: ProcurementRecord.order,
          summary: const {'id': 72},
          scopeHeaders: const {'X-Suite-Branch': '6'},
          cacheScope: null,
          offline: false,
          canIssue: true,
          canReceive: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel with reason'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm cancellation'));
    await tester.pumpAndSettle();
    expect(cancelled, isNull);
    await tester.enterText(
      find.byType(TextFormField),
      'Supplier cannot fulfil',
    );
    await tester.tap(find.text('Confirm cancellation'));
    await tester.pumpAndSettle();
    expect(cancelled?.headers['X-Suite-Branch'], '6');
    expect(cancelled?.data, {
      'version': version,
      'reason': 'Supplier cannot fulfil',
      'request_id': matches(RegExp(r'^[0-9a-f-]{36}$')),
    });
    expect(find.text('PO-72'), findsOneWidget);
    expect(find.text('cancelled'), findsOneWidget);
    expect(find.text('Receive goods'), findsNothing);
    expect(find.text('Cancel with reason'), findsNothing);
  });

  final purchaseConnections = ValueVariant({true, false});
  testWidgets(
    'Purchase order drafts preserve items and retry interrupted saves',
    (tester) async {
      final interrupted = purchaseConnections.currentValue!;
      FlutterSecureStorage.setMockInitialValues({});
      addTearDown(() => FlutterSecureStorage.setMockInitialValues({}));
      mockUnavailableSqlite(tester);
      const scope = '["https://example.test/api/v1",5,7]';
      final writes = <RequestOptions>[];
      final api = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            expect(request.headers['X-Suite-Branch'], '6');
            switch (request.path) {
              case '/master-data/companies':
                expect(request.queryParameters['source'], 'srm');
                return response({
                  'items': [
                    {'id': 4, 'name': 'Paper supplier'},
                  ],
                });
              case '/srm/inventory/items':
                return response({
                  'items': [
                    {'id': 3, 'item_name': 'Office paper'},
                    {'id': 5, 'item_name': 'Ink cartridge'},
                  ],
                });
              case '/srm/inventory/warehouses':
                return response({
                  'items': [
                    {'id': 6, 'warehouse_name': 'Main warehouse'},
                    {'id': 7, 'warehouse_name': 'Annex warehouse'},
                  ],
                });
              case '/srm/procurement/purchase-orders/drafts/offline-create':
                expect(request.method, 'POST');
                expect(request.headers['X-Suite-Organization'], '7');
                writes.add(request);
                if (interrupted && writes.length == 1) {
                  throw DioException(
                    requestOptions: request,
                    type: DioExceptionType.connectionError,
                  );
                }
                return response({'id': 9, 'status': 'draft'}, 201);
              default:
                throw StateError('Unexpected request: ${request.path}');
            }
          }),
      );
      final navigator = GlobalKey<NavigatorState>();
      await tester.pumpWidget(
        MaterialApp(navigatorKey: navigator, home: const Scaffold()),
      );
      final saved = navigator.currentState!.push<Json>(
        MaterialPageRoute(
          builder: (_) => InventoryPurchaseOrderForm(
            api: api,
            scopeHeaders: const {'X-Suite-Branch': '6'},
            cacheScope: scope,
          ),
        ),
      );
      await tester.pumpAndSettle();
      Future<void> tap(String label) async {
        final finder = find.text(label).last;
        await tester.ensureVisible(finder);
        await tester.tap(finder);
        await tester.pumpAndSettle();
      }

      await tap('Choose vendor');
      await tap('Paper supplier');
      await tap('Choose product');
      await tap('Office paper');
      await tap('Warehouse');
      await tap('Main warehouse');
      final quantity = find.widgetWithText(TextFormField, 'Order quantity');
      await tester.enterText(quantity, '0');
      await tap('Create purchase order draft');
      expect(writes, isEmpty);
      await tester.ensureVisible(quantity);
      await tester.enterText(quantity, '4');
      await tap('Add item');
      await tap('Choose product');
      await tap('Ink cartridge');
      await tap('Warehouse');
      await tap('Annex warehouse');
      final secondPrice = find
          .widgetWithText(TextFormField, 'Order unit price')
          .last;
      await tester.ensureVisible(secondPrice);
      await tester.enterText(secondPrice, '12.50');
      await tap('Add item');
      final remove = find.byTooltip('Remove item 3');
      await tester.ensureVisible(remove);
      await tester.tap(remove);
      await tester.pumpAndSettle();
      await tap('Create purchase order draft');
      final operation = writes.single.headers['X-Offline-Operation'];
      expect(operation, matches(RegExp(r'^[0-9a-f-]{36}$')));
      if (interrupted) {
        expect(await saved, {'local': true});
        final drafts = SalesOrderDrafts.purchaseOrders(scope);
        expect((await drafts.entries()).single['operation'], operation);
        await tester.runAsync(() async {
          await api.acceptTokens({'access_token': 'a', 'refresh_token': 'b'});
          await drafts.sync(api);
        });
        expect(await drafts.entries(), isEmpty);
        expect(writes, hasLength(2));
        expect(writes.last.headers['X-Offline-Operation'], operation);
        expect(writes.last.data, writes.first.data);
      } else {
        expect(await saved, {'id': 9, 'status': 'draft'});
      }
      expect(writes.first.data, {
        'vendor_id': 4,
        'vendor_name': 'Paper supplier',
        'lines': [
          {
            'product_id': 3,
            'warehouse_id': 6,
            'quantity': '4',
            'unit_price': '0',
            'tax_amount': '0',
          },
          {
            'product_id': 5,
            'warehouse_id': 7,
            'quantity': '1',
            'unit_price': '12.50',
            'tax_amount': '0',
          },
        ],
      });
    },
    variant: purchaseConnections,
  );

  testWidgets('A purchase order can be issued and receive linked goods', (
    tester,
  ) async {
    final writes = <RequestOptions>[];
    final issueRequests = <RequestOptions>[];
    RequestOptions? edited;
    RequestOptions? revised;
    RequestOptions? archived;
    RequestOptions? pdfRequest;
    const document = '/srm/documents/purchase-orders/72';
    var issued = false;
    final version = 'a' * 64;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Branch'], '6');
          if (request.path == '/srm/documents/purchase-orders/73') {
            if (request.method == 'DELETE') archived = request;
            return response({
              'version': version,
              'editable': archived == null,
              'removed': archived != null,
              'record': {
                'id': 73,
                'po_number': 'PO-73',
                'status': archived == null ? 'draft' : 'archived',
              },
            });
          }
          if (request.path == document && request.method == 'PATCH') {
            edited = request;
            return response({
              'record': {'id': 72, 'status': 'draft'},
            });
          }
          if (request.path == '$document/pdf') {
            pdfRequest = request;
            return response({'message': 'Unexpected response'});
          }
          if (request.path == '$document/issue') {
            expect(request.method, 'POST');
            issueRequests.add(request);
            if (issueRequests.length == 1) {
              return response({'detail': 'Try issuing again.'}, 503);
            }
            issued = true;
            return response({
              'record': {'id': 72, 'status': 'ordered'},
            });
          }
          if (request.path == '$document/revise') {
            revised = request;
            return response({
              'record': {'id': 73, 'status': 'draft'},
            }, 201);
          }
          if (request.method == 'POST') {
            writes.add(request);
            return response({'id': 80, 'grn_number': 'GRN-80'}, 201);
          }
          return switch (request.path) {
            document => response({
              'version': version,
              'editable': !issued,
              'record': {
                'expected_date': '2026-12-01',
                'notes': 'Existing notes',
                'lines': [
                  {
                    'id': 19,
                    'description': 'Printer paper',
                    'quantity': 2,
                    'unit_price': 0,
                    'tax_amount': 0,
                  },
                  {
                    'id': 20,
                    'description': 'Ink cartridge',
                    'quantity': 5,
                    'unit_price': 0,
                    'tax_amount': 0,
                  },
                ],
              },
              'history': [
                if (issued)
                  {
                    'action': 'document_issued',
                    'reason': 'Supplier confirmed',
                    'before': {'status': 'draft', 'po_number': 'PO-72'},
                    'after': {
                      'record': {'status': 'ordered'},
                    },
                  },
              ],
            }),
            '/srm/procurement/purchase-orders/72' => response({
              'id': 72,
              'po_number': 'PO-72',
              'expected_date': edited == null ? '2026-12-01' : '2026-12-03',
              'status': issued
                  ? (writes.isEmpty ? 'ordered' : 'partially_received')
                  : 'draft',
              'lines': [
                {
                  'id': 19,
                  'description': 'Printer paper',
                  'quantity': 2,
                  'received_quantity': writes.isEmpty ? 0 : 1.25,
                },
                {
                  'id': 20,
                  'description': 'Ink cartridge',
                  'quantity': 5,
                  'received_quantity': writes.isEmpty ? 0 : 2,
                },
              ],
            }),
            '/srm/procurement/grn/80' => response({
              'id': 80,
              'grn_number': 'GRN-80',
              'purchase_order_id': 72,
            }),
            '/srm/procurement/purchase-orders/73' => response({
              'id': 73,
              'po_number': 'PO-73',
              'status': 'draft',
            }),
            _ => throw StateError('Unexpected request: ${request.path}'),
          };
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: InventoryProcurementPage(
          api: api,
          summary: const {'id': 72},
          kind: ProcurementRecord.order,
          scopeHeaders: const {'X-Suite-Branch': '6'},
          cacheScope: null,
          offline: false,
          canReceive: true,
          canIssue: true,
          canExport: true,
          canArchive: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Receive goods'), findsNothing);
    await tester.tap(find.text('Modify draft with reason'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Expected date'),
      '2026-12-03',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Reason'),
      'Supplier rescheduled',
    );
    await tester.tap(find.text('Save draft changes'));
    await tester.pumpAndSettle();
    expect(edited?.data, {
      'version': version,
      'reason': 'Supplier rescheduled',
      'request_id': matches(RegExp(r'^[0-9a-f-]{36}$')),
      'changes': {'expected_date': '2026-12-03'},
    });
    expect(find.text('2026-12-03'), findsOneWidget);
    final editLine = find.byTooltip('Edit Printer paper');
    if (editLine.evaluate().isEmpty) {
      await tester.drag(find.byType(ListView), const Offset(0, -350));
      await tester.pumpAndSettle();
    }
    await tester.ensureVisible(editLine);
    await tester.tap(editLine);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Unit price'),
      '12.50',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Reason'),
      'Correct agreed unit price',
    );
    await tester.tap(find.text('Save draft changes'));
    await tester.pumpAndSettle();
    expect((edited?.data as Map)['lines'], [
      {'id': 19, 'unit_price': '12.50'},
      {'id': 20},
    ]);
    await tester.drag(find.byType(ListView), const Offset(0, 400));
    await tester.pumpAndSettle();
    for (var attempt = 0; attempt < 2; attempt++) {
      await tester.tap(find.text('Issue purchase order'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Confirm issue'));
      await tester.pumpAndSettle();
      expect(issueRequests, hasLength(attempt));
      await tester.enterText(
        find.byType(TextFormField),
        '  Supplier confirmed  ',
      );
      await tester.tap(find.text('Confirm issue'));
      await tester.pumpAndSettle();
    }
    expect(issueRequests, hasLength(2));
    expect(issueRequests.first.data, {
      'version': version,
      'reason': 'Supplier confirmed',
      'request_id': matches(RegExp(r'^[0-9a-f-]{36}$')),
    });
    expect(issueRequests.last.data, issueRequests.first.data);
    expect(find.text('Issue purchase order'), findsNothing);
    await tester.tap(find.byTooltip('Document history'));
    await tester.pumpAndSettle();
    expect(find.text('Document issued'), findsOneWidget);
    expect(find.textContaining('Supplier confirmed'), findsOneWidget);
    await tester.tap(find.text('View saved values'));
    await tester.pumpAndSettle();
    expect(find.text('Status: draft'), findsOneWidget);
    expect(find.text('Status: ordered'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.pump(const Duration(seconds: 5));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save purchase order PDF'));
    await tester.pumpAndSettle();
    expect(pdfRequest?.responseType, ResponseType.bytes);
    expect(find.text('The server did not return a PDF.'), findsOneWidget);
    await tester.pump(const Duration(seconds: 5));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Receive goods'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Purchase order line'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Printer paper').last);
    await tester.pumpAndSettle();
    expect(find.text('Remaining quantity: 2.000'), findsOneWidget);
    final accepted = find.widgetWithText(TextFormField, 'Accepted quantity');
    await tester.enterText(accepted, '3');
    final post = find.text('Post goods receipt');
    await tester.ensureVisible(post);
    await tester.tap(post);
    await tester.pumpAndSettle();
    expect(writes, isEmpty);
    await tester.ensureVisible(accepted);
    await tester.enterText(accepted, '1.25');
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Rejected quantity'),
      '0.25',
    );
    final addLine = find.text('Add receipt item');
    await tester.ensureVisible(addLine);
    await tester.tap(addLine);
    await tester.pumpAndSettle();
    final chooseLine = find.text('Purchase order line').last;
    await tester.ensureVisible(chooseLine);
    await tester.tap(chooseLine);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ink cartridge').last);
    await tester.pumpAndSettle();
    final second = find.widgetWithText(TextFormField, 'Accepted quantity').last;
    await tester.ensureVisible(second);
    await tester.enterText(second, '2');
    await tester.ensureVisible(post);
    await tester.tap(post);
    await tester.pumpAndSettle();
    expect(writes.single.path, '/srm/procurement/grn');
    expect(writes.single.data, {
      'purchase_order_id': 72,
      'lines': [
        {
          'purchase_order_line_id': 19,
          'quantity': '1.500',
          'accepted_quantity': '1.25',
          'rejected_quantity': '0.25',
          'tax_amount': '0',
        },
        {
          'purchase_order_line_id': 20,
          'quantity': '2.000',
          'accepted_quantity': '2',
          'rejected_quantity': '0',
          'tax_amount': '0',
        },
      ],
    });
    expect(find.text('GRN-80'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.textContaining('Received: 1.25'), findsOneWidget);
    await tester.tap(find.text('Create revision draft'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), 'Update next delivery');
    await tester.tap(find.text('Create revised draft'));
    await tester.pumpAndSettle();
    expect(revised?.method, 'POST');
    expect(revised?.data, {
      'version': version,
      'reason': 'Update next delivery',
      'request_id': matches(RegExp(r'^[0-9a-f-]{36}$')),
    });
    expect(find.text('PO-73'), findsOneWidget);
    await tester.tap(find.text('Archive draft'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextFormField),
      'Duplicate revision draft',
    );
    await tester.tap(find.text('Confirm archive'));
    await tester.pumpAndSettle();
    expect(archived?.data, {
      'version': version,
      'reason': 'Duplicate revision draft',
      'request_id': matches(RegExp(r'^[0-9a-f-]{36}$')),
    });
    expect(find.text('archived'), findsOneWidget);
    expect(find.text('Archive draft'), findsNothing);
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('PO-72'), findsOneWidget);
    expect(find.text('partially_received'), findsOneWidget);
  });

  testWidgets(
    'Inventory tracking registers batches and product-scoped serials',
    (tester) async {
      final requests = <RequestOptions>[];
      final api = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            expect(request.headers['X-Suite-Branch'], '6');
            requests.add(request);
            if (request.method == 'POST') {
              return response({
                'id': 12,
                ...request.data as Map<String, dynamic>,
              }, 201);
            }
            return switch (request.path) {
              '/srm/inventory/items' => response({
                'items': [
                  {'id': 3, 'item_name': 'Ink cartridge', 'active': true},
                ],
              }),
              '/srm/inventory/warehouses' => response({'items': []}),
              '/srm/inventory/batches' => response({
                'items': [
                  {'id': 12, 'batch_number': 'LOT-12'},
                ],
              }),
              _ => throw StateError('Unexpected request: ${request.path}'),
            };
          }),
      );
      Future<void> tap(String label) async {
        final finder = find.text(label).last;
        await tester.ensureVisible(finder);
        await tester.tap(finder);
        await tester.pumpAndSettle();
      }

      Future<void> enter(String label, String value) async {
        final field = find.widgetWithText(TextFormField, label);
        await tester.ensureVisible(field);
        await tester.enterText(field, value);
        await tester.pumpAndSettle();
      }

      final navigator = GlobalKey<NavigatorState>();
      await tester.pumpWidget(
        MaterialApp(navigatorKey: navigator, home: const Scaffold()),
      );
      for (final serial in [false, true]) {
        unawaited(
          navigator.currentState!.push<Json>(
            MaterialPageRoute(
              builder: (_) => InventoryTrackingForm(
                api: api,
                scopeHeaders: const {'X-Suite-Branch': '6'},
                serial: serial,
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        await tap('Choose product');
        await tap('Ink cartridge');
        if (serial) {
          await enter('Serial number', 'SN-12');
          await tap('Choose batch (optional)');
          await tap('LOT-12');
          await tap('Save serial');
        } else {
          await enter('Batch number', ' LOT-12 ');
          await enter('Quantity', '8');
          await enter('Available quantity (optional)', '10');
          await tap('Save batch');
          expect(
            requests.where((request) => request.method == 'POST'),
            isEmpty,
          );
          await enter('Available quantity (optional)', '7');
          await tap('Save batch');
        }
      }
      final writes = requests
          .where((request) => request.method == 'POST')
          .toList();
      expect(writes.map((request) => request.path), [
        '/srm/inventory/batches',
        '/srm/inventory/serial-numbers',
      ]);
      expect(writes.first.data, {
        'product_id': 3,
        'batch_number': 'LOT-12',
        'quantity': '8',
        'available_quantity': '7',
        'unit_cost': '0',
        'status': 'available',
      });
      expect(writes.last.data, {
        'product_id': 3,
        'serial_number': 'SN-12',
        'batch_id': 12,
        'status': 'available',
      });
      expect(
        requests
            .singleWhere(
              (r) => r.method == 'GET' && r.path == '/srm/inventory/batches',
            )
            .queryParameters['product_id'],
        3,
      );
    },
  );

  testWidgets('Draft quotation date and terms edits use the shared record', (
    tester,
  ) async {
    final updates = <RequestOptions>[];
    final quote = <String, dynamic>{
      'id': 44,
      'quote_number': 'QT-44',
      'status': 'Draft',
      'issue_date': '2026-11-27',
      'expiry_date': '2026-12-27',
      'terms': 'Net 15',
    };
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'PATCH') {
            updates.add(request);
            quote.addAll(request.data as Map<String, dynamic>);
          }
          return response(quote);
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmQuotationPage(
          api: api,
          summary: const {'id': 44},
          offline: false,
          scopeHeaders: const {},
          canManage: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    final edit = find.text('Edit quotation');
    await tester.ensureVisible(edit);
    await tester.tap(edit);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Expiry date'),
      '2027-01-09',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Terms'),
      'Net 30',
    );
    final save = find.text('Save changes');
    await tester.ensureVisible(save);
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(updates.single.path, '/crm/quotations/44');
    expect(updates.single.data, {
      'expiry_date': '2027-01-09',
      'valid_until': '2027-01-09',
      'terms': 'Net 30',
      'terms_and_conditions': 'Net 30',
    });
    expect(find.text('Net 30'), findsOneWidget);
  });

  testWidgets('Quotation item can link to a shared catalog service', (
    tester,
  ) async {
    final writes = <RequestOptions>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.path == '/catalog/items') {
            expect(request.queryParameters['source'], 'crm');
            return response({
              'items': [
                {
                  'id': 81,
                  'kind': 'service',
                  'name': 'Support plan',
                  'price': 100,
                  'tax': 18,
                  'currency': 'INR',
                },
              ],
            });
          }
          writes.add(request);
          return response({'id': 44}, 201);
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmQuotationLinePage(
          api: api,
          quoteId: 8,
          scopeHeaders: const {},
          currency: 'INR',
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Choose from catalog'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Support plan'));
    await tester.pumpAndSettle();
    final discountType = find.byType(DropdownButtonFormField<String>);
    await tester.ensureVisible(discountType);
    await tester.tap(discountType);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Percentage').last);
    await tester.pumpAndSettle();
    final discount = find.widgetWithText(TextFormField, 'Discount');
    await tester.ensureVisible(discount);
    await tester.enterText(discount, '10');
    final save = find.text('Save item');
    await tester.ensureVisible(save);
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(writes.single.path, '/crm/quotes/8/lines');
    expect(writes.single.data, {
      'name': 'Support plan',
      'quantity': 1,
      'unit_price': 100,
      'tax_rate': 18,
      'item_type': 'service',
      'service_id': 81,
      'discount_type': 'percent',
      'discount_value': 10,
    });
  });

  testWidgets(
    'Draft quotation items use shared totals after add, edit, and remove',
    (tester) async {
      final writes = <RequestOptions>[];
      final line = <String, dynamic>{};
      final api = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            if (request.method != 'GET') {
              writes.add(request);
              if (request.method == 'DELETE') {
                line.clear();
              } else {
                line.addAll(request.data as Map<String, dynamic>);
                line['id'] = 8;
                line['line_total'] =
                    (line['unit_price'] as num) * (line['quantity'] as num);
              }
            }
            return response({
              'id': 44,
              'quote_number': 'QT-44',
              'status': 'Draft',
              'currency': 'INR',
              'grand_total': line['line_total'] ?? 0,
              'lines': [if (line.isNotEmpty) line],
            });
          }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: CrmQuotationPage(
            api: api,
            summary: const {'id': 44},
            offline: false,
            scopeHeaders: const {'X-Suite-Organization': '7'},
            canManage: true,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add item'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Item name'),
        'Training',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Unit price'),
        '200',
      );
      await tester.tap(find.text('Save item'));
      await tester.pumpAndSettle();
      expect(find.text('200 INR'), findsNWidgets(2));
      await tester.tap(find.text('Training'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Quantity'),
        '2',
      );
      await tester.tap(find.text('Save item'));
      await tester.pumpAndSettle();
      expect(writes.map((request) => request.path), [
        '/crm/quotes/44/lines',
        '/crm/quote-lines/8',
      ]);
      expect(writes.last.data, {'quantity': 2});
      expect(find.text('400 INR'), findsNWidgets(2));
      await tester.tap(find.text('Training'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Remove item'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(writes, hasLength(2));
      await tester.tap(find.text('Remove item'));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Remove item'),
        ),
      );
      await tester.pumpAndSettle();
      expect(writes.last.method, 'DELETE');
      expect(writes.last.path, '/crm/quote-lines/8');
      expect(find.text('Training'), findsNothing);
      expect(find.text('0 INR'), findsOneWidget);
    },
  );

  testWidgets('A quotation draft opens with its shared CRM deal link', (
    tester,
  ) async {
    final requests = <RequestOptions>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests.add(request);
          if (request.path == '/crm/deal-workspace/18/record') {
            return response({
              'id': 18,
              'name': 'Renewal',
              'company_id': 5,
              'currency': 'INR',
            });
          }
          return response({
            'id': 44,
            'quote_number': 'QT-RENEWAL',
            'status': 'Draft',
          });
        }),
    );
    const scope = {'X-Suite-Organization': '7'};
    await tester.pumpWidget(
      MaterialApp(
        home: CrmDealPage(
          api: api,
          summary: const {'id': 18},
          offline: false,
          scopeHeaders: scope,
          quotationBuilder: (record) => CrmQuotationPage(
            api: api,
            summary: record,
            offline: false,
            scopeHeaders: scope,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('New quotation'));
    await tester.pumpAndSettle();
    final create = find.text('Create draft quotation');
    await tester.ensureVisible(create);
    await tester.tap(create);
    await tester.pump();
    expect(requests.where((request) => request.method == 'POST'), isEmpty);
    for (final (label, value) in [
      ('Quotation number', 'QT-RENEWAL'),
      ('Issue date', '2026-11-27'),
      ('Expiry date', '2026-12-27'),
    ]) {
      await tester.enterText(find.widgetWithText(TextFormField, label), value);
    }
    await tester.ensureVisible(create);
    await tester.tap(create);
    await tester.pumpAndSettle();
    final created = requests.singleWhere((request) => request.method == 'POST');
    expect(created.path, '/crm/quotations');
    expect(created.headers['X-Suite-Organization'], '7');
    expect(created.data, {
      'quote_number': 'QT-RENEWAL',
      'issue_date': '2026-11-27',
      'expiry_date': '2026-12-27',
      'deal_id': 18,
      'company_id': 5,
      'currency': 'INR',
      'status': 'Draft',
    });
    expect(requests.last.path, '/crm/quotations/44');
    expect(find.text('QT-RENEWAL'), findsOneWidget);
  });

  testWidgets('Quotation versioning, sending and conversion use shared APIs', (
    tester,
  ) async {
    final writes = <RequestOptions>[];
    var status = 'Draft';
    var version = 1;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.path == '/srm/sales-orders/57') {
            expect(request.headers['X-Suite-Organization'], '7');
            return response({
              'id': 57,
              'order_number': 'SO-57',
              'status': 'draft',
            });
          }
          if (request.method == 'POST') {
            writes.add(request);
            final action = request.path.split('/').last;
            if (action == 'new-version') version++;
            status = switch (action) {
              'new-version' => 'Draft',
              'submit' => 'Pending Approval',
              'approve' => 'Approved',
              'send' => 'Sent',
              'accept' => 'Accepted',
              _ => throw StateError('Unexpected quotation action: $action'),
            };
          }
          return response({
            'id': 44,
            'quote_number': 'QT-44',
            'version_number': version,
            'status': status,
            'deal_id': 9,
            if (version > 1)
              'versions': [
                {'version_number': 1, 'created_at': '2026-11-27T10:00:00Z'},
              ],
            if (status == 'Accepted')
              'approvals': [
                {'status': 'approved', 'comments': 'Pricing reviewed'},
              ],
            if (status == 'Accepted') 'sentVersionNumber': 2,
            if (status == 'Accepted')
              'sentVersionEvidence': 'Provider accepted the quotation email',
            if (status == 'Accepted') 'converted_srm_sales_order_id': 57,
          });
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmQuotationPage(
          api: api,
          summary: const {'id': 44},
          offline: false,
          scopeHeaders: const {'X-Suite-Organization': '7'},
          canManage: true,
          canApprove: true,
          canSend: true,
          canViewSalesOrder: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Mark quotation as sent'), findsNothing);
    for (final (index, label) in [
      'Create new version',
      'Submit for approval',
      'Approve quotation',
      'Mark quotation as sent',
      'Accept and convert',
    ].indexed) {
      await tester.ensureVisible(find.text(label));
      await tester.tap(find.text(label));
      await tester.pumpAndSettle();
      expect(writes, hasLength(index));
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text(label),
        ),
      );
      await tester.pumpAndSettle();
    }
    expect(writes.map((request) => request.path), [
      '/crm/quotes/44/new-version',
      '/crm/quotes/44/submit',
      '/crm/quotes/44/approve',
      '/crm/quotes/44/send',
      '/crm/quotes/44/accept',
    ]);
    expect(
      writes.map((request) => request.headers['X-Suite-Organization']),
      everyElement('7'),
    );
    expect(find.text('2'), findsNWidgets(2));
    expect(find.text('Mark quotation as sent'), findsNothing);
    expect(find.text('Accepted'), findsOneWidget);
    expect(find.text('57'), findsOneWidget);
    final history = find.text('Version and approval history');
    await tester.ensureVisible(history);
    await tester.tap(history);
    await tester.pumpAndSettle();
    expect(find.text('Version 1'), findsOneWidget);
    expect(find.text('Pricing reviewed'), findsOneWidget);
    expect(find.text('Provider accepted the quotation email'), findsOneWidget);
    await tester.tap(history);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Open sales order'));
    await tester.tap(find.text('Open sales order'));
    await tester.pumpAndSettle();
    expect(find.text('SO-57'), findsOneWidget);
  });

  testWidgets('Issued quotation revisions open a separate shared draft', (
    tester,
  ) async {
    final version = 'a' * 64;
    final writes = <RequestOptions>[];
    const document = '/srm/documents/quotations/44';
    const draft = {'id': 45, 'quote_number': 'QT-44-R2', 'status': 'Draft'};
    var refreshed = 0;
    var originalStatus = 'Sent';
    RequestOptions? cancellation;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Organization'], '7');
          switch (request.path) {
            case '/crm/quotations/44':
              return response({
                'id': 44,
                'quote_number': 'QT-44',
                'status': originalStatus,
              });
            case document:
              return response({
                'version': version,
                'removed': false,
                'history': [
                  if (originalStatus == 'Cancelled')
                    {
                      'action': 'document_cancelled',
                      'actor_id': 7,
                      'reason': 'Offer withdrawn',
                      'before': {
                        'status': 'Sent',
                        'lines': [
                          {
                            'name': 'Consulting',
                            'quantity': 2,
                            'unit_price': 50,
                            'line_total': 100,
                          },
                        ],
                      },
                      'after': {
                        'record': {'status': 'Cancelled', 'total_amount': 100},
                      },
                    },
                  if (refreshed > 0)
                    {
                      'action': 'revision_created',
                      'reason': 'Updated offer',
                      'after': {
                        'record': {'id': 45},
                      },
                    },
                ],
              });
            case '$document/revise':
              expect(request.method, 'POST');
              writes.add(request);
              if (writes.length == 1) {
                return response({'detail': 'Try the revision again.'}, 503);
              }
              return response({'record': draft}, 201);
            case '/crm/quotations/45':
              return response(draft);
            case '$document/cancel':
              expect(request.method, 'POST');
              cancellation = request;
              originalStatus = 'Cancelled';
              return response({
                'record': {'id': 44, 'status': originalStatus},
              });
            default:
              throw StateError('Unexpected request: ${request.path}');
          }
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmQuotationPage(
          api: api,
          summary: const {'id': 44},
          offline: false,
          scopeHeaders: const {'X-Suite-Organization': '7'},
          canManage: true,
          canCreateRevision: true,
          canCancel: true,
          onChanged: () => refreshed++,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Create new version'), findsNothing);
    for (var attempt = 0; attempt < 2; attempt++) {
      await tester.tap(find.text('Create revision draft'));
      await tester.pumpAndSettle();
      final submit = find.text('Create revised draft');
      await tester.tap(submit);
      await tester.pumpAndSettle();
      expect(writes, hasLength(attempt));
      await tester.enterText(find.byType(TextFormField), '  Updated offer  ');
      await tester.tap(submit);
      await tester.pumpAndSettle();
    }
    expect(writes, hasLength(2));
    expect(writes.first.data, {
      'reason': 'Updated offer',
      'version': version,
      'request_id': matches(RegExp(r'^[0-9a-f-]{36}$')),
    });
    expect(writes.last.data, writes.first.data);
    expect(find.text('QT-44-R2'), findsOneWidget);
    expect(refreshed, 1);
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('QT-44'), findsOneWidget);
    expect(find.text('Sent'), findsOneWidget);
    await tester.tap(find.text('Cancel with reason'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), 'Offer withdrawn');
    expect(cancellation, isNull);
    await tester.tap(find.text('Confirm cancellation'));
    await tester.pumpAndSettle();
    expect(cancellation?.data, {
      'reason': 'Offer withdrawn',
      'version': version,
      'request_id': matches(RegExp(r'^[0-9a-f-]{36}$')),
    });
    expect(find.text('QT-44'), findsOneWidget);
    expect(find.text('Cancelled'), findsOneWidget);
    expect(find.text('Cancel with reason'), findsNothing);
    expect(refreshed, 2);
    await tester.tap(find.byTooltip('Document history'));
    await tester.pumpAndSettle();
    expect(find.text('Document cancelled'), findsOneWidget);
    expect(find.textContaining('Offer withdrawn'), findsOneWidget);
    expect(find.textContaining('Updated offer'), findsOneWidget);
    final values = find.text('View saved values');
    await tester.tap(values);
    await tester.pumpAndSettle();
    expect(find.text('Status: Sent'), findsOneWidget);
    expect(find.text('Status: Cancelled'), findsOneWidget);
    expect(find.text('Consulting · 2 × 50 · Total 100'), findsOneWidget);
    await tester.tap(values);
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Open related quotation'));
    await tester.pumpAndSettle();
    expect(find.text('QT-44-R2'), findsOneWidget);
  });

  test(
    'A rejected queued task stays available for review without retrying',
    () async {
      FlutterSecureStorage.setMockInitialValues({});
      const base = 'https://example.test/api/v1';
      final queue = CrmOfflineEdits('["$base",4,7]');
      var sends = 0;
      final api = ApiClient(
        baseUrl: base,
        store: MemoryStore(),
        transport: Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            sends++;
            return response({
              'detail': 'This task changed on the server.',
            }, 409);
          }),
      );
      await api.acceptTokens({'access_token': 'test', 'refresh_token': 'test'});
      await queue.enqueueTaskStatus(21, 'Done', '2026-11-27T09:00:00Z', '');
      final rejected = queue.taskUpdates(21).first;
      await queue.sync(api);
      expect((await rejected).synced, isFalse);
      expect(
        (await queue.pendingTask(21))?['error'],
        contains('This task changed'),
      );
      await queue.sync(api);
      expect(sends, 1);
      await queue.discardTask(21);
      expect(await queue.pendingTask(21), isNull);
    },
  );

  test(
    'Queued task status retries with its original receipt and version',
    () async {
      FlutterSecureStorage.setMockInitialValues({});
      const scope = '["https://example.test/api/v1",4,7]';
      final requests = <RequestOptions>[];
      final queue = CrmOfflineEdits(scope);
      final api = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            requests.add(request);
            return requests.length == 1
                ? response({'detail': 'Unavailable'}, 503)
                : response({'id': 21, 'status': 'Done'});
          }),
      );
      await api.acceptTokens({'access_token': 'test', 'refresh_token': 'test'});
      await queue.enqueueTaskStatus(21, 'Done', '2026-11-27T09:00:00Z', '3');
      expect(requests, isEmpty);
      await queue.sync(api);
      expect(await queue.pendingTask(21), isNotNull);
      final reopened = CrmOfflineEdits(scope);
      final confirmed = reopened.taskUpdates(21).first;
      await reopened.sync(api);
      final result = await confirmed;
      expect(result.synced, isTrue);
      expect(result.record?['status'], 'Done');
      expect(await reopened.pendingTask(21), isNull);
      expect(requests, hasLength(2));
      final receipt = requests.first.headers['X-Offline-Operation'];
      expect(receipt, isNotNull);
      for (final request in requests) {
        expect(request.path, '/project-management/tasks/21');
        expect(request.headers['X-Offline-Operation'], receipt);
        expect(request.headers['X-Suite-Organization'], '7');
        expect(request.headers['X-Suite-Branch'], '3');
        expect(request.data, {
          'status': 'Done',
          'expected_updated_at': '2026-11-27T09:00:00Z',
        });
      }
    },
  );

  testWidgets('Deal creation loads stages for the selected pipeline', (
    tester,
  ) async {
    final writes = <RequestOptions>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'POST') {
            writes.add(request);
            return response({'id': 82}, 201);
          }
          if (request.path.endsWith('/pipelines')) {
            return response({
              'items': [
                {'id': 3, 'name': 'Enterprise'},
              ],
            });
          }
          expect(request.path, '/crm/deal-workspace/pipeline-stages');
          expect(request.queryParameters['pipeline_id'], 3);
          return response({
            'items': [
              {'id': 5, 'name': 'Qualification'},
            ],
          });
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmDealForm(api: api, scopeHeaders: const {}),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<int>).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Enterprise').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<int>).last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Qualification').last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Deal name'),
      'Partner renewal',
    );
    final create = find.text('Create deal');
    await tester.ensureVisible(create);
    await tester.tap(create);
    await tester.pumpAndSettle();
    expect(writes.single.path, '/crm/deals');
    expect(writes.single.data, {
      'name': 'Partner renewal',
      'pipeline_id': 3,
      'stage_id': 5,
    });
  });

  testWidgets('Deal edit sends only changed values with the loaded version', (
    tester,
  ) async {
    final record = <String, dynamic>{
      'id': 18,
      'version': 3,
      'name': 'Renewal',
      'amount': 2000,
      'currency': 'INR',
    };
    final writes = <RequestOptions>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'PATCH') {
            writes.add(request);
            record['name'] = 'Annual renewal';
            record['version'] = 4;
          }
          return response(record);
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmDealPage(
          api: api,
          summary: const {'id': 18},
          offline: false,
          canMove: true,
          scopeHeaders: const {'X-Suite-Organization': '7'},
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Edit deal'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Deal name'),
      'Annual renewal',
    );
    final save = find.text('Save changes');
    await tester.ensureVisible(save);
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(writes.single.path, '/crm/deals/18');
    expect(writes.single.headers['X-Suite-Organization'], '7');
    expect(writes.single.data, {
      'name': 'Annual renewal',
      'expected_version': 3,
    });
    expect(find.text('Annual renewal'), findsOneWidget);
    expect(find.text('2000 INR'), findsOneWidget);
  });

  testWidgets('Deal stage move uses the server plan and current version', (
    tester,
  ) async {
    final writes = <RequestOptions>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'POST') {
            writes.add(request);
            return response({'id': 18, 'stage_id': 4});
          }
          if (request.path.endsWith('/stages')) {
            return response({
              'version': 3,
              'current_stage_id': 1,
              'values': {'amount': '100'},
              'stages': [
                {'id': 1, 'name': 'New'},
                {
                  'id': 4,
                  'name': 'Qualified',
                  'required': ['amount'],
                },
              ],
            });
          }
          return response({
            'id': 18,
            'name': 'Renewal',
            'stage_id': writes.isEmpty ? 1 : 4,
          });
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmDealPage(
          api: api,
          summary: const {'id': 18, 'stage_id': 1, 'stage_name': 'New'},
          offline: false,
          canMove: true,
          scopeHeaders: const {'X-Suite-Organization': '7'},
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Review stage move'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Destination stage'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Qualified').last);
    await tester.pumpAndSettle();
    final move = find.text('Move deal');
    await tester.ensureVisible(move);
    await tester.tap(move);
    await tester.pumpAndSettle();
    expect(writes.single.path, '/crm/productivity/deals/18/transition');
    expect(writes.single.headers['X-Suite-Organization'], '7');
    expect(writes.single.data, {
      'expected_version': 3,
      'stage_id': 4,
      'corrections': {'amount': 100},
      'lost_reason': '',
      'reactivate_at': null,
    });
    expect(find.text('Qualified'), findsOneWidget);
  });

  testWidgets('Contact creation validates the name and posts to shared CRM', (
    tester,
  ) async {
    final requests = <RequestOptions>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests.add(request);
          return response({'id': 82}, 201);
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmContactForm(
          api: api,
          scopeHeaders: const {'X-Suite-Organization': '7'},
        ),
      ),
    );
    final create = find.text('Create contact');
    await tester.ensureVisible(create);
    await tester.tap(create);
    await tester.pumpAndSettle();
    expect(requests, isEmpty);
    final firstName = find.widgetWithText(TextFormField, 'First name');
    await tester.ensureVisible(firstName);
    await tester.enterText(firstName, ' Anya ');
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Last name'),
      'Rao',
    );
    await tester.ensureVisible(create);
    await tester.tap(create);
    await tester.pumpAndSettle();
    expect(requests.single.method, 'POST');
    expect(requests.single.path, '/crm/contacts');
    expect(requests.single.headers['X-Suite-Organization'], '7');
    expect(requests.single.data, {
      'first_name': 'Anya',
      'last_name': 'Rao',
      'full_name': 'Anya Rao',
    });
  });

  testWidgets('Contact edit submits only changed fields and refreshes', (
    tester,
  ) async {
    final record = <String, dynamic>{
      'id': 81,
      'first_name': 'Asha',
      'last_name': 'Rao',
      'full_name': 'Asha Rao',
      'job_title': 'Coordinator',
    };
    final writes = <RequestOptions>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.path, '/crm/contacts/81');
          if (request.method == 'PATCH') {
            writes.add(request);
            record.addAll(request.data as Map<String, dynamic>);
          }
          return response(record);
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmContactPage(
          api: api,
          summary: const {'id': 81},
          offline: false,
          canEdit: true,
          scopeHeaders: const {'X-Suite-Organization': '7'},
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Edit contact'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'First name'),
      'Anya',
    );
    final save = find.text('Save changes');
    await tester.ensureVisible(save);
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(writes.single.headers['X-Suite-Organization'], '7');
    expect(writes.single.data, {'first_name': 'Anya', 'full_name': 'Anya Rao'});
    expect(find.text('Anya Rao'), findsOneWidget);
    expect(find.text('Coordinator'), findsOneWidget);
  });

  testWidgets('Warehouse edit preserves fields and submits a scoped update', (
    tester,
  ) async {
    final requests = <RequestOptions>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests.add(request);
          return response({'id': 4});
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: InventoryWarehouseForm(
          api: api,
          scopeHeaders: const {'X-Suite-Organization': '7'},
          warehouse: const {
            'id': 4,
            'warehouse_code': 'MAIN',
            'warehouse_name': 'Main warehouse',
            'branch': 'Main branch',
            'address': 'Existing address',
          },
        ),
      ),
    );
    expect(find.text('Main warehouse'), findsOneWidget);
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Warehouse name'),
      'Central warehouse',
    );
    final save = find.text('Save changes');
    await tester.ensureVisible(save);
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(requests.single.method, 'PUT');
    expect(requests.single.path, '/srm/inventory/warehouses/4');
    expect(requests.single.headers['X-Suite-Organization'], '7');
    expect(requests.single.data, {
      'warehouse_code': 'MAIN',
      'warehouse_name': 'Central warehouse',
      'branch': 'Main branch',
      'address': 'Existing address',
    });
  });

  testWidgets('Warehouse creation posts to scoped inventory API', (
    tester,
  ) async {
    final requests = <RequestOptions>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests.add(request);
          return response({'id': 2}, 201);
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: InventoryWarehouseForm(
          api: api,
          scopeHeaders: const {'X-Suite-Organization': '7'},
        ),
      ),
    );
    final create = find.text('Create warehouse');
    await tester.ensureVisible(create);
    await tester.tap(create);
    await tester.pump();
    expect(requests, isEmpty);
    final code = find.widgetWithText(TextFormField, 'Warehouse code');
    await tester.ensureVisible(code);
    await tester.enterText(code, ' MAIN ');
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Warehouse name'),
      'Main warehouse',
    );
    await tester.ensureVisible(create);
    await tester.tap(create);
    await tester.pumpAndSettle();
    expect(requests.single.path, '/srm/inventory/warehouses');
    expect(requests.single.method, 'POST');
    expect(requests.single.headers['X-Suite-Organization'], '7');
    expect(requests.single.data, {
      'warehouse_code': 'MAIN',
      'warehouse_name': 'Main warehouse',
    });
  });

  testWidgets(
    'Sales corrects a rejected draft without losing its customer or lines',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({});
      tester.view.physicalSize = const Size(430, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      const base = 'https://example.test/api/v1';
      final drafts = SalesOrderDrafts('["$base",7,7]');
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter(
          (_) async => response({'detail': 'Invalid order'}, 422),
        );
      final api = ApiClient(
        baseUrl: base,
        store: MemoryStore(),
        transport: dio,
      );
      await api.acceptTokens({
        'access_token': 'access',
        'refresh_token': 'refresh',
      });
      final payload = {
        'title': 'Rejected order',
        'currency': 'INR',
        'customer_id': 101,
        'expected_start_date': '2026-12-01',
        'expected_end_date': '2026-12-15',
        'lines': [
          {
            'product_id': 8,
            'description': 'Saved cable',
            'quantity': '2',
            'unit_price': '75.00',
          },
        ],
      };
      await drafts.save('original', payload, customerName: 'Saved customer');
      await tester.runAsync(() => drafts.sync(api));
      await tester.pumpWidget(
        MaterialApp(
          home: SalesOrderDraftsPage(api: api, drafts: drafts),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Rejected order'));
      await tester.pumpAndSettle();
      expect(find.text('Correct order draft'), findsOneWidget);
      expect(find.text('Saved customer'), findsOneWidget);
      await tester.tap(find.text('Order schedule'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Expected end date'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('20'));
      await tester.tap(find.text('OK'));
      await tester.pumpAndSettle();
      expect(find.text('2026-12-20'), findsOneWidget);
      await tester.tap(find.text('Order schedule'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextFormField).first,
        'Corrected order',
      );
      await tester.ensureVisible(find.text('Save order draft'));
      await tester.tap(find.text('Save order draft'));
      await tester.pumpAndSettle();
      final saved = (await drafts.entries()).single;
      expect(saved['operation'], isNot('original'));
      expect(saved['payload'], {
        ...payload,
        'title': 'Corrected order',
        'expected_end_date': '2026-12-20',
      });
      expect(find.text('Corrected order'), findsOneWidget);
      dio.httpClientAdapter = FakeAdapter(
        (_) async => response({'id': 19}, 201),
      );
      await tester.runAsync(() => SalesOrderDrafts('["$base",7,7]').sync(api));
      await tester.pumpAndSettle();
      expect(find.text('No saved order drafts'), findsOneWidget);
    },
  );
  testWidgets('Sales uses a shared inventory product on an order line', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(430, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    RequestOptions? order;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        if (request.path == SalesOrderDrafts.productsEndpoint) {
          expect(request.queryParameters['summary_only'], isTrue);
          return response({
            'items': [
              {
                'id': 8,
                'item_name': 'Stock cable',
                'sku': 'SKU-8',
                'sales_rate': 75,
              },
            ],
          });
        }
        order = request;
        return response({'id': 17}, 201);
      });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: dio,
    );
    await tester.pumpWidget(MaterialApp(home: NewSalesOrderPage(api: api)));
    await tester.enterText(find.byType(TextFormField).first, 'Product order');
    await tester.tap(find.text('Choose product'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Stock cable'));
    await tester.pumpAndSettle();
    expect(find.text('75.00'), findsOneWidget);
    await tester.tap(find.text('Create order'));
    await tester.pumpAndSettle();
    expect(order?.data['lines'], [
      {
        'quantity': '1',
        'product_id': 8,
        'description': 'Stock cable',
        'item_code': 'SKU-8',
        'service_type': 'product',
        'unit_price': '75.00',
      },
    ]);
  });
  testWidgets(
    'Sales saves an offline order and retries with its original receipt',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({});
      tester.view.physicalSize = const Size(430, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      const base = 'https://example.test/api/v1';
      const scope = '["$base",3,7]';
      final drafts = SalesOrderDrafts(scope);
      final requests = <RequestOptions>[];
      var customerRequests = 0;
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.path == SalesOrderDrafts.customersEndpoint) {
            customerRequests++;
            return response({
              'items': [
                {'id': 101, 'name': 'Saved sales customer'},
              ],
            });
          }
          requests.add(request);
          return requests.length == 1
              ? response({'detail': 'Unavailable'}, 503)
              : response({'id': 11}, 201);
        });
      final api = ApiClient(
        baseUrl: base,
        store: MemoryStore(),
        transport: dio,
      );
      await api.acceptTokens({
        'access_token': 'access',
        'refresh_token': 'refresh',
      });
      await tester.runAsync(() => drafts.customers(api, '', offline: false));
      await tester.pumpWidget(
        MaterialApp(
          home: NewSalesOrderPage(api: api, drafts: drafts, offline: true),
        ),
      );
      final fields = find.byType(TextFormField);
      await tester.tap(find.text('Choose customer'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Saved sales customer'));
      await tester.pumpAndSettle();
      expect(customerRequests, 1);
      await tester.enterText(fields.at(0), 'Field sale');
      await tester.enterText(fields.at(3), 'Consulting');
      await tester.enterText(fields.at(5), '100.00');
      await tester.enterText(fields.at(6), '5.00');
      await tester.enterText(fields.at(7), '18.00');
      await tester.ensureVisible(find.text('Save order draft'));
      await tester.tap(find.text('Save order draft'));
      await tester.pumpAndSettle();
      expect(requests, isEmpty);
      final invalidated = <String>[];
      final reopened = SalesOrderDrafts(
        scope,
        invalidate: (key) async => invalidated.add(key),
      );
      final saved = (await reopened.entries()).single;
      await tester.runAsync(() => reopened.sync(api));
      expect(await reopened.entries(), hasLength(1));
      expect(invalidated, isEmpty);
      await tester.runAsync(() => reopened.sync(api));
      expect(await reopened.entries(), isEmpty);
      expect(invalidated, ['$scope:/srm/sales-orders']);
      expect(requests, hasLength(2));
      for (final request in requests) {
        expect(request.path, '/srm/sales-orders');
        expect(request.headers['X-Offline-Operation'], saved['operation']);
        expect(request.data, {
          'title': 'Field sale',
          'customer_id': 101,
          'currency': 'INR',
          'lines': [
            {
              'quantity': '1',
              'description': 'Consulting',
              'unit_price': '100.00',
              'discount_amount': '5.00',
              'tax_amount': '18.00',
            },
          ],
        });
      }
    },
  );
  testWidgets('CRM corrects a lead draft rejected by validation', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    const base = 'https://example.test/api/v1';
    final queue = CrmOfflineEdits('["$base",3,7]');
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter(
        (_) async => response({'detail': 'Invalid contact'}, 422),
      );
    final api = ApiClient(baseUrl: base, store: MemoryStore(), transport: dio);
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    await queue.enqueueCreation('original', {
      'values': {'full_name': 'Original lead'},
    });
    await tester.runAsync(() => queue.sync(api));
    await tester.pumpWidget(
      MaterialApp(
        home: CrmLeadDraftsPage(queue: queue, api: api, canEdit: true),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Invalid contact'), findsOneWidget);
    await tester.tap(find.text('Original lead'));
    await tester.pumpAndSettle();
    expect(find.text('Correct lead draft'), findsOneWidget);
    await tester.enterText(find.byType(TextFormField).first, 'Corrected lead');
    await tester.ensureVisible(find.text('Save lead draft'));
    await tester.tap(find.text('Save lead draft'));
    await tester.pumpAndSettle();
    final corrected = (await queue.creations()).single;
    expect(corrected['key'], isNot('create:original'));
    expect(corrected['values']['full_name'], 'Corrected lead');
    expect(find.text('Awaiting sync'), findsOneWidget);
  });
  testWidgets(
    'offline CRM saves a lead draft and replays its original request',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({});
      const base = 'https://example.test/api/v1';
      const scope = '["$base",3,7]';
      final drafts = CrmOfflineEdits(scope);
      final attempts = <RequestOptions>[];
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          attempts.add(request);
          return attempts.length == 1
              ? response({'detail': 'Unavailable'}, 503)
              : response({'id': 17}, 201);
        });
      final api = ApiClient(
        baseUrl: base,
        store: MemoryStore(),
        transport: dio,
      );
      await api.acceptTokens({
        'access_token': 'access',
        'refresh_token': 'refresh',
      });
      await tester.pumpWidget(
        MaterialApp(
          home: CrmNewLeadPage(api: api, queue: drafts, offline: true),
        ),
      );
      await tester.enterText(find.byType(TextFormField).first, 'Field lead');
      await tester.ensureVisible(find.text('Save lead draft'));
      await tester.tap(find.text('Save lead draft'));
      await tester.pumpAndSettle();
      expect(attempts, isEmpty);
      final reopened = CrmOfflineEdits(scope);
      final saved = (await reopened.creations()).single;
      expect(saved['values']['full_name'], 'Field lead');
      var uploaded = 0;
      await tester.runAsync(
        () => reopened.sync(api, onCreated: () => uploaded++),
      );
      expect(await reopened.creations(), hasLength(1));
      expect(uploaded, 0);
      await tester.runAsync(
        () => reopened.sync(api, onCreated: () => uploaded++),
      );
      expect(await reopened.creations(), isEmpty);
      expect(uploaded, 1);
      for (final request in attempts) {
        expect(request.path, CrmLeadPage.endpoint);
        expect(request.data, {
          'values': {'full_name': 'Field lead'},
        });
        expect(request.headers['X-Suite-Organization'], '7');
        expect(
          'create:${request.headers['X-Offline-Operation']}',
          saved['key'],
        );
      }
    },
  );
  testWidgets('native CRM creates a lead through the shared write API', (
    tester,
  ) async {
    final requests = <RequestOptions>[];
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        requests.add(request);
        return response({'id': 17}, 201);
      });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: dio,
    );
    bool? saved;
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () async {
                saved = await Navigator.of(context).push<bool>(
                  MaterialPageRoute<bool>(
                    builder: (_) => CrmNewLeadPage(api: api),
                  ),
                );
              },
              child: const Text('Open'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).first, '  Sample Lead  ');
    await tester.enterText(find.byType(TextFormField).at(1), 'Sample company');
    await tester.ensureVisible(find.text('Create lead'));
    await tester.tap(find.text('Create lead'));
    await tester.pumpAndSettle();
    expect(saved, isTrue);
    expect(requests.single.path, CrmLeadPage.endpoint);
    expect(requests.single.method, 'POST');
    expect(requests.single.headers['X-Offline-Operation'], isNotEmpty);
    expect(requests.single.data, {
      'values': {'full_name': 'Sample Lead', 'company_name': 'Sample company'},
    });
  });
  testWidgets('CRM pages and searches all authorized leads through the API', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    final pages = <Object?>[];
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        switch (request.path) {
          case '/notifications/unread-count':
            return response({'unread': 0});
          case '/access/me':
            return response({
              'companyId': 7,
              'grants': {
                'crm': {'enabled': true},
              },
            });
          case '/crm/lead-management/leads':
            expect(request.queryParameters['summary_only'], isTrue);
            final page = request.queryParameters['page'];
            pages.add(page);
            final search = request.queryParameters['search'];
            return response({
              'items': [
                {
                  'id': 4,
                  'full_name': search == 'example.test'
                      ? 'Matched email lead'
                      : 'Lead page $page',
                },
              ],
              'total': search == null ? 2 : 1,
              'perPage': 1,
              'page': page,
            });
          default:
            fail('Unexpected pathname ${request.path}');
        }
      });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: dio,
    );
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    final controller = AppController(api, suiteLogin: true)
      ..loading = false
      ..user = SessionUser.fromJson({'id': 2, 'email': 'mobile@example.test'});
    await tester.pumpWidget(BusinessSuiteApp(controller: controller));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('VyaparaCRM'));
    await tester.tap(find.text('VyaparaCRM'));
    await tester.pumpAndSettle();
    expect(find.text('Lead page 1'), findsOneWidget);
    await tester.tap(find.text('Next'));
    await tester.pumpAndSettle();
    expect(find.text('Lead page 2'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'example.test');
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pumpAndSettle();
    expect(find.text('Matched email lead'), findsOneWidget);
    expect(pages, [1, 2, 1]);
    await tester.pumpWidget(const SizedBox.shrink());
  }, variant: TargetPlatformVariant({TargetPlatform.iOS}));
  testWidgets('offline Sales screen reconnects in place through Refresh', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    var orders = 0;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        expect(request.path, '/srm/sales-orders');
        expect(request.queryParameters['summary_only'], isTrue);
        orders++;
        return response([
          {'id': 4, 'order_number': 'SO-4'},
        ]);
      });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: dio,
    );
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    final user = {'id': 2, 'email': 'mobile@example.test'};
    await api.rememberSuite(user, {
      'companyId': 7,
      'grants': {
        'srm': {'enabled': true},
      },
    });
    final controller = AppController(api, suiteLogin: true)
      ..loading = false
      ..offline = true
      ..user = SessionUser.fromJson(user);
    await tester.pumpWidget(BusinessSuiteApp(controller: controller));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Sales & POS'));
    await tester.tap(find.text('Sales & POS'));
    await tester.pumpAndSettle();
    expect(orders, 0);
    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    expect(orders, 1);
    expect(find.text('SO-4'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('offline Notes creation retries with the same operation ID', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    final cache = NotesOfflineCache('["https://example.test/api/v1",2,7]');
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((_) async {
        fail('Offline creation should not call the server');
      });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: dio,
    );
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    await tester.pumpWidget(
      MaterialApp(
        home: NotesPage(api: api, cache: cache, offline: true),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('New note'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextField).first,
      'Offline created note',
    );
    await tester.enterText(find.byType(TextField).last, 'Warehouse checklist');
    await tester.enterText(
      find.widgetWithText(TextField, 'Tags'),
      'cycle count',
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(find.text('Offline created note'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, 'cycle count');
    await tester.pumpAndSettle();
    expect(find.text('Offline created note'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, 'checklist');
    await tester.pumpAndSettle();
    expect(find.text('Offline created note'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, 'unmatched');
    await tester.pumpAndSettle();
    expect(find.text('Offline created note'), findsNothing);
    await tester.enterText(find.byType(TextField).first, '');
    await tester.pumpAndSettle();
    final operations = <Object?>[];
    dio.httpClientAdapter = FakeAdapter((request) async {
      if (request.method == 'GET') {
        expect(request.path, '/project-management/notes');
        return response([
          {'id': 5, 'title': 'Offline created note'},
        ]);
      }
      expect(request.path, '/project-management/notes/offline-create');
      expect(request.method, 'POST');
      expect(request.data['title'], 'Offline created note');
      expect(request.data['tags'], ['cycle count']);
      operations.add(request.headers['X-Offline-Operation']);
      return switch (operations.length) {
        1 => response({'detail': 'Method Not Allowed'}, 405),
        2 => response({'detail': 'Offline'}, 503),
        _ => response({'id': 5}, 201),
      };
    });
    await tester.runAsync(() => cache.sync(api));
    expect(await cache.creations(), hasLength(1));
    await tester.runAsync(() => cache.sync(api));
    expect(await cache.creations(), hasLength(1));
    await tester.tap(find.byTooltip('Refresh notes'));
    await tester.pumpAndSettle();
    expect(operations, hasLength(3));
    expect(operations.first, isNotNull);
    expect(operations.toSet(), hasLength(1));
    expect(await cache.creations(), isEmpty);
    expect(find.text('Saved · Awaiting sync'), findsNothing);
    expect(find.text('Offline created note'), findsOneWidget);
  });
  testWidgets('Notes shows the server list while a draft uploads', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    final cache = NotesOfflineCache('["https://example.test/api/v1",9,7]');
    await cache.enqueueNew({'title': 'Queued note', 'content': 'Draft'});
    final finishUpload = Completer<void>();
    final uploadStarted = Completer<void>();
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        if (request.method == 'POST') {
          uploadStarted.complete();
          await finishUpload.future;
          return response({'id': 31}, 201);
        }
        return response([
          {'id': 8, 'title': 'Note from web'},
        ]);
      });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: dio,
    );
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    await tester.pumpWidget(
      MaterialApp(
        home: NotesPage(api: api, cache: cache),
      ),
    );
    await tester.pumpAndSettle();
    try {
      expect(uploadStarted.isCompleted, isTrue);
      expect(find.text('Note from web'), findsOneWidget);
    } finally {
      finishUpload.complete();
      await tester.pumpAndSettle();
    }
  });

  testWidgets('Notes duplicates a saved note via the shared API', (
    tester,
  ) async {
    const path = '/project-management/notes';
    const original = {'id': 12, 'title': 'Original note', 'can_edit': true};
    const copy = {'id': 13, 'title': 'Original note (copy)'};
    var duplicated = false;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'POST') {
            expect(request.path, '$path/12/duplicate');
            expect(request.data, isNull);
            duplicated = true;
            return response(copy, 201);
          }
          if (request.path == '$path/12') return response(original);
          expect(request.path, path);
          return response([if (duplicated) copy, original]);
        }),
    );
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    await tester.pumpWidget(MaterialApp(home: NotesPage(api: api)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Original note'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Duplicate note'));
    await tester.pumpAndSettle();
    expect(duplicated, isTrue);
    expect(find.text('Original note (copy)'), findsOneWidget);
    expect(find.text('Original note'), findsOneWidget);
  });

  testWidgets('Notes restores history as a new version', (tester) async {
    const path = '/project-management/notes';
    const note = {
      'id': 12,
      'version': 4,
      'title': 'Current note',
      'content': 'Current text',
      'can_edit': true,
      'tags': ['retained'],
    };
    const oldBody = '<!--suite-richtext:v1--><p>Previous text</p>';
    var didSave = false;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'PUT') {
            expect(request.path, '$path/12');
            expect(request.data['version'], 4);
            expect(request.data['title'], 'Previous note');
            expect(request.data['content'], oldBody);
            expect(request.data['tags'], ['retained']);
            didSave = true;
            return response({...note, 'version': 5});
          }
          return switch (request.path) {
            '$path/12' => response(note),
            '$path/12/revisions' => response([
              {'version': 2, 'title': 'Previous note'},
            ]),
            '$path/12/revisions/2' => response({
              'title': 'Previous note',
              'content': oldBody,
            }),
            _ => response([note]),
          };
        }),
    );
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    await tester.pumpWidget(MaterialApp(home: NotesPage(api: api)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Current note'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Version history'));
    await tester.pumpAndSettle();
    for (final label in ['Version 2 · Previous note', 'Use this version']) {
      await tester.tap(find.text(label));
      await tester.pumpAndSettle();
    }
    expect(didSave, isFalse);
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(didSave, isTrue);
  });

  testWidgets('KaryaFlow opens saved suite Notes after losing connection', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    addTearDown(() => FlutterSecureStorage.setMockInitialValues({}));
    mockUnavailableSqlite(tester);
    const url = 'https://example.test/api/v1';
    var connected = true;
    final api = ApiClient(
      baseUrl: url,
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (!connected) fail('Offline KaryaFlow requested ${request.path}');
          return switch (request.path) {
            '/access/me' => response({
              'companyId': 7,
              'grants': {
                'project_management': {'enabled': true},
              },
            }),
            '/access/launcher-preferences' => response({'favorites': []}),
            '/notifications/unread-count' => response({'unread': 0}),
            _ => throw StateError('Unexpected request ${request.path}'),
          };
        }),
    );
    const identity = {'id': 19, 'email': 'member@example.test'};
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    final cache = NotesOfflineCache('["$url",19,7]');
    const note = {
      'id': 17,
      'title': 'Shared suite note',
      'content': 'Saved from the suite Notes screen',
      'can_edit': true,
      'visibility_scope': 'private',
      'visibility': 'private',
    };
    await cache.saveSummaries([note]);
    await cache.saveDetail(note);
    final controller = AppController(api, suiteLogin: true)
      ..loading = false
      ..user = SessionUser.fromJson(identity);
    await tester.pumpWidget(BusinessSuiteApp(controller: controller));
    await tester.pumpAndSettle();
    final module = find.text('KaryaFlow PMS');
    await tester.ensureVisible(module);
    await tester.tap(module);
    await tester.pumpAndSettle();
    expect(find.text('KaryaFlow'), findsOneWidget);
    connected = false;
    controller.offline = true;
    await tester.tap(find.byTooltip('Notes'));
    await tester.pumpAndSettle();
    expect(find.text('Shared suite note'), findsOneWidget);
    await tester.tap(find.text('Shared suite note'));
    await tester.pumpAndSettle();
    expect(find.text('Saved from the suite Notes screen'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    controller.dispose();
  }, variant: TargetPlatformVariant({TargetPlatform.android}));

  testWidgets('Notes filters saved personal notes offline', (tester) async {
    FlutterSecureStorage.setMockInitialValues({});
    final cache = NotesOfflineCache('["https://example.test/api/v1",19,7]');
    await cache.saveSummaries([
      for (final (id, title, flag) in [
        (1, 'Top note', 'pinned'),
        (2, 'Starred note', 'favorite'),
        (3, 'Alpha note', 'test_only'),
      ])
        {
          'id': id,
          'title': title,
          'can_edit': true,
          'visibility_scope': 'private',
          'visibility': 'private',
          if (id == 1) 'folder_id': 42,
          flag: true,
        },
    ]);
    await cache.saveDetail({
      'id': 2,
      'title': 'Starred note',
      'content': 'A searchable section beyond the saved preview',
      'can_edit': true,
      'visibility_scope': 'private',
      'visibility': 'private',
    });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((_) async {
          fail('Offline filtering should use saved notes');
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: NotesPage(api: api, cache: cache, offline: true),
      ),
    );
    await tester.pumpAndSettle();
    for (final (view, visible, hidden) in [
      ('Pinned', 'Top note', 'Starred note'),
      ('Favorites', 'Starred note', 'Top note'),
      ('Quick notes', 'Starred note', 'Top note'),
    ]) {
      await tester.tap(find.byTooltip('Filter notes'));
      await tester.pumpAndSettle();
      await tester.tap(find.text(view));
      await tester.pumpAndSettle();
      expect(find.text(visible), findsOneWidget);
      expect(find.text(hidden), findsNothing);
    }
    await tester.tap(find.byTooltip('Sort notes'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Title'));
    await tester.pumpAndSettle();
    expect(
      tester.getTopLeft(find.text('Alpha note')).dy,
      lessThan(tester.getTopLeft(find.text('Starred note')).dy),
    );
    await tester.enterText(find.byType(TextField), 'beyond the saved preview');
    await tester.pumpAndSettle();
    expect(find.text('Starred note'), findsOneWidget);
    expect(find.text('Alpha note'), findsNothing);
  });

  testWidgets('offline metadata edits preserve formatted Notes content', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    final cache = NotesOfflineCache('["https://example.test/api/v1",49,7]');
    const content = '<!--suite-richtext:v1--><p><strong>Formatted</strong></p>';
    const note = {
      'id': 52,
      'version': 3,
      'title': 'Formatted note',
      'content': content,
      'preview': 'Formatted',
      'visibility_scope': 'private',
      'visibility': 'private',
      'can_edit': true,
    };
    await cache.saveSummaries([note]);
    await cache.saveDetail(note);
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: NotesPage(api: api, cache: cache, offline: true),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Formatted note'));
    await tester.pumpAndSettle();
    expect(
      tester.widget<TextField>(find.byType(TextField).last).readOnly,
      isTrue,
    );
    await tester.tap(find.text('Favorite'));
    await tester.enterText(
      find.widgetWithText(TextField, 'Tags'),
      ' Warehouse\npriority\nWAREHOUSE ',
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    final pending = await cache.pending(52);
    expect(pending?['values']['favorite'], isTrue);
    expect(pending?['values']['tags'], ['warehouse', 'priority']);
    expect(pending?['values']['content'], content);
    expect(find.text('Formatted'), findsOneWidget);
    expect(find.text(content), findsNothing);
  });

  test('syncing an archived note evicts its offline copies', () async {
    TestWidgetsFlutterBinding.ensureInitialized();
    FlutterSecureStorage.setMockInitialValues({});
    final cache = NotesOfflineCache('["https://example.test/api/v1",39,7]');
    const note = {
      'id': 51,
      'version': 2,
      'title': 'Saved work',
      'content': 'Saved body',
      'visibility_scope': 'private',
      'visibility': 'private',
      'can_edit': true,
    };
    await cache.saveSummaries([note]);
    await cache.saveDetail(note);
    await cache.enqueue(note, {'archived': true});
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.path, '/project-management/notes/51');
          expect(request.method, 'PUT');
          expect(request.data['archived'], isTrue);
          return response({...note, 'archived': true, 'version': 3});
        }),
    );
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    await cache.sync(api);
    expect(await cache.pending(51), isNull);
    expect(await cache.summaries(), isEmpty);
    expect(await cache.detail(51), isNull);
  });

  testWidgets('Notes moves a note to Trash and restores it by version', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    final cache = NotesOfflineCache('["https://example.test/api/v1",29,7]');
    const path = '/project-management/notes';
    const note = {
      'id': 15,
      'title': 'Trashed note',
      'can_edit': true,
      'visibility_scope': 'private',
      'visibility': 'private',
      'deleted_at': '2026-11-27T10:00:00Z',
      'version': 8,
    };
    var trashed = false;
    var failedRefresh = false;
    var version = 7;
    Map<String, dynamic> currentNote() => {
      ...note,
      'deleted_at': trashed ? note['deleted_at'] : null,
      'version': version,
    };
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.path == '$path/15/restore') {
            expect(request.method, 'POST');
            expect(request.data, {'version': 8});
            trashed = false;
            version++;
            return response(currentNote());
          }
          if (request.path == '$path/15') {
            if (request.method == 'DELETE') {
              expect(request.data, {'version': 7});
              trashed = true;
              version++;
            }
            return response(currentNote());
          }
          if (trashed && request.queryParameters['view'] == 'all') {
            expect(await cache.summaries(), isEmpty);
            expect(await cache.detail(15), isNull);
            if (!failedRefresh) {
              failedRefresh = true;
              return response({'detail': 'Connection interrupted'}, 503);
            }
          }
          return response([
            if ((request.queryParameters['view'] == 'trash') == trashed)
              currentNote(),
          ]);
        }),
    );
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    await tester.pumpWidget(
      MaterialApp(
        home: NotesPage(api: api, cache: cache),
      ),
    );
    await tester.pumpAndSettle();
    for (final label in ['Trashed note', 'Move to Trash']) {
      await tester.tap(find.text(label));
      await tester.pumpAndSettle();
    }
    expect(await cache.detail(15), isNotNull);
    await tester.tap(find.widgetWithText(FilledButton, 'Move to Trash'));
    await tester.pumpAndSettle();
    expect(trashed, isTrue);
    expect(failedRefresh, isTrue);
    expect(find.text('Trashed note'), findsNothing);
    await tester.tap(find.byTooltip('Refresh notes'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Filter notes'));
    await tester.pumpAndSettle();
    for (final label in ['Trash', 'Trashed note', 'Restore note']) {
      await tester.tap(find.text(label));
      await tester.pumpAndSettle();
    }
    expect(trashed, isFalse);
    expect(version, 9);
    expect(find.text('Trashed note'), findsNothing);
  });

  testWidgets('Notes reuses the online operation ID after a lost response', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    const server = 'https://example.test/api/v1';
    final cache = NotesOfflineCache('["$server",3,7]');
    final operations = <Object?>[];
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        if (request.method == 'GET') return response([]);
        operations.add(request.headers['X-Offline-Operation']);
        expect(request.data['title'], 'New private note');
        if (request.path.endsWith('/offline-create')) {
          return response({'id': 42}, 201);
        }
        expect(request.path, '/project-management/notes');
        throw DioException(
          requestOptions: request,
          type: DioExceptionType.connectionError,
        );
      });
    final api = ApiClient(
      baseUrl: server,
      store: MemoryStore(),
      transport: dio,
    );
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    await tester.pumpWidget(
      MaterialApp(
        home: NotesPage(api: api, cache: cache),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('New note'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'New private note');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(operations, hasLength(2));
    expect(operations.first, isNotNull);
    expect(operations.first, operations.last);
    expect(await cache.creations(), isEmpty);
  });
  for (final connectedInitially in [false, true]) {
    testWidgets(
      'Notes queues an edit and preserves a conflict (online at open: $connectedInitially)',
      (tester) async {
        FlutterSecureStorage.setMockInitialValues({});
        final cache = NotesOfflineCache('["https://example.test/api/v1",2,7]');
        final private = {
          'id': 1,
          'title': 'Private QA note',
          'preview': 'Preview',
          'version': 3,
          'can_edit': true,
          'project_id': null,
          'visibility_scope': 'private',
          'visibility': 'private',
        };
        await cache.saveSummaries([
          private,
          {
            ...private,
            'id': 2,
            'title': 'Shared QA note',
            'visibility': 'shared',
          },
        ]);
        await cache.saveDetail({...private, 'content': 'Saved body'});
        final dio = Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            if (!connectedInitially) {
              fail('Offline Notes should not call the server');
            }
            if (request.method == 'PUT') {
              throw DioException(
                requestOptions: request,
                type: DioExceptionType.connectionError,
              );
            }
            return response(
              request.path.endsWith('/1')
                  ? {...private, 'content': 'Saved body'}
                  : [private],
            );
          });
        final api = ApiClient(
          baseUrl: 'https://example.test/api/v1',
          store: MemoryStore(),
          transport: dio,
        );
        await api.acceptTokens({
          'access_token': 'access',
          'refresh_token': 'refresh',
        });
        await tester.pumpWidget(
          MaterialApp(
            home: NotesPage(
              api: api,
              cache: cache,
              offline: !connectedInitially,
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('Shared QA note'), findsNothing);
        await tester.tap(find.text('Private QA note'));
        await tester.pumpAndSettle();
        expect(find.text('Saved body'), findsOneWidget);
        await tester.tap(find.text('Favorite'));
        await tester.tap(find.text('Archived'));
        await tester.enterText(find.byType(TextField).last, 'Offline edit');
        await tester.pumpAndSettle();
        await tester.tap(find.text('Save'));
        await tester.pumpAndSettle();
        expect((await cache.pending(1))?['values']['content'], 'Offline edit');
        expect((await cache.pending(1))?['values']['favorite'], isTrue);
        expect((await cache.pending(1))?['values']['archived'], isTrue);
        expect(find.text('Offline edit'), findsOneWidget);
        expect(find.byTooltip('Awaiting sync'), findsOneWidget);
        dio.httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'GET') {
            return response({...private, 'content': 'Web edit'});
          }
          expect(request.method, 'PUT');
          expect(request.path, '/project-management/notes/1');
          expect(request.headers['X-Suite-Organization'], '7');
          expect(request.data['version'], 3);
          return response({'detail': 'The note changed on web'}, 409);
        });
        await tester.runAsync(() => cache.sync(api));
        expect((await cache.pending(1))?['error'], 'The note changed on web');
        await tester.tap(find.text('Private QA note'));
        await tester.pumpAndSettle();
        expect(find.text('Offline edit'), findsOneWidget);
        expect(
          tester
              .widgetList<TextField>(find.byType(TextField))
              .every((field) => field.readOnly),
          isTrue,
        );
        await cache.enqueue(
          {...private, 'id': 3},
          {'title': 'Synced', 'content': 'Synced body'},
        );
        dio.httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'GET') {
            return response([
              private,
              {...private, 'id': 3, 'title': 'Synced'},
            ]);
          }
          expect(request.path, '/project-management/notes/3');
          return response({
            ...private,
            'id': 3,
            'version': 4,
            'content': 'Synced body',
          });
        });
        await tester.runAsync(() => cache.sync(api));
        await tester.pumpAndSettle();
        expect(await cache.pending(3), isNull);
        expect((await cache.detail(3))?['content'], 'Synced body');
        expect(await cache.pending(1), isNotNull);
        await tester.pageBack();
        await tester.pumpAndSettle();
        expect(find.text('Synced'), findsOneWidget);
      },
    );
  }
  testWidgets(
    'Notes previews open immediately and only saves refresh the list',
    (tester) async {
      var listRequests = 0;
      var saves = 0;
      final firstDetail = Completer<ResponseBody>();
      var details = 0;
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.path == '/project-management/notes') {
            listRequests++;
            return response([
              {'id': 1, 'title': 'QA note', 'preview': 'Saved preview'},
            ]);
          }
          expect(request.path, '/project-management/notes/1');
          if (request.method == 'PUT') {
            saves++;
            return response({'id': 1});
          }
          details++;
          if (details == 1) return firstDetail.future;
          return response({
            'id': 1,
            'title': 'QA note',
            'content': details == 2 ? 'Full note' : 'Edited on web',
            'can_edit': true,
            'version': 1,
          });
        });
      await tester.pumpWidget(
        MaterialApp(
          home: NotesPage(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('QA note'));
      await tester.pump(const Duration(milliseconds: 350));
      expect(find.text('Saved preview'), findsOneWidget);
      firstDetail.complete(
        response({
          'id': 1,
          'title': 'QA note',
          'content': 'Full note',
          'can_edit': true,
        }),
      );
      await tester.pumpAndSettle();
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(listRequests, 1);
      await tester.tap(find.text('QA note'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Refresh note'));
      await tester.pumpAndSettle();
      expect(find.text('Edited on web'), findsOneWidget);
      await tester.enterText(find.byType(TextField).first, 'Updated title');
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<IconButton>(
              find.byWidgetPredicate(
                (widget) =>
                    widget is IconButton && widget.tooltip == 'Refresh note',
              ),
            )
            .onPressed,
        isNull,
      );
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();
      expect(saves, 1);
      expect(listRequests, 2);
    },
  );
  testWidgets('finance loads outstanding bills and statements on demand', (
    tester,
  ) async {
    final requests = <String>[];
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        requests.add(request.path);
        if (request.path == '/fam/parties/4') {
          return response({
            'legal_name': 'QA Supplier',
            'contacts': [
              {'name': 'Accounts desk'},
            ],
          });
        }
        if (request.path == '/fam/parties/4/statement') {
          return response({
            'party': {'legal_name': 'QA Supplier'},
            'outstanding': 75,
            'billReferences': [
              {'id': 1, 'bill_number': 'B-22', 'status': 'open'},
              {'id': 2, 'bill_number': 'R-7', 'status': 'closed'},
            ],
            'allocations': [
              {
                'from_bill_reference_id': 2,
                'to_bill_reference_id': 1,
                'allocation_date': '2026-11-26',
                'allocated_amount': '25.00',
              },
            ],
          });
        }
        expect(request.path, '/fam/parties/4/outstanding');
        return response({
          'openBills': 1,
          'outstanding': 75,
          'items': [
            {
              'bill_number': 'B-22',
              'due_date': '2026-12-12',
              'outstanding_amount': '75.00',
            },
          ],
        });
      });
    await tester.pumpWidget(
      MaterialApp(
        home: FinancePartyPage(
          api: ApiClient(
            baseUrl: 'https://example.test/api/v1',
            store: MemoryStore(),
            transport: dio,
          ),
          id: 4,
          summary: const {'legal_name': 'Saved QA Supplier'},
          offline: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Saved QA Supplier'), findsOneWidget);
    expect(requests, isEmpty);
    expect(find.text('View statement'), findsNothing);
    await tester.tap(find.text('Reconnect'));
    await tester.pumpAndSettle();
    expect(find.text('QA Supplier'), findsOneWidget);
    expect(find.text('Accounts desk'), findsOneWidget);
    expect(requests, ['/fam/parties/4']);
    await tester.tap(find.text('View outstanding bills'));
    await tester.pumpAndSettle();
    expect(find.text('B-22'), findsOneWidget);
    expect(find.text('75.00'), findsOneWidget);
    await tester.tap(find.text('View statement'));
    await tester.pumpAndSettle();
    expect(find.text('R-7 → B-22'), findsOneWidget);
    expect(find.text('25.00'), findsOneWidget);
  });
  testWidgets(
    'HR leave applies and confirms cancellation through the shared API',
    (tester) async {
      var submitted = false;
      var cancelled = false;
      const type = {
        'id': 2,
        'name': 'Annual leave',
        'is_active': true,
        'half_day_allowed': true,
      };
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          switch (request.path) {
            case '/leave/types':
              return response([type]);
            case '/leave/balance':
              return response([
                {'leave_type': type, 'available': 8, 'used': 2, 'pending': 0},
              ]);
            case '/leave/my-requests':
              return response([
                if (submitted)
                  {
                    'id': 8,
                    'leave_type': type,
                    'from_date': '2026-12-01',
                    'to_date': '2026-12-02',
                    'days_count': 2,
                    'status': cancelled ? 'Cancelled' : 'Pending',
                  },
              ]);
            case '/leave/apply':
              expect(request.method, 'POST');
              expect(request.data, {
                'leave_type_id': 2,
                'from_date': '2026-12-01',
                'to_date': '2026-12-02',
                'is_half_day': false,
              });
              submitted = true;
              return response({'id': 8}, 201);
            case '/leave/requests/8/cancel':
              expect(request.method, 'PUT');
              cancelled = true;
              return response({'message': 'Leave request cancelled'});
            default:
              fail('Unexpected request ${request.path}');
          }
        });
      await tester.pumpWidget(
        MaterialApp(
          home: MyLeavePage(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('8 days available'), findsOneWidget);
      final localizations = MaterialLocalizations.of(
        tester.element(find.byType(MyLeavePage)),
      );
      await tester.tap(find.text('Apply for leave'));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<int>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Annual leave').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Choose leave dates'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip(localizations.inputDateModeButtonLabel));
      await tester.pumpAndSettle();
      final fields = find.descendant(
        of: find.byType(DateRangePickerDialog),
        matching: find.byType(TextField),
      );
      await tester.enterText(fields.first, '12/01/2026');
      await tester.enterText(fields.last, '12/02/2026');
      await tester.tap(find.text(localizations.okButtonLabel));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Submit request'));
      await tester.pumpAndSettle();
      expect(submitted, isTrue);
      expect(find.text('Pending'), findsOneWidget);
      await tester.tap(find.text('Pending'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel request'));
      await tester.pumpAndSettle();
      expect(cancelled, isFalse);
      await tester.tap(find.text('Confirm cancellation'));
      await tester.pumpAndSettle();
      expect(find.text('Cancelled'), findsOneWidget);
    },
  );
  testWidgets(
    'HR attendance records mobile punches and refreshes from the server',
    (tester) async {
      final punches = <String>[];
      final ranges = <Object?>[];
      final months = <Object?>[];
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          switch (request.path) {
            case '/attendance/today':
              return response({
                'attendance': {
                  if (punches.isNotEmpty) 'check_in': '2026-11-27T09:00:00Z',
                  if (punches.length == 2) 'check_out': '2026-11-27T17:00:00Z',
                },
              });
            case '/attendance/my':
              ranges.add(request.queryParameters['from_date']);
              return response([]);
            case '/attendance/summary/monthly':
              months.add(request.queryParameters['month']);
              return response({
                'present': 3,
                'absent': 1,
                'half_day': 2,
                'overtime_hours': 4,
              });
            case '/attendance/check-in':
              expect(request.method, 'POST');
              expect(request.data, {'source': 'Mobile'});
            case '/attendance/check-out':
              expect(request.method, 'POST');
              expect(request.data, isEmpty);
            default:
              fail('Unexpected request ${request.path}');
          }
          punches.add(request.path);
          return response({});
        });
      await tester.pumpWidget(
        MaterialApp(
          home: MyAttendancePage(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Check In'));
      await tester.pumpAndSettle();
      expect(find.text('Checked in'), findsOneWidget);
      await tester.tap(find.text('Check Out'));
      await tester.pumpAndSettle();
      expect(find.text('Checked out'), findsOneWidget);
      expect(find.text('Check Out'), findsNothing);
      expect(punches, ['/attendance/check-in', '/attendance/check-out']);
      expect(ranges.first, endsWith('-01'));
      expect(
        find.text('Present 3 · Absent 1 · Half day 2 · Overtime 4 h'),
        findsOneWidget,
      );
      final localizations = MaterialLocalizations.of(
        tester.element(find.byType(MyAttendancePage)),
      );
      await tester.tap(find.byIcon(Icons.date_range_outlined));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip(localizations.inputDateModeButtonLabel));
      await tester.pumpAndSettle();
      final fields = find.byType(TextField);
      await tester.enterText(fields.first, '02/03/2025');
      await tester.enterText(fields.last, '02/08/2025');
      await tester.tap(find.text(localizations.okButtonLabel));
      await tester.pumpAndSettle();
      expect(ranges.last, '2025-02-03');
      expect(months.last, 2);
    },
  );
  testWidgets(
    'GST opens saved invoice summary without a network request or write actions',
    (tester) async {
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((_) async {
          fail('Offline invoice must not call the server');
        });
      await tester.pumpWidget(
        MaterialApp(
          home: GstInvoicePage(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
            id: 7,
            offline: true,
            canEdit: true,
            canIssue: true,
            canExport: true,
            summary: const {
              'invoice_number': 'GST-7',
              'document_status': 'draft',
              'status': 'draft',
              'currency': 'INR',
              'total_amount': '118.00',
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('GST-7'), findsOneWidget);
      expect(find.text('Offline · Saved invoice'), findsOneWidget);
      expect(find.text('INR 118.00'), findsOneWidget);
      expect(find.text('Edit dates'), findsNothing);
      expect(find.text('Issue invoice'), findsNothing);
      expect(find.text('Save invoice PDF'), findsNothing);
      dio.httpClientAdapter = FakeAdapter((request) async {
        expect(request.path, '/srm/invoices/7');
        return response({'invoice_number': 'GST-7', 'status': 'draft'});
      });
      await tester.tap(find.text('Reconnect'));
      await tester.pumpAndSettle();
      expect(find.text('Offline · Saved invoice'), findsNothing);
      expect(find.text('Save invoice PDF'), findsOneWidget);
    },
  );
  testWidgets(
    'issuing a GST invoice requires confirmation and reloads its status',
    (tester) async {
      var issued = false;
      var changes = 0;
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'POST') {
            expect(request.path, '/srm/invoices/7/approve');
            expect(issued, isFalse);
            issued = true;
            return response({'status': 'approved'});
          }
          expect(request.path, '/srm/invoices/7');
          return response({
            'invoice_number': 'GST-7',
            'status': issued ? 'approved' : 'draft',
            'document_status': issued ? 'issued' : 'draft',
          });
        });
      await tester.pumpWidget(
        MaterialApp(
          home: GstInvoicePage(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
            id: 7,
            canIssue: true,
            onChanged: () => changes++,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Issue invoice'));
      await tester.pumpAndSettle();
      expect(issued, isFalse);
      await tester.tap(find.text('Confirm issue'));
      await tester.pumpAndSettle();
      expect(find.text('issued'), findsOneWidget);
      expect(changes, 1);
      expect(find.text('Issue invoice'), findsNothing);
    },
  );
  testWidgets('GST PDF export rejects a non-PDF server response', (
    tester,
  ) async {
    var pdfRequests = 0;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        if (request.path == '/srm/invoices/7') {
          return response({'invoice_number': 'GST-7'});
        }
        expect(request.path, '/srm/invoices/7/pdf');
        expect(request.responseType, ResponseType.bytes);
        pdfRequests++;
        return response({'detail': 'Not a PDF'});
      });
    await tester.pumpWidget(
      MaterialApp(
        home: GstInvoicePage(
          api: ApiClient(
            baseUrl: 'https://example.test/api/v1',
            store: MemoryStore(),
            transport: dio,
          ),
          id: 7,
          canExport: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save invoice PDF'));
    await tester.pumpAndSettle();
    expect(pdfRequests, 1);
    expect(find.text('The server did not return a PDF.'), findsOneWidget);
  });
  testWidgets(
    'GST updates manual lines and keeps source-backed lines read-only',
    (tester) async {
      final line = {
        'id': 2,
        'description': 'Manual work',
        'quantity': '1',
        'unit_price': '100',
        'discount_amount': '0',
        'tax_amount': '18',
      };
      final invoice = {
        'invoice_number': 'GST-7',
        'status': 'draft',
        'currency': 'INR',
        'lines': [
          line,
          {
            'id': 3,
            'description': 'Reserved work',
            'source_type': 'sales_order',
          },
        ],
      };
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'GET') return response(invoice);
          expect(request.method, 'PATCH');
          expect(request.path, '/srm/business/invoices/7/lines/2');
          expect(
            request.data,
            {...line}
              ..remove('id')
              ..['quantity'] = '2',
          );
          return response({
            ...invoice,
            'total_amount': '218.00',
            'lines': [
              {...line, 'quantity': '2'},
            ],
          });
        });
      await tester.pumpWidget(
        MaterialApp(
          home: GstInvoicePage(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
            id: 7,
            canEdit: true,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byTooltip('Edit draft line'), findsOneWidget);
      await tester.tap(find.byTooltip('Edit draft line'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField).at(1), '2');
      await tester.tap(find.text('Save line'));
      await tester.pumpAndSettle();
      expect(find.text('INR 218.00'), findsOneWidget);
      expect(find.text('Quantity 2'), findsOneWidget);
    },
  );
  testWidgets('GST adds a manual draft line and reloads server totals', (
    tester,
  ) async {
    Json? line;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Branch'], '6');
          switch ((request.method, request.path)) {
            case ('GET', '/srm/invoices/7'):
              return response({
                'invoice_number': 'GST-7',
                'status': 'draft',
                'currency': 'INR',
                'total_amount': line == null ? '0.00' : '29.50',
                'lines': [?line],
              });
            case ('POST', '/srm/invoices/7/lines'):
              expect(request.data, {
                'description': 'Packing materials',
                'quantity': '2',
                'unit_price': '12.50',
                'discount_amount': '0',
                'tax_amount': '4.50',
                'source_type': 'manual',
              });
              line = {'id': 4, ...request.data as Json};
              return response(line!, 201);
            default:
              throw StateError('Unexpected request ${request.path}');
          }
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: GstInvoicePage(
          api: api,
          id: 7,
          canEdit: true,
          scopeHeaders: const {'X-Suite-Branch': '6'},
        ),
      ),
    );
    await tester.pumpAndSettle();
    final add = find.text('Add line item');
    await tester.ensureVisible(add);
    await tester.tap(add);
    await tester.pumpAndSettle();
    for (final (label, value) in [
      ('Description', 'Packing materials'),
      ('Quantity', '2'),
      ('Unit price', '12.50'),
      ('Tax amount', '4.50'),
    ]) {
      final field = find.widgetWithText(TextFormField, label);
      await tester.ensureVisible(field);
      await tester.enterText(field, value);
    }
    await tester.tap(find.text('Save line'));
    await tester.pumpAndSettle();
    expect(find.text('Packing materials'), findsOneWidget);
    expect(find.text('INR 29.50'), findsOneWidget);
  });

  testWidgets('GST draft date editing sends only the changed date', (
    tester,
  ) async {
    var dueDate = '2026-12-01';
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        expect(request.path, '/srm/invoices/7');
        expect(request.headers['X-Suite-Branch'], '6');
        if (request.method == 'PATCH') {
          expect(request.data, {'due_date': '2026-12-15'});
          dueDate = '2026-12-15';
        }
        return response({
          'invoice_number': 'GST-7',
          'status': 'draft',
          'issue_date': '2026-11-27',
          'due_date': dueDate,
        });
      });
    await tester.pumpWidget(
      MaterialApp(
        home: GstInvoicePage(
          api: ApiClient(
            baseUrl: 'https://example.test/api/v1',
            store: MemoryStore(),
            transport: dio,
          ),
          id: 7,
          canEdit: true,
          scopeHeaders: const {'X-Suite-Branch': '6'},
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Edit dates'));
    await tester.pumpAndSettle();
    final field = find.byType(TextFormField).last;
    await tester.enterText(field, '2026-02-31');
    await tester.tap(find.text('Save dates'));
    await tester.pumpAndSettle();
    expect(find.text('Enter a valid date as YYYY-MM-DD.'), findsOneWidget);
    await tester.enterText(field, '2026-12-15');
    await tester.tap(find.text('Save dates'));
    await tester.pumpAndSettle();
    expect(find.text('2026-12-15'), findsOneWidget);
  });
  testWidgets(
    'GST invoice reads document, delivery, and payment from shared API',
    (tester) async {
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.method, 'GET');
          expect(request.path, '/srm/invoices/7');
          return response({
            'invoice_number': 'GST-7',
            'document_status': 'issued',
            'delivery_status': 'delivered',
            'payment_status': 'partially_paid',
            'currency': 'INR',
            'total_amount': '118.00',
            'balance_amount': '18.00',
            'lines': [
              {'description': 'Consulting', 'quantity': 1},
            ],
          });
        });
      await tester.pumpWidget(
        MaterialApp(
          home: GstInvoicePage(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
            id: 7,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('GST-7'), findsOneWidget);
      expect(find.text('partially paid'), findsOneWidget);
      expect(find.text('INR 18.00'), findsOneWidget);
      expect(find.text('Consulting'), findsOneWidget);
    },
  );
  testWidgets('starter values submit one enabled module and show the result', (
    tester,
  ) async {
    var writes = 0;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        if (request.method == 'GET') {
          expect(request.path, '/access/settings/starter-values/catalog');
          return response({
            'groups': [
              {
                'key': 'fam',
                'title': 'Finance',
                'values': ['Cash', 'Card'],
              },
            ],
          });
        }
        expect(request.method, 'POST');
        expect(request.path, '/access/settings/starter-values/apply');
        expect(request.data, {
          'modules': ['fam'],
        });
        return response({'total': writes++ == 0 ? 2 : 0});
      });
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StarterValuesPanel(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
            editable: true,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Cash'), findsOneWidget);
    await tester.tap(find.text('Add starter values'));
    await tester.pumpAndSettle();
    expect(find.text('Added 2 starter records for Finance.'), findsOneWidget);
    await tester.tap(find.text('Add starter values'));
    await tester.pumpAndSettle();
    expect(
      find.text('Finance starter values are already configured.'),
      findsOneWidget,
    );
  });
  testWidgets('lead source settings save normalized lines to the shared API', (
    tester,
  ) async {
    var writes = 0;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        expect(request.path, '/access/settings/crm-lead-sources/options');
        if (request.method == 'GET') {
          return response({
            'sources': ['Existing'],
            'defaults': ['Referral'],
          });
        }
        expect(request.method, 'PUT');
        expect(request.data, {
          'sources': ['Referral', 'Event'],
        });
        writes++;
        return response({
          'sources': ['Referral', 'Event', 'Other'],
        });
      });
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LeadSourcesPanel(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
            editable: true,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final field = find.byType(TextField);
    await tester.tap(find.text('Use starter list'));
    await tester.pumpAndSettle();
    expect(tester.widget<TextField>(field).controller!.text, 'Referral');
    await tester.enterText(field, 'Referral\nreferral');
    await tester.tap(find.text('Save sources'));
    await tester.pumpAndSettle();
    expect(writes, 0);
    await tester.enterText(field, 'Referral\n\n Event ');
    await tester.tap(find.text('Save sources'));
    await tester.pumpAndSettle();
    expect(writes, 1);
    expect(
      tester.widget<TextField>(field).controller!.text,
      'Referral\nEvent\nOther',
    );
  });
  testWidgets(
    'branch assignments preserve existing module roles and policy version',
    (tester) async {
      final savedGrant = {
        'branch_id': 1,
        'can_write': true,
        'module_grants': {
          'crm': {'enabled': true},
        },
      };
      final policy = {
        'version': 5,
        'all_branches': false,
        'manage_access': false,
        'use_home_branch': true,
        'grants': [savedGrant],
      };
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.path.endsWith('/users')) {
            return response([
              {'id': 2, 'email': 'manager@example.test'},
              {'id': 3, 'email': 'member@example.test'},
            ]);
          }
          expect(request.path, '/branches/access/3');
          if (request.method == 'GET') return response(policy);
          expect(request.method, 'PUT');
          expect(request.data['expected_version'], 5);
          expect(request.data['reason'], 'Cover Pune office');
          expect(request.data['grants'], [
            savedGrant,
            {'branch_id': 2, 'can_write': false},
          ]);
          return response({
            ...policy,
            'version': 6,
            'grants': request.data['grants'],
          });
        });
      await tester.pumpWidget(
        MaterialApp(
          home: BranchMembershipPage(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
            actorId: 2,
            branches: const [
              {'id': 2, 'name': 'Pune', 'can_write': true},
            ],
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('manager@example.test'), findsNothing);
      await tester.tap(find.text('member@example.test'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Pune'));
      await tester.enterText(find.byType(TextField), 'Cover Pune office');
      await tester.pumpAndSettle();
      await tester.tap(find.text('Save branch memberships'));
      await tester.pumpAndSettle();
      expect(find.text('Branch memberships saved.'), findsOneWidget);
    },
  );
  testWidgets(
    'branch settings creates and renames a branch with the server version',
    (tester) async {
      var created = false;
      var name = 'Pune';
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'POST') {
            expect(request.path, '/branches');
            expect(request.data, {
              'name': 'Pune',
              'code': 'PNQ',
              'reason': 'New office',
            });
            created = true;
            return response({'id': 3, 'name': 'Pune', 'code': 'PNQ'}, 201);
          }
          if (request.method == 'PATCH') {
            expect(request.path, '/branches/3');
            expect(request.data, {
              'name': 'Pune Central',
              'reason': 'Updated office name',
              'expected_version': 4,
            });
            name = 'Pune Central';
            return response({'id': 3, 'name': name, 'version': 5});
          }
          if (request.path == '/branches/context') {
            return response({'manage_access': true, 'branches': []});
          }
          expect(request.path, '/branches/manage');
          return response({
            'retention_days': 45,
            'branches': [
              if (created)
                {
                  'id': 3,
                  'name': name,
                  'code': 'PNQ',
                  'is_active': true,
                  'can_manage': true,
                  'can_trash': false,
                  'state': 'active',
                  'version': 4,
                },
            ],
          });
        });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: BranchSettingsPanel(
              api: ApiClient(
                baseUrl: 'https://example.test/api/v1',
                store: MemoryStore(),
                transport: dio,
              ),
              editable: true,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Create branch'));
      await tester.pumpAndSettle();
      for (final (index, value) in [
        (0, 'Pune'),
        (1, 'PNQ'),
        (2, 'New office'),
      ]) {
        await tester.enterText(find.byType(TextFormField).at(index), value);
      }
      await tester.tap(find.widgetWithText(FilledButton, 'Create branch').last);
      await tester.pumpAndSettle();
      expect(created, isTrue);
      expect(find.text('Pune'), findsOneWidget);
      await tester.tap(find.byTooltip('Manage Pune'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Rename branch'));
      await tester.pumpAndSettle();
      final fields = find.byType(TextFormField);
      await tester.enterText(fields.first, 'Pune Central');
      await tester.enterText(fields.last, 'Updated office name');
      await tester.tap(find.widgetWithText(FilledButton, 'Rename branch'));
      await tester.pumpAndSettle();
      expect(find.text('Pune Central'), findsOneWidget);
    },
  );
  test('inventory forgets saved branches after access is denied', () async {
    TestWidgetsFlutterBinding.ensureInitialized();
    FlutterSecureStorage.setMockInitialValues({});
    var allowed = true;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        return allowed
            ? response({
                'branches': [
                  {
                    'id': 3,
                    'name': 'Warehouse',
                    'can_write': true,
                    'is_active': true,
                  },
                ],
              })
            : response({'detail': 'Access revoked'}, 403);
      });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: dio,
    );
    final drafts = InventoryOfflineCreates(
      '["https://example.test/api/v1",2,7]',
    );
    expect(await drafts.writableBranches(api), hasLength(1));
    allowed = false;
    await expectLater(drafts.writableBranches(api), throwsA(isA<ApiFailure>()));
    await expectLater(
      drafts.writableBranches(api, offline: true),
      throwsA(isA<ApiFailure>()),
    );
  });
  test('offline inventory creations reuse one server receipt key', () async {
    TestWidgetsFlutterBinding.ensureInitialized();
    FlutterSecureStorage.setMockInitialValues({});
    const base = 'https://example.test/api/v1';
    const scope = '["https://example.test/api/v1",2,7]';
    await InventoryOfflineCreates(scope).enqueue({
      'kind': 'product',
      'name': 'Sample product',
      'code': 'SAMPLE-1',
      'currency': 'INR',
    }, branchId: 4);
    final queue = InventoryOfflineCreates(scope);
    final operations = <String>[];
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        expect(request.method, 'POST');
        expect(request.path, '/catalog/items');
        expect(request.queryParameters['source'], 'srm');
        expect(request.headers['X-Suite-Organization'], '7');
        expect(request.headers['X-Suite-Branch'], '4');
        operations.add(request.headers['X-Offline-Operation'] as String);
        if (operations.length == 1) {
          throw DioException(
            requestOptions: request,
            type: DioExceptionType.connectionError,
          );
        }
        return response({'id': 12}, 201);
      });
    final api = ApiClient(baseUrl: base, store: MemoryStore(), transport: dio);
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    await queue.sync(api);
    expect(await queue.entries(), hasLength(1));
    await queue.sync(api);
    expect(await queue.entries(), isEmpty);
    expect(operations, hasLength(2));
    expect(operations.first, operations.last);
  });
  testWidgets(
    'business defaults keep unrelated overrides and send the server version',
    (tester) async {
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.path, '/access/settings/defaults/configuration');
          if (request.method == 'PUT') {
            expect(request.headers['X-Suite-Organization'], '7');
            expect(request.queryParameters, {'module': 'crm', 'branch_id': 6});
            expect(request.data, {
              'version': 3,
              'values': {
                'currency': 'INR',
                'lead_source': 'Referral',
                'task_priority': 'High',
              },
            });
            return response({'saved': true, 'version': 4});
          }
          return response({
            'companyId': 7,
            'version': 3,
            'inherited': {'currency': 'USD', 'lead_source': 'Website'},
            'overrides': {'lead_source': 'Website', 'task_priority': 'High'},
            'fields': [
              {
                'key': 'lead_source',
                'label': 'Lead source',
                'type': 'select',
                'options': [
                  {'value': 'Website', 'label': 'Website'},
                  {'value': 'Referral', 'label': 'Referral'},
                ],
              },
            ],
            'choices': {
              'branches': [
                {'value': 6, 'label': 'Main Branch'},
              ],
            },
          });
        });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: BusinessDefaultsPanel(
              api: ApiClient(
                baseUrl: 'https://example.test/api/v1',
                store: MemoryStore(),
                transport: dio,
              ),
              editable: true,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('CRM').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<int>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Main Branch').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(SwitchListTile).first);
      await tester.pump();
      await tester.enterText(find.byType(TextFormField), 'inr');
      await tester.pump();
      await tester.ensureVisible(find.byType(DropdownButton<Object>));
      await tester.tap(find.byType(DropdownButton<Object>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Referral').last);
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Save defaults'));
      await tester.tap(find.text('Save defaults'));
      await tester.pumpAndSettle();
      expect(find.text('Business defaults saved.'), findsOneWidget);
    },
  );
  testWidgets(
    'company profile saves only changed fields for the loaded company',
    (tester) async {
      var name = 'Before';
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.path, '/access/settings/company-profile');
          if (request.method == 'PATCH') {
            expect(request.headers['X-Suite-Organization'], '7');
            expect(request.data, {'name': 'After'});
            name = 'After';
            return response({'saved': true});
          }
          return response({
            'companyId': 7,
            'editable': true,
            'profile': {'name': name, 'city': 'Hyderabad'},
          });
        });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: CompanyProfilePanel(
              api: ApiClient(
                baseUrl: 'https://example.test/api/v1',
                store: MemoryStore(),
                transport: dio,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField).first, 'After');
      await tester.pump();
      await tester.tap(find.text('Save company details'));
      await tester.pumpAndSettle();
      expect(name, 'After');
    },
  );
  testWidgets(
    'signed-in dashboard uploads queued CRM edits without opening CRM',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({});
      const base = 'https://example.test/api/v1';
      final queue = CrmOfflineEdits('["$base",2,7]');
      await queue.enqueue(9, 4, {'first_name': 'Queued'});
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.path == '/notifications/unread-count') {
            return response({'unread': 0});
          }
          if (request.path == '/access/me') {
            return response({
              'companyId': 7,
              'grants': {
                'crm': {'enabled': true},
              },
            });
          }
          expect(request.path, '/crm/lead-management/leads/9');
          expect(request.method, 'PATCH');
          return response({'version': 5});
        });
      final api = ApiClient(
        baseUrl: base,
        store: MemoryStore(),
        transport: dio,
      );
      await api.acceptTokens({
        'access_token': 'access',
        'refresh_token': 'refresh',
      });
      final controller = AppController(api, suiteLogin: true)
        ..loading = false
        ..user = SessionUser.fromJson({
          'id': 2,
          'email': 'mobile@example.test',
        });
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpWidget(BusinessSuiteApp(controller: controller));
      await tester.pumpAndSettle();
      expect(await queue.pending(9), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  test(
    'queued CRM names survive retry and preserve a server conflict',
    () async {
      TestWidgetsFlutterBinding.ensureInitialized();
      FlutterSecureStorage.setMockInitialValues({});
      final dio = Dio();
      final api = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: dio,
      );
      await api.acceptTokens({
        'access_token': 'access',
        'refresh_token': 'refresh',
      });
      const scope = '["https://example.test/api/v1",2,7]';
      await CrmOfflineEdits(scope).enqueue(9, 4, {'first_name': 'Local name'});
      final queue = CrmOfflineEdits(scope);
      dio.httpClientAdapter = FakeAdapter(
        (r) async => throw DioException(
          requestOptions: r,
          type: DioExceptionType.connectionError,
        ),
      );
      await queue.sync(api);
      expect(await queue.hasPending, isTrue);
      dio.httpClientAdapter = FakeAdapter((r) async {
        expect(r.path, '/crm/lead-management/leads/9');
        expect(r.headers['X-Suite-Organization'], '7');
        expect(r.data['version'], 4);
        return response({'detail': 'Lead changed'}, 409);
      });
      await queue.sync(api);
      expect(await queue.hasPending, isFalse);
      expect((await queue.pending(9))?['error'], 'Lead changed');
      expect((await queue.pending(9))?['values']['first_name'], 'Local name');
      await queue.enqueue(10, 5, {'first_name': 'Synced name'});
      await queue.enqueue(9, 7, {
        'first_name': 'Reviewed name',
      }, rejectedVersion: 4);
      dio.httpClientAdapter = FakeAdapter((r) async {
        expect(r.path, '/crm/lead-management/leads/9');
        expect(r.data, {
          'version': 7,
          'values': {'first_name': 'Reviewed name'},
        });
        return response({'version': 8});
      });
      await queue.sync(api, leadId: 9);
      expect(await queue.pending(9), isNull);
      expect(await queue.pending(10), isNotNull);
      dio.httpClientAdapter = FakeAdapter((r) async {
        expect(r.path, '/crm/lead-management/leads/10');
        return response({'version': 6});
      });
      await queue.sync(api);
      expect(await queue.pending(10), isNull);
    },
  );
  testWidgets('CRM lead edit sends the displayed record version', (
    tester,
  ) async {
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        expect(request.path, '/crm/lead-management/leads/9');
        if (request.method == 'GET') {
          return response({'first_name': 'Before', 'version': 4});
        }
        expect(request.method, 'PATCH');
        expect(request.data['version'], 4);
        expect(request.data['values'], {'first_name': 'After'});
        return response({'first_name': 'After', 'version': 5});
      });
    await tester.pumpWidget(
      MaterialApp(
        home: CrmLeadPage(
          api: ApiClient(
            baseUrl: 'https://example.test/api/v1',
            store: MemoryStore(),
            transport: dio,
          ),
          summary: const {'id': 9},
          offline: false,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Edit lead details'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).first, 'After');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(find.text('After'), findsOneWidget);
  });
  testWidgets(
    'CRM offers a durable edit after the detail request loses connection',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({});
      final edits = CrmOfflineEdits('["https://example.test/api/v1",2,7]');
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.method, 'GET');
          throw DioException(
            requestOptions: request,
            type: DioExceptionType.connectionError,
          );
        });
      await tester.pumpWidget(
        MaterialApp(
          home: CrmLeadPage(
            api: ApiClient(
              baseUrl: 'https://example.test/api/v1',
              store: MemoryStore(),
              transport: dio,
            ),
            summary: const {'id': 9, 'first_name': 'Before', 'version': 4},
            offline: false,
            offlineEdits: edits,
          ),
        ),
      );
      expect(find.text('Before'), findsOneWidget);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Edit lead offline'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField).at(2), 'Acme');
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();
      expect(find.text('Edit saved · Awaiting sync'), findsOneWidget);
      expect((await edits.pending(9))?['version'], 4);
      expect((await edits.pending(9))?['values'], {'company_name': 'Acme'});
    },
  );
  testWidgets('offline CRM lead reconnects in place', (tester) async {
    var reads = 0;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        reads++;
        expect(request.path, '/crm/lead-management/leads/9');
        return response({'first_name': 'Current lead', 'version': 5});
      });
    await tester.pumpWidget(
      MaterialApp(
        home: CrmLeadPage(
          api: ApiClient(
            baseUrl: 'https://example.test/api/v1',
            store: MemoryStore(),
            transport: dio,
          ),
          summary: const {
            'id': 9,
            'first_name': 'Saved lead',
            'version': 4,
            'source': 'Website',
            'rating': 'Hot',
          },
          offline: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(reads, 0);
    expect(find.text('Saved lead'), findsOneWidget);
    expect(find.text('Website'), findsOneWidget);
    expect(find.text('Hot'), findsOneWidget);
    await tester.tap(find.text('Reconnect'));
    await tester.pumpAndSettle();
    expect(reads, 1);
    expect(find.text('Current lead'), findsOneWidget);
    expect(find.byTooltip('Refresh lead'), findsOneWidget);
  });
  testWidgets('offline order opens locally and reconnects in place', (
    tester,
  ) async {
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((_) async {
        fail('Offline order should not issue a request');
      });
    await tester.pumpWidget(
      MaterialApp(
        home: SalesOrderPage(
          api: ApiClient(
            baseUrl: 'https://example.test/api/v1',
            store: MemoryStore(),
            transport: dio,
          ),
          summary: const {
            'id': 8,
            'order_number': 'SO-8',
            'total_amount': '45.00',
            'currency': 'INR',
          },
          offline: true,
          canEdit: true,
          invoiceBuilder: (invoice) =>
              Scaffold(body: Text('Invoice ${invoice['id']}')),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Offline · Saved order summary'), findsOneWidget);
    expect(find.text('INR 45.00'), findsOneWidget);
    expect(find.text('Line items'), findsNothing);
    expect(find.text('Submit order for approval'), findsNothing);
    expect(find.text('Create invoice draft'), findsNothing);
    final actions = <String>[];
    dio.httpClientAdapter = FakeAdapter((request) async {
      if (request.method == 'POST') {
        actions.add(request.path);
        if (request.path == '/srm/invoices/draft-from-sales-order/8') {
          return response({'id': 19, 'status': 'draft'}, 201);
        }
        return response({
          'status': actions.length == 1 ? 'approved' : 'confirmed',
        });
      }
      expect(request.path, '/srm/sales-orders/8');
      return response({
        'order_number': 'SO-8',
        'status': 'draft',
        'lines': [
          {'description': 'Live order line'},
        ],
      });
    });
    await tester.tap(find.text('Reconnect'));
    await tester.pumpAndSettle();
    expect(find.text('Live order line'), findsOneWidget);
    expect(find.text('Reconnect'), findsNothing);
    for (final label in ['Submit order for approval', 'Confirm sales order']) {
      await tester.tap(find.text(label));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, label));
      await tester.pumpAndSettle();
    }
    expect(actions, [
      '/srm/sales-orders/8/submit',
      '/srm/sales-orders/8/confirm',
    ]);
    expect(find.text('confirmed'), findsOneWidget);
    await tester.tap(find.text('Create invoice draft'));
    await tester.pumpAndSettle();
    expect(actions.last, '/srm/invoices/draft-from-sales-order/8');
    expect(find.text('Create invoice draft'), findsNothing);
    await tester.tap(find.text('Open invoice'));
    await tester.pumpAndSettle();
    expect(find.text('Invoice 19'), findsOneWidget);
  });
  testWidgets('order summary remains visible after a temporary API failure', (
    tester,
  ) async {
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        expect(request.path, '/srm/sales-orders/8');
        expect(request.headers['X-Suite-Branch'], '3');
        return response({'detail': 'Unavailable'}, 503);
      });
    await tester.pumpWidget(
      MaterialApp(
        home: SalesOrderPage(
          api: ApiClient(
            baseUrl: 'https://example.test/api/v1',
            store: MemoryStore(),
            transport: dio,
          ),
          summary: const {'id': 8, 'order_number': 'SO-8'},
          offline: false,
          scopeHeaders: const {'X-Suite-Branch': '3'},
        ),
      ),
    );
    expect(find.text('SO-8'), findsOneWidget);
    await tester.pumpAndSettle();
    expect(find.text('SO-8'), findsOneWidget);
    expect(
      find.text('Refresh unavailable · Saved order summary'),
      findsOneWidget,
    );
    expect(find.text('Retry'), findsOneWidget);
  });
  testWidgets('offline inventory shows the summary and reconnects in place', (
    tester,
  ) async {
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        expect(request.path, '/srm/inventory/items/12');
        expect(request.headers['X-Suite-Branch'], '3');
        return response({
          'item_name': 'Updated product',
          'unit_code': 'EA',
          'balances': [
            {
              'warehouse_id': 4,
              'warehouse_name': 'Main Warehouse',
              'quantity': '9.250',
            },
          ],
          'ledger': [
            {
              'movement_number': 'MOV-12',
              'warehouse_name': 'Main Warehouse',
              'quantity_in': 3,
            },
          ],
        });
      });
    await tester.pumpWidget(
      MaterialApp(
        home: InventoryProductPage(
          api: ApiClient(
            baseUrl: 'https://example.test/api/v1',
            store: MemoryStore(),
            transport: dio,
          ),
          summary: const {'id': 12, 'item_name': 'Saved product'},
          offline: true,
          scopeHeaders: const {'X-Suite-Branch': '3'},
        ),
      ),
    );
    expect(find.text('Saved product'), findsOneWidget);
    await tester.pumpAndSettle();
    expect(find.text('MOV-12'), findsNothing);
    await tester.tap(find.text('Reconnect'));
    await tester.pumpAndSettle();
    expect(find.text('Updated product'), findsOneWidget);
    expect(find.text('Main Warehouse'), findsOneWidget);
    expect(find.text('Main Warehouse · In 3 · Out 0'), findsOneWidget);
    expect(find.text('9.250 EA'), findsOneWidget);
    expect(find.text('MOV-12'), findsOneWidget);
  });
  testWidgets('inventory records a stock movement in the selected branch', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    var recorded = false;
    var productReads = 0;
    final receipts = <Object?>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Branch'], '3');
          if (request.path == '/srm/inventory/warehouses') {
            return response({
              'items': [
                {'id': 4, 'warehouse_name': 'Main warehouse'},
              ],
            });
          }
          if (request.method == 'POST') {
            expect(
              request.path,
              '/srm/inventory/stock-movements/offline-create',
            );
            expect(request.data, {
              'product_id': 12,
              'warehouse_id': 4,
              'movement_type': 'stock_in',
              'quantity': '2.5',
            });
            receipts.add(request.headers['X-Offline-Operation']);
            if (receipts.length == 1) {
              return response({'detail': 'Unavailable'}, 503);
            }
            recorded = true;
            return response({}, 201);
          }
          expect(request.path, '/srm/inventory/items/12');
          productReads++;
          return response({
            'item_name': 'Test product',
            'current_quantity': recorded ? 8.5 : 6,
          });
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: InventoryProductPage(
          api: api,
          summary: const {'id': 12},
          offline: false,
          canRecordStock: true,
          scopeHeaders: const {'X-Suite-Branch': '3'},
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Record stock movement'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<int>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Main warehouse').last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Quantity'),
      '2.5',
    );
    await tester.tap(find.text('Save movement'));
    await tester.pumpAndSettle();
    expect(find.text('Pending stock movement'), findsOneWidget);
    await tester.tap(find.text('Retry same movement'));
    await tester.pumpAndSettle();
    expect(receipts, hasLength(2));
    expect(receipts.first, isNotNull);
    expect(receipts.last, receipts.first);
    expect(recorded, isTrue);
    expect(productReads, 2);
    expect(find.text('8.5'), findsOneWidget);
  });
  testWidgets(
    'native launcher opens authenticated module and settings routes',
    (tester) async {
      tester.view.physicalSize = const Size(430, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final calls = <RequestOptions>[];
      final guidedFlows = <Map<String, dynamic>>[
        {
          'id': 15,
          'name': 'Renewals',
          'active': true,
          'question_json': [
            {'prompt': 'When does the contract end?', 'required': true},
          ],
          'recommendation_json': {
            'nextStep': {'name': 'Book a renewal review'},
          },
        },
      ];
      final transport = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          calls.add(request);
          if (request.uri.path.endsWith('/crm/pipelines')) {
            return response({
              'items': [
                {'id': 2, 'name': 'Sales pipeline', 'is_default': true},
              ],
            });
          }
          if (request.uri.path.endsWith('/crm/pipeline-stages')) {
            expect(request.uri.queryParameters['pipeline_id'], '2');
            return response({
              'items': [
                {'id': 4, 'name': 'Qualified'},
              ],
            });
          }
          if (request.uri.path.endsWith('/crm/deals')) {
            expect(request.uri.queryParameters['pipeline_id'], '2');
            return response({
              'items': [
                {'id': 83, 'name': 'Next deal', 'stage_id': 4},
              ],
              'total': 1,
            });
          }
          if (request.path == '/crm/guided-selling-flows' &&
              request.method == 'POST') {
            final created = {'id': 16, ...request.data as Map<String, dynamic>};
            guidedFlows.add(created);
            return response(created, 201);
          }
          return switch (request.path) {
            '/access/me' => response({
              'companyName': 'Example company',
              'companyId': 7,
              'grants': {
                for (final key in [
                  'srm',
                  'power_apps',
                  'hrms',
                  'crm',
                  'project_management',
                  'fam',
                ])
                  key: {'enabled': true},
              },
            }),
            '/branches/context' => response({
              'branches': [
                {'id': 6, 'name': 'Main Branch', 'is_active': true},
              ],
            }),
            '/access/settings' => response({
              'options': [
                {
                  'id': 'account',
                  'title': 'Account security',
                  'description': 'Manage your account',
                },
              ],
            }),
            '/access/launcher-preferences' => response({
              'favorites': request.method == 'PUT'
                  ? (request.data as Map)['favorites']
                  : ['future_app'],
            }),
            '/access/settings/options/account' => response({
              'description': 'Manage your account',
              'editable': true,
            }),
            '/auth/sessions/me' => response([
              {'device_name': 'Test phone', 'status': 'active'},
            ]),
            '/auth/change-password' => response({'message': 'Updated'}),
            '/srm/industry/records' => response({
              'items': [
                {
                  'id': 61,
                  'title': 'Sample booking',
                  'status': 'booked',
                  'data': {'customer_name': 'Asha Rao'},
                },
                {'id': 62, 'title': 'Previous visit', 'status': 'completed'},
              ],
            }),
            '/srm/industry/appointments/61' => response({
              'id': 61,
              'title': 'Sample booking',
              'revision': 4,
              'status': 'booked',
              'data': {'service_name': 'Consultation'},
            }),
            '/srm/industry/capabilities' => response({
              'appointment_actions': ['check_in'],
            }),
            '/srm/industry/records/61/transition' => response({
              'id': 61,
              'title': 'Sample booking',
              'revision': 5,
              'status': 'checked_in',
            }),
            '/notifications/' => response({
              'items': [
                {
                  'id': 12,
                  'title': 'Sample update',
                  'message': 'Example notification',
                  'is_read': false,
                },
              ],
            }),
            '/notifications/12/read' => response({'is_read': true}),
            '/notifications/unread-count' => response({
              'unread': calls.any((r) => r.path == '/notifications/12/read')
                  ? 0
                  : 1,
            }),
            '/crm/lead-management/leads' ||
            '/fam/parties' ||
            '/project-management/notes' => response([]),
            '/fam/inventory/reports/gross-margin' => response({
              'attribution': {'currency': 'INR'},
              'items': [
                {
                  'item_name': 'Sample product',
                  'revenue_status': 'Incomplete attribution',
                  'revenue': 500,
                  'cogs': 300,
                  'gross_margin': null,
                },
              ],
            }),
            '/fam/inventory/reports/cogs' => response({
              'currency': 'INR',
              'total_cogs': 300,
              'items': [
                {
                  'movement_number': 'OUT-1',
                  'cogs_value': 300,
                  'voucher_posted': true,
                },
              ],
            }),
            '/fam/inventory/reports/hsn-summary' => response({
              'currency': 'INR',
              'items': [
                {'hsn_code': '844399', 'items': 1, 'stock_value': 900},
              ],
            }),
            '/fam/inventory/reconciliation/gl' => response({
              'currency': 'INR',
              'inventory_ledger_id': 12,
              'stock_valuation': 900,
              'ledger_balance': 880,
              'difference': 20,
              'status': 'variance',
            }),
            '/fam/inventory/reconciliation/grni' => response({
              'currency': 'INR',
              'grni_outstanding': 250,
              'total': 1,
              'items': [
                {'movement_number': 'GRN-2', 'grni_value': 250},
              ],
            }),
            '/fam/inventory/reconciliation/cogs' => response({
              'currency': 'INR',
              'stock_issue_value': 300,
              'cogs_posted': 270,
              'difference': 30,
              'items': [
                {'movement_number': 'ISSUE-2', 'difference': 30},
              ],
            }),
            '/fam/inventory/reconciliation/gst' => response({
              'total': 1,
              'exceptions': 1,
              'items': [
                {'sku': 'SKU-12', 'gst_rate_configured': false},
              ],
            }),
            '/fam/inventory/reconciliation/srm' => response({
              'srm_sales_orders': 8,
              'srm_invoices': 3,
              'inventory_reservations': 2,
              'posted_inventory_movements': 1,
              'duplicate_deduction_guard': 'Duplicate deductions are blocked',
            }),
            '/fam/inventory/audit' => response({
              'total': 1,
              'items': [
                {
                  'action': 'STOCK_OUT',
                  'record_type': 'inventory_movement',
                  'record_id': 44,
                },
              ],
            }),
            '/power-apps/environments' => response({
              'items': [
                {'key': 'development', 'enabled': true},
                {'key': 'production', 'enabled': false},
              ],
            }),
            '/power-apps/overview' => response({
              'counts': {'total_apps': 3, 'active_automations': 2},
              'recent': [
                {
                  'name': 'Approval workflow',
                  'id': 12,
                  'application_id': 'automations',
                  'status': 'draft',
                },
              ],
            }),
            '/power-apps/automations/12' => response({
              'name': 'Approval workflow',
              'version': 2,
              'status': 'draft',
              'definition': {
                'trigger': {'type': 'manual'},
                'nodes': [
                  {'id': 'Review', 'type': 'approval'},
                ],
              },
            }),
            '/employees/' => response({
              'total': request.queryParameters['search'] == null ? 2 : 1,
              'per_page': 1,
              'items': [
                if (request.queryParameters['page'] == 2)
                  {'id': 28, 'first_name': 'Next', 'last_name': 'Employee'}
                else
                  {'id': 27, 'first_name': 'Sample', 'last_name': 'Employee'},
              ],
            }),
            '/employees/27' => response({
              'first_name': 'Sample',
              'last_name': 'Employee',
              'work_email': 'qa@example.test',
              'employment_type': 'Full-time',
              'department_id': 10,
              'designation_id': 15,
            }),
            '/company/departments/' => response([
              {'id': 10, 'name': 'Operations'},
            ]),
            '/company/designations/' => response([
              {'id': 15, 'name': 'Coordinator'},
            ]),
            '/srm/sales-orders' => response([
              {'id': 8, 'title': 'Sample order'},
            ]),
            '/srm/sales-orders/8' => response({
              'order_number': 'SO-8',
              'lines': [
                {'description': 'Sample line'},
              ],
            }),
            '/srm/inventory/items' => response({
              'items': [
                {'id': 12, 'item_name': 'Sample product', 'sku': 'SKU-12'},
              ],
            }),
            '/srm/inventory/items/12' => response({
              'item_name': 'Sample product',
              'sku': 'SKU-12',
              'ledger': [
                {'movement_number': 'STOCK-1', 'quantity_in': 3},
              ],
            }),
            '/srm/inventory/warehouses' => response({
              'items': [
                {'id': 4, 'warehouse_name': 'Main warehouse'},
              ],
            }),
            '/srm/inventory/reports/warehouse-stock' => response({
              'items': [
                {
                  'id': 80,
                  'warehouse_name': 'Main warehouse',
                  'sku': 'STOCK-1',
                  'item_name': 'Sample product',
                  'quantity': 3,
                  'average_cost': 20,
                  'stock_value': 60,
                  'currency': 'INR',
                },
              ],
            }),
            '/srm/inventory/reports/valuation' => response({
              'items': [
                {
                  'id': 12,
                  'sku': 'STOCK-1',
                  'item_name': 'Sample product',
                  'current_quantity': 3,
                  'stock_value': 60,
                  'currency': 'INR',
                },
              ],
              'totals_by_currency': [
                {'currency': 'INR', 'total_inventory_value': 60},
                {'currency': 'USD', 'total_inventory_value': 50},
              ],
              'unpriced_currency_items': 1,
            }),
            '/project-management/tasks' => response({
              'items': [
                {
                  'id': 84,
                  'project_id': 5,
                  'title': 'Sample CRM follow-up',
                  'due_date': '2026-11-29',
                },
              ],
              'pages': 1,
              'filters': {
                'projects': [
                  {'id': 5, 'can_manage_tasks': true},
                ],
              },
            }),
            '/project-management/tasks/84' => response({
              'id': 84,
              'title': 'Sample CRM follow-up',
              'description': 'Prepare renewal proposal',
              'updated_at': '2026-11-27T09:00:00Z',
              'status':
                  calls.any(
                    (call) =>
                        call.method == 'PATCH' && call.path.endsWith('/84'),
                  )
                  ? 'Done'
                  : 'To Do',
            }),
            '/master-data/company-directory/query' => response({
              'rows': [
                {'id': 82, 'name': 'Sample customer', 'entityKind': 'Company'},
              ],
              'total': 1,
              'pageSize': 25,
              'context': {'canCreate': true},
            }),
            '/master-data/companies' => response({'id': 83}, 201),
            '/master-data/companies/82' => response({
              'id': 82,
              'name': 'Sample customer',
              'canEdit': true,
              'version': 'reviewed-version',
              'contacts': [
                {'name': 'Customer representative'},
              ],
            }),
            '/crm/quotations' => response({
              'items': [
                {'id': 44, 'quote_number': 'QT-44', 'status': 'Draft'},
              ],
              'pages': 1,
            }),
            '/crm/quote-approvals' => response({
              'items': [
                {
                  'id': 79,
                  'quote_id': 44,
                  'status': 'pending',
                  'reason': 'Discount needs review',
                },
              ],
              'total': 1,
            }),
            '/crm/cpq-rules' => response({
              'items': [
                {
                  'id': 12,
                  'name': 'Discount review',
                  'rule_type': 'approval',
                  'active': true,
                },
              ],
              'total': 1,
            }),
            '/crm/cpq/evaluate' => response({
              'ruleCount': 1,
              'warnings': [
                {'rule': 'Manager approval required'},
              ],
              'recommendations': [],
            }),
            '/crm/guided-selling-flows' => response({
              'items': guidedFlows,
              'total': guidedFlows.length,
            }),
            '/crm/guided-selling-flows/15' => response(
              guidedFlows.first..addAll(request.data as Map<String, dynamic>),
            ),
            '/crm/quotations/44/pdf' => response({
              'message': 'Unexpected payload',
            }),
            '/crm/quotations/44' => response({
              'quote_number': 'QT-44',
              'currency': 'INR',
              'grand_total': 1500,
              'lines': [
                {
                  'name': 'Annual support',
                  'quantity': 1,
                  'unit_price': 1500,
                  'line_total': 1500,
                },
              ],
            }),
            '/crm/deal-workspace/query' => response({
              'items': [
                {
                  'id': 83,
                  'name': request.queryParameters['page'] == 2
                      ? 'Next deal'
                      : 'Sample CRM deal',
                  'stage_name': 'Qualified',
                  'amount': 5000,
                  'currency': 'INR',
                },
              ],
              'pages': 2,
            }),
            '/crm/productivity/deals/83/stages' => response({
              'version': 1,
              'current_stage_id': 4,
              'stages': [
                {'id': 4, 'name': 'Qualified'},
                {'id': 5, 'name': 'Proposal'},
              ],
            }),
            '/crm/deal-workspace/83/record' => response({
              'id': 83,
              'name': 'Next deal',
              'description': 'A renewal from the CRM pipeline',
              'amount': 5000,
              'currency': 'INR',
            }),
            '/crm/contacts' => response({
              'items': [
                {
                  'id': 81,
                  'full_name': 'Sample CRM contact',
                  'company_name': 'Example business',
                  'email': 'sample@example.test',
                },
              ],
              'total': 1,
              'per_page': 25,
            }),
            '/crm/contacts/81' => response({
              'id': 81,
              'full_name': 'Sample CRM contact',
              'job_title': 'Coordinator',
              'timeline': [
                {'title': 'Requested a quote', 'occurredAt': '2026-11-26'},
              ],
            }),
            '/srm/inventory/reports/stock-aging' ||
            '/srm/inventory/reports/dead-stock' ||
            '/srm/inventory/reports/fast-slow-moving' => response({
              'items': [
                {
                  'id': 14,
                  'sku': 'STOCK-3',
                  'item_name': 'Archived stock sample',
                  'last_movement_date': '2026-01-05',
                  'age_days': 101,
                  'quantity_out': 4,
                  'movement_class': 'slow',
                },
              ],
            }),
            '/srm/inventory/reports/stock-summary' => response({
              'items': [
                {
                  'id': 13,
                  'sku': 'STOCK-2',
                  'item_name': 'Healthy product',
                  'current_quantity': 10,
                  'reorder_threshold': 2,
                  'stock_value': 240,
                  'currency': 'INR',
                },
              ],
            }),
            '/srm/procurement/purchase-orders' => response({
              'items': [
                {
                  'id': 72,
                  'po_number': 'PO-72',
                  'vendor_name': 'Example supplier',
                },
              ],
              'total': 1,
              'per_page': 25,
            }),
            '/srm/documents/purchase-orders' => response({
              'items': [
                {
                  'id': 74,
                  'number': 'PO-74',
                  'status': 'archived',
                  'removed': true,
                },
              ],
              'has_more': false,
            }),
            '/srm/documents/purchase-orders/74' => response({
              'record': {'id': 74, 'po_number': 'PO-74', 'status': 'archived'},
              'removed': true,
              'history': [],
            }),
            '/srm/procurement/purchase-orders/72' => response({
              'po_number': 'PO-72',
              'vendor_name': 'Example supplier',
              'lines': [
                {
                  'description': 'Printer paper',
                  'quantity': 10,
                  'received_quantity': 8,
                },
              ],
            }),
            '/srm/procurement/grn' => response({
              'items': [
                {'id': 80, 'grn_number': 'GRN-80', 'purchase_order_id': 72},
              ],
            }),
            '/srm/procurement/grn/80' => response({
              'grn_number': 'GRN-80',
              'purchase_order_id': 72,
              'lines': [
                {
                  'description': 'Printer paper',
                  'accepted_quantity': 8,
                  'rejected_quantity': 2,
                },
              ],
            }),
            '/srm/inventory/batches' => response({
              'items': [
                {
                  'id': 90,
                  'batch_number': 'LOT-90',
                  'available_quantity': 8,
                  'serial_count': 1,
                },
              ],
              'total': 1,
              'per_page': 25,
            }),
            '/srm/inventory/batches/90' => response({
              'batch_number': 'LOT-90',
              'available_quantity': 8,
              'serials': [
                {'serial_number': 'SN-901', 'status': 'available'},
              ],
            }),
            '/srm/inventory/serial-numbers' => response({
              'items': [
                {'id': 901, 'serial_number': 'SN-901', 'batch_id': 90},
              ],
            }),
            '/srm/inventory/reports/reorder' => response({
              'items': [
                {
                  'id': 12,
                  'item_name': 'Sample product',
                  'current_quantity': 0,
                  'reorder_threshold': 3,
                },
              ],
            }),
            _ => throw StateError('Unexpected request: ${request.path}'),
          };
        });
      final api = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: transport,
      );
      await api.acceptTokens({
        'access_token': 'test-token',
        'refresh_token': 'test-refresh',
      });
      final controller = AppController(api, suiteLogin: true)
        ..loading = false
        ..user = SessionUser.fromJson({
          'id': 5,
          'email': 'mobile@example.test',
          'role': {
            'permissions': [
              {'name': 'crm_cpq_manage'},
              {'name': 'crm_deals_manage'},
            ],
          },
        });
      await tester.pumpWidget(BusinessSuiteApp(controller: controller));
      await tester.pumpAndSettle();
      expect(find.text('Your applications (7)'), findsOneWidget);
      for (final (title, caption, icon) in const [
        ('Appointments', 'Bookings & schedule', LucideIcons.calendarDays),
        ('Power Apps', 'Build & automate', LucideIcons.zap),
        ('AI HRMS', 'People & payroll', LucideIcons.users),
        ('VyaparaCRM', 'Leads & customers', LucideIcons.users),
        ('KaryaFlow PMS', 'Projects & tasks', LucideIcons.listChecks),
        ('Sales & POS', 'Sales & inventory', LucideIcons.shoppingCart),
        (
          'Finance & Accounting',
          'Accounts & ledgers',
          LucideIcons.chartNoAxesColumnIncreasing,
        ),
      ]) {
        final card = find.ancestor(
          of: find.text(title),
          matching: find.byType(Card),
        );
        expect(card, findsOneWidget);
        expect(
          find.descendant(of: card, matching: find.text(caption)),
          findsOneWidget,
        );
        expect(
          find.descendant(of: card, matching: find.byIcon(icon)),
          findsOneWidget,
        );
      }
      await tester.tap(find.byTooltip('Add Appointments to favorites'));
      await tester.pumpAndSettle();
      final preferenceWrite = calls.singleWhere(
        (r) => r.path == '/access/launcher-preferences' && r.method == 'PUT',
      );
      expect(preferenceWrite.data, {
        'favorites': ['future_app', 'appointments'],
      });
      await tester.tap(find.text('Favorites (1)'));
      await tester.pumpAndSettle();
      expect(find.text('Power Apps'), findsNothing);
      expect(find.text('Appointments'), findsOneWidget);
      await tester.tap(find.text('All applications'));
      await tester.pumpAndSettle();

      Future<void> open(String label) async {
        final target = find.text(label).last;
        if (!target.evaluate().any((_) => true)) {
          await tester.drag(find.byType(ListView).first, const Offset(0, -450));
          await tester.pumpAndSettle();
        }
        await tester.ensureVisible(target);
        await tester.tap(target);
        await tester.pumpAndSettle();
      }

      Future<void> back() async {
        await tester.tap(find.byTooltip('Back'));
        await tester.pumpAndSettle();
      }

      await open('Appointments');
      await open('Main Branch');
      expect(find.text('Sample booking'), findsOneWidget);
      final branchRequest = calls.singleWhere(
        (r) => r.path == '/srm/industry/records',
      );
      expect(branchRequest.headers['X-Suite-Branch'], '6');
      final today = DateTime.now();
      await open('Choose schedule date');
      await open('OK');
      final datedRequest = calls.lastWhere(
        (r) => r.path == '/srm/industry/records',
      );
      expect(datedRequest.headers['X-Suite-Branch'], '6');
      expect(
        datedRequest.queryParameters['from_at'],
        DateTime(today.year, today.month, today.day).toUtc().toIso8601String(),
      );
      expect(
        datedRequest.queryParameters['until_at'],
        DateTime(
          today.year,
          today.month,
          today.day + 1,
        ).toUtc().toIso8601String(),
      );
      await tester.tap(find.byTooltip('Previous day'));
      await tester.pumpAndSettle();
      expect(
        calls
            .lastWhere((r) => r.path == '/srm/industry/records')
            .queryParameters['until_at'],
        datedRequest.queryParameters['from_at'],
      );
      await tester.tap(find.byTooltip('Next day'));
      await tester.pumpAndSettle();
      expect(
        calls
            .lastWhere((r) => r.path == '/srm/industry/records')
            .queryParameters,
        datedRequest.queryParameters,
      );
      await open('Week');
      final weekRequest = calls.lastWhere(
        (r) => r.path == '/srm/industry/records',
      );
      expect(
        weekRequest.queryParameters['until_at'],
        DateTime(
          today.year,
          today.month,
          today.day + 7,
        ).toUtc().toIso8601String(),
      );
      await tester.tap(find.byTooltip('Next week'));
      await tester.pumpAndSettle();
      expect(
        calls
            .lastWhere((r) => r.path == '/srm/industry/records')
            .queryParameters['from_at'],
        weekRequest.queryParameters['until_at'],
      );
      await tester.tap(find.byTooltip('Clear schedule date'));
      await tester.pumpAndSettle();
      expect(
        calls
            .lastWhere((r) => r.path == '/srm/industry/records')
            .queryParameters,
        isNot(contains('from_at')),
      );
      await open('All statuses');
      await open('Confirmed');
      expect(find.text('Previous visit'), findsNothing);
      final search = find.byType(TextField);
      await tester.enterText(search, 'unknown customer');
      await tester.pumpAndSettle();
      expect(find.text('Sample booking'), findsNothing);
      await tester.enterText(search, 'Asha');
      await tester.pumpAndSettle();
      await open('Sample booking');
      expect(find.text('Consultation'), findsOneWidget);
      expect(find.text('Cancel appointment'), findsNothing);
      await open('Check in');
      final transition = calls.singleWhere(
        (r) => r.path == '/srm/industry/records/61/transition',
      );
      expect(transition.method, 'POST');
      expect(transition.headers['X-Suite-Branch'], '6');
      expect(transition.data, {
        'expected_revision': 4,
        'status': 'checked_in',
        'reason': '',
      });
      expect(find.text('checked in'), findsOneWidget);
      await back();
      await back();
      await back();
      for (final entry in {
        'Power Apps': '/power-apps/environments',
        'AI HRMS': '/employees/',
        'VyaparaCRM': '/crm/lead-management/leads',
        'Sales & POS': '/srm/sales-orders',
        'Finance & Accounting': '/fam/parties',
        'Notes': '/project-management/notes',
      }.entries) {
        await open(entry.key);
        expect(calls.any((r) => r.path == entry.value), isTrue);
        if (entry.key == 'Finance & Accounting') {
          for (final (report, row, detail) in [
            ('Gross Margin', 'Sample product', 'Incomplete attribution'),
            ('COGS Report', 'OUT-1', 'Voucher posted: Yes'),
            ('HSN Summary', '844399', 'Stock value: 900'),
            ('GL Reconciliation', 'Inventory ledger: 12', 'Difference: INR 20'),
            ('GRNI Reconciliation', 'GRN-2', 'Unbilled receipts: 1'),
            ('COGS Reconciliation', 'ISSUE-2', 'Cost posted: INR 270'),
            ('GST Reconciliation', 'SKU-12', 'Missing mappings: 1'),
            (
              'Sales Reconciliation',
              'Sales orders: 8',
              'Duplicate deductions are blocked',
            ),
            ('Stock Movement Audit', 'STOCK_OUT', 'Record ID: 44'),
          ]) {
            await tester.tap(find.byTooltip('Inventory financial reports'));
            await tester.pumpAndSettle();
            await open(report);
            expect(find.text(row), findsOneWidget);
            expect(find.textContaining(detail), findsOneWidget);
            if (report == 'Gross Margin') {
              expect(find.text('Currency: INR'), findsOneWidget);
              expect(
                find.textContaining('Gross margin: Not available'),
                findsOneWidget,
              );
            }
            await back();
          }
        }
        if (entry.key == 'Power Apps') {
          await open('production');
          expect(calls.any((r) => r.path == '/power-apps/overview'), isFalse);
          await open('development');
          expect(find.text('Active automations'), findsOneWidget);
          expect(find.text('Approval workflow'), findsOneWidget);
          await open('Approval workflow');
          expect(find.text('Automation details'), findsOneWidget);
          expect(find.text('Review'), findsOneWidget);
          expect(
            calls.any(
              (r) =>
                  r.path == '/power-apps/automations/12' &&
                  r.queryParameters['environment'] == 'development',
            ),
            isTrue,
          );
          await back();
          expect(
            calls.any(
              (r) =>
                  r.path == '/power-apps/overview' &&
                  r.queryParameters['environment'] == 'development',
            ),
            isTrue,
          );
          await back();
        }
        if (entry.key == 'AI HRMS') {
          await tester.tap(find.text('Next'));
          await tester.pumpAndSettle();
          expect(find.text('Next Employee'), findsOneWidget);
          await tester.enterText(find.byType(TextField), 'Sample');
          await tester.pump(const Duration(milliseconds: 350));
          await tester.pumpAndSettle();
          expect(
            calls.any(
              (r) =>
                  r.path == '/employees/' &&
                  r.queryParameters['page'] == 1 &&
                  r.queryParameters['search'] == 'Sample',
            ),
            isTrue,
          );
          await open('Sample Employee');
          expect(find.text('Employee profile'), findsOneWidget);
          expect(find.text('Work email'), findsOneWidget);
          expect(find.text('Operations'), findsOneWidget);
          expect(find.text('Coordinator'), findsOneWidget);
          expect(calls.any((r) => r.path == '/employees/27'), isTrue);
          await back();
        }
        if (entry.key == 'Sales & POS') {
          await open('Sample order');
          expect(find.text('Sample line'), findsOneWidget);
          await back();
          await tester.tap(find.byTooltip('Inventory'));
          await tester.pumpAndSettle();
          expect(calls.any((r) => r.path == '/srm/inventory/items'), isTrue);
          await open('Sample product');
          expect(find.text('STOCK-1'), findsOneWidget);
          await back();
          await tester.tap(find.byTooltip('Procurement'));
          await tester.pumpAndSettle();
          await open('Purchase orders');
          await open('PO-72');
          expect(find.text('Printer paper'), findsOneWidget);
          expect(find.textContaining('Received: 8'), findsOneWidget);
          await back();
          await tester.tap(find.byTooltip('Archived orders'));
          await tester.pumpAndSettle();
          await open('PO-74');
          expect(find.text('archived'), findsOneWidget);
          await back();
          await back();
          await back();
          await tester.tap(find.byTooltip('Procurement'));
          await tester.pumpAndSettle();
          await open('Goods receipts');
          await open('GRN-80');
          expect(find.textContaining('Accepted: 8'), findsOneWidget);
          await open('Open purchase order');
          expect(find.text('PO-72'), findsOneWidget);
          await back();
          await back();
          await back();
          await tester.tap(find.byTooltip('Batches & Serials'));
          await tester.pumpAndSettle();
          expect(find.textContaining('8 available'), findsOneWidget);
          await open('LOT-90');
          expect(find.text('SN-901'), findsOneWidget);
          await back();
          await tester.tap(find.byTooltip('Serial numbers'));
          await tester.pumpAndSettle();
          expect(find.text('SN-901'), findsOneWidget);
          expect(find.textContaining('Batch #90'), findsOneWidget);
          await back();
          await back();
          await tester.tap(find.byTooltip('Low stock alerts'));
          await tester.pumpAndSettle();
          expect(find.text('1 item needs attention'), findsOneWidget);
          expect(find.text('Out of stock'), findsOneWidget);
          expect(find.text('Healthy product'), findsNothing);
          await back();
          await tester.tap(find.byTooltip('Stock Summary'));
          await tester.pumpAndSettle();
          expect(find.text('Healthy product'), findsOneWidget);
          expect(find.textContaining('Quantity 10'), findsOneWidget);
          expect(find.textContaining('Stock value 240 INR'), findsOneWidget);
          for (final (title, path, detail) in [
            ('Stock Aging', 'stock-aging', 'Days since last movement 101'),
            ('Dead Stock', 'dead-stock', 'Last movement 2026-01-05'),
            ('Fast and Slow Moving Stock', 'fast-slow-moving', 'Slow moving'),
          ]) {
            await tester.tap(find.byTooltip('Stock activity reports'));
            await tester.pumpAndSettle();
            await open(title);
            expect(find.text('Archived stock sample'), findsOneWidget);
            expect(find.textContaining(detail), findsOneWidget);
            expect(
              calls.any((r) => r.path == '/srm/inventory/reports/$path'),
              isTrue,
            );
            await back();
          }
          await back();
          await tester.tap(find.byTooltip('Warehouses'));
          await tester.pumpAndSettle();
          expect(find.text('Main warehouse'), findsOneWidget);
          await tester.tap(find.byTooltip('Warehouse Stock'));
          await tester.pumpAndSettle();
          expect(find.text('Sample product'), findsOneWidget);
          expect(find.textContaining('Stock value 60 INR'), findsOneWidget);
          await tester.enterText(find.byType(TextField), 'Other warehouse');
          await tester.pumpAndSettle();
          expect(find.text('Sample product'), findsNothing);
          await tester.enterText(find.byType(TextField), 'Main warehouse');
          await tester.pumpAndSettle();
          expect(find.text('Sample product'), findsOneWidget);
          await tester.tap(find.byTooltip('Inventory Valuation'));
          await tester.pumpAndSettle();
          expect(find.textContaining('Stock value 60 INR'), findsOneWidget);
          await open('Inventory value by currency');
          expect(find.text('USD'), findsOneWidget);
          expect(find.text('50'), findsOneWidget);
          expect(find.text('1 items have no currency'), findsOneWidget);
          await back();
          await back();
          await back();
          await back();
        }
        if (entry.key == 'VyaparaCRM') {
          await tester.tap(find.byTooltip('CRM tasks'));
          await tester.pumpAndSettle();
          expect(
            calls.any(
              (request) =>
                  request.path == '/project-management/tasks' &&
                  request.queryParameters['sourceModule'] == 'crm',
            ),
            isTrue,
          );
          await open('Sample CRM follow-up');
          expect(find.text('Prepare renewal proposal'), findsOneWidget);
          await open('Change status');
          await open('Done');
          final taskUpdate = calls.lastWhere(
            (request) =>
                request.method == 'PATCH' &&
                request.path == '/project-management/tasks/84',
          );
          expect(taskUpdate.data, {
            'status': 'Done',
            'expected_updated_at': '2026-11-27T09:00:00Z',
          });
          expect(find.text('Done'), findsOneWidget);
          await back();
          await back();
          await tester.tap(find.byTooltip('Customers'));
          await tester.pumpAndSettle();
          await tester.tap(find.byTooltip('New customer'));
          await tester.pumpAndSettle();
          await tester.enterText(
            find.widgetWithText(TextFormField, 'Customer name'),
            'New customer sample',
          );
          await open('Create customer');
          final createdCustomer = calls.lastWhere(
            (request) => request.path == '/master-data/companies',
          );
          expect(createdCustomer.method, 'POST');
          expect(createdCustomer.data, {
            'name': 'New customer sample',
            'entityKind': 'Individual',
            'roles': ['Customer'],
          });
          await tester.enterText(find.byType(TextField), 'sample');
          await tester.pump(const Duration(milliseconds: 350));
          await tester.pumpAndSettle();
          final customerQuery = calls
              .lastWhere(
                (request) =>
                    request.path == '/master-data/company-directory/query',
              )
              .queryParameters;
          expect(customerQuery['role'], 'Customer');
          expect(customerQuery['entity_kind'], 'all');
          expect(jsonDecode(customerQuery['state'] as String), {
            'page': 1,
            'pageSize': 25,
            'search': 'sample',
          });
          await open('Sample customer');
          expect(find.text('Customer representative'), findsOneWidget);
          await open('Edit customer');
          await tester.enterText(
            find.widgetWithText(TextFormField, 'Email'),
            'updated@example.test',
          );
          await open('Save changes');
          final updatedCustomer = calls.lastWhere(
            (request) =>
                request.method == 'PATCH' &&
                request.path == '/master-data/companies/82',
          );
          expect(updatedCustomer.data['version'], 'reviewed-version');
          expect(updatedCustomer.data['email'], 'updated@example.test');
          await back();
          await back();
          await tester.tap(find.byTooltip('Deals'));
          await tester.pumpAndSettle();
          expect(find.text('Sample CRM deal'), findsOneWidget);
          await tester.tap(find.byTooltip('Pipeline'));
          await tester.pumpAndSettle();
          expect(find.text('Sales pipeline'), findsOneWidget);
          await open('Qualified');
          expect(
            calls
                .lastWhere((r) => r.uri.path.endsWith('/crm/deals'))
                .uri
                .queryParameters['stage_id'],
            '4',
          );
          expect(find.text('1 deal'), findsOneWidget);
          expect(
            tester
                .widget<ChoiceChip>(
                  find.widgetWithText(ChoiceChip, 'Qualified'),
                )
                .selected,
            isTrue,
          );
          await tester.tap(find.byTooltip('Move Next deal'));
          await tester.pumpAndSettle();
          expect(find.text('Review stage move'), findsOneWidget);
          await back();
          await open('Next deal');
          expect(find.text('A renewal from the CRM pipeline'), findsOneWidget);
          await back();
          await back();
          await tester.tap(find.byTooltip('Quotations'));
          await tester.pumpAndSettle();
          await open('QT-44');
          expect(find.text('Annual support'), findsOneWidget);
          expect(find.text('1500 INR'), findsNWidgets(2));
          await open('Save quotation PDF');
          expect(find.text('The server did not return a PDF.'), findsOneWidget);
          expect(
            calls
                .lastWhere(
                  (request) => request.path == '/crm/quotations/44/pdf',
                )
                .queryParameters['download'],
            isTrue,
          );
          await tester.pump(const Duration(seconds: 5));
          await back();
          await tester.tap(find.byTooltip('Quote Approvals'));
          await tester.pumpAndSettle();
          expect(find.textContaining('Discount needs review'), findsOneWidget);
          await open('Quotation #44');
          expect(find.text('Annual support'), findsOneWidget);
          await back();
          await back();
          await tester.tap(find.byTooltip('CPQ Rules'));
          await tester.pumpAndSettle();
          expect(find.text('Discount review'), findsOneWidget);
          await tester.tap(find.byTooltip('Evaluate CPQ rules'));
          await tester.pumpAndSettle();
          await tester.enterText(
            find.widgetWithText(TextFormField, 'Discount'),
            '250.50',
          );
          await open('Evaluate');
          expect(find.text('Warnings: 1'), findsOneWidget);
          expect(find.text('Manager approval required'), findsOneWidget);
          final evaluation = calls.lastWhere(
            (request) => request.path == '/crm/cpq/evaluate',
          );
          expect(evaluation.method, 'POST');
          expect(evaluation.data, {'amount': 250000, 'discount': 250.50});
          await back();
          await tester.tap(find.byTooltip('Guided Selling'));
          await tester.pumpAndSettle();
          expect(find.text('Renewals'), findsOneWidget);
          await tester.tap(find.byTooltip('Edit Renewals'));
          await tester.pumpAndSettle();
          await tester.tap(find.byType(Switch));
          await tester.pumpAndSettle();
          await open('Save changes');
          expect(find.text('Inactive'), findsOneWidget);
          expect(
            calls
                .lastWhere((r) => r.path == '/crm/guided-selling-flows/15')
                .data,
            {'active': false},
          );
          await tester.tap(find.byTooltip('Edit Renewals'));
          await tester.pumpAndSettle();
          await open('Questions and recommendations');
          final questions = find.widgetWithText(
            TextFormField,
            'Questions JSON',
          );
          expect(
            tester.widget<TextFormField>(questions).initialValue,
            contains('When does the contract end?'),
          );
          await tester.enterText(questions, '[');
          await tester.pumpAndSettle();
          await open('Save changes');
          expect(find.text('Enter valid JSON.'), findsOneWidget);
          await tester.enterText(questions, '[{"prompt":"Renew this month?"}]');
          await tester.pumpAndSettle();
          await open('Save changes');
          expect(
            calls
                .lastWhere((r) => r.path == '/crm/guided-selling-flows/15')
                .data,
            {
              'questions': [
                {'prompt': 'Renew this month?'},
              ],
            },
          );
          await tester.tap(find.byTooltip('New guided selling flow'));
          await tester.pumpAndSettle();
          await tester.enterText(find.byType(TextFormField), 'New sales');
          await open('Create flow');
          expect(find.text('New sales'), findsOneWidget);
          await back();
          await back();
          await back();
          await tester.tap(find.text('Next'));
          await tester.pumpAndSettle();
          await open('Next deal');
          expect(find.text('A renewal from the CRM pipeline'), findsOneWidget);
          expect(find.text('Qualified'), findsOneWidget);
          await back();
          await back();
          await tester.tap(find.byTooltip('Contacts'));
          await tester.pumpAndSettle();
          await tester.enterText(find.byType(TextField), 'sample');
          await tester.pump(const Duration(milliseconds: 350));
          await tester.pumpAndSettle();
          expect(
            calls.any(
              (r) =>
                  r.path == '/crm/contacts' &&
                  r.queryParameters['search'] == 'sample',
            ),
            isTrue,
          );
          await open('Sample CRM contact');
          expect(find.text('Coordinator'), findsOneWidget);
          expect(find.text('Requested a quote'), findsOneWidget);
          await back();
          await back();
        }
        await back();
      }
      expect(
        tester.widget<Badge>(find.byType(Badge).first).isLabelVisible,
        isTrue,
      );
      await tester.tap(find.byTooltip('Notifications'));
      await tester.pumpAndSettle();
      expect(find.text('Sample update'), findsOneWidget);
      await tester.tap(find.text('Sample update'));
      await tester.pumpAndSettle();
      expect(
        calls.any(
          (r) => r.path == '/notifications/12/read' && r.method == 'PUT',
        ),
        isTrue,
      );
      await tester.tap(find.text('Close'));
      await tester.pumpAndSettle();
      await back();
      expect(
        tester.widget<Badge>(find.byType(Badge).first).isLabelVisible,
        isFalse,
      );
      await tester.tap(find.byTooltip('Settings'));
      await tester.pumpAndSettle();
      await open('Account security');
      expect(find.text('Test phone'), findsOneWidget);
      await tester.tap(find.text('Change password'));
      await tester.pumpAndSettle();
      final passwords = find.byType(TextFormField);
      await tester.enterText(passwords.at(0), 'sample-old-password');
      await tester.enterText(passwords.at(1), 'sample-new-password');
      await tester.enterText(passwords.at(2), 'sample-new-password');
      await tester.tap(find.text('Change password').last);
      await tester.pumpAndSettle();
      expect(
        calls.any(
          (r) => r.method == 'POST' && r.path == '/auth/change-password',
        ),
        isTrue,
      );
      expect(
        calls.any((r) => r.path == '/access/settings/options/account'),
        isTrue,
      );
      expect(tester.takeException(), isNull);
      expect(
        api.offlineSuite?['access']['grants']['project_management']['enabled'],
        isTrue,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
      controller.offline = true;
      await tester.pumpWidget(BusinessSuiteApp(controller: controller));
      await tester.pumpAndSettle();
      final requestsBeforeNotes = calls.length;
      await open('Notes');
      expect(find.byTooltip('Refresh notes'), findsOneWidget);
      expect(calls.length, requestsBeforeNotes);
    },
    variant: TargetPlatformVariant({TargetPlatform.iOS}),
  );
}
