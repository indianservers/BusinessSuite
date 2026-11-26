import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/inventory_offline_creates.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/core/notes_offline_cache.dart';
import 'package:business_suite_mobile/features/crm_lead_page.dart';
import 'package:business_suite_mobile/features/gst_invoice_page.dart';
import 'package:business_suite_mobile/features/inventory_drafts_page.dart';
import 'package:business_suite_mobile/features/my_attendance_page.dart';
import 'package:business_suite_mobile/features/my_leave_page.dart';
import 'package:business_suite_mobile/features/notes_page.dart';
import 'package:business_suite_mobile/features/sales_order_page.dart';
import 'package:business_suite_mobile/features/suite_dashboard.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import '../test/api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

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
              {'id': 10, 'title': 'Android offline note', 'preview': 'QA body'},
            ]);
          }
          expectSync(request.path, '/project-management/notes/offline-create');
          expectSync(request.data, {
            'title': 'Android offline note',
            'content': 'QA body',
          });
          operations.add(request.headers['X-Offline-Operation']);
          if (operations.length == 1)
            return response({'detail': 'Unavailable'}, 503);
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
      await waitFor(find.text('QA body'));
      expect(await reopened.creations(), isEmpty);
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
      final drafts = InventoryOfflineCreates('["$base",$user,7]');
      final submissions = <RequestOptions>[];
      var connected = true;
      final dio = Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          expectSync(request.headers['X-Suite-Organization'], '7');
          if (request.method == 'GET') {
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
          home: InventoryDraftsPage(api: api, drafts: drafts),
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
      expect(submissions, isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
      final reopened = InventoryOfflineCreates('["$base",$user,7]');
      await reopened.sync(api);
      expect(
        (await reopened.entries()).single['operation'],
        saved['operation'],
      );
      connected = true;
      await reopened.sync(api);
      expect(await reopened.entries(), isEmpty);
      expect(submissions, hasLength(2));
      for (final request in submissions) {
        expect(request.path, '/catalog/items');
        expect(request.headers['X-Suite-Branch'], '3');
        expect(request.headers['X-Offline-Operation'], saved['operation']);
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
        'ledger': [
          {'movement_number': 'QA movement', 'quantity_in': 5},
        ],
      },
      '/srm/sales-orders/1': {
        'order_number': 'QA order',
        'lines': [
          {'description': 'QA order line', 'quantity': 2},
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
      final requestsBeforeOffline = requests;
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpWidget(MaterialApp(home: page(true)));
      await findDetail(expected);
      expect(find.text('qa@example.test'), findsNothing);
      expect(requests, requestsBeforeOffline);
      await tester.pumpWidget(const SizedBox.shrink());
    }
    expect(requests, 4);
  });
}
