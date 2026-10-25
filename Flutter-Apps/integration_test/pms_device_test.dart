import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:business_suite_mobile/main.dart' as app;
import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  WidgetController.hitTestWarningShouldBeFatal = true;
  testWidgets('20 live PMS operations on a physical Android phone', (
    tester,
  ) async {
    const adminEmail = String.fromEnvironment('QA_ADMIN_EMAIL');
    const adminPassword = String.fromEnvironment('QA_ADMIN_PASSWORD');
    const memberEmail = String.fromEnvironment('QA_MEMBER_EMAIL');
    const memberPassword = String.fromEnvironment('QA_MEMBER_PASSWORD');
    const runId = String.fromEnvironment('QA_RUN_ID');
    expect(
      adminEmail,
      isNotEmpty,
      reason: 'Provide ignored dart-define-from-file test credentials',
    );
    expect(runId, isNotEmpty);
    final operations = <Map<String, Object?>>[];
    binding.reportData = {
      'backend': const String.fromEnvironment('API_BASE_URL'),
      'run_id': runId,
      'operations': operations,
    };
    app.main();
    await tester.pumpAndSettle(const Duration(milliseconds: 200));
    AppController controller() => tester
        .widget<app.BusinessSuiteApp>(find.byType(app.BusinessSuiteApp))
        .controller;

    Future<void> waitUntil(bool Function() ready, String description) async {
      final end = DateTime.now().add(const Duration(seconds: 120));
      while (!ready()) {
        if (DateTime.now().isAfter(end)) {
          fail('Timed out: $description; app error: ${controller().error}');
        }
        await tester.pump(const Duration(milliseconds: 200));
      }
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
    }

    Future<void> waitFor(Finder finder, {int seconds = 100}) async {
      final end = DateTime.now().add(Duration(seconds: seconds));
      while (finder.evaluate().isEmpty) {
        if (DateTime.now().isAfter(end)) {
          fail(
            'Timed out waiting for $finder; app error: ${controller().error}',
          );
        }
        await tester.pump(const Duration(milliseconds: 200));
      }
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
    }

    Future<void> tap(Finder finder) async {
      await waitFor(finder);
      if (tester.view.viewInsets.bottom > 0) {
        FocusManager.instance.primaryFocus?.unfocus();
        await waitUntil(
          () => tester.view.viewInsets.bottom == 0,
          'Android keyboard dismissal',
        );
      }
      await tester.ensureVisible(finder.first);
      await tester.tap(finder.first);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
    }

    Future<void> record(
      String name,
      Future<void> Function() action, {
      bool screenshot = false,
    }) async {
      final number = operations.length + 1;
      try {
        await action();
        expect(tester.takeException(), isNull);
        operations.add({
          'number': number,
          'operation': name,
          'status': 'passed',
          'completed_at': DateTime.now().toUtc().toIso8601String(),
        });
        if (screenshot) {
          await binding.takeScreenshot(
            'operation-${number.toString().padLeft(2, '0')}',
          );
        }
        // No credentials or invitation tokens are written to the report.
        // ignore: avoid_print
        print('DEVICE OPERATION $number PASSED: $name');
      } catch (error) {
        operations.add({
          'number': number,
          'operation': name,
          'status': 'failed',
          'error': '$error',
        });
        rethrow;
      }
    }

    Future<void> login(String email, String password) async {
      await waitFor(find.widgetWithText(FilledButton, 'Sign in'));
      await tester.enterText(find.byType(TextFormField).at(0), email);
      await tester.enterText(find.byType(TextFormField).at(1), password);
      await tap(find.widgetWithText(FilledButton, 'Sign in'));
      await waitFor(find.byTooltip('Sign out'));
      expect(controller().user!.email, email);
      expect(controller().error, isNull);
    }

    Future<void> logout() async {
      await tap(find.byTooltip('Sign out'));
      await waitFor(find.widgetWithText(FilledButton, 'Sign in'));
    }

    Future<void> workspace(String name) async {
      await tap(find.byType(DropdownButtonFormField<int>).first);
      await tap(find.text(name).last);
      expect(controller().selected!.name, name);
    }

    Future<void> account() async => tap(find.text('Account').last);
    Future<void> createWorkspace(String name) async {
      if (controller().selected == null) {
        await tap(find.byType(FloatingActionButton));
      } else {
        await account();
        await tap(find.text('Create workspace'));
      }
      await tester.enterText(find.byType(TextFormField).first, name);
      await tap(find.widgetWithText(FilledButton, 'Create'));
      await waitUntil(
        () => find.byType(AlertDialog).evaluate().isEmpty,
        'workspace creation confirmation',
      );
      await waitFor(find.byTooltip('Refresh workspaces'));
      expect(controller().workspaces.any((w) => w.name == name), true);
    }

    Future<void> createProject(String name, String key) async {
      await tap(find.text('Projects').last);
      await tap(find.byType(FloatingActionButton));
      await tester.enterText(find.byType(TextFormField).at(0), name);
      await tester.enterText(find.byType(TextFormField).at(1), key);
      await tap(find.widgetWithText(FilledButton, 'Create'));
      await waitUntil(
        () => find.byType(AlertDialog).evaluate().isEmpty,
        'project creation confirmation',
      );
      await waitFor(find.text(name));
    }

    Future<void> createTask(
      String project,
      String title,
      String key, {
      String priority = 'Medium',
    }) async {
      await tap(find.text('Projects').last);
      await tap(find.text(project));
      await tap(find.byType(FloatingActionButton));
      await tester.enterText(find.byType(TextFormField).at(0), title);
      await tester.enterText(find.byType(TextFormField).at(1), key);
      await tester.enterText(
        find.byType(TextFormField).at(2),
        'Created on the connected physical Android device for $runId',
      );
      if (priority != 'Medium') {
        await tap(find.byType(DropdownButtonFormField<String>));
        await tap(find.text(priority).last);
      }
      await tap(find.widgetWithText(FilledButton, 'Create'));
      await waitUntil(
        () => find.byType(AlertDialog).evaluate().isEmpty,
        'task creation confirmation',
      );
      await waitFor(find.widgetWithText(ListTile, title));
      expect(
        controller().overview!.tasks.any(
          (t) => t.key == key && t.priority == priority,
        ),
        true,
      );
    }

    Future<void> status(String title, String value) async {
      await tap(find.widgetWithText(ListTile, title));
      await tap(find.byType(DropdownButtonFormField<String>));
      await tap(find.text(value).last);
      await tap(find.widgetWithText(FilledButton, 'Save status'));
      await waitFor(find.byType(FloatingActionButton));
      expect(
        controller().overview!.tasks.firstWhere((t) => t.title == title).status,
        value,
      );
    }

    Future<void> people() async {
      await account();
      await tap(find.text('Workspace people'));
      await waitFor(find.text(adminEmail).last);
    }

    Future<String> invite(String email) async {
      await tap(find.text('Invite user'));
      await tester.enterText(find.byType(TextFormField), email);
      await tap(find.text('Create invitation'));
      await waitFor(find.text('Invitation created'));
      final token = tester
          .widget<SelectableText>(find.byType(SelectableText))
          .data!;
      await tap(find.widgetWithText(TextButton, 'Done'));
      await waitFor(find.text(email));
      return token;
    }

    await binding.convertFlutterSurfaceToImage();
    await tester.pumpAndSettle();
    if (find.byTooltip('Sign out').evaluate().isNotEmpty) await logout();
    final firstWorkspace = 'Android QA $runId A';
    final secondWorkspace = 'Android QA $runId B';
    final projectA = 'Phone launch $runId';
    final projectB = 'Phone support $runId';
    final projectKeyA = 'A$runId';
    final projectKeyB = 'B$runId';
    final taskA = 'Android acceptance $runId';
    final taskB = 'Android priority $runId';
    final inviteEmail = 'android.qa.$runId@example.invalid';
    String memberToken = '';
    await record(
      'Sign in to deployed backend as PMS admin',
      () => login(adminEmail, adminPassword),
    );
    await record(
      'Create first workspace',
      () => createWorkspace(firstWorkspace),
    );
    await record(
      'Create second workspace',
      () => createWorkspace(secondWorkspace),
    );
    await record('Switch workspace and load owner permissions', () async {
      await workspace(firstWorkspace);
      expect(controller().selected!.role, 'Owner');
    }, screenshot: true);
    await record(
      'Create first project',
      () => createProject(projectA, projectKeyA),
    );
    await record(
      'Create second project',
      () => createProject(projectB, projectKeyB),
      screenshot: true,
    );
    await record(
      'Create task with description',
      () => createTask(projectA, taskA, '$projectKeyA-1'),
    );
    await record(
      'Create high priority task in another project',
      () => createTask(projectB, taskB, '$projectKeyB-1', priority: 'High'),
    );
    await record('Filter tasks by project', () async {
      await tap(find.byType(DropdownButtonFormField<int>).last);
      await tap(find.text(projectA).last);
      expect(find.widgetWithText(ListTile, taskA), findsOneWidget);
      expect(find.widgetWithText(ListTile, taskB), findsNothing);
    });
    await record('Search task by title across projects', () async {
      await tap(find.byType(DropdownButtonFormField<int>).last);
      await tap(find.text('All projects').last);
      await tester.enterText(find.byType(TextField).first, taskA);
      await tester.pumpAndSettle();
      expect(find.widgetWithText(ListTile, taskA), findsOneWidget);
      expect(find.widgetWithText(ListTile, taskB), findsNothing);
    });
    await record(
      'Change task to In Progress',
      () => status(taskA, 'In Progress'),
    );
    await record(
      'Complete task',
      () => status(taskA, 'Done'),
      screenshot: true,
    );
    await record('Refresh and confirm persisted task status', () async {
      await tap(find.byTooltip('Refresh workspaces'));
      expect(
        controller().overview!.tasks.firstWhere((t) => t.title == taskA).status,
        'Done',
      );
    });
    await record('Invite existing user to workspace', () async {
      await people();
      memberToken = await invite(memberEmail);
    });
    await record('Create second user invitation', () async {
      await invite(inviteEmail);
    });
    await record('Revoke pending invitation', () async {
      await tap(find.byTooltip('Revoke invitation for $inviteEmail'));
      await waitFor(find.text('Member · revoked'));
    }, screenshot: true);
    await record(
      'Accept invitation as member and add workspace user',
      () async {
        await tap(find.byTooltip('Back'));
        await logout();
        await login(memberEmail, memberPassword);
        await tap(find.byTooltip('Join workspace'));
        await tester.enterText(find.byType(TextField), memberToken);
        await tap(find.widgetWithText(FilledButton, 'Join'));
        await waitUntil(
          () => find.byType(AlertDialog).evaluate().isEmpty,
          'workspace invitation acceptance',
        );
        await waitFor(find.byTooltip('Refresh workspaces'));
        expect(controller().selected!.name, firstWorkspace);
        expect(controller().selected!.role, 'Member');
      },
    );
    await record(
      'Create a task with member permissions',
      () => createTask(projectA, 'Member task $runId', '$projectKeyA-2'),
      screenshot: true,
    );
    await record('Change member to Guest as workspace owner', () async {
      await logout();
      await login(adminEmail, adminPassword);
      await workspace(firstWorkspace);
      await people();
      await tap(find.byTooltip('Manage $memberEmail'));
      await tap(find.text('Set Guest'));
      await waitFor(find.text('Guest'));
    });
    await record('Guest can read but cannot mutate workspace tasks', () async {
      await tap(find.byTooltip('Back'));
      await logout();
      await login(memberEmail, memberPassword);
      await workspace(firstWorkspace);
      await tap(find.text('Tasks').last);
      expect(find.byType(FloatingActionButton), findsNothing);
      final taskId = controller().overview!.tasks
          .firstWhere((t) => t.title == taskA)
          .id;
      // Additional device-side API assertion confirms server enforcement beyond hidden buttons.
      try {
        await controller().repository.setStatus(taskId, 'To Do');
        fail('Guest mutation unexpectedly succeeded');
      } on ApiFailure catch (e) {
        expect(e.status, 403);
      }
      await tap(find.widgetWithText(ListTile, taskA));
      final button = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Save status'),
      );
      expect(button.onPressed, isNull);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
    }, screenshot: true);
    // Leave the phone signed into the owner account with its QA workspace open.
    await logout();
    await login(adminEmail, adminPassword);
    await workspace(firstWorkspace);
    await people();
    await tap(find.byTooltip('Manage $memberEmail'));
    await tap(find.text('Remove member'));
    await tap(find.widgetWithText(FilledButton, 'Remove'));
    await tester.pumpAndSettle();
    expect(
      find.text(memberEmail),
      findsOneWidget,
      reason: 'Accepted invitation remains in history; member is removed',
    );
    await tap(find.byTooltip('Back'));
    await tap(find.text('Projects').last);
    binding.reportData!['workspace_ids'] = controller().workspaces
        .where((w) => w.name.startsWith('Android QA $runId'))
        .map((w) => w.id)
        .toList();
    expect(operations.length, 20);
  }, timeout: const Timeout(Duration(minutes: 25)));
}
