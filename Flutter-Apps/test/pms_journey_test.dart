import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/main.dart';
import 'api_client_test.dart' show MemoryStore, FakeAdapter, response;

void main() {
  testWidgets('phone: sign in, create task, update status, and sign out', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final requests = <RequestOptions>[];
    var created = false;
    var status = 'To Do';
    final dio = Dio();
    dio.httpClientAdapter = FakeAdapter((r) async {
      requests.add(r);
      if (r.path == '/auth/login') {
        expect(r.data['module'], 'project_management');
        return response({'access_token': 'access', 'refresh_token': 'refresh'});
      }
      if (r.path == '/auth/me') {
        return response({
          'email': 'member@example.test',
          'role': {'name': 'pms_team_member', 'permissions': []},
        });
      }
      if (r.path.endsWith('/workspaces')) {
        return response([
          {'id': 1, 'name': 'Delivery', 'role': 'Member'},
        ]);
      }
      if (r.path.endsWith('/overview')) {
        return response({
          'role': 'Member',
          'projects': [
            {'id': 2, 'name': 'Mobile', 'project_key': 'APP'},
          ],
          'tasks': created
              ? [
                  {
                    'id': 3,
                    'project_id': 2,
                    'task_key': 'APP-1',
                    'title': 'Ship Flutter',
                    'status': status,
                    'priority': 'Medium',
                  },
                ]
              : [],
        });
      }
      if (r.path.endsWith('/projects/2/tasks')) {
        expect(r.data['title'], 'Ship Flutter');
        expect(r.data['task_key'], 'APP-1');
        created = true;
        return response({'id': 3});
      }
      if (r.path.endsWith('/tasks/3')) {
        if (r.method == 'GET') {
          return response({
            'id': 3,
            'project_id': 2,
            'task_key': 'APP-1',
            'title': 'Ship Flutter',
            'status': status,
            'priority': 'Medium',
          });
        }
        status = r.data['status'] as String;
        return response({'id': 3});
      }
      if (r.path == '/auth/logout') return response({'message': 'Logged out'});
      fail('Unexpected API call: ${r.method} ${r.path}');
    });
    final store = MemoryStore();
    final c = AppController(
      ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: store,
        transport: dio,
      ),
    );
    c.loading = false;
    await tester.pumpWidget(BusinessSuiteApp(controller: c));
    await tester.enterText(
      find.byType(TextFormField).at(0),
      'member@example.test',
    );
    await tester.enterText(find.byType(TextFormField).at(1), 'password');
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('Mobile'), findsOneWidget);
    await tester.tap(find.text('Tasks'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(FloatingActionButton));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).at(0), 'Ship Flutter');
    await tester.enterText(find.byType(TextFormField).at(1), 'app-1');
    await tester.tap(find.widgetWithText(FilledButton, 'Create'));
    await tester.pumpAndSettle();
    expect(find.text('Ship Flutter'), findsOneWidget);
    await tester.tap(find.text('Ship Flutter'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('To Do').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Done').last);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Save status'));
    await tester.pumpAndSettle();
    expect(status, 'Done');
    expect(find.text('APP-1 · Done · Medium'), findsOneWidget);
    await tester.tap(find.byTooltip('Sign out'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
    expect(store.value, isNull);
    expect(
      requests
          .where(
            (r) => r.method == 'POST' && r.path.endsWith('/projects/2/tasks'),
          )
          .length,
      1,
    );
    expect(tester.takeException(), isNull);
  });
}
