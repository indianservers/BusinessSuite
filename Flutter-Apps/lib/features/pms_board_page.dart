import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../app_controller.dart';
import '../core/api_client.dart';
import '../core/models.dart';
import 'pms_catalog.dart';
import 'pms_native_views.dart';

class PmsBoardPage extends StatefulWidget {
  const PmsBoardPage({
    super.key,
    required this.controller,
    required this.projectId,
    required this.catalog,
    required this.openAction,
  });
  final AppController controller;
  final int projectId;
  final PmsCatalog catalog;
  final OpenPmsAction openAction;
  @override
  State<PmsBoardPage> createState() => _PmsBoardPageState();
}

class _PmsBoardPageState extends State<PmsBoardPage> {
  List<Json> _columns = [];
  final _selected = <int>{};
  bool _loading = false, _list = false;
  String? _error;
  AppController get c => widget.controller;
  Map<String, dynamic> get scope => {
    'project_id': widget.projectId,
    'workspace_id': c.selected!.id,
  };
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await c.api.request(
        'GET',
        '/project-management/projects/${widget.projectId}/board',
      );
      if (mounted) {
        setState(() {
          _columns = records(data['columns']);
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '$e';
          if (e is ApiFailure && const {403, 404}.contains(e.status)) {
            _columns = [];
            _selected.clear();
          }
        });
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _move(Json task, Json col, int position) async {
    if (_loading || c.selected?.canEdit != true) return;
    setState(() => _loading = true);
    try {
      final order = records(
        col['tasks'],
      ).where((t) => t['id'] != task['id']).toList();
      order.insert(position.clamp(0, order.length), task);
      for (final (i, row) in order.indexed) {
        if (row['id'] != task['id'] && row['position'] == i) continue;
        await c.api.request(
          'POST',
          '/project-management/projects/${widget.projectId}/board/reorder',
          data: {'task_id': row['id'], 'column_id': col['id'], 'position': i},
        );
      }
      await _load();
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _action(String action, Json task, Json col, int index) async {
    if (action == 'copy-id' || action == 'copy-link') {
      final origin = Uri.parse(c.api.dio.options.baseUrl).origin;
      await Clipboard.setData(
        ClipboardData(
          text: action == 'copy-id'
              ? '${task['id']}'
              : '$origin/pms/projects/${widget.projectId}/tasks/${task['id']}',
        ),
      );
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Copied')));
      }
    } else if (action == 'up' || action == 'down') {
      await _move(
        task,
        col,
        action == 'up' ? (index - 1).clamp(0, 100000) : index + 1,
      );
    } else {
      final duplicate = action == 'duplicate';
      final op = widget.catalog.find(
        duplicate ? 'POST' : 'GET',
        duplicate
            ? '/project-management/projects/{project_id}/tasks'
            : '/project-management/tasks/{task_id}',
      )!;
      final data = Map<String, dynamic>.from(task);
      if (duplicate) {
        data['title'] = '${task['title']} (copy)';
        data['task_key'] =
            '${task['task_key']}-copy-${DateTime.now().millisecondsSinceEpoch % 100000}';
      }
      await widget.openAction(op, {
        ...scope,
        'task_id': task['id'],
      }, duplicate ? data : {});
      if (mounted) await _load();
    }
  }

  Widget _task(Json task, Json col, int index) {
    final edit = c.selected?.canEdit == true;
    final card = Card(
      key: ValueKey('board-task-${task['id']}'),
      child: ListTile(
        leading: edit
            ? Checkbox(
                value: _selected.contains(task['id']),
                onChanged: _loading
                    ? null
                    : (v) => setState(() {
                        v == true
                            ? _selected.add(task['id'])
                            : _selected.remove(task['id']);
                      }),
              )
            : null,
        title: Text('${task['title']}'),
        subtitle: Text('${task['task_key']} · ${task['priority']}'),
        onTap: () => _action('open', task, col, index),
        onLongPress: edit ? null : () => _action('open', task, col, index),
        trailing: PopupMenuButton<String>(
          tooltip: 'Task actions ${task['task_key']}',
          onSelected: (v) => _action(v, task, col, index),
          itemBuilder: (_) => [
            const PopupMenuItem(value: 'open', child: Text('Open task')),
            const PopupMenuItem(value: 'copy-id', child: Text('Copy task ID')),
            const PopupMenuItem(
              value: 'copy-link',
              child: Text('Copy task link'),
            ),
            if (edit) ...[
              const PopupMenuItem(
                value: 'duplicate',
                child: Text('Duplicate task'),
              ),
              const PopupMenuItem(value: 'up', child: Text('Move up')),
              const PopupMenuItem(value: 'down', child: Text('Move down')),
            ],
          ],
        ),
      ),
    );
    if (!edit || _loading) return card;
    return LongPressDraggable<Json>(
      data: task,
      feedback: Material(
        elevation: 8,
        child: SizedBox(
          width: 260,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Text('${task['title']}'),
          ),
        ),
      ),
      childWhenDragging: Opacity(opacity: .35, child: card),
      child: card,
    );
  }

  Widget _column(Json col) {
    final tasks = records(col['tasks']);
    return DragTarget<Json>(
      onWillAcceptWithDetails: (_) => !_loading && c.selected?.canEdit == true,
      onAcceptWithDetails: (d) => _move(d.data, col, tasks.length),
      builder: (context, candidates, rejected) => Container(
        key: ValueKey('board-column-${col['id']}'),
        width: 310,
        margin: const EdgeInsets.all(8),
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: candidates.isEmpty
              ? Theme.of(context).colorScheme.surfaceContainerLow
              : Theme.of(context).colorScheme.primaryContainer,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.all(12),
              child: Text(
                '${col['name']} (${tasks.length})',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            Expanded(
              child: ListView(
                children: [
                  for (final (i, task) in tasks.indexed) _task(task, col, i),
                  if (tasks.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(20),
                      child: Text('Drop a task here'),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        _selected.isEmpty ? 'Project board' : '${_selected.length} selected',
      ),
      actions: [
        if (_selected.isNotEmpty)
          IconButton(
            tooltip: 'Edit selected tasks',
            onPressed: () async {
              await widget.openAction(
                widget.catalog.find('PATCH', '/project-management/tasks/bulk')!,
                scope,
                {'task_ids': _selected.toList()},
              );
              if (mounted) {
                setState(_selected.clear);
                await _load();
              }
            },
            icon: const Icon(Icons.edit),
          ),
        IconButton(
          tooltip: _list ? 'Board layout' : 'List layout',
          onPressed: () => setState(() => _list = !_list),
          icon: Icon(_list ? Icons.view_kanban : Icons.view_list),
        ),
        IconButton(
          tooltip: 'Refresh board',
          onPressed: _loading ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: Column(
      children: [
        if (_loading) const LinearProgressIndicator(),
        if (_error != null)
          Padding(padding: const EdgeInsets.all(12), child: Text(_error!)),
        Expanded(
          child: _list
              ? ListView(
                  children: [
                    for (final col in _columns) ...[
                      ListTile(title: Text('${col['name']}')),
                      for (final (i, task) in records(col['tasks']).indexed)
                        _task(task, col, i),
                    ],
                  ],
                )
              : SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: _columns.map(_column).toList(),
                  ),
                ),
        ),
      ],
    ),
  );
}
