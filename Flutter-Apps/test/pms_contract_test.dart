import 'package:dio/dio.dart';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/features/contract_form.dart';
import 'package:business_suite_mobile/features/pms_catalog.dart';
import 'package:business_suite_mobile/features/pms_feature_hub.dart';
import 'api_client_test.dart' show MemoryStore, FakeAdapter, response;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'nested form conditions retain scalar schemas at full contract depth',
    () async {
      final catalog = await PmsCatalog.load();
      final body = catalog
          .find('PUT', '/project-management/workspaces/{wid}/forms/{fid}')!
          .body;
      final condition =
          body['properties']['definition']['properties']['fields']['items']['properties']['condition'];
      expect(condition['properties']['field']['type'], 'string');
      expect(
        condition['properties']['operator']['enum'],
        contains('not_empty'),
      );
    },
  );
  testWidgets('untyped object array items expose a native property editor', (
    tester,
  ) async {
    final c = AppController(
      ApiClient(baseUrl: 'https://example.test/api/v1', store: MemoryStore()),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ContractField(
            name: 'action_items',
            schema: const {
              'type': 'array',
              'items': {'type': 'object'},
            },
            value: const [],
            onChanged: (_) {},
            controller: c,
            scope: const {},
          ),
        ),
      ),
    );
    await tester.tap(find.widgetWithText(OutlinedButton, 'Add item'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(OutlinedButton, 'Add property'), findsOneWidget);
  });
  testWidgets('comma-separated task tags submit distinct trimmed names', (
    tester,
  ) async {
    final names = <String>[];
    final dio = Dio();
    dio.httpClientAdapter = FakeAdapter((r) async {
      names.add(r.data['name']);
      return response({'id': names.length, 'name': r.data['name']});
    });
    final c = AppController(
      ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: dio,
      ),
    );
    c.selected = const Workspace(8, 'QA', 'Owner');
    final catalog = (await tester.runAsync(PmsCatalog.load))!;
    await tester.pumpWidget(
      MaterialApp(
        home: PmsOperationPage(
          controller: c,
          catalog: catalog,
          operation: catalog.find(
            'POST',
            '/project-management/tasks/{task_id}/tags',
          )!,
          scope: const {'workspace_id': 8, 'task_id': 40},
        ),
      ),
    );
    await tester.enterText(
      find.byKey(const ValueKey('input-name')),
      ' blue, red, blue ',
    );
    await tester.pumpAndSettle();
    final save = find.widgetWithText(FilledButton, 'Save');
    await tester.ensureVisible(save);
    await tester.pumpAndSettle();
    await tester.tap(save);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();
    expect(names, ['blue', 'red']);
  });
  test(
    'binary contracts accept picked bytes and reject paths empty files and oversized files',
    () {
      const schema = {'type': 'string', 'format': 'binary'};
      expect(
        validateContract(
          schema,
          PickedUpload('qa.txt', Uint8List.fromList([65])),
        ),
        isNull,
      );
      expect(validateContract(schema, '/sdcard/qa.txt'), isNotNull);
      expect(
        validateContract(schema, PickedUpload('qa.txt', Uint8List(0))),
        isNotNull,
      );
      expect(
        validateContract(
          schema,
          PickedUpload('qa.txt', Uint8List(3 * 1024 * 1024 + 1)),
        ),
        isNotNull,
      );
    },
  );
  testWidgets(
    'existing array values can be reordered and edited without recreation',
    (tester) async {
      final c = AppController(
        ApiClient(baseUrl: 'https://example.test/api/v1', store: MemoryStore()),
      );
      var values = <dynamic>['A', 'B'];
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, update) => ContractField(
                name: 'options',
                schema: const {
                  'type': 'array',
                  'items': {'type': 'string'},
                },
                value: values,
                onChanged: (v) => update(() => values = List<dynamic>.from(v)),
                controller: c,
                scope: const {},
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.byTooltip('Move item down').first);
      await tester.pumpAndSettle();
      expect(values, ['B', 'A']);
      await tester.tap(find.widgetWithText(ListTile, 'B'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField), 'B edited');
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Save item'));
      await tester.pumpAndSettle();
      expect(values, ['B edited', 'A']);
    },
  );
  testWidgets('PUT custom-field clearing submits an explicit nullable value', (
    tester,
  ) async {
    var writes = 0;
    final dio = Dio();
    dio.httpClientAdapter = FakeAdapter((r) async {
      writes++;
      expect(r.data, {'value': null});
      return response({'value': null});
    });
    final c = AppController(
      ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: dio,
      ),
    );
    c.selected = const Workspace(8, 'QA', 'Owner');
    final catalog = (await tester.runAsync(PmsCatalog.load))!;
    await tester.pumpWidget(
      MaterialApp(
        home: PmsOperationPage(
          controller: c,
          catalog: catalog,
          operation: catalog.find(
            'PUT',
            '/project-management/tasks/{task_id}/custom-fields/{field_id}',
          )!,
          scope: const {'workspace_id': 8, 'task_id': 40, 'field_id': 3},
          initial: const {'value': 'existing'},
        ),
      ),
    );
    await tester.tap(find.widgetWithText(TextButton, 'Clear value'));
    await tester.pumpAndSettle();
    final save = find.widgetWithText(FilledButton, 'Save');
    await tester.ensureVisible(save);
    await tester.pumpAndSettle();
    await tester.tap(save);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();
    expect(writes, 1);
  });
  test(
    'custom-field contract accepts text number boolean and null without coercion',
    () async {
      final catalog = await PmsCatalog.load();
      final op = catalog.find(
        'PUT',
        '/project-management/tasks/{task_id}/custom-fields/{field_id}',
      )!;
      for (final v in ['Android', 12.5, true, null]) {
        expect(validateContract(op.body, {'value': v}), isNull);
      }
      expect(
        validateContract(op.body, {
          'value': {'unexpected': 'object'},
        }),
        isNotNull,
      );
    },
  );
  testWidgets(
    'PUT edit normalizes null read-model strings to their declared defaults',
    (tester) async {
      final dio = Dio();
      var writes = 0;
      dio.httpClientAdapter = FakeAdapter((r) async {
        writes++;
        expect(r.data['plural_name'], '');
        return response({'id': 7, 'name': 'QA updated'});
      });
      final c = AppController(
        ApiClient(
          baseUrl: 'https://example.test/api/v1',
          store: MemoryStore(),
          transport: dio,
        ),
      );
      c.selected = const Workspace(8, 'QA', 'Owner');
      final catalog = (await tester.runAsync(PmsCatalog.load))!;
      await tester.pumpWidget(
        MaterialApp(
          home: PmsOperationPage(
            controller: c,
            catalog: catalog,
            operation: catalog.find(
              'PUT',
              '/project-management/task-types/{type_id}',
            )!,
            scope: const {'workspace_id': 8, 'type_id': 7},
            initial: const {
              'id': 7,
              'name': 'QA',
              'plural_name': null,
              'description': null,
              'category': 'General',
              'icon': 'task',
              'color': '#2255cc',
              'default_priority': 'Medium',
              'archived': false,
            },
          ),
        ),
      );
      await tester.enterText(
        find.byKey(const ValueKey('input-description')),
        'QA updated',
      );
      await tester.pumpAndSettle();
      final save = find.widgetWithText(FilledButton, 'Save');
      await tester.ensureVisible(save);
      await tester.pumpAndSettle();
      await tester.tap(save);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
      await tester.pumpAndSettle();
      expect(writes, 1);
    },
  );
  test(
    'super-admin reset access does not depend on the selected workspace role',
    () async {
      final catalog = await PmsCatalog.load();
      final c = AppController(
        ApiClient(baseUrl: 'https://example.test/api/v1', store: MemoryStore()),
      );
      final reset = catalog.find(
        'POST',
        '/project-management/admin/workspaces/reset-all',
      )!;
      c.selected = const Workspace(8, 'QA', 'Owner');
      c.user = SessionUser.fromJson({
        'id': 1,
        'email': 'admin@example.test',
        'is_superuser': false,
      });
      expect(reset.allowed(c), false);
      c.user = SessionUser.fromJson({
        'id': 1,
        'email': 'super@example.test',
        'is_superuser': true,
      });
      c.selected = const Workspace(8, 'QA', 'Guest');
      expect(reset.allowed(c), true);
      c.selected = null;
      expect(reset.allowed(c), true);
    },
  );
  testWidgets(
    'editing refreshes stale project values before an unarchive mutation',
    (tester) async {
      var reads = 0, writes = 0;
      final dio = Dio();
      dio.httpClientAdapter = FakeAdapter((r) async {
        if (r.method == 'GET') {
          reads++;
          return response({'id': 22, 'name': 'QA', 'is_archived': true});
        }
        writes++;
        expect(r.data, {'is_archived': false});
        return response({'id': 22, 'name': 'QA', 'is_archived': false});
      });
      final c = AppController(
        ApiClient(
          baseUrl: 'https://example.test/api/v1',
          store: MemoryStore(),
          transport: dio,
        ),
      );
      c.selected = const Workspace(8, 'QA', 'Owner');
      final catalog = (await tester.runAsync(PmsCatalog.load))!;
      await tester.pumpWidget(
        MaterialApp(
          home: PmsOperationPage(
            controller: c,
            catalog: catalog,
            operation: catalog.find(
              'PATCH',
              '/project-management/projects/{project_id}',
            )!,
            scope: const {'workspace_id': 8, 'project_id': 22},
            initial: const {'is_archived': false},
          ),
        ),
      );
      await tester.pumpAndSettle();
      final field = find.byWidgetPredicate(
        (w) => w is ContractField && w.name == 'is_archived',
      );
      final toggle = find.descendant(
        of: field,
        matching: find.byType(SwitchListTile),
      );
      expect(reads, 1);
      expect(tester.widget<SwitchListTile>(toggle).value, true);
      await tester.ensureVisible(toggle);
      await tester.pumpAndSettle();
      await tester.tap(toggle);
      await tester.pumpAndSettle();
      final save = find.widgetWithText(FilledButton, 'Save');
      await tester.ensureVisible(save);
      await tester.pumpAndSettle();
      await tester.tap(save);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
      await tester.pumpAndSettle();
      expect(writes, 1);
    },
  );
  testWidgets(
    'PATCH date clearing retains explicit null instead of omitting the update',
    (tester) async {
      final c = AppController(
        ApiClient(baseUrl: 'https://example.test/api/v1', store: MemoryStore()),
      );
      Map<String, dynamic>? sent;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ContractFields(
              schema: const {
                'type': 'object',
                'properties': {
                  'due_date': {'type': 'string', 'format': 'date'},
                },
              },
              values: const {'due_date': '2026-10-24'},
              preserveNulls: true,
              onChanged: (value) => sent = value,
              controller: c,
              scope: const {},
            ),
          ),
        ),
      );
      await tester.tap(find.byTooltip('Clear date'));
      expect(sent!.containsKey('due_date'), true);
      expect(sent!['due_date'], isNull);
    },
  );
  test(
    'supplied catalog preserves deployed versus undeployed capabilities',
    () async {
      final catalog = await PmsCatalog.load();
      expect(catalog.operations.length, 312);
      expect(
        catalog.find('POST', '/project-management/notes')!.available,
        false,
      );
      expect(
        catalog
            .find('POST', '/project-management/projects/{project_id}/epics')!
            .body['required'],
        containsAll(['name', 'epic_key']),
      );
    },
  );
  test(
    'contract validation rejects incomplete and out-of-range business input',
    () {
      const schema = {
        'type': 'object',
        'required': ['title', 'probability'],
        'properties': {
          'title': {'type': 'string', 'minLength': 1},
          'probability': {'type': 'integer', 'minimum': 1, 'maximum': 5},
        },
      };
      expect(
        validateContract(schema, {'title': 'Risk'}),
        contains('Probability'),
      );
      expect(
        validateContract(schema, {'title': 'Risk', 'probability': 9}),
        contains('at most'),
      );
      expect(
        validateContract(schema, {'title': 'Risk', 'probability': 3}),
        isNull,
      );
    },
  );
  test(
    'monetary decimal strings remain exact and UUID technical fields stay typed',
    () async {
      final catalog = await PmsCatalog.load();
      final schema = catalog
          .find('POST', '/project-management/time-logs')!
          .body;
      expect(schema['properties']['duration_minutes']['type'], 'integer');
      expect(
        validateContract({
          'type': 'number',
          'decimalString': true,
        }, '123456789.123456789'),
        isNull,
      );
    },
  );
  test(
    'record scopes map IDs to the correct child action without losing workspace',
    () async {
      final catalog = await PmsCatalog.load();
      final op = catalog.find(
        'GET',
        '/project-management/projects/{project_id}/sprints',
      )!;
      final scope = recordContext(
        op,
        {'id': 31, 'name': 'Sprint'},
        {'workspace_id': 8, 'project_id': 22},
        catalog,
      );
      expect(scope['sprint_id'], 31);
      expect(scope['workspace_id'], 8);
      expect(scope['project_id'], 22);
    },
  );
  test(
    'guest mutations and non-superuser global recovery fail closed',
    () async {
      final catalog = await PmsCatalog.load();
      final c = AppController(
        ApiClient(baseUrl: 'https://example.test/api/v1', store: MemoryStore()),
      );
      c.selected = const Workspace(8, 'Team', 'Guest');
      expect(
        catalog
            .find('POST', '/project-management/projects/{project_id}/sprints')!
            .allowed(c),
        false,
      );
      c.selected = const Workspace(8, 'Team', 'Owner');
      expect(
        catalog
            .find('POST', '/project-management/admin/workspaces/reset-all')!
            .allowed(c),
        false,
      );
    },
  );
  testWidgets(
    'creating a component requires confirmation before a network mutation',
    (tester) async {
      var writes = 0;
      final dio = Dio();
      dio.httpClientAdapter = FakeAdapter((r) async {
        writes++;
        expect(r.data['name'], 'Mobile');
        return response({'id': 1, 'name': 'Mobile'});
      });
      final c = AppController(
        ApiClient(
          baseUrl: 'https://example.test/api/v1',
          store: MemoryStore(),
          transport: dio,
        ),
      );
      c.selected = const Workspace(8, 'Team', 'Owner');
      final catalog = (await tester.runAsync(PmsCatalog.load))!;
      await tester.pumpWidget(
        MaterialApp(
          home: PmsOperationPage(
            controller: c,
            catalog: catalog,
            operation: catalog.find(
              'POST',
              '/project-management/projects/{project_id}/components',
            )!,
            scope: const {'workspace_id': 8, 'project_id': 22},
          ),
        ),
      );
      await tester.enterText(
        find.byKey(const ValueKey('input-name')),
        'Mobile',
      );
      await tester.ensureVisible(find.widgetWithText(FilledButton, 'Save'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Save'));
      await tester.pumpAndSettle();
      expect(find.byType(AlertDialog), findsOneWidget);
      expect(writes, 0);
      await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
      await tester.pumpAndSettle();
      expect(writes, 1);
      expect(find.text('Saved successfully.'), findsOneWidget);
      await tester.pumpWidget(
        MaterialApp(
          home: PmsOperationPage(
            key: const ValueKey('tag-form'),
            controller: c,
            catalog: catalog,
            operation: catalog.find(
              'POST',
              '/project-management/tasks/{task_id}/tags',
            )!,
            scope: const {'workspace_id': 8, 'project_id': 22, 'task_id': 40},
          ),
        ),
      );
      expect(find.byKey(const ValueKey('input-name')), findsOneWidget);
    },
  );
}
