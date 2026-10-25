import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/features/workspace_page.dart';

import 'api_client_test.dart' show MemoryStore, FakeAdapter, response;

void main() {
  AppController controller(String role) {
    final dio = Dio();
    dio.httpClientAdapter = FakeAdapter(
      (r) async => response({
        'id': 3,
        'project_id': 2,
        'task_key': 'APP-1',
        'title': 'Ship mobile',
        'status': 'To Do',
        'priority': 'High',
      }),
    );
    final c = AppController(
      ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: dio,
      ),
    );
    c.loading = false;
    c.user = SessionUser.fromJson({
      'email': 'member@example.test',
      'role': null,
    });
    c.selected = Workspace(1, 'Delivery', role);
    c.workspaces = [c.selected!];
    c.overview = Overview.fromJson({
      'role': role,
      'projects': [
        {'id': 2, 'name': 'Mobile launch', 'project_key': 'APP'},
      ],
      'tasks': [
        {
          'id': 3,
          'project_id': 2,
          'task_key': 'APP-1',
          'title': 'Ship mobile',
          'status': 'To Do',
          'priority': 'High',
        },
      ],
    });
    return c;
  }

  test('unknown roles fail closed', () {
    expect(const Workspace(1, 'Team', 'FutureRole').canEdit, false);
    expect(const Workspace(1, 'Team', 'Guest').canManage, false);
    expect(const Workspace(1, 'Team', 'Member').canEdit, true);
  });
  testWidgets('guest can browse tasks but cannot create or save', (
    tester,
  ) async {
    final c = controller('Guest');
    await tester.pumpWidget(MaterialApp(home: WorkspacePage(controller: c)));
    expect(find.byType(FloatingActionButton), findsNothing);
    await tester.tap(find.text('Tasks'));
    await tester.pumpAndSettle();
    expect(find.text('Ship mobile'), findsOneWidget);
    expect(find.byType(FloatingActionButton), findsNothing);
    await tester.tap(find.text('Ship mobile'));
    await tester.pumpAndSettle();
    final save = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Save status'),
    );
    expect(save.onPressed, isNull);
  });
  testWidgets('member can create tasks but not projects', (tester) async {
    await tester.pumpWidget(
      MaterialApp(home: WorkspacePage(controller: controller('Member'))),
    );
    expect(find.byType(FloatingActionButton), findsNothing);
    await tester.tap(find.text('Tasks'));
    await tester.pumpAndSettle();
    expect(find.byType(FloatingActionButton), findsOneWidget);
  });
}
