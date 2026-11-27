import 'dart:convert';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/inventory_offline_creates.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/core/sales_order_drafts.dart';
import 'package:business_suite_mobile/features/gst_invoice_page.dart';
import 'package:business_suite_mobile/features/sales_order_drafts_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  final rejectionStatuses = ValueVariant({404, 422});
  testWidgets('GST corrects a rejected draft under a new request ID', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    addTearDown(() => FlutterSecureStorage.setMockInitialValues({}));
    const url = 'https://example.test/api/v1';
    const headers = {'X-Suite-Branch': '6'};
    const payload = {
      'customer_id': 5,
      'due_date': '2026-12-15',
      'lines': [
        {'description': 'Original line', 'quantity': '2'},
      ],
    };
    final drafts = SalesOrderDrafts.gstInvoices('["$url",5,7]');
    await drafts.save(
      'old-operation',
      payload,
      scopeHeaders: headers,
      customerName: 'Saved customer',
    );
    final api = ApiClient(
      baseUrl: url,
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expect(request.headers['X-Suite-Branch'], '6');
          return response({
            'detail': 'Correct the draft',
          }, rejectionStatuses.currentValue!);
        }),
    );
    await tester.runAsync(() async {
      await api.acceptTokens({'access_token': 'a', 'refresh_token': 'b'});
      await drafts.sync(api);
    });
    expect(
      (await drafts.entries()).single['status'],
      rejectionStatuses.currentValue,
    );
    await tester.pumpWidget(
      MaterialApp(
        home: SalesOrderDraftsPage(
          api: api,
          drafts: drafts,
          editGstDraft: (context, draft) async {
            await showGstInvoiceDraftForm(
              context,
              api: api,
              scopeHeaders: headers,
              drafts: drafts,
              offline: true,
              savedDraft: draft,
            );
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('GST invoice'));
    await tester.pumpAndSettle();
    expect(find.text('Correct GST invoice draft'), findsOneWidget);
    expect(find.text('2026-12-15'), findsOneWidget);
    await tester.tap(find.text('Original line'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Description'),
      'Corrected line',
    );
    await tester.tap(find.text('Save line'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save corrected draft'));
    await tester.pumpAndSettle();
    final entry = (await drafts.entries()).single;
    expect(entry['operation'], isNot('old-operation'));
    expect(entry['status'], isNull);
    expect(entry['headers'], headers);
    expect(entry['payload']['due_date'], '2026-12-15');
    expect(entry['payload']['lines'].single['description'], 'Corrected line');
  }, variant: rejectionStatuses);

  testWidgets('GST starts and stores a draft without a connection', (
    tester,
  ) async {
    const url = 'https://example.test/api/v1';
    const scope = '["$url",5,7]';
    const headers = {'X-Suite-Branch': '6', 'X-Suite-Organization': '7'};
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
    final branchStore = InventoryOfflineCreates(scope);
    api.dio.httpClientAdapter = FakeAdapter((request) async {
      expect(request.path, '/branches/context');
      expect(request.headers['X-Suite-Organization'], '7');
      return response({
        'branches': [
          {
            'id': 1,
            'name': 'Head office',
            'is_active': true,
            'can_write': true,
          },
          {'id': 6, 'name': 'Retail', 'is_active': true, 'can_write': true},
        ],
      }, 200);
    });
    await tester.runAsync(() async {
      await api.acceptTokens({'access_token': 'a', 'refresh_token': 'b'});
      await branchStore.writableBranches(api);
    });
    api.dio.httpClientAdapter = FakeAdapter((_) async {
      fail('Offline draft should not call the server');
    });
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
                  scopeHeaders: const {},
                  drafts: drafts,
                  branchStore: branchStore,
                  customerCacheScope: scope,
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
    final chooser = find.widgetWithText(OutlinedButton, 'Choose customer');
    expect(tester.widget<OutlinedButton>(chooser).onPressed, isNull);
    await tester.tap(find.byType(DropdownButton<String>));
    await tester.pumpAndSettle();
    await tap('Retail');
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
    expect(entry['unsent'], true);
    await tester.pumpWidget(
      MaterialApp(
        home: SalesOrderDraftsPage(
          api: api,
          drafts: drafts,
          editGstDraft: (context, draft) async {
            await showGstInvoiceDraftForm(
              context,
              api: api,
              scopeHeaders: headers,
              drafts: drafts,
              branchStore: branchStore,
              offline: true,
              savedDraft: draft,
            );
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tap('GST invoice');
    expect(find.text('Edit saved GST invoice draft'), findsOneWidget);
    await tap('Delivery');
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Description'),
      'Updated delivery',
    );
    await tap('Save line');
    await tap('Save changes');
    final edited = (await drafts.entries()).single;
    expect(
      edited['payload']['lines'].single['description'],
      'Updated delivery',
    );
    expect(edited['unsent'], true);
    final operation = edited['operation'] as String;
    api.dio.httpClientAdapter = FakeAdapter((request) async {
      expect(request.data['request_id'], operation);
      expect(request.headers, containsPair('X-Suite-Branch', '6'));
      expect(request.headers, containsPair('X-Suite-Organization', '7'));
      throw DioException(
        requestOptions: request,
        type: DioExceptionType.connectionError,
      );
    });
    await tester.runAsync(() async {
      await api.acceptTokens({'access_token': 'a', 'refresh_token': 'b'});
      await drafts.sync(api);
    });
    await tester.pumpAndSettle();
    expect((await drafts.entries()).single['unsent'], isNull);
    expect(
      tester
          .widget<ListTile>(find.widgetWithText(ListTile, 'GST invoice'))
          .onTap,
      isNull,
    );
    await expectLater(
      drafts.save('replacement', {}, replaceUnsent: operation, unsent: true),
      throwsStateError,
    );
  });
}
