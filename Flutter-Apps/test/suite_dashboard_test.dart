import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/features/sales_order_page.dart';
import 'package:business_suite_mobile/main.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets('offline order summary opens without a network request', (
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
            '/srm/industry/records' => response({
              'items': [
                {'title': 'Sample booking'},
              ],
            }),
            '/notifications/' => response({
              'items': [
                {'title': 'Sample update'},
              ],
            }),
            '/power-apps/environments' ||
            '/employees/' ||
            '/crm/leads' ||
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
        'VyaparaCRM': '/crm/leads',
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
          await back();
        }
        await back();
      }
      await tester.tap(find.byTooltip('Notifications'));
      await tester.pumpAndSettle();
      expect(find.text('Sample update'), findsOneWidget);
      await back();
      await tester.tap(find.byTooltip('Settings'));
      await tester.pumpAndSettle();
      await open('Account security');
      expect(
        calls.any((r) => r.path == '/access/settings/options/account'),
        isTrue,
      );
      expect(tester.takeException(), isNull);
    },
  );
}
