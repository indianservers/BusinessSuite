import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/crm_offline_edits.dart';
import 'package:business_suite_mobile/core/inventory_offline_creates.dart';
import 'package:business_suite_mobile/core/inventory_stock_receipts.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/core/notes_offline_cache.dart';
import 'package:business_suite_mobile/core/sales_order_drafts.dart';
import 'package:business_suite_mobile/core/suite_read_cache.dart';
import 'package:business_suite_mobile/features/crm_lead_page.dart';
import 'package:business_suite_mobile/features/crm_contact_page.dart';
import 'package:business_suite_mobile/features/crm_customer_page.dart';
import 'package:business_suite_mobile/features/crm_deal_page.dart';
import 'package:business_suite_mobile/features/gst_invoice_page.dart';
import 'package:business_suite_mobile/features/inventory_drafts_page.dart';
import 'package:business_suite_mobile/features/inventory_stock_movement_page.dart';
import 'package:business_suite_mobile/features/my_attendance_page.dart';
import 'package:business_suite_mobile/features/my_leave_page.dart';
import 'package:business_suite_mobile/features/notes_page.dart';
import 'package:business_suite_mobile/features/sales_order_page.dart';
import 'package:business_suite_mobile/features/suite_dashboard.dart';
import 'package:business_suite_mobile/main.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import '../test/api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  final stockConnections = ValueVariant({'offline', 'interrupted'});

  testWidgets(
    'Android retains CRM contact, deal, and customer details offline',
    (tester) async {
      final scope = 'crm-detail-qa-${DateTime.now().microsecondsSinceEpoch}';
      var connected = true;
      final requests = <String>[];
      final api = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            requests.add(request.path);
            if (!connected) throw StateError('Offline request ${request.path}');
            return switch (request.path) {
              '/crm/contacts/4' => response({
                'id': 4,
                'full_name': 'Cached contact',
                'timeline': [
                  {'title': 'Requested a quote', 'occurredAt': '2026-11-27'},
                ],
              }),
              '/crm/deal-workspace/9/record' => response({
                'id': 9,
                'name': 'Cached deal',
                'description': 'Annual support renewal',
              }),
              '/master-data/companies/7' => response({
                'name': 'Cached customer',
                'contacts': [
                  {'name': 'Customer representative'},
                ],
              }),
              _ => throw StateError('Unexpected request ${request.path}'),
            };
          }),
      );

      Future<void> open(Widget page) async {
        await tester.pumpWidget(MaterialApp(home: page));
        await tester.pumpAndSettle();
      }

      for (final offline in [false, true]) {
        connected = !offline;
        await open(
          CrmContactPage(
            api: api,
            summary: const {'id': 4},
            offline: offline,
            cacheScope: scope,
            canEdit: true,
            scopeHeaders: const {},
          ),
        );
        expect(find.text('Requested a quote'), findsOneWidget);
        expect(
          find.text('Edit contact'),
          offline ? findsNothing : findsOneWidget,
        );
        await open(
          CrmDealPage(
            api: api,
            summary: const {'id': 9},
            offline: offline,
            cacheScope: scope,
            canMove: true,
            scopeHeaders: const {},
          ),
        );
        expect(find.text('Annual support renewal'), findsOneWidget);
        expect(
          find.text('Review stage move'),
          offline ? findsNothing : findsOneWidget,
        );
        await open(
          CrmCustomerPage(
            api: api,
            summary: const {'id': 7},
            offline: offline,
            cacheScope: scope,
            scopeHeaders: const {},
          ),
        );
        expect(find.text('Customer representative'), findsOneWidget);
      }
      expect(requests, [
        '/crm/contacts/4',
        '/crm/deal-workspace/9/record',
        '/master-data/companies/7',
      ]);
    },
  );

  testWidgets('Android reopens stock activity reports offline', (tester) async {
    var connected = true;
    final requests = <String>[];
    final transport = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        requests.add(request.path);
        if (!connected) throw StateError('Offline request ${request.path}');
        return switch (request.path) {
          '/access/me' => response({
            'companyId': 7,
            'grants': {
              'srm': {'enabled': true},
            },
          }),
          '/notifications/unread-count' => response({'unread': 0}),
          '/access/launcher-preferences' => response({
            'favorites': ['srm'],
          }),
          '/srm/sales-orders' ||
          '/srm/inventory/items' ||
          '/srm/inventory/reports/stock-summary' => response({
            'items': [
              {'id': 4, 'item_name': 'Sample inventory item'},
            ],
          }),
          final path
              when InventoryStockReceipts.activityReports.containsKey(path) =>
            response({
              'items': [
                {
                  'id': 4,
                  'item_name': 'Cached activity item',
                  'last_movement_date': '2026-01-05',
                  'age_days': 101,
                  'quantity_out': 4,
                  'movement_class': 'slow',
                },
              ],
            }),
          _ => throw StateError('Unexpected request ${request.path}'),
        };
      });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: transport,
    );
    await api.acceptTokens({
      'access_token': 'device-qa',
      'refresh_token': 'device-qa',
    });
    final user = SessionUser.fromJson({
      'id': DateTime.now().microsecondsSinceEpoch,
      'email': 'qa@example.test',
    });

    Future<void> tap(Finder finder) async {
      final deadline = DateTime.now().add(const Duration(seconds: 15));
      while (finder.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(finder, findsOneWidget);
      await tester.ensureVisible(finder);
      await tester.tap(finder);
      await tester.pumpAndSettle();
    }

    Future<void> checkReports(bool offline) async {
      final controller = AppController(api, suiteLogin: true)
        ..loading = false
        ..user = user
        ..offline = offline;
      await tester.pumpWidget(BusinessSuiteApp(controller: controller));
      await tester.pumpAndSettle();
      await tap(find.text('Favorites (1)'));
      await tap(find.text('Sales & POS'));
      await tap(find.byTooltip('Inventory'));
      await tap(find.byTooltip('Stock Summary'));
      for (final report in InventoryStockReceipts.activityReports.values) {
        await tap(find.byTooltip('Stock activity reports'));
        await tap(find.text(report));
        expect(find.text('Cached activity item'), findsOneWidget);
        expect(
          find.textContaining(
            report == 'Fast and Slow Moving Stock'
                ? 'Quantity issued 4'
                : 'Days since last movement 101',
          ),
          findsOneWidget,
        );
        await tester.pageBack();
        await tester.pumpAndSettle();
      }
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
    }

    await checkReports(false);
    for (final path in InventoryStockReceipts.activityReports.keys) {
      expect(requests.where((request) => request == path), hasLength(1));
    }
    final beforeOffline = requests.length;
    connected = false;
    await checkReports(true);
    expect(requests, hasLength(beforeOffline));
  });

  testWidgets('Android saves a stock movement offline and sends it later', (
    tester,
  ) async {
    final scope =
        '["https://example.test/api/v1",${DateTime.now().microsecondsSinceEpoch},7]';
    await SuiteReadCache.write('$scope:/srm/inventory/warehouses:3', [
      {'id': 4, 'warehouse_name': 'Offline QA warehouse'},
    ]);
    final calls = <RequestOptions>[];
    final startsOffline = stockConnections.currentValue == 'offline';
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'GET') {
            return response({
              'items': [
                {'id': 4, 'warehouse_name': 'Offline QA warehouse'},
              ],
            });
          }
          calls.add(request);
          if (!startsOffline && calls.length == 1) {
            return response({'detail': 'Unavailable'}, 503);
          }
          return response({}, 201);
        }),
    );
    await api.acceptTokens({
      'access_token': 'qa-access',
      'refresh_token': 'qa-refresh',
    });
    Widget page(bool offline) => MaterialApp(
      home: InventoryStockMovementPage(
        api: api,
        productId: 12,
        scopeHeaders: const {'X-Suite-Branch': '3'},
        cacheScope: scope,
        offline: offline,
      ),
    );
    Future<void> waitFor(Finder finder) async {
      final deadline = DateTime.now().add(const Duration(seconds: 30));
      while (finder.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(finder, findsOneWidget);
    }

    final save = find.text(startsOffline ? 'Save for later' : 'Save movement');
    await tester.pumpWidget(page(startsOffline));
    await waitFor(save);
    await tester.tap(find.byType(DropdownButtonFormField<int>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Offline QA warehouse').last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Quantity'),
      '2.5',
    );
    await tester.tap(save);
    await waitFor(find.text('Pending stock movement'));
    expect(calls, hasLength(startsOffline ? 0 : 1));

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpWidget(page(false));
    await waitFor(find.text('Retry same movement'));
    final receipts = InventoryStockReceipts(scope);
    await Future.wait([receipts.sync(api), receipts.sync(api)]);
    await tester.tap(find.text('Retry same movement'));
    await tester.pumpAndSettle();
    expect(calls, hasLength(startsOffline ? 1 : 2));
    final sent = calls.last;
    expect(sent.path, '/srm/inventory/stock-movements/offline-create');
    expect(sent.headers['X-Suite-Branch'], '3');
    expect(sent.headers['X-Suite-Organization'], '7');
    expect(sent.headers['X-Offline-Operation'], isNotNull);
    expect(
      sent.headers['X-Offline-Operation'],
      calls.first.headers['X-Offline-Operation'],
    );
    expect(sent.data, {
      'product_id': 12,
      'warehouse_id': 4,
      'movement_type': 'stock_in',
      'quantity': '2.5',
    });
  }, variant: stockConnections);

  const notesQaUrl = String.fromEnvironment('NOTES_QA_API_URL');
  const browserRun = String.fromEnvironment('NOTES_BROWSER_RUN');
  testWidgets('Android Notes sees edits from another authenticated session', (
    tester,
  ) async {
    expect(Uri.parse(notesQaUrl).host, anyOf('127.0.0.1', '10.0.2.2'));
    const path = '/project-management/notes';
    final mobile = ApiClient(baseUrl: notesQaUrl, store: MemoryStore());
    final other = ApiClient(baseUrl: notesQaUrl, store: MemoryStore());
    for (final api in [mobile, other]) {
      await api.acceptTokens(
        await api.login('notes-admin@example.com', 'NotesQA@123'),
      );
    }
    final title = browserRun.isEmpty
        ? 'Android QA ${DateTime.now().microsecondsSinceEpoch}'
        : 'Android browser QA $browserRun';
    const body = 'Created from native Notes';
    await tester.pumpWidget(MaterialApp(home: NotesPage(api: mobile)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('New note'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Title'), title);
    await tester.enterText(find.widgetWithText(TextField, 'Note'), body);
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(
      find.text('New note'),
      findsOneWidget,
      reason: 'The editor should close after saving.',
    );
    final results =
        await other.request('GET', path, query: {'q': title}) as List;
    expect(
      results,
      hasLength(1),
      reason: 'The note should exist on the shared backend.',
    );
    final note = results.whereType<Json>().single;
    final notePath = '$path/${note['id']}';
    final created = await other.request('GET', notePath) as Json;
    expect(created['content'], body);
    if (browserRun.isNotEmpty) {
      final expectedTitle = '$title edited on web';
      final deadline = DateTime.now().add(const Duration(minutes: 3));
      var webTitle = '';
      while (DateTime.now().isBefore(deadline)) {
        final current = await other.request('GET', notePath) as Json;
        webTitle = current['title'] as String? ?? '';
        if (webTitle == expectedTitle) break;
        await tester.pump(const Duration(seconds: 1));
      }
      expect(webTitle, expectedTitle);
      await tester.pumpWidget(
        MaterialApp(
          home: NotesPage(key: UniqueKey(), api: mobile),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).first, title);
      await tester.pumpAndSettle(const Duration(milliseconds: 300));
      expect(find.widgetWithText(ListTile, expectedTitle), findsOneWidget);
      return;
    }
    const updatedBody = 'Updated in a second session';
    await other.request(
      'PUT',
      notePath,
      data: {
        for (final key in [
          'version',
          'title',
          'tags',
          'project_id',
          'folder_id',
          'task_id',
          'archived',
          'pinned',
          'favorite',
        ])
          key: created[key],
        'content': updatedBody,
      },
    );
    await tester.tap(find.byTooltip('Refresh notes'));
    await tester.pumpAndSettle();
    expect(find.text(updatedBody), findsOneWidget);
  }, skip: notesQaUrl.isEmpty);

  testWidgets('Android Sales keeps products viewed in the picker offline', (
    tester,
  ) async {
    const base = 'https://example.test/api/v1';
    final scope = '["$base",${DateTime.now().microsecondsSinceEpoch},7]';
    await SuiteReadCache.write('$scope:${SalesOrderDrafts.productsEndpoint}', [
      {
        'id': 4,
        'item_name': 'Inventory cable',
        'sku': 'SKU-4',
        'sales_rate': 12,
      },
    ]);
    var requests = 0;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        requests++;
        expectSync(request.path, SalesOrderDrafts.productsEndpoint);
        return response({
          'items': [
            {
              'id': 9,
              'item_name': 'Picker cable',
              'sku': 'SKU-9',
              'sales_rate': 19,
            },
          ],
        });
      });
    final api = ApiClient(baseUrl: base, store: MemoryStore(), transport: dio);
    await api.acceptTokens({
      'access_token': 'device-qa',
      'refresh_token': 'device-qa',
    });
    await SalesOrderDrafts(scope).products(api, 'cable', offline: false);
    final reopened = SalesOrderDrafts(scope);
    expect(
      (await reopened.products(
        api,
        'cable',
        offline: true,
      )).map((row) => row['id']),
      unorderedEquals([4, 9]),
    );
    expect(
      (await reopened.products(
        api,
        'SKU-9',
        offline: true,
      )).single['sales_rate'],
      19,
    );
    expect(requests, 1);
  });

  testWidgets('Android creates an offline sales order from saved inventory', (
    tester,
  ) async {
    const base = 'https://example.test/api/v1';
    final id = DateTime.now().microsecondsSinceEpoch;
    final scope = '["$base",$id,7]';
    final drafts = SalesOrderDrafts(scope);
    await SuiteReadCache.write('$scope:${SalesOrderDrafts.productsEndpoint}', [
      {
        'id': 8,
        'item_name': 'Saved inventory cable',
        'sku': 'SKU-8',
        'sales_rate': 75,
      },
    ]);
    final submitted = <RequestOptions>[];
    var connected = false;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        if (!connected) {
          throw DioException(
            requestOptions: request,
            type: DioExceptionType.connectionError,
          );
        }
        if (request.path != SalesOrderDrafts.endpoint) {
          throw StateError('Unexpected request ${request.path}');
        }
        if (request.method == 'GET') {
          return response([
            if (submitted.isNotEmpty)
              {
                'id': 19,
                'title': 'Android offline order',
                'order_number': 'SO-19',
              },
          ]);
        }
        submitted.add(request);
        return response({'id': 19, 'order_number': 'SO-19'}, 201);
      });
    final api = ApiClient(baseUrl: base, store: MemoryStore(), transport: dio);
    await api.acceptTokens({
      'access_token': 'device-qa',
      'refresh_token': 'device-qa',
    });
    final identity = {'id': id, 'email': 'qa@example.test'};
    await api.rememberSuite(identity, {
      'companyId': 7,
      'canCreateOrder': true,
      'grants': {
        'srm': {'enabled': true},
      },
    });
    final controller = AppController(api, suiteLogin: true)
      ..loading = false
      ..user = SessionUser.fromJson(identity)
      ..offline = true;
    Future<void> waitFor(Finder finder) async {
      final deadline = DateTime.now().add(const Duration(seconds: 20));
      while (finder.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(finder, findsOneWidget);
    }

    await tester.pumpWidget(BusinessSuiteApp(controller: controller));
    await waitFor(find.text('Sales & POS'));
    await tester.ensureVisible(find.text('Sales & POS'));
    await tester.tap(find.text('Sales & POS'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Sales order actions'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('New sales order'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextFormField).first,
      'Android offline order',
    );
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.pumpAndSettle();
    final picker = find.text('Choose product').hitTestable();
    await tester.scrollUntilVisible(
      picker,
      120,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(picker);
    await waitFor(find.text('Saved inventory cable'));
    await tester.tap(find.text('Saved inventory cable'));
    await tester.pumpAndSettle();
    final save = find.text('Save order draft').hitTestable();
    await tester.scrollUntilVisible(
      save,
      150,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(save);
    await waitFor(find.byTooltip('Sales order actions'));
    final saved = (await drafts.entries()).single;
    expect(saved['payload']['lines'][0]['product_id'], 8);
    expect(submitted, isEmpty);
    await tester.tap(find.byTooltip('Sales order actions'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Order drafts'));
    await waitFor(find.text('Awaiting sync'));
    connected = true;
    await tester.tap(find.byTooltip('Sync order drafts'));
    await waitFor(find.text('No saved order drafts'));
    expect(submitted, hasLength(1));
    expect(submitted.single.headers['X-Offline-Operation'], saved['operation']);
    expect(submitted.single.data, saved['payload']);
    await tester.pageBack();
    await waitFor(find.text('Android offline order'));
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
    'Android creates a CRM lead from the offline dashboard and syncs it',
    (tester) async {
      const base = 'https://example.test/api/v1';
      final id = DateTime.now().microsecondsSinceEpoch;
      final queue = CrmOfflineEdits('["$base",$id,7]');
      final submitted = <RequestOptions>[];
      var connected = false;
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (!connected) {
            throw DioException(
              requestOptions: request,
              type: DioExceptionType.connectionError,
            );
          }
          if (request.path == CrmLeadPage.endpoint && request.method == 'GET') {
            return response({
              'items': [
                if (submitted.isNotEmpty)
                  {'id': 19, 'full_name': 'Android field lead'},
              ],
            });
          }
          if (request.path != CrmLeadPage.endpoint ||
              request.method != 'POST') {
            throw StateError('Unexpected request ${request.path}');
          }
          submitted.add(request);
          return response({'id': 19}, 201);
        });
      final api = ApiClient(
        baseUrl: base,
        store: MemoryStore(),
        transport: dio,
      );
      await api.acceptTokens({
        'access_token': 'device-qa',
        'refresh_token': 'device-qa',
      });
      final identity = {'id': id, 'email': 'qa@example.test'};
      await api.rememberSuite(identity, {
        'companyId': 7,
        'canCreateLead': true,
        'grants': {
          'crm': {'enabled': true},
        },
      });
      final controller = AppController(api, suiteLogin: true)
        ..loading = false
        ..user = SessionUser.fromJson(identity)
        ..offline = true;
      Future<void> waitFor(Finder finder) async {
        final deadline = DateTime.now().add(const Duration(seconds: 15));
        while (finder.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
          await tester.pump(const Duration(milliseconds: 100));
        }
        expect(finder, findsOneWidget);
      }

      await tester.pumpWidget(BusinessSuiteApp(controller: controller));
      await waitFor(find.text('VyaparaCRM'));
      await tester.ensureVisible(find.text('VyaparaCRM'));
      await tester.tap(find.text('VyaparaCRM'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('New lead'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextFormField).first,
        'Android field lead',
      );
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.pumpAndSettle();
      final save = find.text('Save lead draft');
      await tester.scrollUntilVisible(
        save,
        150,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(save);
      await waitFor(find.byTooltip('Lead drafts'));
      final saved = (await queue.creations()).single;
      expect(saved['values']['full_name'], 'Android field lead');
      expect(submitted, isEmpty);
      await tester.tap(find.byTooltip('Lead drafts'));
      await waitFor(find.text('Android field lead'));
      expect(find.text('Awaiting sync'), findsOneWidget);
      connected = true;
      await tester.tap(find.byTooltip('Sync lead drafts'));
      await waitFor(find.text('No saved lead drafts'));
      expect(submitted, hasLength(1));
      expect(submitted.single.data, {
        'values': {'full_name': 'Android field lead'},
      });
      expect(
        'create:${submitted.single.headers['X-Offline-Operation']}',
        saved['key'],
      );
      expect(await queue.creations(), isEmpty);
      await tester.pageBack();
      await waitFor(find.text('Android field lead'));
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets('Android CRM combines saved pages without duplicate leads', (
    tester,
  ) async {
    final scope = 'crm-pages-${DateTime.now().microsecondsSinceEpoch}';
    final neighboringScope = '$scope:page;2';
    await SuiteReadCache.write(neighboringScope, [
      {'id': 99, 'first_name': 'Lead from a different scope'},
    ]);
    await SuiteReadCache.writePage(scope, 1, [
      {'id': 3, 'first_name': 'Newest lead'},
      {'id': 2, 'first_name': 'Current duplicate', 'version': 2},
    ]);
    await SuiteReadCache.writePage(scope, 2, [
      {'id': 2, 'first_name': 'Older duplicate', 'version': 1},
      {'id': 1, 'first_name': 'Saved from page two'},
    ]);
    final rows = await SuiteReadCache.readPages(scope);
    expect(rows?.map((row) => row['id']), [3, 2, 1]);
    expect(rows?[1]['version'], 2);
    await SuiteReadCache.clearPages(scope);
    expect(await SuiteReadCache.readPages(scope), isNull);
    expect((await SuiteReadCache.read(neighboringScope))?.single['id'], 99);
    await SuiteReadCache.clear(neighboringScope);
  });

  testWidgets(
    'Android reopens a cached Finance party from the offline dashboard',
    (tester) async {
      var connected = true;
      final requests = <String>[];
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests.add(request.path);
          if (!connected) throw StateError('Offline request ${request.path}');
          if (request.path == '/fam/parties') {
            expectSync(request.queryParameters['summary_only'], isTrue);
          }
          return switch (request.path) {
            '/access/me' => response({
              'companyId': 7,
              'grants': {
                'fam': {'enabled': true},
              },
            }),
            '/notifications/unread-count' => response({'unread': 0}),
            '/access/launcher-preferences' => response({
              'favorites': ['fam'],
            }),
            '/fam/parties' => response({
              'items': [
                {
                  'id': 4,
                  'legal_name': 'Saved Android Supplier',
                  'party_code': 'ANDROID-4',
                },
              ],
              'total': 1,
            }),
            _ => throw StateError('Unexpected request ${request.path}'),
          };
        });
      final api = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: dio,
      );
      await api.acceptTokens({
        'access_token': 'device-qa',
        'refresh_token': 'device-qa',
      });
      final user = SessionUser.fromJson({
        'id': DateTime.now().microsecondsSinceEpoch,
        'email': 'qa@example.test',
      });
      Future<void> openFinance(bool offline) async {
        final controller = AppController(api, suiteLogin: true)
          ..loading = false
          ..user = user
          ..offline = offline;
        await tester.pumpWidget(BusinessSuiteApp(controller: controller));
        await tester.pumpAndSettle();
        final finance = find.text('Finance & Accounting');
        final deadline = DateTime.now().add(const Duration(seconds: 15));
        while (finance.evaluate().isEmpty &&
            DateTime.now().isBefore(deadline)) {
          await tester.pump(const Duration(milliseconds: 100));
        }
        expect(
          finance,
          findsOneWidget,
          reason: 'offline=$offline, requests=$requests',
        );
        final favorites = find.text('Favorites (1)');
        while (favorites.evaluate().isEmpty &&
            DateTime.now().isBefore(deadline)) {
          await tester.pump(const Duration(milliseconds: 100));
        }
        expect(favorites, findsOneWidget, reason: 'offline=$offline');
        await tester.tap(favorites);
        await tester.pumpAndSettle();
        await tester.ensureVisible(finance);
        await tester.tap(finance);
        await tester.pumpAndSettle();
      }

      final supplier = find.text('Saved Android Supplier');
      await openFinance(false);
      expect(supplier, findsOneWidget);
      expect(requests.where((path) => path == '/fam/parties'), hasLength(1));
      expect(api.offlineSuite?['access']['grants']['fam']['enabled'], isTrue);
      final onlineRequests = requests.length;
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
      connected = false;
      await openFinance(true);
      await tester.tap(supplier);
      await tester.pumpAndSettle();
      expect(find.text('Saved party summary'), findsOneWidget);
      expect(find.text('ANDROID-4'), findsOneWidget);
      expect(requests, hasLength(onlineRequests));
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets('Android Sales searches older orders and falls back offline', (
    tester,
  ) async {
    final id = DateTime.now().microsecondsSinceEpoch;
    var requests = 0;
    final searches = <Object?>[];
    var lostConnection = false;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        switch (request.path) {
          case '/access/me':
            return response({
              'companyId': 7,
              'grants': {
                'srm': {'enabled': true},
              },
            });
          case '/notifications/unread-count':
            return response({'unread': 0});
          case '/srm/sales-orders':
            if (request.queryParameters['search'] case final String term) {
              searches.add(term);
              if (lostConnection) {
                throw DioException(
                  requestOptions: request,
                  type: DioExceptionType.connectionError,
                );
              }
              return response([
                {'id': 2, 'order_number': 'ARCHIVED-ORDER'},
              ]);
            }
            requests++;
            return response([
              {'id': 1, 'order_number': 'QA-SALE-$requests'},
            ]);
          default:
            throw StateError('Unexpected request ${request.path}');
        }
      });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: dio,
    );
    await api.acceptTokens({
      'access_token': 'device-qa',
      'refresh_token': 'device-qa',
    });
    final controller = AppController(api, suiteLogin: true)
      ..loading = false
      ..user = SessionUser.fromJson({'id': id, 'email': 'qa@example.test'});
    await tester.pumpWidget(BusinessSuiteApp(controller: controller));
    await tester.pumpAndSettle();
    Future<void> openSales() async {
      final sales = find.text('Sales & POS');
      await tester.ensureVisible(sales);
      await tester.pumpAndSettle();
      await tester.tap(sales);
      await tester.pumpAndSettle();
    }

    await openSales();
    expect(find.text('QA-SALE-1'), findsOneWidget);
    expect(requests, 1);
    await tester.tap(find.byTooltip('Refresh'));
    Future<void> waitForOrder(String number) async {
      final order = find.text(number);
      final deadline = DateTime.now().add(const Duration(seconds: 15));
      while (order.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(order, findsOneWidget);
    }

    await waitForOrder('QA-SALE-2');
    expect(requests, 2);
    final search = find.byType(TextField);
    await tester.enterText(search, 'archived');
    await waitForOrder('ARCHIVED-ORDER');
    expect(searches, ['archived']);
    final snapshots = await SuiteReadCache.read(
      '["https://example.test/api/v1",$id,7]:/srm/sales-orders',
    );
    expect(snapshots?.single['order_number'], 'QA-SALE-2');
    lostConnection = true;
    await tester.enterText(search, 'QA-SALE');
    final savedSearch = find.text('Search saved orders');
    final deadline = DateTime.now().add(const Duration(seconds: 15));
    while (savedSearch.evaluate().isEmpty &&
        DateTime.now().isBefore(deadline)) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    expect(savedSearch, findsOneWidget);
    await tester.enterText(search, 'QA-SALE-2');
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.widgetWithText(ListTile, 'QA-SALE-2'), findsOneWidget);
    expect(searches, ['archived', 'QA-SALE']);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
    'Android Notes reopens a durable draft and syncs it after reconnect',
    (tester) async {
      const server = 'https://example.test/api/v1';
      final scope = '["$server",${DateTime.now().microsecondsSinceEpoch},7]';
      final cache = NotesOfflineCache(scope);
      final operations = <Object?>[];
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.method == 'GET') {
            expectSync(request.path, '/project-management/notes');
            return response([
              if (operations.length == 2)
                {
                  'id': 10,
                  'title': 'Android offline note',
                  'preview': 'QA body',
                },
            ]);
          }
          expectSync(request.path, '/project-management/notes/offline-create');
          expectSync(request.data, {
            'title': 'Android offline note',
            'content': 'QA body',
          });
          operations.add(request.headers['X-Offline-Operation']);
          if (operations.length == 1) {
            return response({'detail': 'Unavailable'}, 503);
          }
          return response({
            'id': 10,
            'title': 'Android offline note',
            'content': 'QA body',
          }, 201);
        });
      final api = ApiClient(
        baseUrl: server,
        store: MemoryStore(),
        transport: dio,
      );
      await api.acceptTokens({
        'access_token': 'device-qa',
        'refresh_token': 'device-qa',
      });
      Future<void> waitFor(Finder finder) async {
        final deadline = DateTime.now().add(const Duration(seconds: 15));
        while (finder.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
          await tester.pump(const Duration(milliseconds: 100));
        }
        expect(finder, findsOneWidget);
      }

      await tester.pumpWidget(
        MaterialApp(
          home: NotesPage(api: api, cache: cache, offline: true),
        ),
      );
      await tester.tap(find.text('New note'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextField).first,
        'Android offline note',
      );
      await tester.enterText(find.byType(TextField).last, 'QA body');
      await tester.tap(find.text('Save'));
      await waitFor(find.text('Saved · Awaiting sync'));
      expect(operations, isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
      final reopened = NotesOfflineCache(scope);
      await tester.pumpWidget(
        MaterialApp(
          home: NotesPage(api: api, cache: reopened, offline: true),
        ),
      );
      await waitFor(find.text('Saved · Awaiting sync'));
      expect(await reopened.creations(), hasLength(1));
      await reopened.sync(api);
      expect(await reopened.creations(), hasLength(1));
      await tester.tap(find.byTooltip('Refresh notes'));
      final deadline = DateTime.now().add(const Duration(seconds: 15));
      final pendingBadge = find.text('Saved · Awaiting sync');
      while (((await reopened.creations()).isNotEmpty ||
              pendingBadge.evaluate().isNotEmpty) &&
          DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(await reopened.creations(), isEmpty);
      await waitFor(find.text('QA body'));
      expect(pendingBadge, findsNothing);
      expect(operations, hasLength(2));
      expect(operations.first, isNotNull);
      expect(operations.first, operations.last);
    },
  );

  testWidgets('Android HRMS shows attendance and leave from the shared API', (
    tester,
  ) async {
    var checkedIn = false;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        switch (request.path) {
          case '/attendance/today':
            return response({
              'attendance': {if (checkedIn) 'check_in': '2026-11-27T08:00:00Z'},
            });
          case '/attendance/check-in':
            expectSync(request.method, 'POST');
            expectSync(request.data, {'source': 'Mobile'});
            checkedIn = true;
            return response({});
          case '/attendance/my':
          case '/leave/my-requests':
            return response([]);
          case '/attendance/summary/monthly':
            return response({'present': 1});
          case '/leave/balance':
            return response([
              {
                'leave_type': {'name': 'QA Annual leave'},
                'available': 8,
                'used': 2,
                'pending': 0,
              },
            ]);
          default:
            throw StateError('Unexpected request ${request.path}');
        }
      });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: dio,
    );
    Future<void> waitFor(Finder element) async {
      final deadline = DateTime.now().add(const Duration(seconds: 15));
      while (element.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(element, findsOneWidget);
    }

    await tester.pumpWidget(MaterialApp(home: MyAttendancePage(api: api)));
    final checkIn = find.text('Check In');
    await waitFor(checkIn);
    await tester.tap(checkIn);
    await waitFor(find.text('Check Out'));
    expect(checkedIn, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpWidget(MaterialApp(home: MyLeavePage(api: api)));
    await waitFor(find.text('QA Annual leave'));
    expect(find.text('8 days available'), findsOneWidget);
  });

  testWidgets(
    'Android queues and retries an offline product in its selected branch',
    (tester) async {
      const base = 'https://example.test/api/v1';
      final user = DateTime.now().microsecondsSinceEpoch;
      final scope = '["$base",$user,7]';
      final drafts = InventoryOfflineCreates(scope);
      final inventoryKey = '$scope:${InventoryOfflineCreates.itemsEndpoint}';
      await SuiteReadCache.write(inventoryKey, [
        {'id': 2, 'sku': 'PREVIOUS'},
      ]);
      final submissions = <RequestOptions>[];
      var branchRequests = 0;
      var connected = true;
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expectSync(request.headers['X-Suite-Organization'], '7');
          if (request.method == 'GET') {
            branchRequests++;
            return response(
              connected
                  ? {
                      'branches': [
                        {
                          'id': 3,
                          'name': 'North warehouse',
                          'can_write': true,
                          'is_active': true,
                        },
                        {
                          'id': 4,
                          'name': 'Read-only warehouse',
                          'can_write': false,
                          'is_active': true,
                        },
                      ],
                    }
                  : {'detail': 'Unavailable'},
              connected ? 200 : 503,
            );
          }
          submissions.add(request);
          return connected
              ? response({'id': 1}, 201)
              : response({'detail': 'Unavailable'}, 503);
        });
      final api = ApiClient(
        baseUrl: base,
        store: MemoryStore(),
        transport: dio,
      );
      await api.acceptTokens({
        'access_token': 'device-qa',
        'refresh_token': 'device-qa',
      });
      expect(await drafts.writableBranches(api), hasLength(1));
      connected = false;
      await tester.pumpWidget(
        MaterialApp(
          home: InventoryDraftsPage(api: api, drafts: drafts, offline: true),
        ),
      );
      final branchPicker = find.byType(DropdownButtonFormField<int>);
      final deadline = DateTime.now().add(const Duration(seconds: 10));
      while (branchPicker.evaluate().isEmpty &&
          DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      await tester.tap(branchPicker);
      await tester.pumpAndSettle();
      expect(find.text('Read-only warehouse'), findsNothing);
      await tester.tap(find.text('North warehouse').last);
      await tester.pumpAndSettle();
      final fields = find.byType(TextFormField);
      for (final (index, value) in [
        (0, 'QA Product'),
        (1, 'QA-SKU'),
        (2, 'INR'),
        (3, 'QA Accessories'),
      ]) {
        final field = fields.at(index);
        await tester.ensureVisible(field);
        await tester.enterText(field, value);
        await tester.pumpAndSettle();
      }
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.pumpAndSettle();
      final save = find.text('Save product draft').hitTestable();
      await tester.scrollUntilVisible(
        save,
        220,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.tap(save);
      await tester.pumpAndSettle();
      final saved = (await drafts.entries()).single;
      expect(saved['branch'], 3);
      expect(saved['product']['code'], 'QA-SKU');
      expect(saved['product']['category'], 'QA Accessories');
      expect(branchRequests, 1);
      expect(submissions, isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
      final reopened = InventoryOfflineCreates(
        scope,
        invalidate: SuiteReadCache.invalidate,
      );
      await reopened.sync(api);
      expect(
        (await SuiteReadCache.snapshot(inventoryKey))?.invalidated,
        isFalse,
      );
      expect(
        (await reopened.entries()).single['operation'],
        saved['operation'],
      );
      connected = true;
      await reopened.sync(api);
      expect(await reopened.entries(), isEmpty);
      final snapshot = await SuiteReadCache.snapshot(inventoryKey);
      expect(snapshot?.invalidated, isTrue);
      expect(snapshot?.rows.single['sku'], 'PREVIOUS');
      expect(submissions, hasLength(2));
      for (final request in submissions) {
        expect(request.path, '/catalog/items');
        expect(request.headers['X-Suite-Branch'], '3');
        expect(request.headers['X-Offline-Operation'], saved['operation']);
        expect(request.data['category'], 'QA Accessories');
      }
    },
  );

  testWidgets('Android saves and reopens stock, sales, and CRM details offline', (
    tester,
  ) async {
    final scope = 'device-qa-${DateTime.now().microsecondsSinceEpoch}';
    final fixtures = <String, Json>{
      '/srm/inventory/items/1': {
        'item_name': 'QA stock',
        'unit_code': 'EA',
        'balances': [
          {'warehouse_id': 41, 'warehouse_name': 'QA warehouse', 'quantity': 5},
        ],
        'ledger': [
          {
            'movement_number': 'QA movement',
            'warehouse_name': 'QA warehouse',
            'quantity_in': 5,
          },
        ],
      },
      '/srm/sales-orders/1': {
        'order_number': 'QA order',
        'currency': 'INR',
        'terms': 'Payment due in 30 days',
        'engagement': {'engagement_number': 'QA-ENG-1', 'status': 'active'},
        'lines': [
          {'description': 'QA order line', 'quantity': 2, 'tax_amount': 18},
        ],
      },
      '/crm/lead-management/leads/1': {
        'first_name': 'QA lead',
        'source': 'QA referral',
        'email': 'qa@example.test',
        'version': 2,
      },
      '/srm/invoices/1': {
        'invoice_number': 'QA invoice',
        'lines': [
          {'description': 'QA invoice line', 'quantity': 2},
        ],
      },
    };
    var requests = 0;
    final transportErrors = <String>[];
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        requests++;
        expectSync(request.method, 'GET');
        return response(fixtures[request.path]!);
      });
    dio.interceptors.add(
      InterceptorsWrapper(
        onError: (error, handler) {
          transportErrors.add('${error.requestOptions.path}: ${error.error}');
          handler.next(error);
        },
      ),
    );
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: dio,
    );
    final pages = <(Widget Function(bool), String)>[
      (
        (offline) => GstInvoicePage(
          api: api,
          id: 1,
          offline: offline,
          cacheScope: scope,
        ),
        'QA invoice line',
      ),
      (
        (offline) => InventoryProductPage(
          api: api,
          summary: const {'id': 1},
          offline: offline,
          cacheScope: scope,
        ),
        'QA movement',
      ),
      (
        (offline) => SalesOrderPage(
          api: api,
          summary: const {'id': 1},
          offline: offline,
          cacheScope: scope,
        ),
        'QA order line',
      ),
      (
        (offline) => CrmLeadPage(
          api: api,
          summary: const {'id': 1},
          offline: offline,
          cacheScope: scope,
        ),
        'QA referral',
      ),
    ];
    Future<void> findDetail(String expected) async {
      final detail = find.text(expected);
      final deadline = DateTime.now().add(const Duration(seconds: 15));
      while (DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
        if (detail.evaluate().isNotEmpty) return;
        final list = find.byType(ListView);
        if (list.evaluate().length == 1 &&
            find.byType(LinearProgressIndicator).evaluate().isEmpty) {
          await tester.drag(list, const Offset(0, -180));
        }
      }
      expect(
        detail,
        findsOneWidget,
        reason:
            'requests=$requests; '
            'transportErrors=$transportErrors; '
            'rendered=${tester.widgetList<Text>(find.byType(Text)).map((text) => text.data).toList()}',
      );
    }

    for (final (page, expected) in pages) {
      await tester.pumpWidget(MaterialApp(home: page(false)));
      await findDetail(expected);
      if (expected == 'QA invoice line') {
        final cached = await SuiteReadCache.read('$scope:/srm/invoices/1');
        expect(cached?.single['invoice_number'], 'QA invoice');
      }
      final requestsBeforeOffline = requests;
      if (expected == 'QA movement' || expected == 'QA order line') {
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpWidget(MaterialApp(home: page(false)));
        await findDetail(expected);
        expect(requests, requestsBeforeOffline);
      }
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpWidget(MaterialApp(home: page(true)));
      if (expected == 'QA order line') {
        await findDetail('Payment due in 30 days');
      }
      if (expected == 'QA movement') {
        await findDetail('QA warehouse');
        await findDetail('5 EA');
        await findDetail('QA warehouse · In 5 · Out 0');
      }
      await findDetail(expected);
      if (expected == 'QA order line') {
        expect(find.textContaining('Tax INR 18'), findsOneWidget);
        await findDetail('QA-ENG-1 · active');
      }
      expect(find.text('qa@example.test'), findsNothing);
      expect(requests, requestsBeforeOffline);
      await tester.pumpWidget(const SizedBox.shrink());
    }
    expect(requests, 4);

    await tester.pumpWidget(
      MaterialApp(
        home: InventoryProductPage(
          api: api,
          summary: const {
            'id': 2,
            'item_name': 'Unopened catalogue product',
            'category_name': 'Accessories',
            'hsn_code': '8471',
            'sales_rate': 125.5,
            'gst_rate': 18,
          },
          offline: true,
          cacheScope: scope,
        ),
      ),
    );
    await findDetail('125.5');
    expect(find.text('Accessories'), findsOneWidget);
    expect(find.text('8471'), findsOneWidget);
    expect(find.text('18'), findsOneWidget);
    expect(requests, 4);
  });
}
