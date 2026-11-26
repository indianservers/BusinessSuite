import 'dart:async';

import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/crm_offline_edits.dart';
import 'package:business_suite_mobile/core/inventory_offline_creates.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/core/notes_offline_cache.dart';
import 'package:business_suite_mobile/features/crm_lead_page.dart';
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
import 'package:business_suite_mobile/features/suite_dashboard.dart';
import 'package:business_suite_mobile/main.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
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
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save'));
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
        await tester.enterText(find.byType(TextField).last, 'Offline edit');
        await tester.pumpAndSettle();
        await tester.tap(find.text('Save'));
        await tester.pumpAndSettle();
        expect((await cache.pending(1))?['values']['content'], 'Offline edit');
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
        ),
      ),
    );
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
    },
  );
  testWidgets(
    'issuing a GST invoice requires confirmation and reloads its status',
    (tester) async {
      var issued = false;
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
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Offline · Saved order summary'), findsOneWidget);
    expect(find.text('INR 45.00'), findsOneWidget);
    expect(find.text('Line items'), findsNothing);
    dio.httpClientAdapter = FakeAdapter((request) async {
      expect(request.path, '/srm/sales-orders/8');
      return response({
        'order_number': 'SO-8',
        'lines': [
          {'description': 'Live order line'},
        ],
      });
    });
    await tester.tap(find.text('Reconnect'));
    await tester.pumpAndSettle();
    expect(find.text('Live order line'), findsOneWidget);
    expect(find.text('Reconnect'), findsNothing);
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
  testWidgets('inventory renders the summary before fetching stock movements', (
    tester,
  ) async {
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        expect(request.path, '/srm/inventory/items/12');
        expect(request.headers['X-Suite-Branch'], '3');
        return response({
          'item_name': 'Updated product',
          'ledger': [
            {'movement_number': 'MOV-12', 'quantity_in': 3},
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
          offline: false,
          scopeHeaders: const {'X-Suite-Branch': '3'},
        ),
      ),
    );
    expect(find.text('Saved product'), findsOneWidget);
    await tester.pumpAndSettle();
    expect(find.text('Updated product'), findsOneWidget);
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
                {'title': 'Sample booking'},
              ],
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
            '/power-apps/environments' ||
            '/employees/' ||
            '/crm/lead-management/leads' ||
            '/fam/parties' ||
            '/project-management/notes' => response([]),
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
            '/srm/inventory/reports/stock-summary' => response({
              'items': [
                {
                  'id': 12,
                  'item_name': 'Sample product',
                  'current_quantity': 0,
                  'reorder_threshold': 3,
                },
                {
                  'id': 13,
                  'item_name': 'Healthy product',
                  'current_quantity': 20,
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
    },
  );
}
