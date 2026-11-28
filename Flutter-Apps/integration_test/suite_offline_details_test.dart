import 'dart:async';
import 'dart:convert';

import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/crm_detail_snapshot.dart';
import 'package:business_suite_mobile/core/crm_offline_edits.dart';
import 'package:business_suite_mobile/core/inventory_offline_creates.dart';
import 'package:business_suite_mobile/core/inventory_stock_receipts.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/core/notes_offline_cache.dart';
import 'package:business_suite_mobile/core/sales_order_drafts.dart';
import 'package:business_suite_mobile/core/suite_read_cache.dart';
import 'package:business_suite_mobile/features/crm_lead_page.dart';
import 'package:business_suite_mobile/features/sales_contract_page.dart';
import 'package:business_suite_mobile/features/sales_billing_plan_page.dart';
import 'package:business_suite_mobile/features/crm_contact_page.dart';
import 'package:business_suite_mobile/features/crm_customer_page.dart';
import 'package:business_suite_mobile/features/crm_task_page.dart';
import 'package:business_suite_mobile/features/crm_deal_page.dart';
import 'package:business_suite_mobile/features/crm_quotation_page.dart';
import 'package:business_suite_mobile/features/crm_pipeline_page.dart';
import 'package:business_suite_mobile/features/inventory_purchase_order_form.dart';
import 'package:business_suite_mobile/features/gst_invoice_page.dart';
import 'package:business_suite_mobile/features/gst_collections_page.dart';
import 'package:business_suite_mobile/features/inventory_drafts_page.dart';
import 'package:business_suite_mobile/features/inventory_stock_movement_page.dart';
import 'package:business_suite_mobile/features/my_attendance_page.dart';
import 'package:business_suite_mobile/features/my_leave_page.dart';
import 'package:business_suite_mobile/features/notes_page.dart';
import 'package:business_suite_mobile/features/payment_requests_page.dart';
import 'package:business_suite_mobile/features/sales_order_page.dart';
import 'package:business_suite_mobile/features/sales_order_drafts_page.dart';
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

  testWidgets('Android reopens outstanding collections offline', (
    tester,
  ) async {
    final scope = 'collections-${DateTime.now().microsecondsSinceEpoch}';
    const headers = {'X-Suite-Branch': '4'};
    final outstanding = <String, dynamic>{
      'id': 17,
      'invoice_number': 'GST-17',
      'document_status': 'issued',
      'currency': 'INR',
      'balance_amount': 240,
      'collection_hold': true,
      'branch_id': 4,
    };
    var requests = 0;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests++;
          expectSync(request.headers['X-Suite-Branch'], '4');
          return switch (request.path) {
            GstCollectionsPage.endpoint => response({
              'can_record': true,
              'items': [
                outstanding,
                {
                  ...outstanding,
                  'id': 18,
                  'invoice_number': 'GST-18',
                  'balance_amount': 0,
                },
                {
                  ...outstanding,
                  'id': 19,
                  'invoice_number': 'GST-19',
                  'document_status': 'draft',
                },
              ],
            }),
            '/srm/invoices/17' => response(outstanding),
            '/srm/business/invoices/17' => response({
              'invoice_number': 'GST-17',
              'currency': 'INR',
              'deliveries': [
                {
                  'status': 'failed',
                  'request_id': 'send-17',
                  'error': 'Mailbox unavailable',
                },
              ],
              'history': [
                {
                  'from_status': 'draft',
                  'to_status': 'approved',
                  'notes': 'Approved by finance',
                },
              ],
              'payments': [
                {
                  'receipt_id': 43,
                  'amount': 40,
                  'allocated_at': '2026-11-28T10:00:00Z',
                },
                {
                  'receipt_id': 42,
                  'amount': 10,
                  'reversed_at': '2026-11-27T10:00:00Z',
                },
              ],
            }),
            '/srm/business/invoices/17/payments' => (() {
              expectSync(request.method, 'POST');
              expectSync(request.data['amount'], '40');
              outstanding['balance_amount'] = 200;
              return response({'receipt_id': 43, 'invoice': outstanding}, 201);
            })(),
            '/srm/collections/17/control' => (() {
              expectSync(request.method, 'PUT');
              final paused = request.data['hold'] as bool;
              final reason = paused ? 'Customer dispute' : 'Review finished';
              expectSync(request.data, {
                'hold': paused,
                'reason': reason,
                'resume_at': null,
              });
              outstanding['collection_hold'] = paused;
              outstanding['collection_hold_reason'] = reason;
              return response(outstanding);
            })(),
            _ => throw StateError('Unexpected request ${request.path}'),
          };
        }),
    );
    Future<void> open({required bool offline}) async {
      await tester.pumpWidget(
        MaterialApp(
          home: GstCollectionsPage(
            api: api,
            scopeHeaders: headers,
            cacheScope: scope,
            offline: offline,
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    await open(offline: false);
    expect(find.text('GST-17'), findsOneWidget);
    expect(find.text('GST-18'), findsNothing);
    await tester.tap(find.byTooltip('Record payment for GST-17'));
    await tester.pumpAndSettle();
    final submit = find.widgetWithText(FilledButton, 'Record received payment');
    final readyBy = DateTime.now().add(const Duration(seconds: 10));
    while (tester.widget<FilledButton>(submit).onPressed == null &&
        DateTime.now().isBefore(readyBy)) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    expect(tester.widget<FilledButton>(submit).onPressed, isNotNull);
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Received amount'),
      '40',
    );
    await tester.ensureVisible(submit);
    await tester.tap(submit);
    final updatedBalance = find.textContaining('INR 200');
    final deadline = DateTime.now().add(const Duration(seconds: 10));
    while (updatedBalance.evaluate().isEmpty &&
        DateTime.now().isBefore(deadline)) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    expect(
      updatedBalance,
      findsOneWidget,
      reason: tester
          .widgetList<Text>(find.byType(Text))
          .map((text) => text.data)
          .join(' | '),
    );
    await tester.pumpAndSettle();
    for (final (action, reason) in [
      ('Resume', 'Review finished'),
      ('Pause', 'Customer dispute'),
    ]) {
      await tester.tap(find.byTooltip('$action collections for GST-17'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Reason'),
        reason,
      );
      await tester.tap(find.widgetWithText(FilledButton, action));
      await tester.pumpAndSettle();
    }
    expect(find.textContaining('Customer dispute'), findsOneWidget);
    await tester.tap(find.text('Outstanding only'));
    await tester.pumpAndSettle();
    expect(find.text('GST-18'), findsOneWidget);
    expect(find.text('GST-19'), findsNothing);
    await tester.enterText(find.byType(TextField), 'GST-17');
    await tester.pumpAndSettle();
    expect(find.text('GST-18'), findsNothing);
    await tester.tap(find.widgetWithText(ListTile, 'GST-17'));
    await tester.pumpAndSettle();
    expect(find.byType(GstInvoicePage), findsOneWidget);
    await tester.tap(find.text('Invoice history'));
    await tester.pumpAndSettle();
    expect(find.text('Receipt #43'), findsOneWidget);
    expect(find.textContaining('Reversed'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.textContaining('Mailbox unavailable'),
      180,
    );
    expect(find.textContaining('Reference send-17'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.textContaining('Approved by finance'),
      180,
    );
    expect(find.text('draft → approved'), findsOneWidget);
    await flushCrmDetailWrite(
      '$scope:/srm/business/invoices/17:4:payment-history',
    );
    await flushCrmDetailWrite('$scope:${GstCollectionsPage.endpoint}:4');
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await open(offline: true);
    expect(find.text('Saved collections'), findsOneWidget);
    expect(find.byTooltip('Record payment for GST-17'), findsNothing);
    expect(find.byTooltip('Resume collections for GST-17'), findsNothing);
    expect(find.textContaining('Collections on hold'), findsOneWidget);
    await tester.tap(find.text('GST-17'));
    await tester.pumpAndSettle();
    expect(find.byType(GstInvoicePage), findsOneWidget);
    expect(find.text('INR 200'), findsOneWidget);
    await tester.tap(find.text('Invoice history'));
    await tester.pumpAndSettle();
    expect(find.text('Saved invoice history'), findsOneWidget);
    expect(find.text('Receipt #42'), findsOneWidget);
    expect(find.textContaining('Reversed'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.textContaining('Mailbox unavailable'),
      180,
    );
    expect(find.textContaining('Reference send-17'), findsOneWidget);
    expect(requests, 9);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Android reads saved payment requests offline without actions', (
    tester,
  ) async {
    final scope = 'payments-${DateTime.now().microsecondsSinceEpoch}';
    var requests = 0;
    var accessRemoved = false;
    final listingFailure = Completer<ResponseBody>();
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests++;
          if (accessRemoved && request.path == '/payment-requests/context') {
            return response({'detail': 'Temporary failure'}, 503);
          }
          if (accessRemoved && request.path == '/payment-requests') {
            return listingFailure.future;
          }
          return switch (request.path) {
            '/srm/business/collection-invoices' => response({
              'items': [
                {
                  'id': 16,
                  'invoice_number': 'GST-16',
                  'document_status': 'issued',
                },
              ],
            }),
            '/payment-requests/context' => response({
              'reference': 'GST-16',
              'currency': 'INR',
              'available_amount': '200',
              'payable': true,
            }),
            '/payment-requests' => response({
              'items': [
                {
                  'id': 2,
                  'request_id': 'request-2',
                  'currency': 'INR',
                  'amount': '100',
                  'status': 'link_ready',
                  'payment_url': 'https://pay.example.test/2',
                  'instructions': 'Use reference 16',
                },
              ],
            }),
            _ => throw StateError('Unexpected request ${request.path}'),
          };
        }),
    );
    Future<void> openDirectory({required bool offline}) async {
      await tester.pumpWidget(
        MaterialApp(
          home: PaymentSourceDirectory(
            api: api,
            scopeHeaders: const {'X-Suite-Branch': '4'},
            cacheScope: scope,
            offline: offline,
          ),
        ),
      );
      await tester.pumpAndSettle();
      if (offline) expect(find.text('Saved payment sources'), findsOneWidget);
      await tester.tap(find.text('GST-16'));
      await tester.pumpAndSettle();
    }

    await openDirectory(offline: false);
    expect(find.text('INR 100'), findsOneWidget);
    expect(find.text('Save payment request'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await openDirectory(offline: true);
    expect(
      find.text('Saved payment requests · Refresh to reconnect'),
      findsOneWidget,
    );
    expect(find.text('INR 100'), findsOneWidget);
    expect(find.textContaining('Use reference 16'), findsNothing);
    expect(find.text('Save payment request'), findsNothing);
    expect(find.text('Copy request text'), findsNothing);
    expect(requests, 3);
    accessRemoved = true;
    await tester.tap(find.byTooltip('Refresh payment requests'));
    final savedAmount = find.text('INR 100');
    final deadline = DateTime.now().add(const Duration(seconds: 5));
    do {
      await tester.pump(const Duration(milliseconds: 100));
    } while (savedAmount.evaluate().isEmpty &&
        DateTime.now().isBefore(deadline));
    expect(savedAmount, findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    expect(find.text('Save payment request'), findsNothing);
    listingFailure.complete(
      response({'detail': 'Payment access removed'}, 403),
    );
    await tester.pumpAndSettle();
    expect(find.text('Payment access removed'), findsOneWidget);
    expect(find.text('INR 100'), findsNothing);
    expect(requests, 5);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await openDirectory(offline: true);
    expect(
      find.text('No payment information saved on this device.'),
      findsOneWidget,
    );
    expect(find.text('INR 100'), findsNothing);
    expect(requests, 5);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Android saves a milestone invoice when the connection drops', (
    tester,
  ) async {
    final scope = 'milestone-invoice-${DateTime.now().microsecondsSinceEpoch}';
    var draftCreated = false;
    var requests = 0;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests++;
          if (draftCreated) {
            throw DioException(
              requestOptions: request,
              type: DioExceptionType.connectionError,
            );
          }
          if (request.path == '/srm/billing-plans/91') {
            return response({
              'name': 'Delivery billing',
              'milestones': [
                {
                  'id': 92,
                  'name': 'Delivery',
                  'status': 'approved',
                  'amount': 50,
                },
              ],
            });
          }
          expectSync(
            request.path,
            '/srm/invoices/draft-from-billing-milestone/92',
          );
          expectSync(request.method, 'POST');
          draftCreated = true;
          return response({
            'id': 93,
            'invoice_number': 'GST-093',
            'status': 'draft',
            'lines': [
              {'description': 'Saved delivery line'},
            ],
          }, 201);
        }),
    );
    await api.acceptTokens({'access_token': 'qa', 'refresh_token': 'qa'});
    Widget app({required bool offline}) => MaterialApp(
      home: SalesBillingPlanPage(
        api: api,
        summary: const {'id': 91},
        scopeHeaders: const {},
        cacheScope: scope,
        offline: offline,
        canEdit: false,
        canCreateInvoice: true,
      ),
    );
    await tester.pumpWidget(app(offline: false));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Actions for Delivery'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Generate invoice draft'));
    await tester.pumpAndSettle();
    expect(find.text('Saved delivery line'), findsOneWidget);
    final afterDraft = requests;
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await tester.pumpWidget(app(offline: true));
    await tester.pumpAndSettle();
    expect(find.text('invoiced · 50'), findsOneWidget);
    await tester.tap(find.text('GST-093'));
    await tester.pumpAndSettle();
    expect(find.text('Saved delivery line'), findsOneWidget);
    expect(requests, afterDraft);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Android reopens a new order invoice offline before viewing it', (
    tester,
  ) async {
    final scope = 'order-invoice-${DateTime.now().microsecondsSinceEpoch}';
    var requests = 0;
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests++;
          return switch ((request.method, request.path)) {
            ('GET', '/srm/sales-orders/84') => response({
              'id': 84,
              'order_number': 'SO-084',
              'status': 'confirmed',
            }),
            ('POST', '/srm/invoices/draft-from-sales-order/84') => response({
              'id': 85,
              'invoice_number': 'GST-085',
              'status': 'draft',
              'lines': [
                {'description': 'Saved consulting line', 'quantity': 1},
              ],
            }, 201),
            _ => throw StateError('Unexpected request ${request.path}'),
          };
        }),
    );
    await api.acceptTokens({'access_token': 'qa', 'refresh_token': 'qa'});
    Widget app({required bool offline}) => MaterialApp(
      home: SalesOrderPage(
        api: api,
        summary: const {'id': 84},
        cacheScope: scope,
        offline: offline,
        invoiceBuilder: (_) => const SizedBox.shrink(),
      ),
    );
    await tester.pumpWidget(app(offline: false));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Create invoice draft'));
    await tester.pumpAndSettle();
    expect(find.text('Open invoice'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await tester.pumpWidget(app(offline: true));
    await tester.pumpAndSettle();
    await tester.tap(find.text('GST-085'));
    await tester.pumpAndSettle();
    expect(find.text('Saved consulting line'), findsOneWidget);
    expect(requests, 2);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Android opens shared billing plans and saves details offline', (
    tester,
  ) async {
    const base = 'https://example.test/api/v1';
    final id = DateTime.now().microsecondsSinceEpoch;
    var status = 'draft';
    var detailReads = 0;
    var eligibilityReads = 0;
    num milestoneAmount = 600;
    var milestoneStatus = 'approved';
    String? milestoneDue = '2026-12-15';
    const invoice = {
      'id': 61,
      'invoice_number': 'MS-061',
      'status': 'draft',
      'currency': 'INR',
      'total_amount': 725.5,
    };
    Json plan() => {
      'id': 32,
      'name': 'Support billing',
      'status': status,
      'total_amount': 1200,
      'currency': 'INR',
    };
    final api = ApiClient(
      baseUrl: base,
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          switch (request.path) {
            case '/access/me':
              return response({
                'companyId': 7,
                'grants': {
                  'srm': {'enabled': true},
                },
              });
            case '/access/launcher-preferences':
              return response({'favorites': []});
            case '/notifications/unread-count':
              return response({'unread': 0});
            case '/srm/sales-orders':
              return response([
                {'id': 41, 'order_number': 'SO-041'},
              ]);
            case '/srm/sales-orders/41':
              return response({
                'id': 41,
                'order_number': 'SO-041',
                'billing_plan': plan(),
                'contract': {'id': 42, 'contract_number': 'CT-042'},
                'pms_project': {'id': 43, 'name': 'Support rollout'},
                'invoices': [if (milestoneStatus == 'invoiced') invoice],
              });
            case '/srm/contracts/42':
              return response({
                'id': 42,
                'contract_number': 'CT-042',
                'title': 'Support agreement',
                'status': 'active',
              });
            case '/project-management/projects/43':
              return response({
                'name': 'Support rollout',
                'progress_percent': 65,
              });
            case '/srm/engagements':
              return response([
                {'id': 40, 'name': 'Support delivery'},
              ]);
            case '/srm/engagements/40':
              return response({
                'id': 40,
                'name': 'Support delivery',
                'billing_plan': plan(),
              });
            case '/srm/billing-plans':
              return response([plan()]);
            case '/srm/billing-plans/32':
              detailReads++;
              return response({
                ...plan(),
                'milestones': [
                  {
                    'id': 45,
                    'name': 'First delivery',
                    'amount': milestoneAmount,
                    'due_date': milestoneDue,
                    'status': milestoneStatus,
                    if (milestoneStatus == 'invoiced') 'invoice_draft_id': 72,
                  },
                ],
                'invoices': [if (milestoneStatus == 'invoiced') invoice],
              });
            case '/srm/billing-plans/32/activate':
              expectSync(request.method, 'POST');
              status = 'active';
              return response(plan());
            case '/srm/billing-milestones/45':
              expectSync(request.method, 'PATCH');
              expectSync(request.data, {
                'amount': '725.50',
                'due_date': null,
                'reason': 'Updated delivery scope',
                'expected_amount': '600',
                'expected_due_date': '2026-12-15',
              });
              milestoneAmount = 725.5;
              milestoneStatus = 'pending';
              milestoneDue = null;
              return response({'id': 45});
            case '/srm/billing-milestones/45/approve':
              expectSync(request.method, 'POST');
              expectSync(milestoneStatus, 'pending');
              milestoneStatus = 'approved';
              return response({'id': 45});
            case '/srm/invoices/draft-from-billing-milestone/45':
              expectSync(request.method, 'POST');
              expectSync(milestoneStatus, 'approved');
              milestoneStatus = 'invoiced';
              return response(invoice, 201);
            case '/srm/invoices/61':
              return response(invoice);
            case '/srm/billing-plans/32/eligibility':
              eligibilityReads++;
              expectSync(request.method, 'GET');
              final today = DateTime.now().toIso8601String().split('T').first;
              expectSync(request.queryParameters, {
                'date_from': today,
                'date_to': today,
              });
              return response({
                'milestones': [
                  {
                    'name': 'Eligible delivery',
                    'amount': 600,
                    'due_date': today,
                  },
                ],
              });
            default:
              throw StateError('Unexpected request ${request.path}');
          }
        }),
    );
    await api.acceptTokens({'access_token': 'qa', 'refresh_token': 'qa'});
    final controller = AppController(api, suiteLogin: true)
      ..loading = false
      ..user = SessionUser.fromJson({
        'id': id,
        'email': 'qa@example.test',
        'role': {
          'permissions': [
            {'name': 'srm_manage'},
            {'name': 'srm_invoice_approve'},
            {'name': 'srm_invoice_create'},
          ],
        },
      });
    await tester.pumpWidget(BusinessSuiteApp(controller: controller));
    await tester.pumpAndSettle();
    Future<void> openPlan({bool fromEngagement = false}) async {
      for (final target in [
        find.text('Sales & POS'),
        find.byTooltip('Engagements'),
        if (fromEngagement) ...[
          find.text('Support delivery'),
          find.text('Open billing plan'),
        ] else ...[
          find.byTooltip('Billing plans'),
          find.text('Support billing'),
        ],
      ]) {
        await tester.ensureVisible(target);
        await tester.tap(target);
        await tester.pumpAndSettle();
      }
    }

    await openPlan();
    expect(find.text('First delivery'), findsOneWidget);
    await tester.tap(find.text('Activate billing plan'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Activate'));
    await tester.pumpAndSettle();
    expect(find.text('Pause billing plan'), findsOneWidget);
    expect(detailReads, 2);
    final checkEligibility = find.text('Check billing eligibility');
    await tester.ensureVisible(checkEligibility);
    await tester.tap(checkEligibility);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Check eligibility'));
    await tester.pumpAndSettle();
    expect(find.text('1 eligible milestone'), findsOneWidget);
    expect(find.text('Eligible delivery'), findsOneWidget);
    expect(eligibilityReads, 1);
    await tester.tap(find.text('Close'));
    await tester.pumpAndSettle();
    final milestoneActions = find.byTooltip('Actions for First delivery');
    Future<void> selectAction(String label) async {
      await tester.ensureVisible(milestoneActions);
      await tester.tap(milestoneActions);
      await tester.pumpAndSettle();
      await tester.tap(find.text(label));
      await tester.pumpAndSettle();
    }

    await selectAction('Amend milestone');
    final fields = find.byType(TextFormField);
    await tester.enterText(fields.first, '725.50');
    await tester.tap(find.byTooltip('Clear due date'));
    await tester.enterText(fields.last, 'Updated delivery scope');
    await tester.tap(find.text('Save amendment'));
    await tester.pumpAndSettle();
    expect(find.text('pending · 725.5'), findsOneWidget);
    await selectAction('Approve milestone');
    expect(find.text('approved · 725.5'), findsOneWidget);
    await selectAction('Generate invoice draft');
    expect(find.byType(GstInvoicePage), findsOneWidget);
    expect(find.text('MS-061'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('invoiced · 725.5'), findsOneWidget);
    expect(milestoneActions, findsNothing);
    await flushCrmDetailWrite('["$base",$id,7]:/srm/billing-plans/32:');
    for (var index = 0; index < 4; index++) {
      await tester.pageBack();
      await tester.pumpAndSettle();
    }
    await openPlan(fromEngagement: true);
    expect(find.text('invoiced · 725.5'), findsOneWidget);
    await flushCrmDetailWrite('["$base",$id,7]:/srm/engagements/40:');
    for (var index = 0; index < 4; index++) {
      await tester.pageBack();
      await tester.pumpAndSettle();
    }
    Future<void> openOrder() async {
      for (final target in [find.text('Sales & POS'), find.text('SO-041')]) {
        await tester.ensureVisible(target);
        await tester.tap(target);
        await tester.pumpAndSettle();
      }
    }

    Future<void> openLinkedRecord(String label) async {
      final link = find.widgetWithText(ListTile, label);
      await tester.ensureVisible(link);
      await tester.tap(link);
      await tester.pumpAndSettle();
    }

    Future<void> checkContractAndProject({required bool offline}) async {
      await openLinkedRecord('Contract');
      expect(find.text('Support agreement'), findsOneWidget);
      if (offline) expect(find.text('Saved contract'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await openLinkedRecord('Project');
      expect(find.text('65%'), findsOneWidget);
      if (offline) expect(find.text('Saved project overview'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
    }

    await openOrder();
    await checkContractAndProject(offline: false);
    await openLinkedRecord('Billing plan');
    expect(find.text('invoiced · 725.5'), findsOneWidget);
    await flushCrmDetailWrite('["$base",$id,7]:/srm/sales-orders/41');
    await flushCrmDetailWrite('["$base",$id,7]:/srm/contracts/42:');
    await flushCrmDetailWrite(
      '["$base",$id,7]:/project-management/projects/43:',
    );
    for (var index = 0; index < 3; index++) {
      await tester.pageBack();
      await tester.pumpAndSettle();
    }
    controller.offline = true;
    await openPlan(fromEngagement: true);
    expect(find.text('Saved billing plan'), findsOneWidget);
    expect(find.text('First delivery'), findsOneWidget);
    expect(find.text('Pause billing plan'), findsNothing);
    expect(checkEligibility, findsNothing);
    expect(milestoneActions, findsNothing);
    expect(find.text('invoiced · 725.5'), findsOneWidget);
    for (var index = 0; index < 4; index++) {
      await tester.pageBack();
      await tester.pumpAndSettle();
    }
    await openOrder();
    await checkContractAndProject(offline: true);
    await openLinkedRecord('MS-061');
    expect(find.byType(GstInvoicePage), findsOneWidget);
    expect(find.text('MS-061'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await openLinkedRecord('Billing plan');
    expect(find.text('Saved billing plan'), findsOneWidget);
    expect(find.text('invoiced · 725.5'), findsOneWidget);
    expect(detailReads, 7);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
    'Android GST retries a saved invoice draft with its original request ID',
    (tester) async {
      const base = 'https://example.test/api/v1';
      final id = DateTime.now().microsecondsSinceEpoch;
      final drafts = SalesOrderDrafts.gstInvoices('["$base",$id,7]');
      const branch = {'X-Suite-Branch': '6'};
      const operation = 'android-gst-draft';
      const payload = {
        'customer_id': 5,
        'lines': [
          {'description': 'Saved GST test item', 'quantity': '2'},
        ],
      };
      await drafts.save(
        operation,
        payload,
        scopeHeaders: branch,
        customerName: 'Android QA customer',
      );
      final attempts = <RequestOptions>[];
      final api = ApiClient(
        baseUrl: base,
        store: MemoryStore(),
        transport: Dio()
          ..httpClientAdapter = FakeAdapter((request) async {
            attempts.add(request);
            expect(request.path, '/srm/invoices/manual');
            expect(request.method, 'POST');
            expect(request.headers['X-Suite-Organization'], '7');
            expect(request.headers['X-Suite-Branch'], '6');
            expect(request.data, {...payload, 'request_id': operation});
            if (attempts.length == 1) {
              throw DioException(
                requestOptions: request,
                type: DioExceptionType.connectionError,
              );
            }
            return response({'id': 24, 'status': 'draft'}, 201);
          }),
      );
      await api.acceptTokens({
        'access_token': 'device-qa',
        'refresh_token': 'device-qa',
      });
      await tester.pumpWidget(
        MaterialApp(
          home: SalesOrderDraftsPage(api: api, drafts: drafts),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('Awaiting sync'), findsOneWidget);
      await tester.tap(find.text('Sync GST drafts').hitTestable());
      await tester.pumpAndSettle();
      expect(attempts, hasLength(1));
      expect((await drafts.entries()).single['operation'], operation);
      await tester.tap(find.text('Sync GST drafts').hitTestable());
      await tester.pumpAndSettle();
      expect(attempts, hasLength(2));
      expect(find.text('No saved GST drafts'), findsOneWidget);
      expect(await drafts.entries(), isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets('Android creates and syncs a purchase draft from saved choices', (
    tester,
  ) async {
    const base = 'https://example.test/api/v1';
    final scope = '["$base",${DateTime.now().microsecondsSinceEpoch},7]';
    const branch = '6';
    final choices = '$scope:purchase-choices:$branch';
    await SuiteReadCache.write('$choices:vendor', [
      {'id': 22, 'name': 'Saved supplier'},
    ]);
    await SuiteReadCache.write('$choices:product', [
      {'id': 3, 'item_name': 'Saved paper', 'sku': 'PAPER-3'},
    ]);
    await SuiteReadCache.write('$choices:warehouses', [
      {'id': 6, 'warehouse_name': 'Saved warehouse'},
    ]);
    final writes = <RequestOptions>[];
    final api = ApiClient(
      baseUrl: base,
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          writes.add(request);
          return writes.length == 1
              ? response({'detail': 'Temporarily unavailable'}, 503)
              : response({'id': 9, 'status': 'draft'}, 201);
        }),
    );
    await api.acceptTokens({'access_token': 'qa', 'refresh_token': 'qa'});
    final navigator = GlobalKey<NavigatorState>();
    await tester.pumpWidget(
      MaterialApp(navigatorKey: navigator, home: const Scaffold()),
    );
    final result = navigator.currentState!.push<Json>(
      MaterialPageRoute(
        builder: (_) => InventoryPurchaseOrderForm(
          api: api,
          scopeHeaders: const {'X-Suite-Branch': branch},
          cacheScope: scope,
          offline: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    Future<void> tap(String label) async {
      final finder = find.text(label).last;
      final deadline = DateTime.now().add(const Duration(seconds: 30));
      while (find.text(label).evaluate().isEmpty &&
          DateTime.now().isBefore(deadline)) {
        await Future<void>.delayed(const Duration(milliseconds: 100));
        await tester.pump();
      }
      expect(find.text(label), findsWidgets);
      await tester.ensureVisible(finder);
      await tester.tap(finder);
      await tester.pumpAndSettle();
    }

    await tap('Choose vendor');
    await tap('Saved supplier');
    await tap('Choose product');
    await tap('Saved paper');
    await tap('Warehouse');
    await tap('Saved warehouse');
    await tap('Save draft offline');
    expect(await result.timeout(const Duration(seconds: 30)), {'local': true});
    expect(writes, isEmpty);
    final drafts = SalesOrderDrafts.purchaseOrders(scope);
    final saved = (await drafts.entries()).single;
    expect(saved['branch'], branch);
    expect(saved['payload']['vendor_id'], 22);
    await drafts.sync(api);
    expect((await drafts.entries()).single['operation'], saved['operation']);
    await drafts.sync(api);
    expect(await drafts.entries(), isEmpty);
    expect(writes, hasLength(2));
    for (final request in writes) {
      expect(
        request.path,
        '/srm/procurement/purchase-orders/drafts/offline-create',
      );
      expect(request.headers['X-Suite-Organization'], '7');
      expect(request.headers['X-Suite-Branch'], branch);
      expect(request.headers['X-Offline-Operation'], saved['operation']);
      expect(request.data, saved['payload']);
    }
  });

  testWidgets('Android pipeline renders saved deals during refresh', (
    tester,
  ) async {
    final scope = 'pipeline-${DateTime.now().microsecondsSinceEpoch}';
    const pipelines = '/crm/pipelines?per_page=100';
    const stages =
        '/crm/pipeline-stages?pipeline_id=2&sort_by=position&sort_order=asc&per_page=100';
    const deals = '/crm/deals?pipeline_id=2&page=1&per_page=25';
    final cached = {
      pipelines: [
        {'id': 2, 'name': 'Saved sales pipeline', 'is_default': true},
      ],
      stages: [
        {'id': 4, 'name': 'Qualified'},
      ],
      deals: [
        {'id': 83, 'name': 'Saved pipeline deal'},
      ],
    };
    for (final entry in cached.entries) {
      await SuiteReadCache.write('$scope:${entry.key}:', [
        {'items': entry.value, 'total': entry.value.length},
      ]);
    }
    final gate = Completer<void>();
    addTearDown(() {
      if (!gate.isCompleted) gate.complete();
    });
    final requests = <String>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests.add(request.path);
          await gate.future;
          return response({
            'items': request.path == deals
                ? [
                    {'id': 83, 'name': 'Refreshed pipeline deal'},
                  ]
                : cached[request.path],
            'total': 1,
          });
        }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CrmPipelinePage(
          api: api,
          scopeHeaders: const {},
          cacheScope: scope,
          offline: false,
          canMove: true,
          dealBuilder: (_, _, _) => const SizedBox.shrink(),
        ),
      ),
    );
    Future<void> waitFor(String label) async {
      final finder = find.text(label);
      final deadline = DateTime.now().add(const Duration(seconds: 30));
      while (finder.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
        await Future<void>.delayed(const Duration(milliseconds: 100));
        await tester.pump();
      }
      expect(finder, findsOneWidget, reason: 'Requested: $requests');
    }

    await waitFor('Saved pipeline deal');
    await waitFor('Qualified');
    expect(requests.toSet(), containsAll(cached.keys));
    expect(find.byTooltip('Move Saved pipeline deal'), findsNothing);
    gate.complete();
    await waitFor('Refreshed pipeline deal');
    expect(find.byTooltip('Move Refreshed pipeline deal'), findsOneWidget);
    await Future.wait(
      cached.keys.map((path) => flushCrmDetailWrite('$scope:$path:')),
    );
    final saved = await SuiteReadCache.read('$scope:$deals:');
    expect(
      (saved?.single['items'] as List).single['name'],
      'Refreshed pipeline deal',
    );
  });

  testWidgets('Android shows a saved CRM contact while refresh is pending', (
    tester,
  ) async {
    const path = '/crm/contacts/33';
    final scope = 'crm-cache-first-${DateTime.now().microsecondsSinceEpoch}';
    await SuiteReadCache.write('$scope:$path:', [
      {'full_name': 'Saved contact from SQLite'},
    ]);
    final responseReady = Completer<void>();
    String? requestedPath;
    String? transportError;
    int? responseStatus;
    addTearDown(() {
      if (!responseReady.isCompleted) responseReady.complete();
    });
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requestedPath = request.path;
          await responseReady.future;
          return response({'id': 33, 'full_name': 'Live contact from API'});
        })
        ..interceptors.add(
          InterceptorsWrapper(
            onError: (error, handler) {
              transportError = '${error.type}: ${error.error}';
              handler.next(error);
            },
          ),
        ),
    )..onResponse = (_, _, status) => responseStatus = status;
    await tester.pumpWidget(
      MaterialApp(
        home: CrmContactPage(
          api: api,
          summary: const {'id': 33, 'full_name': 'List summary'},
          offline: false,
          scopeHeaders: const {},
          cacheScope: scope,
          canEdit: true,
        ),
      ),
    );
    final saved = find.text('Saved contact from SQLite');
    Future<void> waitForContact(Finder finder) async {
      final deadline = DateTime.now().add(const Duration(seconds: 30));
      while ((requestedPath == null || finder.evaluate().isEmpty) &&
          DateTime.now().isBefore(deadline)) {
        await Future<void>.delayed(const Duration(milliseconds: 100));
        await tester.pump();
      }
      expect(
        finder,
        findsOneWidget,
        reason:
            'Request: $requestedPath, HTTP status: $responseStatus. '
            'Transport error: $transportError. '
            'Visible text: ${tester.widgetList<Text>(find.byType(Text)).map((widget) => widget.data).join(', ')}',
      );
    }

    await waitForContact(saved);
    expect(requestedPath, path);
    expect(find.text('Edit contact'), findsNothing);
    responseReady.complete();
    await waitForContact(find.text('Live contact from API'));
    expect(find.text('Edit contact'), findsOneWidget);
  });

  testWidgets('Android saves and syncs a CRM task status from offline', (
    tester,
  ) async {
    const base = 'https://example.test/api/v1';
    const taskPath = '/project-management/tasks/21';
    const stamp = '2026-11-27T09:00:00Z';
    final scope = '["$base",${DateTime.now().microsecondsSinceEpoch},7]';
    final queue = CrmOfflineEdits.withTaskSnapshots(scope);
    final requests = <RequestOptions>[];
    var connected = false;
    var status = 'To Do';
    final api = ApiClient(
      baseUrl: base,
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests.add(request);
          expect(connected, isTrue);
          expect(request.path, taskPath);
          if (request.method == 'PATCH') status = 'Done';
          return response({
            'id': 21,
            'title': 'CRM follow-up',
            'status': status,
            'updated_at': stamp,
          });
        }),
    );
    await api.acceptTokens({
      'access_token': 'device-qa',
      'refresh_token': 'device-qa',
    });
    await SuiteReadCache.write('$scope:$taskPath:3', [
      {
        'id': 21,
        'title': 'CRM follow-up',
        'status': 'To Do',
        'updated_at': stamp,
      },
    ]);
    final listScope = '$scope:/project-management/tasks';
    await SuiteReadCache.writePage(listScope, 2, [
      {
        'id': 21,
        'title': 'CRM follow-up',
        'status': 'To Do',
        'updated_at': stamp,
      },
    ]);
    Future<void> open(bool offline) async {
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpWidget(
        MaterialApp(
          home: CrmTaskPage(
            api: api,
            summary: const {'id': 21},
            offline: offline,
            scopeHeaders: const {'X-Suite-Branch': '3'},
            cacheScope: scope,
            canEdit: true,
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    Future<void> waitFor(Finder finder) async {
      final deadline = DateTime.now().add(const Duration(seconds: 15));
      while (finder.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(finder, findsOneWidget);
    }

    await open(true);
    final change = find.text('Change status');
    await waitFor(change);
    await tester.tap(change);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Done'));
    await waitFor(find.text('Waiting to sync'));
    final receipt = (await queue.pendingTask(21))?['operation'];
    expect(receipt, isNotNull);
    expect(requests, isEmpty);

    await open(true);
    await waitFor(find.text('Saved status Done'));
    expect(requests, isEmpty);

    connected = true;
    await queue.sync(api);
    final sent = requests.singleWhere((request) => request.method == 'PATCH');
    expect(sent.headers['X-Offline-Operation'], receipt);
    expect(sent.headers['X-Suite-Branch'], '3');
    expect(sent.headers['X-Suite-Organization'], '7');
    expect(sent.data, {'status': 'Done', 'expected_updated_at': stamp});
    expect(await queue.pendingTask(21), isNull);
    expect(
      (await SuiteReadCache.readPages(listScope))?.single['status'],
      'Done',
    );
    expect(
      (await SuiteReadCache.read('$scope:$taskPath:3'))?.single['status'],
      'Done',
    );
    await waitFor(find.text('Done'));
    expect(find.text('Waiting to sync'), findsNothing);
    expect(requests, hasLength(1));
  });

  final customerConflict = ValueVariant<bool>({false, true});
  testWidgets('Android retains CRM contact, deal, and customer details offline', (
    tester,
  ) async {
    final scope =
        '["https://example.test/api/v1",${DateTime.now().microsecondsSinceEpoch},7]';
    var connected = true;
    final conflict = customerConflict.currentValue!;
    var customerName = 'Cached customer';
    var version = 'customer-v1';
    String? operationId;
    var editAttempts = 0;
    Map<String, dynamic>? receipt;
    final requests = <String>[];
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..httpClientAdapter = FakeAdapter((request) async {
          requests.add(request.path);
          if (!connected) throw StateError('Offline request ${request.path}');
          if (request.method == 'PATCH') {
            expect(request.path, '/master-data/companies/7');
            expect(request.headers['X-Suite-Branch'], '3');
            expect(request.headers['X-Suite-Organization'], '7');
            expect(request.queryParameters['source'], 'crm');
            expect(request.data, {
              'name': 'Offline customer edit',
              'version': 'customer-v1',
            });
            final id = request.headers['X-Offline-Operation'];
            expect(
              id,
              isA<String>().having(
                (value) => value.isNotEmpty,
                'nonempty',
                true,
              ),
            );
            operationId ??= id as String;
            expect(id, operationId);
            editAttempts++;
            if (receipt != null) return response(receipt!);
            if (version != 'customer-v1') {
              return response({
                'detail': 'Customer changed on the server',
              }, 409);
            }
            customerName = 'Offline customer edit';
            version = 'customer-v2';
            receipt = {'id': 7, 'name': customerName, 'version': version};
            return response({'detail': 'Response lost after saving'}, 503);
          }
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
              'id': 7,
              'name': customerName,
              'version': version,
              'canEdit': true,
              'contacts': [
                {'name': 'Customer representative'},
              ],
            }),
            _ => throw StateError('Unexpected request ${request.path}'),
          };
        }),
    );
    await api.acceptTokens({'access_token': 'qa', 'refresh_token': 'qa'});

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
          scopeHeaders: const {'X-Suite-Branch': '3'},
        ),
      );
      expect(find.text('Customer representative'), findsOneWidget);
    }
    expect(requests, [
      '/crm/contacts/4',
      '/crm/deal-workspace/9/record',
      '/master-data/companies/7',
    ]);
    await tester.tap(find.text('Edit customer').hitTestable());
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Customer name'),
      'Offline customer edit',
    );
    final save = find.text('Save edit offline');
    await tester.ensureVisible(save);
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(find.text('Customer edit saved · awaiting sync'), findsOneWidget);
    expect(customerName, 'Cached customer');
    expect(requests, hasLength(3));
    if (conflict) {
      customerName = 'Customer edited in web';
      version = 'customer-web-v2';
    }
    connected = true;
    await tester.tap(find.text('Sync now').hitTestable());
    await tester.pumpAndSettle();
    if (!conflict) {
      expect(find.text('Customer edit saved · awaiting sync'), findsOneWidget);
      expect(customerName, 'Offline customer edit');
      customerName = 'Customer edited in web after sync';
      version = 'customer-web-v3';
      await tester.tap(find.text('Sync now').hitTestable());
      await tester.pumpAndSettle();
    }
    expect(editAttempts, conflict ? 1 : 2);
    expect(
      customerName,
      conflict ? 'Customer edited in web' : 'Customer edited in web after sync',
    );
    expect(find.text(customerName), findsOneWidget);
    if (conflict) {
      expect(find.text('Saved customer edit needs review'), findsOneWidget);
      expect(
        (await CrmOfflineEdits(scope).pendingCustomer(7))?['body']['name'],
        'Offline customer edit',
      );
      await tester.tap(find.text('Discard').hitTestable());
      await tester.pumpAndSettle();
      expect(find.text('Customer edited in web'), findsOneWidget);
      expect(find.text('Saved customer edit needs review'), findsNothing);
    }
    expect(find.text('Customer edit saved · awaiting sync'), findsNothing);
    expect(await CrmOfflineEdits(scope).pendingCustomer(7), isNull);
    connected = false;
    await open(
      CrmCustomerPage(
        api: api,
        summary: const {'id': 7},
        offline: true,
        cacheScope: scope,
        scopeHeaders: const {'X-Suite-Branch': '3'},
      ),
    );
    expect(find.text(customerName), findsOneWidget);
  }, variant: customerConflict);

  testWidgets('Android opens and activates a contract from Sales & POS', (
    tester,
  ) async {
    var status = 'draft';
    var engagementStatus = 'active';
    var activations = 0;
    var historyRequests = 0;
    var projectRequests = 0;
    var handoffs = 0;
    final transportErrors = <String>[];
    Json engagement() => {
      'id': 22,
      'name': 'Site deployment',
      'engagement_number': 'ENG-022',
      if (handoffs > 0) 'pms_project_id': 47,
      'customer_id': 18,
      'status': engagementStatus,
      'billing_type': 'fixed_fee',
    };
    Json contract() => {
      'id': 4,
      'title': 'Support renewal',
      'contract_number': 'CTR-004',
      'status': status,
      'terms': 'Annual maintenance',
      'customer_id': 18,
      'sales_order': {'id': 9, 'order_number': 'SO-009'},
      'engagement': engagement(),
      'invoices': [
        {'id': 12, 'invoice_number': 'INV-012'},
      ],
    };
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: MemoryStore(),
      transport: Dio()
        ..interceptors.add(
          InterceptorsWrapper(
            onError: (error, handler) {
              transportErrors.add(
                '${error.requestOptions.uri}: ${error.error}',
              );
              handler.next(error);
            },
          ),
        )
        ..httpClientAdapter = FakeAdapter((request) async {
          if (request.path == '/srm/engagements/22/timeline') {
            historyRequests++;
          }
          if (request.path == '/project-management/projects/47') {
            projectRequests++;
          }
          if (request.path == '/srm/engagements/22/create-pms-project') {
            expectSync(request.method, 'POST');
            handoffs++;
            return response({
              'project': {'id': 47},
            });
          }
          if (request.path == '/srm/engagements/22/lifecycle/close') {
            expectSync(request.method, 'POST');
            expectSync(request.data, {'reason': 'Work accepted'});
            engagementStatus = 'closed';
            return response(engagement());
          }
          if (request.path == '/srm/contracts/4/activate') {
            expectSync(request.method, 'POST');
            activations++;
            status = 'active';
            return response(contract());
          }
          if (request.path == '/master-data/companies/18') {
            expectSync(request.queryParameters['source'], 'srm');
          }
          return switch (request.path) {
            '/access/me' => response({
              'companyId': 7,
              'grants': {
                'srm': {
                  'enabled': true,
                  'actions': ['view', 'edit'],
                },
              },
            }),
            '/notifications/unread-count' => response({'unread': 0}),
            '/access/launcher-preferences' => response({
              'favorites': ['srm'],
            }),
            '/srm/sales-orders' => response({'items': []}),
            '/srm/contracts' => response([contract()]),
            '/srm/contracts/4' => response(contract()),
            '/srm/engagements' => response([engagement()]),
            '/srm/engagements/22' => response(engagement()),
            '/project-management/projects/47' => response({
              'id': 47,
              'name': 'Delivery rollout',
              'project_key': 'DEPLOY',
              'progress_percent': 65,
            }),
            '/srm/engagements/22/timeline' => response({
              'audit': [
                {
                  'entity_type': 'sales_order',
                  'action': 'close',
                  'after_json': {'reason': 'Order-only event'},
                },
                {
                  'entity_type': 'engagement',
                  'action': 'close',
                  'actor_user_id': 7,
                  'after_json': {'reason': 'Work accepted'},
                },
              ],
            }),
            '/master-data/companies/18' => response({
              'id': 18,
              'name': 'Shared contract customer',
              'version': 'customer-v1',
              'canEdit': true,
              'industry': 'Property services',
            }),
            '/srm/sales-orders/9' => response({
              'order_number': 'SO-009',
              'terms': 'Linked order terms',
              'engagement': engagement(),
            }),
            '/srm/invoices/12' => response({
              'invoice_number': 'INV-012',
              'lines': [
                {'description': 'Linked invoice service'},
              ],
            }),
            _ => throw StateError('Unexpected request ${request.path}'),
          };
        }),
    );
    await api.acceptTokens({'access_token': 'qa', 'refresh_token': 'qa'});
    final controller = AppController(api, suiteLogin: true)
      ..loading = false
      ..user = SessionUser.fromJson({
        'id': DateTime.now().microsecondsSinceEpoch,
        'email': 'qa@example.test',
        'role': {
          'permissions': [
            {'name': 'srm_manage'},
          ],
        },
      });
    await tester.pumpWidget(BusinessSuiteApp(controller: controller));
    await tester.pumpAndSettle();
    for (final target in [
      find.text('Favorites (1)'),
      find.text('Sales & POS'),
      find.byTooltip('Contracts'),
      find.text('Support renewal'),
    ]) {
      final deadline = DateTime.now().add(const Duration(seconds: 15));
      while (target.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      await tester.ensureVisible(target);
      await tester.tap(target);
      await tester.pumpAndSettle();
    }
    expect(find.text('Annual maintenance', findRichText: true), findsOneWidget);
    await tester.tap(find.text('Activate contract'));
    await tester.pumpAndSettle();
    expect(activations, 1);
    expect(find.text('active', findRichText: true), findsOneWidget);
    expect(find.text('Activate contract'), findsNothing);
    for (final (link, detail) in const [
      ('Open customer', 'Shared contract customer'),
      ('SO-009', 'Linked order terms'),
      ('ENG-022', 'Site deployment'),
      ('INV-012', 'Linked invoice service'),
    ]) {
      final tile = find.widgetWithText(ListTile, link);
      await tester.scrollUntilVisible(
        tile,
        200,
        scrollable: find
            .descendant(
              of: find.byType(ListView),
              matching: find.byType(Scrollable),
            )
            .first,
      );
      await tester.tap(tile);
      await tester.pumpAndSettle();
      final expected = find.text(detail, findRichText: true);
      final deadline = DateTime.now().add(const Duration(seconds: 10));
      while (expected.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(
        expected,
        findsOneWidget,
        reason:
            '$transportErrors | ${tester.widgetList<Text>(find.byType(Text)).map((value) => value.data).join(' | ')}',
      );
      expect(find.text('Edit customer'), findsNothing);
      if (link == 'SO-009') {
        final engagementLink = find.text('Engagement');
        await tester.scrollUntilVisible(engagementLink, 200);
        await tester.tap(engagementLink);
        await tester.pumpAndSettle();
        expect(find.text('Site deployment'), findsOneWidget);
        await tester.pageBack();
        await tester.pumpAndSettle();
      }
      await tester.pageBack();
      await tester.pumpAndSettle();
    }
    final live = tester.widget<SalesContractPage>(
      find.byType(SalesContractPage),
    );
    await flushCrmDetailWrite(
      "${live.cacheScope}:/srm/contracts/4:${live.scopeHeaders['X-Suite-Branch'] ?? ''}",
    );
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('CTR-004 · active'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Engagements'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Site deployment'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Create delivery project'), 200);
    await tester.tap(find.text('Create delivery project'));
    await tester.pumpAndSettle();
    expect(find.text('Delivery rollout'), findsOneWidget);
    expect(find.text('65%'), findsOneWidget);
    expect(handoffs, 1);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Open customer'), 200);
    await tester.tap(find.text('Open customer'));
    await tester.pumpAndSettle();
    expect(find.text('Shared contract customer'), findsOneWidget);
    expect(find.text('Edit customer'), findsNothing);
    await tester.pageBack();
    await tester.pumpAndSettle();
    final close = find.text('Close engagement');
    await tester.scrollUntilVisible(close, 200);
    await tester.tap(close);
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Work accepted');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm'));
    await tester.pumpAndSettle();
    expect(engagementStatus, 'closed', reason: '$transportErrors');
    await tester.scrollUntilVisible(find.text('Reopen engagement'), 200);
    await tester.ensureVisible(find.text('Lifecycle history'));
    await tester.tap(find.text('Lifecycle history'));
    await tester.pumpAndSettle();
    expect(find.text('Engagement closed'), findsOneWidget);
    expect(find.textContaining('Work accepted'), findsOneWidget);
    expect(find.textContaining('Order-only event'), findsNothing);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('ENG-022 · closed'), findsOneWidget);
    await tester.pumpWidget(
      MaterialApp(
        home: SalesContractPage(
          api: api,
          summary: const {'id': 4},
          scopeHeaders: live.scopeHeaders,
          cacheScope: live.cacheScope,
          offline: true,
          canEdit: true,
          onChanged: () {},
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Saved contract'), findsOneWidget);
    expect(find.text('Annual maintenance', findRichText: true), findsOneWidget);
    expect(find.text('Activate contract'), findsNothing);
    final engagementTile = find.widgetWithText(ListTile, 'ENG-022');
    await tester.scrollUntilVisible(
      engagementTile,
      200,
      scrollable: find
          .descendant(
            of: find.byType(ListView),
            matching: find.byType(Scrollable),
          )
          .first,
    );
    await tester.tap(engagementTile);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Lifecycle history'), 200);
    await tester.tap(find.text('Lifecycle history'));
    await tester.pumpAndSettle();
    expect(find.text('Saved lifecycle history'), findsOneWidget);
    expect(find.textContaining('Work accepted'), findsOneWidget);
    expect(historyRequests, 1);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Open delivery project'));
    await tester.tap(find.text('Open delivery project'));
    await tester.pumpAndSettle();
    expect(find.text('Saved project overview'), findsOneWidget);
    expect(find.text('Delivery rollout'), findsOneWidget);
    expect(projectRequests, 1);
  });

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
          '/branches/context' => response({
            'branches': [
              {'id': 21, 'name': 'North', 'is_active': true},
              {'id': 22, 'name': 'South', 'is_active': true},
            ],
          }),
          '/srm/inventory/reports/stock-summary' => response({
            'items': [
              {
                'id': 4,
                'item_name': switch (request.headers['X-Suite-Branch']) {
                  '21' => 'North stock',
                  '22' => 'South stock',
                  _ => 'Sample inventory item',
                },
              },
            ],
          }),
          '/srm/sales-orders' ||
          '/srm/inventory/items' => response({
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
      for (final (branch, other) in [('North', 'South'), ('South', 'North')]) {
        await tap(find.byTooltip('Choose inventory branch'));
        await tap(find.text(branch));
        expect(find.text('$branch stock'), findsOneWidget);
        expect(find.text('$other stock'), findsNothing);
        await tester.pageBack();
        await tester.pumpAndSettle();
      }
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
    await tester.pumpAndSettle();
    final orderActions = find.byTooltip('Sales order actions').hitTestable();
    await waitFor(orderActions);
    final saved = (await drafts.entries()).single;
    expect(saved['payload']['lines'][0]['product_id'], 8);
    expect(submitted, isEmpty);
    await tester.tap(orderActions);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Order drafts'));
    await waitFor(find.text('Awaiting sync'));
    connected = true;
    await tester.tap(find.text('Sync order drafts').hitTestable());
    await waitFor(find.text('No saved order drafts'));
    expect(submitted, hasLength(1));
    expect(submitted.single.headers['X-Offline-Operation'], saved['operation']);
    expect(submitted.single.data, saved['payload']);
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
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
      await waitFor(find.text('Awaiting sync').hitTestable());
      expect(
        find.widgetWithText(ListTile, 'Android field lead').hitTestable(),
        findsOneWidget,
      );
      connected = true;
      await tester.tap(find.text('Sync lead drafts').hitTestable());
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
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
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

  final commercialSearch = ValueVariant<String>({
    'sales',
    'invoice',
    'inventory',
    'crm',
    'customer',
    'contact',
    'deal',
    'task',
    'quotation',
  });
  testWidgets('Android keeps business record search results offline', (
    tester,
  ) async {
    final kind = commercialSearch.currentValue!;
    final usesTimestamp = const {
      'sales',
      'invoice',
      'inventory',
    }.contains(kind);
    final crm = const {
      'crm',
      'customer',
      'contact',
      'deal',
      'task',
      'quotation',
    }.contains(kind);
    final (endpoint, numberField, menu, offlineLabel) = switch (kind) {
      'invoice' => (
        '/srm/invoices',
        'invoice_number',
        'GST Billing',
        'Search saved invoices',
      ),
      'inventory' => (
        '/srm/inventory/items',
        'item_name',
        'Inventory',
        'Search saved products',
      ),
      'crm' => (CrmLeadPage.endpoint, 'first_name', null, 'Search saved leads'),
      'customer' => (
        CrmCustomerPage.endpoint,
        'name',
        'Customers',
        'Search saved customers',
      ),
      'contact' => (
        CrmContactPage.endpoint,
        'full_name',
        'Contacts',
        'Search saved contacts',
      ),
      'deal' => (CrmDealPage.endpoint, 'name', 'Deals', 'Search saved deals'),
      'task' => (
        CrmTaskPage.endpoint,
        'title',
        'CRM tasks',
        'Search saved tasks',
      ),
      'quotation' => (
        CrmQuotationPage.endpoint,
        'quote_number',
        'Quotations',
        'Search saved quotations',
      ),
      _ => ('/srm/sales-orders', 'order_number', null, 'Search saved orders'),
    };
    final id = DateTime.now().microsecondsSinceEpoch;
    var requests = 0;
    final searches = <Object?>[];
    var lostConnection = false;
    var denied = false;
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        switch (request.path) {
          case '/access/me':
            return response({
              'companyId': 7,
              'grants': {
                (crm ? 'crm' : 'srm'): {'enabled': true},
              },
            });
          case '/notifications/unread-count':
            return response({'unread': 0});
          case '/srm/sales-orders' when menu != null:
          case CrmLeadPage.endpoint when crm && menu != null:
          case CrmDealPage.endpoint when kind == 'quotation':
            return response([]);
          case final path when path == endpoint:
            if (denied) return response({'detail': 'Access removed'}, 403);
            final query = kind == 'customer'
                ? (jsonDecode(request.queryParameters['state'] as String)
                      as Json)['search']
                : request.queryParameters['search'];
            if (query case final String term when term.isNotEmpty) {
              searches.add(term);
              if (lostConnection) {
                throw DioException(
                  requestOptions: request,
                  type: DioExceptionType.connectionError,
                );
              }
              return response([
                {
                  'id': 2,
                  numberField: 'ARCHIVED-RECORD',
                  if (kind == 'crm') 'version': 2,
                  if (usesTimestamp) 'updated_at': '2026-11-28T10:00:00Z',
                },
              ]);
            }
            requests++;
            return response([
              {'id': 1, numberField: 'QA-SALE-$requests'},
              if (kind == 'crm')
                {'id': 2, numberField: 'Older lead title', 'version': 1},
              if (usesTimestamp)
                {
                  'id': 2,
                  numberField: 'Older record label',
                  'updated_at': '2026-11-28T09:00:00Z',
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
    await api.acceptTokens({
      'access_token': 'device-qa',
      'refresh_token': 'device-qa',
    });
    final controller = AppController(api, suiteLogin: true)
      ..loading = false
      ..user = SessionUser.fromJson({'id': id, 'email': 'qa@example.test'});
    await tester.pumpWidget(BusinessSuiteApp(controller: controller));
    await tester.pumpAndSettle();
    Future<void> openModule() async {
      final module = find.text(crm ? 'VyaparaCRM' : 'Sales & POS');
      await tester.ensureVisible(module);
      await tester.pumpAndSettle();
      await tester.tap(module);
      await tester.pumpAndSettle();
    }

    await openModule();
    if (kind == 'quotation') {
      await tester.tap(find.byTooltip('Deals'));
      await tester.pumpAndSettle();
    }
    if (menu != null) {
      await tester.tap(find.byTooltip(menu));
      await tester.pumpAndSettle();
    }
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
    await waitForOrder('ARCHIVED-RECORD');
    expect(searches, ['archived']);
    final snapshots = await SuiteReadCache.read(
      '["https://example.test/api/v1",$id,7]:$endpoint',
    );
    expect(
      snapshots?.singleWhere((row) => row['id'] == 1)[numberField],
      'QA-SALE-2',
    );
    lostConnection = true;
    await tester.enterText(search, 'QA-SALE');
    final savedSearch = find.text(offlineLabel);
    final deadline = DateTime.now().add(const Duration(seconds: 15));
    while (savedSearch.evaluate().isEmpty &&
        DateTime.now().isBefore(deadline)) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    expect(savedSearch, findsOneWidget);
    await tester.enterText(search, 'QA-SALE-2');
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.widgetWithText(ListTile, 'QA-SALE-2'), findsOneWidget);
    await tester.enterText(search, 'archived');
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.widgetWithText(ListTile, 'ARCHIVED-RECORD'), findsOneWidget);
    expect(find.widgetWithText(ListTile, 'QA-SALE-2'), findsNothing);
    expect(searches, ['archived', 'QA-SALE']);
    if (kind == 'crm') {
      await tester.pageBack();
      await tester.pumpAndSettle();
      controller.offline = true;
      await openModule();
      await tester.enterText(find.byType(TextField), 'archived');
      await tester.pumpAndSettle();
      expect(find.widgetWithText(ListTile, 'ARCHIVED-RECORD'), findsOneWidget);
      expect(searches, ['archived', 'QA-SALE']);
      expect(requests, 2);
    }
    if (kind == 'customer') {
      denied = true;
      await tester.tap(find.byTooltip('Refresh'));
      await waitForOrder('Access removed');
      await tester.pumpAndSettle();
      final key = '["https://example.test/api/v1",$id,7]:$endpoint';
      final purgeDeadline = DateTime.now().add(const Duration(seconds: 5));
      while (await SuiteReadCache.read('$key:recent-search-results') != null &&
          DateTime.now().isBefore(purgeDeadline)) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(await SuiteReadCache.readPages(key), isNull);
      expect(await SuiteReadCache.read('$key:recent-search-results'), isNull);
      expect(find.text('ARCHIVED-RECORD'), findsNothing);
    }
    await tester.pumpWidget(const SizedBox.shrink());
  }, variant: commercialSearch);

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
    final blockedRefreshes = <String, Completer<void>>{};
    final dio = Dio()
      ..httpClientAdapter = FakeAdapter((request) async {
        requests++;
        expectSync(request.method, 'GET');
        await blockedRefreshes[request.path]?.future;
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
      if (const {
        'QA movement',
        'QA order line',
        'QA invoice line',
      }.contains(expected)) {
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

    await tester.pumpWidget(const SizedBox.shrink());
    await SuiteReadCache.invalidateInventoryItem(scope, 1);
    final productRefresh = blockedRefreshes['/srm/inventory/items/1'] =
        Completer<void>();
    fixtures['/srm/inventory/items/1']!['item_name'] = 'Updated QA stock';
    await tester.pumpWidget(MaterialApp(home: pages[1].$1(false)));
    await findDetail('QA stock');
    expect(requests, 5);
    expect(find.text('Updated QA stock'), findsNothing);
    productRefresh.complete();
    await findDetail('Updated QA stock');

    await tester.pumpWidget(const SizedBox.shrink());
    await SuiteReadCache.invalidate('$scope:/srm/sales-orders/1');
    final orderRefresh = blockedRefreshes['/srm/sales-orders/1'] =
        Completer<void>();
    fixtures['/srm/sales-orders/1']!['terms'] = 'Payment due in 45 days';
    await tester.pumpWidget(MaterialApp(home: pages[2].$1(false)));
    await findDetail('Payment due in 30 days');
    expect(requests, 6);
    expect(find.text('Payment due in 45 days'), findsNothing);
    orderRefresh.complete();
    await findDetail('Payment due in 45 days');

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpWidget(MaterialApp(home: pages[0].$1(false)));
    await findDetail('QA invoice line');
    expect(requests, 6);
    fixtures['/srm/invoices/1']!['lines'] = [
      {'description': 'Updated invoice line', 'quantity': 3},
    ];
    await tester.tap(find.text('Refresh').hitTestable());
    await findDetail('Updated invoice line');
    expect(requests, 7);
  });
}
