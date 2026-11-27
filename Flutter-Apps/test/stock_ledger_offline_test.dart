import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/inventory_finance_report_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets('Stock Ledger reopens the matching filter offline', (
    tester,
  ) async {
    const channel = MethodChannel('com.tekartik.sqflite');
    final messenger = tester.binding.defaultBinaryMessenger;
    databaseFactory = databaseFactorySqflitePlugin;
    final snapshots = <String, Map>{};
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
        case 'delete':
          return 0;
        default:
          fail('Unexpected SQLite method ${call.method}');
      }
    });
    addTearDown(() {
      messenger.setMockMethodCallHandler(channel, null);
      databaseFactory = null;
    });
    var requests = 0;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests++;
          final warehouse = request.queryParameters['warehouse_id'] ?? 'all';
          return response({
            'total': 1,
            'items': [
              {'movement_number': 'Movements for $warehouse'},
            ],
          });
        }),
    );
    Future<void> open(bool offline) async {
      await tester.pumpWidget(
        MaterialApp(
          home: InventoryFinanceReportPage(
            key: ValueKey(offline),
            api: api,
            report: InventoryFinanceReport.stockLedger,
            scopeHeaders: const {'X-Suite-Branch': '6'},
            cacheScope: 'ledger-test',
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
    await open(true);
    expect(find.text('Movements for all'), findsOneWidget);
    await warehouse('6');
    expect(find.text('Saved report'), findsOneWidget);
    expect(find.text('Movements for 6'), findsOneWidget);
    await warehouse('7');
    expect(find.text('No saved report.'), findsOneWidget);
    expect(find.text('Movements for 6'), findsNothing);
    expect(requests, 3);
  });
}
