import 'dart:async';

import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/crm_offline_edits.dart';
import 'package:business_suite_mobile/core/inventory_offline_creates.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/core/notes_offline_cache.dart';
import 'package:business_suite_mobile/core/sales_order_drafts.dart';
import 'package:business_suite_mobile/features/crm_lead_page.dart';
import 'package:business_suite_mobile/features/crm_new_lead_page.dart';
import 'package:business_suite_mobile/features/company_profile_panel.dart';
import 'package:business_suite_mobile/features/branch_settings_panel.dart';
import 'package:business_suite_mobile/features/branch_membership_page.dart';
import 'package:business_suite_mobile/features/lead_sources_panel.dart';
import 'package:business_suite_mobile/features/starter_values_panel.dart';
import 'package:business_suite_mobile/features/gst_invoice_page.dart';
import 'package:business_suite_mobile/features/my_attendance_page.dart';
import 'package:business_suite_mobile/features/my_leave_page.dart';
import 'package:business_suite_mobile/features/notes_page.dart';
import 'package:business_suite_mobile/features/finance_party_page.dart';
import 'package:business_suite_mobile/features/business_defaults_panel.dart';
import 'package:business_suite_mobile/features/sales_order_page.dart';
import 'package:business_suite_mobile/features/sales_order_drafts_page.dart';
import 'package:business_suite_mobile/features/suite_dashboard.dart';
import 'package:business_suite_mobile/main.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
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
  testWidgets('GST draft date editing sends only the changed date', (
    tester,
  ) async {
    var dueDate = '2026-12-01';
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        expect(request.path, '/srm/invoices/7');
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
  testWidgets(
    'native launcher opens authenticated module and settings routes',
    (tester) async {
      tester.view.physicalSize = const Size(430, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final calls = <RequestOptions>[];
      final transport = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          calls.add(request);
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
          await tester.tap(find.byTooltip('Low stock alerts'));
          await tester.pumpAndSettle();
          expect(find.text('1 item needs attention'), findsOneWidget);
          expect(find.text('Out of stock'), findsOneWidget);
          expect(find.text('Healthy product'), findsNothing);
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
