import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/inventory_finance_report_page.dart';
import 'package:business_suite_mobile/features/sales_order_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets('Stock Ledger separates offline filters, branches and companies', (
    tester,
  ) async {
    const channel = MethodChannel('com.tekartik.sqflite');
    final messenger = tester.binding.defaultBinaryMessenger;
    databaseFactory = databaseFactorySqflitePlugin;
    final snapshots = <String, Map>{};
    final invalidatedProducts = <String>[];
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
          if ((args['sql'] as String).toUpperCase().contains('USER_VERSION')) {
            return [
              {'user_version': 3},
            ];
          }
          final key = (args['arguments'] as List).first as String;
          return [?snapshots[key]];
        case 'insert':
          final values = (call.arguments as Map)['arguments'] as List;
          snapshots[values[0] as String] = {
            'saved_at': values[1],
            'rows': values[2],
            'invalidated': 0,
          };
          return 1;
        case 'update':
          final args = call.arguments as Map;
          final values = args['arguments'] as List;
          if ((args['sql'] as String).startsWith('DELETE')) {
            if (values.length != 4) return 0;
            expect(values, [
              'ledger-test:ledger:',
              'ledger-test:ledger;',
              ':/srm/inventory/reports:6',
              ':/srm/inventory/reports:6',
            ]);
            snapshots.removeWhere(
              (key, _) =>
                  key.startsWith(values.first as String) &&
                  key.endsWith(values.last as String),
            );
            return 0;
          }
          if (values.length == 2) return 0;
          if (values.length == 3) {
            expect(
              values.last,
              '${(values[1] as String).substring(0, (values[1] as String).length - 1)};',
            );
            invalidatedProducts.add(values[1] as String);
            return 0;
          }
          expect(values, [
            1,
            'ledger-test:',
            'ledger-test;',
            'ledger-test:',
            ':/srm/inventory/reports:',
          ]);
          for (final entry in snapshots.entries) {
            if (entry.key.contains(':/srm/inventory/reports:')) {
              entry.value['invalidated'] = 1;
            }
          }
          return snapshots.length;
        default:
          fail('Unexpected SQLite method ${call.method}');
      }
    });
    addTearDown(() {
      messenger.setMockMethodCallHandler(channel, null);
      databaseFactory = null;
    });
    var requests = 0;
    var connected = true;
    var denied = false;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.path == '/srm/sales-orders/24') {
            return response({
              'id': 24,
              'status': 'approved',
              'lines': [
                {'product_id': 9},
                {'product_id': 9},
                {'product_id': 12},
                {'description': 'Service without a catalog product'},
              ],
            });
          }
          if (request.path == '/srm/sales-orders/24/confirm') {
            expect(request.method, 'POST');
            return response({'id': 24, 'status': 'confirmed'});
          }
          expect(request.path, '/srm/inventory/reports');
          requests++;
          if (denied) {
            return response({'detail': 'Inventory access revoked'}, 403);
          }
          if (!connected) {
            throw DioException(
              requestOptions: request,
              type: DioExceptionType.connectionError,
            );
          }
          final warehouse = request.queryParameters['warehouse_id'] ?? 'all';
          return response({
            'total': 1,
            'items': [
              {'movement_number': 'Movements for $warehouse'},
            ],
          });
        }),
    );
    Future<void> open(
      bool offline, {
      String branch = '6',
      String scope = 'ledger-test',
      bool finance = false,
      Map<String, String> filters = const {},
    }) async {
      await tester.pumpWidget(
        MaterialApp(
          home: InventoryFinanceReportPage(
            key: ValueKey((
              offline,
              branch,
              scope,
              finance,
              filters.toString(),
            )),
            api: api,
            report: InventoryFinanceReport.stockLedger,
            scopeHeaders: {'X-Suite-Branch': branch},
            cacheScope: scope,
            financeAnalysis: finance,
            initialFilters: filters,
            offline: offline,
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    Future<void> warehouse(String value) async {
      await tester.tap(find.byTooltip('Stock ledger filters'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Warehouse ID'),
        value,
      );
      await tester.ensureVisible(find.text('Apply filters'));
      await tester.tap(find.text('Apply filters'));
      await tester.pumpAndSettle();
    }

    await open(false);
    expect(find.text('Movements for all'), findsOneWidget);
    await warehouse('6');
    expect(find.text('Movements for 6'), findsOneWidget);
    expect(snapshots, hasLength(2));
    await warehouse('6');
    expect(find.text('Movements for 6'), findsOneWidget);
    expect(requests, 2);
    await tester.tap(find.byTooltip('Refresh report'));
    await tester.pumpAndSettle();
    expect(requests, 3);
    await tester.pumpWidget(
      MaterialApp(
        home: SalesOrderPage(
          api: api,
          summary: const {'id': 24},
          offline: false,
          cacheScope: 'ledger-test',
          canEdit: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm sales order'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Confirm sales order'));
    await tester.pumpAndSettle();
    expect(
      invalidatedProducts,
      unorderedEquals([
        'ledger-test:/srm/inventory/items/9:',
        'ledger-test:/srm/inventory/items/12:',
      ]),
    );
    await open(false);
    await warehouse('6');
    expect(requests, 5);
    await open(true);
    expect(find.text('Movements for all'), findsOneWidget);
    await warehouse('6');
    expect(find.text('Saved report'), findsOneWidget);
    expect(find.textContaining(RegExp(r'^Saved .+\d')), findsOneWidget);
    expect(find.text('Movements for 6'), findsOneWidget);
    await warehouse('7');
    expect(find.text('No saved report.'), findsOneWidget);
    expect(find.text('Movements for 6'), findsNothing);
    await open(true, branch: '7');
    expect(find.text('No saved report.'), findsOneWidget);
    await open(true, scope: 'different-company');
    expect(find.text('No saved report.'), findsOneWidget);
    await open(true, finance: true);
    expect(find.text('No saved report.'), findsOneWidget);
    await open(true);
    expect(find.text('Movements for all'), findsOneWidget);
    expect(requests, 5);
    await open(false, filters: {'warehouse_id': '6', 'product_id': '12'});
    expect(find.text('Movements for 6'), findsOneWidget);
    expect(requests, 6);
    await open(false, filters: {'product_id': '12', 'warehouse_id': '6'});
    connected = false;
    await tester.tap(find.byTooltip('Refresh report'));
    await tester.pumpAndSettle();
    expect(find.text('Offline · Refresh to reconnect'), findsOneWidget);
    expect(find.text('Movements for 6'), findsOneWidget);
    expect(requests, 7);
    await tester.tap(find.byTooltip('Remove Product ID filter'));
    await tester.pumpAndSettle();
    expect(find.text('Movements for 6'), findsOneWidget);
    expect(requests, 7);
    connected = true;
    await tester.tap(find.byTooltip('Refresh report'));
    await tester.pumpAndSettle();
    expect(find.text('Offline · Refresh to reconnect'), findsNothing);
    expect(requests, 8);
    await open(true, filters: {'product_id': '12', 'warehouse_id': '6'});
    expect(find.text('Movements for 6'), findsOneWidget);
    expect(requests, 8);
    denied = true;
    await tester.tap(find.byTooltip('Refresh report'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Inventory access revoked'), findsOneWidget);
    expect(find.text('Movements for 6'), findsNothing);
    await open(true);
    expect(find.text('No saved report.'), findsOneWidget);
    await warehouse('6');
    expect(find.text('No saved report.'), findsOneWidget);
    expect(requests, 9);
  });
}
