import 'dart:async';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/features/gst_invoice_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
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
