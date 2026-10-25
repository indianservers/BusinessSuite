import 'dart:convert';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:flutter/services.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:business_suite_mobile/main.dart' as app;
import 'package:business_suite_mobile/core/models.dart';
import 'package:business_suite_mobile/features/pms_catalog.dart';
import 'package:business_suite_mobile/features/pms_feature_hub.dart';
import 'package:business_suite_mobile/features/contract_form.dart';
import 'package:business_suite_mobile/features/pms_board_page.dart';
import 'package:business_suite_mobile/features/pms_planner_page.dart';
import 'full_pms_cases.dart';

void main() => runPmsDeviceMatrix(fullPmsCasesJson);

void runPmsDeviceMatrix(String plan) {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  WidgetController.hitTestWarningShouldBeFatal = true;
  testWidgets('Full PMS native phone matrix', (tester) async {
    const run = String.fromEnvironment('QA_RUN_ID');
    const email = String.fromEnvironment('QA_ADMIN_EMAIL');
    const password = String.fromEnvironment('QA_ADMIN_PASSWORD');
    final cases = (jsonDecode(plan) as List).cast<Json>();
    final results = <Json>[], traffic = <Json>[];
    final fixtures = Map<String, dynamic>.from(
      jsonDecode(
        const String.fromEnvironment('QA_SEED_RECORDS', defaultValue: '{}'),
      ),
    ).map((k, v) => MapEntry(k, Map<String, dynamic>.from(v)));
    final names = <int, String>{};
    final ids = Map<String, dynamic>.from(
      jsonDecode(
        const String.fromEnvironment('QA_SEED_IDS', defaultValue: '{}'),
      ),
    );
    binding.reportData = {
      'run_id': run,
      'operations': results,
      'fixtures': ids,
      'fixture_records': fixtures,
      'backend': const String.fromEnvironment('API_BASE_URL'),
      'method':
          'Native Flutter page routing and physical controls; no direct API mutation calls',
    };
    app.main();
    await tester.pump();
    final controller = tester
        .widget<app.BusinessSuiteApp>(find.byType(app.BusinessSuiteApp))
        .controller;
    controller.api.dio.interceptors.add(
      InterceptorsWrapper(
        onResponse: (r, h) {
          traffic.add({
            'method': r.requestOptions.method,
            'path': r.requestOptions.path,
            'status': r.statusCode,
            'data': r.data,
            'request': r.requestOptions.data,
          });
          h.next(r);
        },
        onError: (e, h) {
          traffic.add({
            'method': e.requestOptions.method,
            'path': e.requestOptions.path,
            'status': e.response?.statusCode,
            'error': e.response?.data,
          });
          h.next(e);
        },
      ),
    );
    Future<void> settle() => tester.pumpAndSettle(
      const Duration(milliseconds: 100),
      EnginePhase.sendSemanticsUpdate,
      const Duration(seconds: 90),
    );
    Future<void> until(bool Function() ready, String description) async {
      final end = DateTime.now().add(const Duration(seconds: 100));
      while (true) {
        var done = false;
        try {
          done = ready();
        } on StateError {
          /* A lazy list has not built its target yet. */
        }
        if (done) break;
        if (DateTime.now().isAfter(end)) {
          throw StateError(
            'Timeout $description; ${traffic.isEmpty ? 'no response' : traffic.last['status']}',
          );
        }
        await tester.pump(const Duration(milliseconds: 150));
      }
      await settle();
    }

    Future<void> visible(Finder f) =>
        until(() => f.evaluate().isNotEmpty, 'visible control');
    Future<void> tap(Finder f) async {
      await visible(f);
      FocusManager.instance.primaryFocus?.unfocus();
      await settle();
      await tester.ensureVisible(f.first);
      await settle();
      await tester.tap(f.first);
      await settle();
    }

    await until(() => !controller.loading, 'session startup');
    if (controller.user != null) await tap(find.byTooltip('Sign out'));
    await visible(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.enterText(find.byType(TextFormField).at(0), email);
    await tester.enterText(find.byType(TextFormField).at(1), password);
    await tap(find.widgetWithText(FilledButton, 'Sign in'));
    await until(
      () => controller.user != null && !controller.busy && !controller.loading,
      'login',
    );
    ids['user'] = controller.user!.id;
    names[controller.user!.id!] = email;
    final catalog = (await tester.runAsync(PmsCatalog.load))!;
    final checkpoint = File(
      '${(await getApplicationDocumentsDirectory()).path}/full-pms-checkpoint.json',
    );
    final today = DateTime.now();
    dynamic resolve(dynamic v) {
      if (v is String) {
        if (v.startsWith('@')) {
          final id = ids[v.substring(1)];
          if (id == null) {
            throw StateError('Missing QA fixture ${v.substring(1)}');
          }
          return id;
        }
        if (v == '\$today') return today.toIso8601String().split('T').first;
        if (v == '\$tomorrow') {
          return today
              .add(const Duration(days: 1))
              .toIso8601String()
              .split('T')
              .first;
        }
        if (v == '\$monday') {
          return today
              .subtract(Duration(days: today.weekday - 1))
              .toIso8601String()
              .split('T')
              .first;
        }
        if (v == '\$future') {
          return today
              .add(const Duration(days: 90))
              .toIso8601String()
              .split('T')
              .first;
        }
        if (v == '\$workspace_name') return fixtures['workspace']!['name'];
        return v.replaceAll('\$run', run);
      }
      if (v is List) return v.map(resolve).toList();
      if (v is Map) return v.map((k, v) => MapEntry(k, resolve(v)));
      return v;
    }

    Map<String, dynamic> context() => {
      if (ids['workspace'] != null) 'workspace_id': ids['workspace'],
      if (ids['workspace'] != null) 'wid': ids['workspace'],
      if (ids['project'] != null) 'project_id': ids['project'],
      if (ids['task'] != null) 'task_id': ids['task'],
      for (final k in [
        'client',
        'epic',
        'component',
        'release',
        'milestone',
        'sprint',
        'item',
        'comment',
        'tag',
        'field',
        'type',
        'dependency',
        'time_log',
        'timesheet',
        'event',
        'view',
        'filter',
        'risk',
        'team',
        'document',
        'rule',
        'tool',
        'file',
        'point',
      ])
        if (ids[k] != null) '${k}_id': ids[k],
      if (ids['dashboard'] != null) 'did': ids['dashboard'],
      if (ids['form'] != null) 'fid': ids['form'],
      if (ids['restore_hash'] != null)
        'expected_current_hash': ids['restore_hash'],
    };
    Future<void> root() async {
      for (
        var n = 0;
        n < 8 && find.byTooltip('PMS features').evaluate().isEmpty;
        n++
      ) {
        await tester.binding.handlePopRoute();
        await settle();
      }
      await visible(find.byTooltip('PMS features'));
    }

    Future<void> field(
      String name,
      Json schema,
      dynamic value, {
      Finder? within,
    }) async {
      final matches = within == null
          ? find.byWidgetPredicate((w) => w is ContractField && w.name == name)
          : find.descendant(
              of: within,
              matching: find.byWidgetPredicate(
                (w) => w is ContractField && w.name == name,
              ),
            );
      final finder = schema['variants'] is List ? matches.first : matches.last;
      await visible(finder);
      await tester.ensureVisible(finder);
      await settle();
      Finder child(Finder f) => find.descendant(of: finder, matching: f);
      if (schema['variants'] is List) {
        if (value == null) {
          await tap(child(find.widgetWithText(TextButton, 'Clear value')));
          return;
        }
        final type = value is bool
            ? 'boolean'
            : value is num
            ? 'number'
            : value is Map
            ? 'object'
            : value is List
            ? 'array'
            : 'string';
        final variants = (schema['variants'] as List).cast<Json>();
        await tap(child(find.byType(DropdownButtonFormField<int>)).first);
        await tap(find.text(type).last);
        await field(
          name,
          variants.firstWhere((v) => v['type'] == type),
          value,
          within: finder,
        );
        return;
      }
      if (schema['format'] == 'binary') {
        await tap(child(find.byType(OutlinedButton)).first);
        await until(
          () => tester.widget<ContractField>(finder).value is PickedUpload,
          'Android document picker',
        );
        return;
      }
      if (value == null) {
        final clear = child(
          find.byTooltip(
            schema['format'] == 'date' || schema['format'] == 'date-time'
                ? 'Clear date'
                : 'Clear selection',
          ),
        );
        if (clear.evaluate().isNotEmpty) {
          await tap(clear);
          return;
        }
        final text = child(find.byType(TextFormField));
        if (text.evaluate().isNotEmpty) {
          await tester.enterText(text.last, '');
          await settle();
          return;
        }
        throw StateError('No clear control for $name');
      }
      if (schema['type'] == 'object' || schema.containsKey('properties')) {
        if ((schema['properties'] as Map? ?? {}).isEmpty) {
          for (final entry in (value as Map).entries) {
            await tap(
              child(find.widgetWithText(OutlinedButton, 'Add property')).last,
            );
            final dialog = find.byType(AlertDialog).last;
            final fields = find.descendant(
              of: dialog,
              matching: find.byType(TextField),
            );
            await tester.enterText(fields.at(0), '${entry.key}');
            await tester.enterText(fields.at(1), '${entry.value}');
            if (entry.value is num || entry.value is bool) {
              await tap(
                find.descendant(
                  of: dialog,
                  matching: find.byType(DropdownButtonFormField<String>),
                ),
              );
              await tap(
                find.text(entry.value is bool ? 'Yes / no' : 'Number').last,
              );
            }
            await tap(find.widgetWithText(FilledButton, 'Add').last);
          }
          return;
        }
        for (final entry in (value as Map).entries) {
          await field(
            entry.key,
            Map<String, dynamic>.from(schema['properties']?[entry.key] ?? {}),
            entry.value,
            within: finder,
          );
        }
      } else if (schema['type'] == 'array') {
        // Existing arrays are removed through the same row controls users see.
        var remove = child(find.byTooltip('Remove item'));
        while (remove.evaluate().isNotEmpty) {
          await tap(remove.first);
          remove = child(find.byTooltip('Remove item'));
        }
        for (final item in value as List) {
          await tap(child(find.widgetWithText(OutlinedButton, 'Add item')));
          final dialog = find.byType(AlertDialog).last;
          final itemSchema = Map<String, dynamic>.from(schema['items'] ?? {});
          if (item is Map) {
            for (final e in item.entries) {
              await field(
                e.key,
                Map<String, dynamic>.from(
                  itemSchema['properties']?[e.key] ?? {},
                ),
                e.value,
                within: dialog,
              );
            }
          } else {
            final f = tester.widget<ContractField>(
              find
                  .descendant(of: dialog, matching: find.byType(ContractField))
                  .last,
            );
            await field(f.name, itemSchema, item, within: dialog);
          }
          await tap(find.widgetWithText(FilledButton, 'Add').last);
        }
      } else if (schema['type'] == 'boolean') {
        final f = child(find.byType(SwitchListTile));
        if (tester.widget<SwitchListTile>(f).value != value) await tap(f);
      } else if (schema['enum'] is List) {
        await tap(child(find.byType(DropdownButtonFormField<dynamic>)));
        await tap(find.text('$value').last);
      } else if (schema['format'] == 'date' ||
          schema['format'] == 'date-time') {
        await tap(child(find.byTooltip('Choose ${fieldLabel(name)}')));
        final d = DateTime.parse('$value');
        var current = DateTime(today.year, today.month);
        final target = DateTime(d.year, d.month);
        while (current != target) {
          final forward = current.isBefore(target);
          await tap(find.byTooltip(forward ? 'Next month' : 'Previous month'));
          current = DateTime(current.year, current.month + (forward ? 1 : -1));
        }
        await tap(find.text('${d.day}').last);
        await tap(find.text('OK').last);
        if (find.byType(TimePickerDialog).evaluate().isNotEmpty) {
          await tap(find.text('OK').last);
        }
      } else if (child(
        find.byTooltip('Choose ${fieldLabel(name)}'),
      ).evaluate().isNotEmpty) {
        final widget = tester.widget<ContractField>(finder);
        if (widget.value == value) {
          return; // The related-record route already bound this ID.
        }
        await tap(child(find.byTooltip('Choose ${fieldLabel(name)}')));
        final key =
            const {
              'wid': 'workspace',
              'did': 'dashboard',
              'assignee_user_id': 'user',
              'reporter_user_id': 'user',
              'owner_user_id': 'user',
              'manager_user_id': 'user',
              'assignee_id': 'user',
              'source_task_id': 'task',
              'target_task_id': 'other',
              'depends_on_task_id': 'other',
              'parent_task_id': 'task',
            }[name] ??
            name.replaceFirst(RegExp(r'_id$'), '');
        final record = fixtures.entries
            .where(
              (e) =>
                  e.value['id'] == value &&
                  (e.key == key ||
                      (key == 'task' &&
                          const {'task', 'other', 'child'}.contains(e.key)) ||
                      (key == 'project' && e.key == 'clone')),
            )
            .firstOrNull
            ?.value;
        final title = key == 'user'
            ? email
            : record != null
            ? recordTitle(record)
            : names[value];
        if (title == null) {
          throw StateError('No QA display name for $name=$value');
        }
        await tester.enterText(find.byType(TextField).last, title);
        await settle();
        final choice = find.byWidgetPredicate(
          (w) =>
              w is ListTile &&
              w.title is Text &&
              ((w.title as Text).data ?? '').contains(title),
        );
        await tap(choice.first);
      } else {
        await tester.enterText(
          child(find.byType(TextFormField)).last,
          '$value',
        );
        await settle();
      }
    }

    for (var index = 0; index < cases.length; index++) {
      final spec = cases[index];
      final stamp = DateTime.now().toUtc().toIso8601String();
      final result = <String, dynamic>{
        'number': index + 1,
        'operation': spec['label'],
        'method': spec['method'],
        'path': spec['path'],
        'started_at': stamp,
      };
      try {
        await root();
        final op = catalog.find(spec['method'], spec['path'])!;
        final scope = {
          ...context(),
          ...Map<String, dynamic>.from(resolve(spec['scope'] ?? {})),
        };
        for (final p in op.parameters.where((p) => p['in'] == 'path')) {
          if (scope[p['name']] == null) {
            throw StateError('Missing QA fixture ${p['name']}');
          }
        }
        final body = Map<String, dynamic>.from(resolve(spec['body']));
        final props = Map<String, dynamic>.from(op.body['properties'] ?? {});
        for (final key in body.keys) {
          if (!props.containsKey(key)) {
            throw StateError('Field $key is absent from supplied API contract');
          }
        }
        final initial = <String, dynamic>{};
        if (op.method == 'PATCH' || op.method == 'PUT') {
          final resource = op.path.split('/').last;
          final id = scope[resource.replaceAll(RegExp('[{}]'), '')];
          final key = resource
              .replaceAll(RegExp('[{}]'), '')
              .replaceFirst(RegExp(r'_id$'), '');
          for (final e in fixtures.entries) {
            if (e.value['id'] == id &&
                (e.key == key ||
                    (key == 'task' &&
                        const {'task', 'other', 'child'}.contains(e.key)))) {
              initial.addAll(e.value);
            }
          }
        }
        for (final entry in {
          '/dashboards/{did}': 'dashboard',
          '/forms/{fid}': 'form',
          '/docs/{document_id}': 'document',
        }.entries) {
          if (op.path.contains(entry.key) && fixtures[entry.value] != null) {
            initial.addAll(fixtures[entry.value]!);
          }
        }
        final before = traffic.length;
        final nav = Navigator.of(
          tester.element(find.byTooltip('PMS features')),
        );
        Future<void> openAction(
          PmsOperation action,
          Map<String, dynamic> actionScope,
          Json initial,
        ) => nav.push(
          MaterialPageRoute<void>(
            builder: (_) => PmsOperationPage(
              controller: controller,
              catalog: catalog,
              operation: action,
              scope: actionScope,
              initial: initial,
            ),
          ),
        );
        nav.push(
          MaterialPageRoute<void>(
            builder: (_) => spec['native'] == 'board'
                ? PmsBoardPage(
                    controller: controller,
                    projectId: ids['project'],
                    catalog: catalog,
                    openAction: openAction,
                  )
                : spec['native'] == 'planner'
                ? PmsPlannerPage(
                    controller: controller,
                    projectId: ids['project'],
                    catalog: catalog,
                    openAction: openAction,
                  )
                : PmsOperationPage(
                    controller: controller,
                    catalog: catalog,
                    operation: op,
                    scope: scope,
                    initial: initial,
                  ),
          ),
        );
        await settle();
        for (final e in body.entries) {
          await field(e.key, Map<String, dynamic>.from(props[e.key]), e.value);
        }
        if (op.method == 'GET') {
          for (final p in op.parameters.where(
            (p) => p['required'] == true && p['in'] == 'query',
          )) {
            final schema = Map<String, dynamic>.from(p['schema']);
            final name = p['name'] as String;
            final existing = find.byWidgetPredicate(
              (w) => w is ContractField && w.name == name,
            );
            if (existing.evaluate().isEmpty ||
                tester.widget<ContractField>(existing.last).value != null) {
              continue;
            }
            await field(
              name,
              schema,
              schema['format'] == 'date' || schema['format'] == 'date-time'
                  ? resolve(
                      name.contains('end') || name.contains('to')
                          ? '\$tomorrow'
                          : '\$today',
                    )
                  : name == 'q'
                  ? 'QA'
                  : scope[name] ?? 1,
            );
          }
          if (find
              .widgetWithText(FilledButton, 'Apply filters')
              .evaluate()
              .isNotEmpty) {
            await tap(find.widgetWithText(FilledButton, 'Apply filters'));
          }
        } else {
          await tap(find.widgetWithText(FilledButton, 'Save'));
          await visible(find.byType(AlertDialog));
          await tap(find.widgetWithText(FilledButton, 'Confirm'));
        }
        final path = op.path.replaceAllMapped(
          RegExp(r'\{([^}]+)\}'),
          (m) => '${scope[m[1]]}',
        );
        await until(
          () => traffic
              .skip(before)
              .any((r) => r['method'] == op.method && r['path'] == path),
          'server result',
        );
        final response = traffic
            .skip(before)
            .lastWhere((r) => r['method'] == op.method && r['path'] == path);
        result['http_status'] = response['status'];
        if ((response['status'] ?? 0) < 200 ||
            (response['status'] ?? 500) >= 300) {
          throw StateError(
            'Server rejected operation: ${response['status']} ${response['error']}',
          );
        }
        await settle();
        if (op.mutation) await visible(find.text('Saved successfully.'));
        final data = response['data'];
        if (spec['capture_tasks'] == true) {
          result['observed_records'] = [
            for (final row in records(data))
              {
                for (final key in [
                  'id',
                  'task_key',
                  'title',
                  'status',
                  'due_date',
                  'recurrence_rule',
                  'recurrence_interval',
                ])
                  key: row[key],
              },
          ];
        }
        if (data is Map && data['expected_current_hash'] is String) {
          ids['restore_hash'] = data['expected_current_hash'];
        }
        if (spec['native'] == 'board') {
          final taskId = ids['task'];
          if (spec['action'] == 'drag') {
            final columns = records(data['columns']);
            final source = columns.firstWhere(
              (col) => records(col['tasks']).any((t) => t['id'] == taskId),
            );
            final target = columns.firstWhere(
              (col) =>
                  col['id'] != source['id'] &&
                  col['status_key'] == 'IN_PROGRESS',
            );
            final card = find.byKey(ValueKey('board-task-$taskId'));
            await tester.ensureVisible(card);
            await settle();
            final box = tester.getRect(
              find.byKey(ValueKey('board-column-${target['id']}')),
            );
            final screenWidth =
                tester.view.physicalSize.width / tester.view.devicePixelRatio;
            final end = Offset(
              (box.left + 4).clamp(8, screenWidth - 8).toDouble(),
              box.top + 40,
            );
            final moved = traffic.length;
            final gesture = await tester.startGesture(tester.getCenter(card));
            await tester.pump(const Duration(milliseconds: 650));
            await gesture.moveTo(end);
            await tester.pump(const Duration(milliseconds: 350));
            await gesture.up();
            await settle();
            await until(
              () => traffic
                  .skip(moved)
                  .any(
                    (r) =>
                        r['method'] == 'POST' &&
                        '${r['path']}'.endsWith('/board/reorder') &&
                        r['status'] == 200,
                  ),
              'board drag persistence',
            );
          } else if (spec['action'] == 'layouts') {
            await tap(find.byTooltip('List layout'));
            await visible(find.byTooltip('Board layout'));
            await tap(find.byTooltip('Board layout'));
          } else if (spec['action'] == 'copy') {
            await tap(
              find.byTooltip('Task actions ${fixtures['task']!['task_key']}'),
            );
            await tap(find.text('Copy task ID'));
            expect((await Clipboard.getData('text/plain'))?.text, '$taskId');
          } else if (spec['action'] == 'bulk') {
            final tile = find
                .descendant(
                  of: find.byKey(ValueKey('board-task-$taskId')),
                  matching: find.byType(ListTile),
                )
                .first;
            await tap(
              find.descendant(of: tile, matching: find.byType(Checkbox)),
            );
            await tap(find.byTooltip('Edit selected tasks'));
            final bulk = catalog.find(
              'PATCH',
              '/project-management/tasks/bulk',
            )!;
            await field(
              'priority',
              Map<String, dynamic>.from(bulk.body['properties']['priority']),
              'Urgent',
            );
            final started = traffic.length;
            await tap(find.widgetWithText(FilledButton, 'Save'));
            await tap(find.widgetWithText(FilledButton, 'Confirm'));
            await until(
              () => traffic
                  .skip(started)
                  .any(
                    (r) =>
                        r['method'] == 'PATCH' &&
                        r['path'] == '/project-management/tasks/bulk' &&
                        r['status'] == 200,
                  ),
              'bulk board edit',
            );
          } else if (spec['action'] == 'duplicate') {
            await tap(
              find.byTooltip('Task actions ${fixtures['task']!['task_key']}'),
            );
            await tap(find.text('Duplicate task'));
            final beforeDuplicate = traffic.length;
            await tap(find.widgetWithText(FilledButton, 'Save'));
            await tap(find.widgetWithText(FilledButton, 'Confirm'));
            await until(
              () => traffic
                  .skip(beforeDuplicate)
                  .any(
                    (r) =>
                        r['method'] == 'POST' &&
                        r['path'] ==
                            '/project-management/projects/${ids['project']}/tasks' &&
                        r['status'] == 200,
                  ),
              'task duplication',
            );
          }
        }
        if (spec['native'] == 'planner') {
          if (spec['action'] == 'navigate') {
            for (final view in ['Week', 'Day', 'Agenda', 'Month']) {
              await tap(find.byType(DropdownButton<String>).first);
              await tap(find.text(view).last);
            }
            await tap(find.byTooltip('Next period'));
            await tap(find.byTooltip('Previous period'));
            await tap(find.text('Today'));
            await tester.enterText(
              find.widgetWithText(TextField, 'Search planner'),
              'QA',
            );
            await settle();
          } else if (spec['action'] == 'create') {
            await tap(find.byTooltip('Create calendar item'));
            await tap(find.text('Create event'));
            await field('title', {'type': 'string'}, 'QA calendar event $run');
            final submitted = traffic.length;
            await tap(find.widgetWithText(FilledButton, 'Save'));
            await tap(find.widgetWithText(FilledButton, 'Confirm'));
            await until(
              () => traffic
                  .skip(submitted)
                  .any(
                    (r) =>
                        r['method'] == 'POST' &&
                        r['path'] == '/project-management/planner/events' &&
                        r['status'] == 201,
                  ),
              'calendar event creation',
            );
          }
        }
        if (spec['assert_recurring_generated'] != null) {
          final generated = records(data).where(
            (r) =>
                r['recurrence_rule'] == spec['assert_recurring_generated'] &&
                '${r['due_date']}'.compareTo('${resolve('\$today')}') > 0,
          );
          expect(
            generated,
            isNotEmpty,
            reason: 'Server generated the next occurrence',
          );
        }
        if (spec['assert_file'] == true) {
          expect(
            utf8.decode((data as List).cast<int>()),
            contains('physical-device QA attachment'),
          );
        }
        if (spec['save_download'] == true) {
          await tap(find.widgetWithText(FilledButton, 'Save file'));
          await visible(find.text('File saved successfully.'));
        }
        if (response['request'] is Map) {
          for (final entry in body.entries) {
            if (entry.value is List || entry.key.endsWith('_id')) {
              expect(
                response['request'][entry.key],
                entry.value,
                reason: 'Actual submitted ${entry.key}',
              );
            }
          }
        }
        if (spec['save'] != null) {
          final row = data is Map
              ? Map<String, dynamic>.from(data)
              : <String, dynamic>{};
          final nested = row['data'];
          if (nested is Map) row.addAll(Map<String, dynamic>.from(nested));
          final id =
              row['id'] ??
              row['${spec['save']}_id'] ??
              ((const {'PUT', 'PATCH'}.contains(op.method) ||
                      op.path.endsWith('/trash') ||
                      op.path.endsWith('/restore'))
                  ? ids[spec['save']]
                  : null);
          if (id == null) {
            throw StateError(
              'Successful response omitted record ID for ${spec['save']}',
            );
          }
          ids[spec['save']] = id;
          fixtures[spec['save']] = {
            ...?fixtures[spec['save']],
            ...row,
            'id': id,
          };
          names[id] = recordTitle(row);
        }
        if (data is Map && data['id'] is int) {
          final id = data['id'];
          for (final key in fixtures.keys.toList()) {
            if (fixtures[key]!['id'] == id &&
                op.path.contains(key.replaceAll('_', '-'))) {
              fixtures[key] = Map<String, dynamic>.from(data);
            }
          }
          names[id] = recordTitle(Map<String, dynamic>.from(data));
        }
        if (spec['verify'] is Map && data is Map) {
          for (final e in (spec['verify'] as Map).entries) {
            expect(data[e.key], resolve(e.value), reason: 'Persisted ${e.key}');
          }
        }
        result['status'] = 'passed';
        if (spec['save'] == 'workspace') {
          await root();
          await controller.loadAccount();
          await settle();
          await tap(find.byType(DropdownButtonFormField<int>).first);
          await tester.scrollUntilVisible(
            find.text(names[ids['workspace']]!),
            400,
            scrollable: find.byType(Scrollable).last,
          );
          await tap(find.text(names[ids['workspace']]!).last);
          await until(
            () => !controller.loading && controller.overview != null,
            'QA workspace',
          );
        } else if (op.mutation && ids['workspace'] != null) {
          await controller.selectWorkspace(controller.selected!);
          await settle();
        }
      } catch (e) {
        result['status'] =
            '$e'.contains('Missing QA fixture') ||
                '$e'.contains('absent from supplied API contract')
            ? 'blocked'
            : 'failed';
        result['error'] = '$e';
        tester.takeException();
      }
      result['completed_at'] = DateTime.now().toUtc().toIso8601String();
      results.add(result);
      // ignore: avoid_print
      print(
        'FULL PMS ${index + 1}/${cases.length} ${result['status']}: ${spec['label']}',
      );
      if (result['error'] != null) {
        // ignore: avoid_print
        print('FULL PMS ISSUE: ${result['error']}');
      }
      await checkpoint.writeAsString(jsonEncode(binding.reportData));
    }
    binding.reportData!['passed'] = results
        .where((r) => r['status'] == 'passed')
        .length;
    binding.reportData!['failed'] = results
        .where((r) => r['status'] == 'failed')
        .length;
    binding.reportData!['blocked'] = results
        .where((r) => r['status'] == 'blocked')
        .length;
    await root();
  }, timeout: const Timeout(Duration(hours: 2)));
}
