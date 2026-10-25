import 'package:flutter/material.dart';
import '../app_controller.dart';
import '../core/api_client.dart';
import '../core/models.dart';
import 'pms_catalog.dart';
import 'pms_native_views.dart';

class PmsPlannerPage extends StatefulWidget {
  const PmsPlannerPage({
    super.key,
    required this.controller,
    required this.catalog,
    required this.openAction,
    this.projectId,
  });
  final AppController controller;
  final PmsCatalog catalog;
  final OpenPmsAction openAction;
  final int? projectId;
  @override
  State<PmsPlannerPage> createState() => _PmsPlannerPageState();
}

class _PmsPlannerPageState extends State<PmsPlannerPage> {
  DateTime _day = DateUtils.dateOnly(DateTime.now());
  String _view = 'Month', _search = '';
  List<Json> _tasks = [], _events = [], _projects = [];
  bool _loading = false;
  String? _error;
  int? _projectId;
  AppController get c => widget.controller;
  String date(DateTime d) => d.toIso8601String().split('T').first;
  Map<String, dynamic> get scope => {
    'workspace_id': c.selected!.id,
    if (_projectId != null) 'project_id': _projectId,
  };
  @override
  void initState() {
    super.initState();
    _projectId = widget.projectId;
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final first = DateTime(
            _day.year,
            _day.month,
            1,
          ).subtract(const Duration(days: 7)),
          last = DateTime(
            _day.year,
            _day.month + 1,
            1,
          ).add(const Duration(days: 7));
      final data = await c.api.request('GET', '/project-management/planner');
      final events = await c.api.request(
        'GET',
        '/project-management/planner/events',
        query: {
          'start': first.toUtc().toIso8601String(),
          'end': last.toUtc().toIso8601String(),
        },
      );
      final projects = records(
        data['projects'],
      ).where((p) => p['workspace_id'] == c.selected?.id).toList();
      final projectIds = projects.map((p) => p['id']).toSet();
      if (mounted) {
        setState(() {
          _projects = projects;
          _tasks = records(
            data['tasks'],
          ).where((t) => projectIds.contains(t['project_id'])).toList();
          _events = records(events)
              .where(
                (e) =>
                    e['workspace_id'] == null ||
                    e['workspace_id'] == c.selected?.id,
              )
              .toList();
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '$e';
          if (e is ApiFailure && const {403, 404}.contains(e.status)) {
            _tasks = [];
            _events = [];
          }
        });
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  bool _matches(Json row) =>
      '${row['title']} ${row['task_key'] ?? ''}'.toLowerCase().contains(
        _search.toLowerCase(),
      ) &&
      (_projectId == null ||
          row['project_id'] == _projectId ||
          row['project_id'] == null);
  List<Json> _items(DateTime day) => [
    ..._tasks
        .where(
          (t) =>
              _matches(t) &&
              '${t['due_date'] ?? t['start_date']}'.startsWith(date(day)),
        )
        .map((t) => {...t, '_task': true}),
    ..._events.where(
      (e) =>
          _matches(e) &&
          DateUtils.isSameDay(
            DateTime.tryParse('${e['start_at']}')?.toLocal(),
            day,
          ),
    ),
  ];
  Future<void> _reschedule(Json task, DateTime day) async {
    if (_loading ||
        task['can_schedule'] != true ||
        c.selected?.canEdit != true) {
      return;
    }
    setState(() => _loading = true);
    try {
      final due = DateTime.tryParse('${task['due_date']}'),
          start = DateTime.tryParse('${task['start_date']}');
      await c.api.request(
        'PATCH',
        '/project-management/tasks/${task['id']}/schedule',
        data: {
          'due_date': date(day),
          if (start != null && due != null)
            'start_date': date(start.add(day.difference(due))),
        },
      );
      await _load();
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create(bool task) async {
    if (task && _projectId == null) {
      setState(() => _error = 'Choose a project before creating a task.');
      return;
    }
    final initial = task
        ? {
            'due_date': date(_day),
            'task_key': 'TASK-${DateTime.now().millisecondsSinceEpoch}',
          }
        : {
            'start_at': DateTime(
              _day.year,
              _day.month,
              _day.day,
              9,
            ).toUtc().toIso8601String(),
            'end_at': DateTime(
              _day.year,
              _day.month,
              _day.day,
              10,
            ).toUtc().toIso8601String(),
            'timezone': 'UTC',
          };
    await widget.openAction(
      widget.catalog.find(
        'POST',
        task
            ? '/project-management/projects/{project_id}/tasks'
            : '/project-management/planner/events',
      )!,
      scope,
      initial,
    );
    if (mounted) await _load();
  }

  Future<void> _open(Json row) async {
    if (row['_task'] == true) {
      await widget.openAction(
        widget.catalog.find('GET', '/project-management/tasks/{task_id}')!,
        {...scope, 'project_id': row['project_id'], 'task_id': row['id']},
        {},
      );
    } else {
      final action = await showModalBottomSheet<String>(
        context: context,
        builder: (context) => SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                title: Text('${row['title']}'),
                subtitle: Text('${row['start_at']} – ${row['end_at']}'),
              ),
              if (c.selected?.canEdit == true) ...[
                ListTile(
                  title: const Text('Edit event'),
                  onTap: () => Navigator.pop(context, 'PUT'),
                ),
                ListTile(
                  title: const Text('Delete event'),
                  onTap: () => Navigator.pop(context, 'DELETE'),
                ),
              ],
            ],
          ),
        ),
      );
      if (action != null) {
        await widget.openAction(
          widget.catalog.find(
            action,
            '/project-management/planner/events/{event_id}',
          )!,
          {...scope, 'event_id': row['id']},
          row,
        );
      }
    }
    if (mounted) await _load();
  }

  Widget _dayCell(DateTime day) {
    final count = _items(day).length;
    return DragTarget<Json>(
      onWillAcceptWithDetails: (_) => !_loading && c.selected?.canEdit == true,
      onAcceptWithDetails: (d) => _reschedule(d.data, day),
      builder: (context, candidates, rejected) => InkWell(
        key: ValueKey('calendar-day-${date(day)}'),
        onTap: () => setState(() => _day = day),
        child: Container(
          margin: const EdgeInsets.all(2),
          decoration: BoxDecoration(
            border: Border.all(
              color: Theme.of(context).colorScheme.outlineVariant,
            ),
            color: candidates.isNotEmpty || DateUtils.isSameDay(day, _day)
                ? Theme.of(context).colorScheme.primaryContainer
                : null,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('${day.day}'),
              if (count > 0)
                Text(
                  '$count items',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _item(Json row) {
    final tile = Card(
      child: ListTile(
        title: Text('${row['title']}'),
        subtitle: Text(
          row['_task'] == true
              ? '${row['task_key']} · ${row['status']}'
              : '${row['kind']} · ${row['start_at']}',
        ),
        onTap: () => _open(row),
        trailing: const Icon(Icons.chevron_right),
      ),
    );
    return row['_task'] == true &&
            row['can_schedule'] == true &&
            c.selected?.canEdit == true &&
            !_loading
        ? LongPressDraggable<Json>(
            data: row,
            feedback: Material(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text('${row['title']}'),
              ),
            ),
            childWhenDragging: Opacity(opacity: .4, child: tile),
            child: tile,
          )
        : tile;
  }

  Future<void> _navigate(int step) async {
    setState(
      () => _day = _view == 'Month'
          ? DateTime(_day.year, _day.month + step, 1)
          : _day.add(Duration(days: step * (_view == 'Week' ? 7 : 1))),
    );
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final month = DateTime(_day.year, _day.month),
        days = DateTime(_day.year, _day.month + 1, 0).day;
    final agenda = _view == 'Week'
        ? List.generate(
            7,
            (i) => _day
                .subtract(Duration(days: _day.weekday - 1))
                .add(Duration(days: i)),
          )
        : [_day];
    return Scaffold(
      appBar: AppBar(
        title: const Text('Calendar & planner'),
        actions: [
          IconButton(
            tooltip: 'Planner preferences',
            icon: const Icon(Icons.settings),
            onPressed: () => widget.openAction(
              widget.catalog.find(
                'GET',
                '/project-management/planner/preferences',
              )!,
              scope,
              {},
            ),
          ),
          IconButton(
            tooltip: 'Refresh calendar',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_loading) const LinearProgressIndicator(),
          if (_error != null)
            Padding(padding: const EdgeInsets.all(8), child: Text(_error!)),
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              decoration: const InputDecoration(labelText: 'Search planner'),
              onChanged: (v) => setState(() => _search = v),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: DropdownButtonFormField<int>(
              initialValue: _projectId,
              decoration: const InputDecoration(labelText: 'Project'),
              items: [
                const DropdownMenuItem<int>(
                  value: null,
                  child: Text('All workspace projects'),
                ),
                ..._projects.map(
                  (p) => DropdownMenuItem<int>(
                    value: p['id'],
                    child: Text('${p['name']}'),
                  ),
                ),
              ],
              onChanged: (v) => setState(() => _projectId = v),
            ),
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                tooltip: 'Previous period',
                onPressed: () => _navigate(-1),
                icon: const Icon(Icons.chevron_left),
              ),
              Text('${_day.year}-${_day.month.toString().padLeft(2, '0')}'),
              TextButton(
                onPressed: () async {
                  setState(() => _day = DateUtils.dateOnly(DateTime.now()));
                  await _load();
                },
                child: const Text('Today'),
              ),
              IconButton(
                tooltip: 'Next period',
                onPressed: () => _navigate(1),
                icon: const Icon(Icons.chevron_right),
              ),
              DropdownButton<String>(
                value: _view,
                items: const ['Month', 'Week', 'Day', 'Agenda']
                    .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                    .toList(),
                onChanged: (v) => setState(() => _view = v!),
              ),
            ],
          ),
          Expanded(
            child: ListView(
              children: [
                if (_view == 'Month')
                  GridView.count(
                    crossAxisCount: 7,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    children: [
                      for (var i = 1; i < month.weekday; i++) const SizedBox(),
                      for (var d = 1; d <= days; d++)
                        _dayCell(DateTime(_day.year, _day.month, d)),
                    ],
                  ),
                for (final day in agenda) ...[
                  ListTile(title: Text(date(day))),
                  if (_items(day).isEmpty)
                    const ListTile(title: Text('No scheduled items')),
                  ..._items(day).map(_item),
                ],
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: c.selected?.canEdit == true
          ? PopupMenuButton<bool>(
              tooltip: 'Create calendar item',
              icon: const Icon(Icons.add_circle, size: 48),
              onSelected: _create,
              itemBuilder: (_) => const [
                PopupMenuItem(value: true, child: Text('Create task')),
                PopupMenuItem(value: false, child: Text('Create event')),
              ],
            )
          : null,
    );
  }
}
