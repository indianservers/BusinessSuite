import 'dart:convert';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/core/sales_order_drafts.dart';
import 'package:business_suite_mobile/features/gst_invoice_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore;

void main() {
  testWidgets('GST starts and stores a draft without a connection', (
    tester,
  ) async {
    const url = 'https://example.test/api/v1';
    const scope = '["$url",5,7]';
    const headers = {'X-Suite-Branch': '6'};
    final picker = gstCacheKey(scope, '/srm/invoices/customer-picker', headers);
    const channel = MethodChannel('com.tekartik.sqflite');
    databaseFactory = databaseFactorySqflitePlugin;
    FlutterSecureStorage.setMockInitialValues({});
    final messenger = tester.binding.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(channel, (call) async {
      return switch (call.method) {
        'getDatabasesPath' => '/test',
        'openDatabase' => {'id': 1},
        'execute' => null,
        'query' =>
          (call.arguments['sql'] as String).toUpperCase().contains(
                'USER_VERSION',
              )
              ? [
                  {'user_version': 3},
                ]
              : [
                  {
                    'saved_at': DateTime.now().millisecondsSinceEpoch,
                    'rows': jsonEncode([
                      {'id': 5, 'name': 'Saved customer'},
                    ]),
                  },
                ],
        _ => fail('Unexpected SQLite method ${call.method}'),
      };
    });
    addTearDown(() {
      messenger.setMockMethodCallHandler(channel, null);
      databaseFactory = null;
      FlutterSecureStorage.setMockInitialValues({});
    });
    final api = ApiClient(
      baseUrl: url,
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((_) async {
          fail('Offline draft should not call the server');
        }),
    );
    final drafts = SalesOrderDrafts.gstInvoices(scope);
    Json? result;
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () async {
                result = await showGstInvoiceDraftForm(
                  context,
                  api: api,
                  scopeHeaders: headers,
                  drafts: drafts,
                  customerCacheScope: picker,
                  offline: true,
                );
              },
              child: const Text('Open draft'),
            ),
          ),
        ),
      ),
    );
    Future<void> tap(String label) async {
      final finder = find.text(label).last;
      await tester.ensureVisible(finder);
      await tester.tap(finder);
      await tester.pumpAndSettle();
    }

    await tap('Open draft');
    await tap('Choose customer');
    await tap('Saved customer');
    await tap('Add line item');
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Description'),
      'Delivery',
    );
    await tap('Save line');
    await tap('Save draft offline');
    expect(result, {'local': true});
    final entry = (await drafts.entries()).single;
    expect(entry['headers'], headers);
    expect(entry['payload']['customer_id'], 5);
    expect(entry['payload']['lines'].single['description'], 'Delivery');
  });
}
