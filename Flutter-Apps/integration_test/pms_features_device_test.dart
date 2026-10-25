import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:business_suite_mobile/main.dart' as app;
import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/features/contract_form.dart';
import 'package:business_suite_mobile/features/pms_catalog.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  WidgetController.hitTestWarningShouldBeFatal = true;
  testWidgets('Extended live PMS feature acceptance', (tester) async {
    const email = String.fromEnvironment('QA_ADMIN_EMAIL'),
        password = String.fromEnvironment('QA_ADMIN_PASSWORD'),
        run = String.fromEnvironment('QA_RUN_ID');
    expect(run, isNotEmpty);
    const resume = bool.fromEnvironment('QA_RESUME');
    const resumeFrom = int.fromEnvironment('QA_RESUME_FROM', defaultValue: 21);
    var ordinal = 0;
    final checks = <Map<String, dynamic>>[], calls = <Map<String, dynamic>>[];
    binding.reportData = {
      'backend': const String.fromEnvironment('API_BASE_URL'),
      'run_id': run,
      'operations': checks,
    };
    app.main();
    await tester.pumpAndSettle(const Duration(milliseconds: 100));
    AppController c() => tester
        .widget<app.BusinessSuiteApp>(find.byType(app.BusinessSuiteApp))
        .controller;
    c().api.onResponse = (method, path, status) =>
        calls.add({'method': method, 'path': path, 'status': status});
    Future<void> until(bool Function() condition, String label) async {
      final end = DateTime.now().add(const Duration(seconds: 100));
      while (!condition()) {
        if (DateTime.now().isAfter(end)) {
          fail(
            'Timeout: $label. Recent responses: ${calls.skip(calls.length > 5 ? calls.length - 5 : 0).toList()}',
          );
        }
        await tester.pump(const Duration(milliseconds: 200));
      }
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
    }

    Future<void> visible(Finder finder) async => until(() {
      try {
        return finder.evaluate().isNotEmpty;
      } on StateError {
        return false;
      }
    }, 'widget visibility');
    Future<void> tap(Finder finder) async {
      await visible(finder);
      if (tester.view.viewInsets.bottom > 0) {
        FocusManager.instance.primaryFocus?.unfocus();
        await until(
          () => tester.view.viewInsets.bottom == 0,
          'keyboard dismissal',
        );
      }
      await tester.ensureVisible(finder.first);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      await tester.tap(finder.first);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
    }

    Future<void> fill(String name, String value) async {
      final finder = find.byKey(ValueKey('input-$name'));
      await visible(finder);
      await tester.ensureVisible(finder);
      await tester.enterText(finder, value);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
    }

    Future<void> back() async {
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
    }

    Future<void> root() async {
      while (find.byTooltip('PMS features').evaluate().isEmpty) {
        await back();
      }
      await tap(find.text('Projects').last);
    }

    Future<void> check(
      String label,
      Future<void> Function() action, {
      bool shot = false,
    }) async {
      final number = ++ordinal;
      if (resume && number < resumeFrom) return;
      try {
        await action();
        expect(tester.takeException(), isNull);
        checks.add({
          'number': number,
          'operation': label,
          'status': 'passed',
          'completed_at': DateTime.now().toUtc().toIso8601String(),
        });
        if (shot) {
          binding.reportData!['last_visual_checkpoint'] = label;
        }
        // ignore: avoid_print
        print('PMS FEATURE $number PASSED: $label');
      } catch (e) {
        checks.add({
          'number': number,
          'operation': label,
          'status': 'failed',
          'error': '$e',
        });
        rethrow;
      }
    }

    Future<void> login() async {
      await until(() => !c().loading, 'startup restoration');
      if (find.byTooltip('Sign out').evaluate().isNotEmpty) {
        await tap(find.byTooltip('Sign out'));
      }
      await visible(find.widgetWithText(FilledButton, 'Sign in'));
      await tester.enterText(find.byType(TextFormField).at(0), email);
      await tester.enterText(find.byType(TextFormField).at(1), password);
      await tap(find.widgetWithText(FilledButton, 'Sign in'));
      await visible(find.byTooltip('PMS features'));
    }

    await login();
    await tester.pump();
    await tester.pumpAndSettle(const Duration(milliseconds: 100));
    final workspace = 'PMS Features QA $run',
        project = 'Feature delivery $run',
        key = 'F$run',
        task = 'Feature task $run';
    if (!resume) {
      await tap(find.text('Account').last);
      await tap(find.text('Create workspace'));
      await tester.enterText(find.byType(TextFormField).first, workspace);
      await tap(find.widgetWithText(FilledButton, 'Create'));
      await until(
        () =>
            find.byType(AlertDialog).evaluate().isEmpty &&
            !c().loading &&
            !c().busy,
        'workspace creation',
      );
    }
    await tap(find.byType(DropdownButtonFormField<int>).first);
    await tester.scrollUntilVisible(
      find.text(workspace),
      400,
      scrollable: find.byType(Scrollable).last,
    );
    await tap(find.text(workspace).last);
    await tap(find.text('Projects').last);
    if (!resume) {
      await tap(find.byType(FloatingActionButton));
      await tester.enterText(find.byType(TextFormField).at(0), project);
      await tester.enterText(find.byType(TextFormField).at(1), key);
      await tap(find.widgetWithText(FilledButton, 'Create'));
      await until(
        () =>
            find.byType(AlertDialog).evaluate().isEmpty &&
            !c().loading &&
            !c().busy,
        'project creation',
      );
      await tap(find.widgetWithText(ListTile, project));
      await tap(find.byType(FloatingActionButton));
      await tester.enterText(find.byType(TextFormField).at(0), task);
      await tester.enterText(find.byType(TextFormField).at(1), '$key-1');
      await tap(find.widgetWithText(FilledButton, 'Create'));
      await until(
        () =>
            find.byType(AlertDialog).evaluate().isEmpty &&
            !c().loading &&
            !c().busy,
        'task creation',
      );
    }
    await until(
      () =>
          !c().loading &&
          c().overview != null &&
          c().selected?.name == workspace,
      'workspace overview',
    );
    final catalog = await PmsCatalog.load();
    final projectId = c().overview!.projects
        .firstWhere((p) => p.name == project)
        .id;
    final taskId = c().overview!.tasks.firstWhere((t) => t.title == task).id;
    binding.reportData!['workspace_id'] = c().selected!.id;
    binding.reportData!['project_id'] = projectId;
    binding.reportData!['task_id'] = taskId;
    Future<PmsOperation> feature(
      String method,
      String path, {
      Map<String, String> references = const {},
    }) async {
      await root();
      await tap(find.byTooltip('Project features for $project'));
      final op = catalog.find(method, '/project-management/$path')!;
      await tester.enterText(find.byType(TextField).first, op.title);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      await tap(find.widgetWithText(ListTile, op.title));
      for (final entry in references.entries) {
        await tap(find.byTooltip('Choose ${fieldLabel(entry.key)}'));
        final option = find.byWidgetPredicate(
          (w) =>
              w is ListTile &&
              w.title is Text &&
              ((w.title as Text).data ?? '').contains(entry.value),
        );
        await tap(option);
      }
      return op;
    }

    Future<void> date(String name, {int days = 0}) async {
      await tap(find.byTooltip('Choose ${fieldLabel(name)}'));
      if (days != 0) {
        await tap(
          find.text('${DateTime.now().add(Duration(days: days)).day}').last,
        );
      }
      await tap(find.text('OK').last);
      if (find.byType(TimePickerDialog).evaluate().isNotEmpty) {
        await tap(find.text('OK').last);
      }
    }

    Future<void> save() async {
      await tap(find.widgetWithText(FilledButton, 'Save'));
      await visible(find.byType(AlertDialog));
      await tap(find.widgetWithText(FilledButton, 'Confirm'));
      await visible(find.text('Saved successfully.'));
      expect(calls.last['status'], inInclusiveRange(200, 299));
    }

    Future<void> read(
      String path, {
      Map<String, String> references = const {},
    }) async {
      final before = calls.length;
      final op = await feature('GET', path, references: references);
      if (find
          .widgetWithText(FilledButton, 'Apply filters')
          .evaluate()
          .isNotEmpty) {
        final params = op.parameters.where(
          (p) => p['required'] == true && p['in'] == 'query',
        );
        for (final p in params) {
          if (p['schema']['format'] == 'date' ||
              p['schema']['format'] == 'date-time') {
            await date(p['name'] as String, days: p['name'] == 'end' ? 7 : 0);
          }
        }
        await tap(find.widgetWithText(FilledButton, 'Apply filters'));
      }
      final pattern = RegExp(
        '^${op.path.replaceAll(RegExp(r'\{[^}]+\}'), '[^/]+')}\$',
      );
      await until(
        () => calls
            .skip(before)
            .any((r) => r['method'] == 'GET' && pattern.hasMatch(r['path'])),
        'feature response',
      );
      final response = calls
          .skip(before)
          .lastWhere(
            (r) => r['method'] == 'GET' && pattern.hasMatch(r['path']),
          );
      expect(response['status'], inInclusiveRange(200, 299));
    }

    final epic = 'Epic $run',
        component = 'Component $run',
        release = 'Release $run',
        milestone = 'Milestone $run',
        risk = 'Risk $run',
        doc = 'Document $run',
        team = 'Team $run';
    await check('Create epic', () async {
      await feature('POST', 'projects/{project_id}/epics');
      await fill('name', epic);
      await fill('epic_key', 'E$run');
      await save();
    });
    await check('Read epic list', () => read('projects/{project_id}/epics'));
    await check('Update epic through record picker', () async {
      await feature('PATCH', 'epics/{epic_id}', references: {'epic_id': epic});
      await fill('name', '$epic updated');
      await save();
    });
    await check('Create project component', () async {
      await feature('POST', 'projects/{project_id}/components');
      await fill('name', component);
      await save();
    });
    await check(
      'Read components',
      () => read('projects/{project_id}/components'),
    );
    await check('Create release', () async {
      await feature('POST', 'projects/{project_id}/releases');
      await fill('name', release);
      await save();
    });
    await check('Read releases', () => read('projects/{project_id}/releases'));
    await check(
      'Read release readiness',
      () => read(
        'releases/{release_id}/readiness',
        references: {'release_id': release},
      ),
    );
    await check('Create milestone', () async {
      await feature('POST', 'projects/{project_id}/milestones');
      await fill('name', milestone);
      await save();
    });
    await check(
      'Read milestones',
      () => read('projects/{project_id}/milestones'),
    );
    await check('Create sprint with dates', () async {
      await feature('POST', 'projects/{project_id}/sprints');
      await fill('name', 'Sprint $run');
      await date('start_date');
      await date('end_date', days: 7);
      await save();
    });
    await check('Read sprints', () => read('projects/{project_id}/sprints'));
    await check('Create project risk', () async {
      await feature('POST', 'risks');
      await fill('title', risk);
      await fill('mitigation_plan', 'Verify on physical Android');
      await save();
    });
    await check('Read risk register', () => read('risks'));
    await check('Add task comment', () async {
      await feature(
        'POST',
        'tasks/{task_id}/comments',
        references: {'task_id': task},
      );
      await fill('body', 'Android comment $run');
      await save();
    });
    await check(
      'Read task comments',
      () => read('tasks/{task_id}/comments', references: {'task_id': task}),
    );
    await check('Add checklist item', () async {
      await feature(
        'POST',
        'tasks/{task_id}/checklists',
        references: {'task_id': task},
      );
      await fill('title', 'Verify acceptance $run');
      await save();
    });
    await check(
      'Read checklist',
      () => read('tasks/{task_id}/checklists', references: {'task_id': task}),
    );
    await check('Create subtask', () async {
      await feature(
        'POST',
        'tasks/{task_id}/subtasks',
        references: {'task_id': task},
      );
      await fill('title', 'Android subtask $run');
      await save();
    });
    await check(
      'Read subtasks',
      () => read('tasks/{task_id}/subtasks', references: {'task_id': task}),
    );
    await check('Add task tag', () async {
      await feature(
        'POST',
        'tasks/{task_id}/tags',
        references: {'task_id': task},
      );
      await fill('name', 'android-$run');
      await save();
    });
    await check(
      'Read task tags',
      () => read('tasks/{task_id}/tags', references: {'task_id': task}),
    );
    await check('Log task time', () async {
      await feature(
        'POST',
        'tasks/{task_id}/time-logs',
        references: {'task_id': task},
      );
      await date('log_date');
      await fill('duration_minutes', '15');
      await fill('description', 'Android time log $run');
      await save();
    });
    await check(
      'Read task time logs',
      () => read('tasks/{task_id}/time-logs', references: {'task_id': task}),
    );
    await check('Create saved project filter', () async {
      await feature('POST', 'projects/{project_id}/saved-filters');
      await fill('name', 'Filter $run');
      await save();
    });
    await check(
      'Read saved filters',
      () => read('projects/{project_id}/saved-filters'),
    );
    await check('Create workspace team', () async {
      await feature('POST', 'workspaces/{workspace_id}/teams');
      await fill('name', team);
      await fill('alias', 'qa-$run');
      await save();
    });
    await check('Read teams', () => read('workspaces/{workspace_id}/teams'));
    await check('Create project document', () async {
      await feature('POST', 'projects/{project_id}/docs');
      await fill('title', doc);
      await fill('content', 'Physical Android document $run');
      await save();
    });
    await check('Read documents', () => read('docs'));
    await check(
      'Read Kanban board',
      () => read('projects/{project_id}/board'),
      shot: true,
    );
    await check('Read project dashboard', () => read('dashboard/{project_id}'));
    await check(
      'Read task distribution report',
      () => read('reports/task-distribution'),
    );
    await check(
      'Read resource workload',
      () => read('projects/{project_id}/workload'),
    );
    await check(
      'Read workspace activity',
      () => read('workspaces/{workspace_id}/activity'),
    );
    await check('Read notification inbox', () => read('notifications'));
    await check('Read trash', () => read('trash/tasks'));
    await check('Start native project timer', () async {
      await feature('GET', 'timer');
      await tester.enterText(find.byType(TextField).last, 'Android timer $run');
      await tap(find.widgetWithText(FilledButton, 'Start timer'));
      await visible(find.widgetWithText(FilledButton, 'Stop and save time'));
    }, shot: true);
    await check('Stop timer and persist time log', () async {
      await tap(find.widgetWithText(FilledButton, 'Stop and save time'));
      await tap(find.widgetWithText(FilledButton, 'Confirm'));
      await visible(find.widgetWithText(FilledButton, 'Start timer'));
    });
    await check('Create private chat channel', () async {
      await feature('GET', 'workspaces/{wid}/chat/conversations');
      await tap(find.byType(FloatingActionButton));
      await fill('name', 'Android room $run');
      final field = find.byWidgetPredicate(
        (w) => w is ContractField && w.name == 'kind',
      );
      await tap(
        find.descendant(
          of: field,
          matching: find.byType(DropdownButtonFormField<dynamic>),
        ),
      );
      await tap(find.text('channel').last);
      await save();
      await back();
      await visible(find.widgetWithText(ListTile, 'Android room $run'));
    });
    await check('Send native chat message', () async {
      await tap(find.widgetWithText(ListTile, 'Android room $run'));
      await tester.enterText(
        find.byType(TextField).last,
        'Message from Android $run',
      );
      await tap(find.byTooltip('Send message'));
      await visible(find.text('Message from Android $run'));
    }, shot: true);
    await check('Edit own chat message', () async {
      await tester.longPress(find.text('Message from Android $run'));
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      await tap(find.text('Edit message'));
      await fill('body', 'Edited Android message $run');
      await save();
      await back();
      await visible(find.text('Edited Android message $run'));
    });
    await check('Reply in message thread', () async {
      if (resume && resumeFrom == 43) {
        await feature('GET', 'workspaces/{wid}/chat/conversations');
        await tap(find.widgetWithText(ListTile, 'Android room $run'));
        await visible(find.text('Edited Android message $run'));
      }
      await tap(find.byTooltip('Message actions').last);
      await tap(find.text('Replies'));
      await tester.enterText(find.byType(TextField).last, 'Thread reply $run');
      await tap(find.byTooltip('Send message'));
      await visible(find.text('Thread reply $run'));
    });
    await root();
    binding.reportData!['http_operations_observed'] = calls.length;
    binding.reportData!['checks_passed'] = checks.length;
  }, timeout: const Timeout(Duration(minutes: 35)));
}
