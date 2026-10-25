import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../core/models.dart';
import 'people_page.dart';
import 'pms_feature_hub.dart';

class WorkspacePage extends StatefulWidget {
  const WorkspacePage({super.key, required this.controller});
  final AppController controller;
  @override
  State<WorkspacePage> createState() => _WorkspacePageState();
}

class _WorkspacePageState extends State<WorkspacePage> {
  int _tab = 0;
  String _query = '';
  int? _projectId;
  int? _workspaceId;
  final _search = TextEditingController();
  AppController get c => widget.controller;
  Future<void> _join() async {
    var token = '', saving = false;
    String? error;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialog) => StatefulBuilder(
        builder: (context, update) => PopScope(
          canPop: !saving,
          child: AlertDialog(
            title: const Text('Join workspace'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Sign in with the invited email, then paste your private invitation token.',
                ),
                const SizedBox(height: 16),
                TextField(
                  decoration: const InputDecoration(
                    labelText: 'Invitation token',
                  ),
                  enabled: !saving,
                  onChanged: (v) => token = v.trim(),
                ),
                if (error != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(error!),
                  ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(dialog),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        if (token.length < 20) {
                          update(
                            () => error = 'Enter a valid invitation token',
                          );
                          return;
                        }
                        update(() {
                          saving = true;
                          error = null;
                        });
                        try {
                          final id = await c.repository.acceptInvitation(token);
                          await c.loadAccount();
                          final workspace = c.workspaces
                              .where((w) => w.id == id)
                              .firstOrNull;
                          if (workspace != null) {
                            await c.selectWorkspace(workspace);
                          }
                          if (dialog.mounted) Navigator.pop(dialog);
                        } catch (e) {
                          if (dialog.mounted) {
                            update(() {
                              saving = false;
                              error = '$e';
                            });
                          }
                        }
                      },
                child: Text(saving ? 'Joining…' : 'Join'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _create(String kind) async {
    final workspace = c.selected;
    final projects = c.overview?.projects ?? <Project>[];
    final title = TextEditingController();
    final key = TextEditingController();
    final description = TextEditingController();
    final form = GlobalKey<FormState>();
    int? projectId = _projectId ?? projects.firstOrNull?.id;
    var priority = 'Medium';
    String? error;
    var saving = false;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) => PopScope(
          canPop: !saving,
          child: AlertDialog(
            title: Text('Create $kind'),
            content: SizedBox(
              width: 420,
              child: SingleChildScrollView(
                child: Form(
                  key: form,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (kind == 'task') ...[
                        DropdownButtonFormField<int>(
                          initialValue: projectId,
                          decoration: const InputDecoration(
                            labelText: 'Project',
                          ),
                          isExpanded: true,
                          items: projects
                              .map(
                                (p) => DropdownMenuItem(
                                  value: p.id,
                                  child: Text(p.name),
                                ),
                              )
                              .toList(),
                          onChanged: saving
                              ? null
                              : (id) => update(() => projectId = id),
                          validator: (v) =>
                              v == null ? 'Choose a project' : null,
                        ),
                        const SizedBox(height: 12),
                      ],
                      TextFormField(
                        controller: title,
                        enabled: !saving,
                        autofocus: true,
                        maxLength: kind == 'task' ? 220 : 180,
                        decoration: InputDecoration(
                          labelText: kind == 'task' ? 'Task title' : 'Name',
                        ),
                        validator: (v) => v == null || v.trim().isEmpty
                            ? 'Enter a name'
                            : null,
                      ),
                      if (kind != 'workspace') ...[
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: key,
                          enabled: !saving,
                          textCapitalization: TextCapitalization.characters,
                          maxLength: kind == 'task' ? 30 : 20,
                          decoration: InputDecoration(
                            labelText: kind == 'task'
                                ? 'Task key'
                                : 'Project key',
                            hintText: kind == 'task' ? 'APP-101' : 'APP',
                          ),
                          validator: (v) =>
                              v == null ||
                                  !RegExp(
                                    r'^[A-Za-z0-9][A-Za-z0-9_-]*$',
                                  ).hasMatch(v.trim())
                              ? 'Use letters, numbers, hyphens, or underscores'
                              : null,
                        ),
                      ],
                      if (kind == 'task') ...[
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: description,
                          enabled: !saving,
                          maxLines: 3,
                          decoration: const InputDecoration(
                            labelText: 'Description (optional)',
                          ),
                        ),
                        const SizedBox(height: 12),
                        DropdownButtonFormField<String>(
                          initialValue: priority,
                          decoration: const InputDecoration(
                            labelText: 'Priority',
                          ),
                          items: const ['Low', 'Medium', 'High', 'Critical']
                              .map(
                                (p) =>
                                    DropdownMenuItem(value: p, child: Text(p)),
                              )
                              .toList(),
                          onChanged: saving ? null : (p) => priority = p!,
                        ),
                      ],
                      if (error != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 12),
                          child: Text(
                            error!,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.error,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(dialogContext),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        if (!form.currentState!.validate()) return;
                        update(() {
                          saving = true;
                          error = null;
                        });
                        try {
                          if (kind == 'workspace') {
                            await c.repository.createWorkspace(
                              title.text.trim(),
                            );
                          } else if (workspace == null ||
                              c.selected?.id != workspace.id ||
                              c.overview == null) {
                            throw StateError(
                              'Workspace access changed. Reopen this form.',
                            );
                          } else if (kind == 'project') {
                            if (!c.selected!.canManage) {
                              throw StateError(
                                'Workspace administrator required.',
                              );
                            }
                            await c.repository.createProject(
                              workspace.id,
                              title.text.trim(),
                              key.text.trim().toUpperCase(),
                            );
                          } else {
                            if (!c.selected!.canEdit) {
                              throw StateError('Workspace is read-only.');
                            }
                            await c.repository.createTask(
                              projectId!,
                              title: title.text.trim(),
                              key: key.text.trim().toUpperCase(),
                              description: description.text.trim(),
                              priority: priority,
                            );
                          }
                          if (!dialogContext.mounted) return;
                          Navigator.pop(dialogContext);
                          await c.loadAccount();
                        } catch (e) {
                          if (dialogContext.mounted) {
                            update(() {
                              error = '$e';
                              saving = false;
                            });
                          }
                        }
                      },
                child: Text(saving ? 'Saving…' : 'Create'),
              ),
            ],
          ),
        ),
      ),
    );
    // Wait for the dialog route animation before disposing field controllers.
    await Future<void>.delayed(const Duration(milliseconds: 300));
    title.dispose();
    key.dispose();
    description.dispose();
  }

  Future<void> _taskDetail(WorkTask summary) async {
    final workspaceId = c.selected?.id;
    FocusManager.instance.primaryFocus?.unfocus();
    final task = await c.taskDetails(summary.id);
    if (!mounted || task == null || c.selected?.id != workspaceId) return;
    var status = task.status;
    var saving = false;
    String? error;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, update) {
          final editable =
              c.selected?.id == workspaceId &&
              c.overview != null &&
              c.selected!.canEdit &&
              !c.busy;
          return PopScope(
            canPop: !saving,
            child: Padding(
              padding: EdgeInsets.fromLTRB(
                24,
                24,
                24,
                MediaQuery.viewInsetsOf(context).bottom + 24,
              ),
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      task.key,
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      task.title,
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      task.description.isEmpty
                          ? 'No description provided.'
                          : task.description,
                    ),
                    const SizedBox(height: 16),
                    Text('Priority: ${task.priority}'),
                    if (task.dueDate != null) Text('Due: ${task.dueDate}'),
                    const SizedBox(height: 20),
                    DropdownButtonFormField<String>(
                      initialValue: status,
                      decoration: const InputDecoration(labelText: 'Status'),
                      items:
                          {
                                task.status,
                                'To Do',
                                'In Progress',
                                'In Review',
                                'Blocked',
                                'Done',
                              }
                              .map(
                                (s) =>
                                    DropdownMenuItem(value: s, child: Text(s)),
                              )
                              .toList(),
                      onChanged: editable && !saving
                          ? (s) => update(() => status = s!)
                          : null,
                    ),
                    if (!editable)
                      const Padding(
                        padding: EdgeInsets.only(top: 12),
                        child: Text(
                          'Your current workspace access is read-only.',
                        ),
                      ),
                    if (error != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Text(
                          error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: !editable || saving
                          ? null
                          : () async {
                              update(() {
                                saving = true;
                                error = null;
                              });
                              final ok = await c.mutate(
                                () => c.repository.setStatus(task.id, status),
                              );
                              if (!sheetContext.mounted) return;
                              if (ok) {
                                Navigator.pop(sheetContext);
                              } else {
                                update(() {
                                  saving = false;
                                  error = c.error ?? 'Unable to save.';
                                });
                              }
                            },
                      child: Text(saving ? 'Saving…' : 'Save status'),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: saving
                          ? null
                          : () async {
                              Navigator.pop(sheetContext);
                              await Navigator.of(this.context).push(
                                MaterialPageRoute<void>(
                                  builder: (_) =>
                                      PmsFeatureHub(controller: c, task: task),
                                ),
                              );
                              if (c.selected != null) {
                                await c.selectWorkspace(c.selected!);
                              }
                            },
                      icon: const Icon(Icons.apps),
                      label: const Text('More task actions'),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_workspaceId != c.selected?.id) {
      _workspaceId = c.selected?.id;
      _projectId = null;
      _query = '';
      _search.clear();
    }
    final overview = c.overview;
    final projects = overview?.projects ?? <Project>[];
    final tasks = (overview?.tasks ?? <WorkTask>[])
        .where(
          (t) =>
              (_projectId == null || t.projectId == _projectId) &&
              '${t.key} ${t.title}'.toLowerCase().contains(
                _query.toLowerCase(),
              ),
        )
        .toList();
    final editable =
        !c.loading && !c.busy && overview != null && c.selected!.canEdit;
    return Scaffold(
      appBar: AppBar(
        title: const Text('KaryaFlow'),
        actions: [
          IconButton(
            tooltip: 'PMS features',
            onPressed: c.loading || c.busy || c.selected == null
                ? null
                : () async {
                    await Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => PmsFeatureHub(controller: c),
                      ),
                    );
                    if (c.selected != null) {
                      await c.selectWorkspace(c.selected!);
                    }
                  },
            icon: const Icon(Icons.apps),
          ),
          IconButton(
            tooltip: 'Join workspace',
            onPressed: c.loading || c.busy ? null : _join,
            icon: const Icon(Icons.group_add_outlined),
          ),
          IconButton(
            tooltip: 'Refresh workspaces',
            onPressed: c.loading || c.busy ? null : c.loadAccount,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Sign out',
            onPressed: c.busy ? null : c.signOut,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    c.user!.email,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 12),
                  if (c.workspaces.isNotEmpty)
                    DropdownButtonFormField<int>(
                      key: ValueKey(c.selected?.id),
                      initialValue: c.selected?.id,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Workspace'),
                      items: c.workspaces
                          .map(
                            (w) => DropdownMenuItem(
                              value: w.id,
                              child: Text(
                                w.name,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: c.loading || c.busy
                          ? null
                          : (id) => c.selectWorkspace(
                              c.workspaces.firstWhere((w) => w.id == id),
                            ),
                    ),
                  if (c.selected != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(
                        '${c.selected!.role} access${c.selected!.role == 'Guest' ? ' · Read only' : ''}',
                      ),
                    ),
                ],
              ),
            ),
            if (c.error != null)
              MaterialBanner(
                content: Text(c.error!),
                actions: [
                  TextButton(
                    onPressed: c.loading || c.busy ? null : c.loadAccount,
                    child: const Text('Retry'),
                  ),
                ],
              ),
            if (c.loading || c.busy) const LinearProgressIndicator(),
            Expanded(
              child: c.loading
                  ? const Center(child: Text('Loading your workspace…'))
                  : c.selected == null
                  ? _empty(
                      'Your team starts here',
                      'Ask your PMS administrator for workspace access, or create a workspace if your role allows it.',
                    )
                  : overview == null
                  ? _empty(
                      'Workspace unavailable',
                      'Refresh to reload your membership and projects.',
                    )
                  : _tab == 2
                  ? ListView(
                      padding: const EdgeInsets.all(20),
                      children: [
                        Text(
                          'Account & access',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        ListTile(
                          title: const Text('Account'),
                          subtitle: Text(c.user!.email),
                        ),
                        ListTile(
                          title: const Text('PMS role'),
                          subtitle: Text(c.user!.role),
                        ),
                        ListTile(
                          title: const Text('Workspace membership'),
                          subtitle: Text(c.selected!.role),
                        ),
                        const Text(
                          'Workspace permissions come from your server membership. Guests can browse; members can work on tasks; owners and administrators can create projects.',
                        ),
                        const SizedBox(height: 20),
                        OutlinedButton.icon(
                          onPressed: c.busy
                              ? null
                              : () => Navigator.of(context).push(
                                  MaterialPageRoute<void>(
                                    builder: (_) => PeoplePage(
                                      controller: c,
                                      workspace: c.selected!,
                                    ),
                                  ),
                                ),
                          icon: const Icon(Icons.people_outline),
                          label: const Text('Workspace people'),
                        ),
                        const SizedBox(height: 12),
                        if (c.user!.canCreateWorkspace)
                          OutlinedButton.icon(
                            onPressed: c.busy
                                ? null
                                : () => _create('workspace'),
                            icon: const Icon(Icons.add),
                            label: const Text('Create workspace'),
                          ),
                      ],
                    )
                  : RefreshIndicator(
                      onRefresh: c.loadAccount,
                      child: ListView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        keyboardDismissBehavior:
                            ScrollViewKeyboardDismissBehavior.onDrag,
                        padding: const EdgeInsets.all(20),
                        children: [
                          Text(
                            _tab == 0 ? 'Projects' : 'Team tasks',
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '${projects.length} projects · ${overview.tasks.where((t) => !t.isDone).length} open tasks',
                          ),
                          const SizedBox(height: 20),
                          if (_tab == 0) ...[
                            if (projects.isEmpty)
                              const Text(
                                'No projects yet. A workspace owner or administrator can create the first project.',
                              ),
                            ...projects.map((p) {
                              final projectTasks = overview.tasks
                                  .where((t) => t.projectId == p.id)
                                  .toList();
                              return Card(
                                child: ListTile(
                                  contentPadding: const EdgeInsets.all(16),
                                  leading: const Icon(Icons.folder_outlined),
                                  title: Text(p.name),
                                  subtitle: Text(
                                    '${p.key} · ${projectTasks.where((t) => !t.isDone).length} open tasks',
                                  ),
                                  trailing: IconButton(
                                    tooltip: 'Project features for ${p.name}',
                                    icon: const Icon(Icons.more_horiz),
                                    onPressed: () async {
                                      await Navigator.of(context).push(
                                        MaterialPageRoute<void>(
                                          builder: (_) => PmsFeatureHub(
                                            controller: c,
                                            project: p,
                                          ),
                                        ),
                                      );
                                      if (c.selected != null) {
                                        await c.selectWorkspace(c.selected!);
                                      }
                                    },
                                  ),
                                  onTap: () => setState(() {
                                    _projectId = p.id;
                                    _tab = 1;
                                  }),
                                ),
                              );
                            }),
                          ] else ...[
                            TextField(
                              controller: _search,
                              textInputAction: TextInputAction.search,
                              onSubmitted: (_) =>
                                  FocusManager.instance.primaryFocus?.unfocus(),
                              decoration: const InputDecoration(
                                labelText: 'Search tasks',
                                prefixIcon: Icon(Icons.search),
                              ),
                              onChanged: (v) => setState(() => _query = v),
                            ),
                            const SizedBox(height: 12),
                            DropdownButtonFormField<int>(
                              key: ValueKey('filter-$_projectId'),
                              initialValue: _projectId,
                              decoration: const InputDecoration(
                                labelText: 'Project filter',
                              ),
                              isExpanded: true,
                              items: [
                                const DropdownMenuItem<int>(
                                  value: null,
                                  child: Text('All projects'),
                                ),
                                ...projects.map(
                                  (p) => DropdownMenuItem(
                                    value: p.id,
                                    child: Text(p.name),
                                  ),
                                ),
                              ],
                              onChanged: (id) =>
                                  setState(() => _projectId = id),
                            ),
                            const SizedBox(height: 16),
                            if (tasks.isEmpty)
                              const Text('No tasks match this view.'),
                            ...tasks.map(
                              (t) => Card(
                                child: ListTile(
                                  leading: Icon(
                                    t.isDone
                                        ? Icons.check_circle_outline
                                        : Icons.radio_button_unchecked,
                                  ),
                                  title: Text(t.title),
                                  subtitle: Text(
                                    '${t.key} · ${t.status} · ${t.priority}',
                                  ),
                                  trailing: const Icon(Icons.chevron_right),
                                  onTap: () => _taskDetail(t),
                                ),
                              ),
                            ),
                          ],
                          const SizedBox(height: 90),
                        ],
                      ),
                    ),
            ),
          ],
        ),
      ),
      floatingActionButton:
          editable &&
              (_tab == 1
                  ? projects.isNotEmpty
                  : _tab == 0 && c.selected!.canManage)
          ? FloatingActionButton.extended(
              onPressed: () => _create(_tab == 0 ? 'project' : 'task'),
              icon: const Icon(Icons.add),
              label: Text(_tab == 0 ? 'Project' : 'Task'),
            )
          : c.selected == null && c.user!.canCreateWorkspace && !c.loading
          ? FloatingActionButton.extended(
              onPressed: () => _create('workspace'),
              icon: const Icon(Icons.add),
              label: const Text('Workspace'),
            )
          : null,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (index) => setState(() => _tab = index),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.folder_outlined),
            label: 'Projects',
          ),
          NavigationDestination(icon: Icon(Icons.checklist), label: 'Tasks'),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            label: 'Account',
          ),
        ],
      ),
    );
  }

  Widget _empty(String title, String body) => Center(
    child: SingleChildScrollView(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.workspaces_outline, size: 48),
          const SizedBox(height: 16),
          Text(
            title,
            style: Theme.of(context).textTheme.titleLarge,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),
          Text(body, textAlign: TextAlign.center),
        ],
      ),
    ),
  );
}
