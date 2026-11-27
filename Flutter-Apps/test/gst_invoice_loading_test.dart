import 'dart:async';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/features/gst_invoice_page.dart';
import 'package:business_suite_mobile/main.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  for (final (screen, route, prefix) in [
    ('GST', 'GST Billing', 'GST'),
    ('Sales Orders', null, 'ORDER'),
    ('Inventory', 'Inventory', 'ITEM'),
  ]) {
    testWidgets('Refreshing the $screen list does not wait for SQLite', (
      tester,
    ) async {
      const channel = MethodChannel('com.tekartik.sqflite');
      final messenger = tester.binding.defaultBinaryMessenger;
      databaseFactory = databaseFactorySqflitePlugin;
      final opening = Completer<String>();
      var holdCache = false;
      var cacheWaiting = false;
      messenger.setMockMethodCallHandler(channel, (call) async {
        expect(call.method, 'getDatabasesPath');
        if (!holdCache) throw PlatformException(code: 'cache_unavailable');
        cacheWaiting = true;
        return opening.future;
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
            return switch (request.path) {
              '/access/me' => response({
                'companyId': 7,
                'grants': {
                  'srm': {'enabled': true},
                },
              }),
              '/access/launcher-preferences' => response({'favorites': []}),
              '/notifications/unread-count' => response({'unread': 0}),
              '/srm/sales-orders' => response([
                if (route == null)
                  {
                    'id': 6,
                    'order_number': 'ORDER-${++requests}',
                    'status': 'draft',
                  },
              ]),
              '/srm/invoices' => response([
                {
                  'id': 7,
                  'invoice_number': 'GST-${++requests}',
                  'status': 'draft',
                },
              ]),
              '/srm/inventory/items' => response({
                'items': [
                  {'id': 8, 'item_name': 'ITEM-${++requests}', 'sku': 'stock'},
                ],
                'total': 1,
              }),
              _ => throw StateError('Unexpected request ${request.path}'),
            };
          }),
      );
      final controller = AppController(api, suiteLogin: true)
        ..loading = false
        ..user = SessionUser.fromJson({'id': 5, 'email': 'test@example.test'});
      try {
        await tester.pumpWidget(BusinessSuiteApp(controller: controller));
        await tester.pumpAndSettle();
        final sales = find.text('Sales & POS');
        await tester.ensureVisible(sales);
        await tester.tap(sales);
        await tester.pumpAndSettle();
        if (route != null) {
          await tester.tap(find.byTooltip(route));
          await tester.pumpAndSettle();
        }
        expect(find.text('$prefix-1'), findsOneWidget);
        holdCache = true;
        await tester.tap(find.byTooltip('Refresh'));
        await tester.pumpAndSettle();
        expect(cacheWaiting, isTrue);
        expect(opening.isCompleted, isFalse);
        expect(find.text('$prefix-2'), findsOneWidget);
      } finally {
        if (cacheWaiting) {
          opening.completeError(PlatformException(code: 'cache_unavailable'));
        }
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpAndSettle();
        controller.dispose();
      }
    }, variant: TargetPlatformVariant({TargetPlatform.android}));
  }

  testWidgets('Live GST invoice opens while SQLite is still starting', (
    tester,
  ) async {
    final opening = Completer<String>();
    var waiting = false;
    const sqlite = MethodChannel('com.tekartik.sqflite');
    final messenger = tester.binding.defaultBinaryMessenger;
    databaseFactory = databaseFactorySqflitePlugin;
    messenger.setMockMethodCallHandler(sqlite, (call) async {
      expect(call.method, 'getDatabasesPath');
      waiting = true;
      return opening.future;
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
          expect(request.path, '/srm/invoices/7');
          return response({'invoice_number': 'LIVE-GST-7', 'status': 'draft'});
        }),
    );
    try {
      await tester.pumpWidget(
        MaterialApp(
          home: GstInvoicePage(
            api: api,
            id: 7,
            cacheScope: '["https://example.test/api/v1",5,7]',
            summary: const {'invoice_number': 'SAVED-GST-7'},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(waiting, isTrue);
      expect(opening.isCompleted, isFalse);
      expect(find.text('LIVE-GST-7'), findsOneWidget);
      expect(find.text('SAVED-GST-7'), findsNothing);
    } finally {
      opening.completeError(PlatformException(code: 'cache_unavailable'));
      await tester.pumpAndSettle();
    }
  });
}
