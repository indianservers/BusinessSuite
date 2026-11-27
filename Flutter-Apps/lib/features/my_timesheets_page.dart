import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class MyTimesheetsPage extends StatefulWidget {
  const MyTimesheetsPage({
    super.key,
    required this.api,
    required this.employeeId,
    required this.canCreate,
  });

  final ApiClient api;
  final int? employeeId;
  final bool canCreate;

  @override
  State<MyTimesheetsPage> createState() => _MyTimesheetsPageState();
}

class _MyTimesheetsPageState extends State<MyTimesheetsPage> {
  late var _data = _load();
  bool _busy = false;
  int? _selected;

  String _date(DateTime value) => value.toIso8601String().split('T').first;

  Future<({List<Json> projects, List<Json> sheets})> _load() async {
    final api = widget.api;
    final revision = api.sessionRevision;
    final employee = widget.employeeId;
    if (employee == null) return (projects: <Json>[], sheets: <Json>[]);
    final results = await Future.wait([
      api.request('GET', '/timesheets/projects'),
      api.request('GET', '/timesheets/', query: {'employee_id': employee}),
    ]);
    if (revision != api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    return (
      projects: (results[0] as List).cast<Json>(),
      sheets: (results[1] as List)
          .cast<Json>()
          .where((sheet) => sheet['employee_id'] == employee)
          .toList(),
    );
  }

  Future<void> _save(String method, String path, {Json? data}) async {
    final api = widget.api;
    final revision = api.sessionRevision;
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final result = await api.request(method, path, data: data);
      if (!mounted || revision != api.sessionRevision) return;
      setState(() {
        if (path == '/timesheets/' && result is Json) {
          _selected = result['id'] as int?;
        }
        _data = _load();
      });
    } on ApiFailure catch (error) {
      if (!mounted || revision != api.sessionRevision) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _create(List<Json> projects) async {
    final revision = widget.api.sessionRevision;
    final today = DateUtils.dateOnly(DateTime.now());
    final start = DateUtils.addDaysToDate(today, 1 - today.weekday);
    var period = DateTimeRange(
      start: start,
      end: DateUtils.addDaysToDate(start, 6),
    );
    int? projectId;
    final data = await showDialog<Json>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('New timesheet'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              DropdownButtonFormField<int>(
                initialValue: projectId,
                decoration: const InputDecoration(labelText: 'Project'),
                isExpanded: true,
                items: [
                  for (final project in projects)
                    DropdownMenuItem(
                      value: project['id'] as int,
                      child: Text('${project['name']}'),
                    ),
                ],
                onChanged: (id) => update(() => projectId = id),
              ),
              TextButton(
                onPressed: () async {
                  final selected = await showDateRangePicker(
                    context: context,
                    firstDate: DateTime(2000),
                    lastDate: DateTime(2100, 12, 31),
                    initialDateRange: period,
                    helpText: 'Timesheet period',
                  );
                  if (context.mounted && selected != null) {
                    update(() => period = selected);
                  }
                },
                child: Text('${_date(period.start)} – ${_date(period.end)}'),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: projectId == null
                  ? null
                  : () => Navigator.pop(context, <String, dynamic>{
                      'project_id': projectId,
                      'period_start': _date(period.start),
                      'period_end': _date(period.end),
                    }),
              child: const Text('Create timesheet'),
            ),
          ],
        ),
      ),
    );
    if (!mounted || data == null || revision != widget.api.sessionRevision) {
      return;
    }
    await _save('POST', '/timesheets/', data: data);
  }

  Future<void> _addEntry(Json sheet) async {
    final revision = widget.api.sessionRevision;
    final start = DateTime.parse(sheet['period_start'] as String);
    final end = DateTime.parse(sheet['period_end'] as String);
    final today = DateUtils.dateOnly(DateTime.now());
    var date = today.isBefore(start) || today.isAfter(end) ? start : today;
    var hours = '8';
    var task = '';
    var billable = true;
    final form = GlobalKey<FormState>();
    final data = await showDialog<Json>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          scrollable: true,
          title: const Text('Add timesheet entry'),
          content: Form(
            key: form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextButton(
                  onPressed: () async {
                    final selected = await showDatePicker(
                      context: context,
                      initialDate: date,
                      firstDate: start,
                      lastDate: end,
                    );
                    if (context.mounted && selected != null) {
                      update(() => date = selected);
                    }
                  },
                  child: Text('Work date · ${_date(date)}'),
                ),
                TextFormField(
                  initialValue: hours,
                  decoration: const InputDecoration(labelText: 'Hours'),
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  onChanged: (value) => hours = value.trim(),
                  validator: (text) {
                    final value = num.tryParse(text?.trim() ?? '');
                    return value == null ||
                            !value.isFinite ||
                            value <= 0 ||
                            value > 24
                        ? 'Enter hours greater than 0 and up to 24.'
                        : null;
                  },
                ),
                TextFormField(
                  decoration: const InputDecoration(labelText: 'Task'),
                  onChanged: (value) => task = value.trim(),
                ),
                SwitchListTile(
                  title: const Text('Billable'),
                  value: billable,
                  onChanged: (value) => update(() => billable = value),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                if (!form.currentState!.validate()) return;
                Navigator.pop(context, <String, dynamic>{
                  'work_date': _date(date),
                  'hours': hours,
                  'is_billable': billable,
                  if (task.isNotEmpty) 'task_name': task,
                });
              },
              child: const Text('Save entry'),
            ),
          ],
        ),
      ),
    );
    if (!mounted || data == null || revision != widget.api.sessionRevision) {
      return;
    }
    await _save('POST', '/timesheets/${sheet['id']}/entries', data: data);
  }

  Widget _sheet(Json sheet, Map<Object?, Object?> names) {
    final entries = (sheet['entries'] as List? ?? const []).cast<Json>();
    final draft = sheet['status'] == 'Draft';
    final project = sheet['project_id'];
    return Card(
      child: ExpansionTile(
        key: ValueKey(sheet['id']),
        initiallyExpanded: _selected == sheet['id'],
        title: Text('${names[project] ?? 'Project #$project'}'),
        subtitle: Text(
          '${sheet['period_start']} – ${sheet['period_end']}\n${sheet['status']} · ${sheet['total_hours']} h',
        ),
        children: [
          for (final entry in entries)
            ListTile(
              title: Text('${entry['task_name'] ?? entry['work_date']}'),
              subtitle: Text(
                '${entry['work_date']} · ${entry['is_billable'] == true ? 'Billable' : 'Non-billable'}',
              ),
              trailing: Text('${entry['hours']} h'),
            ),
          if (draft && widget.canCreate)
            Wrap(
              spacing: 8,
              children: [
                TextButton(
                  onPressed: _busy ? null : () => _addEntry(sheet),
                  child: const Text('Add entry'),
                ),
                FilledButton(
                  onPressed: _busy || entries.isEmpty
                      ? null
                      : () => _save('PUT', '/timesheets/${sheet['id']}/submit'),
                  child: const Text('Submit'),
                ),
              ],
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('My Timesheets'),
      actions: [
        IconButton(
          tooltip: 'Refresh timesheets',
          icon: const Icon(LucideIcons.refreshCw),
          onPressed: _busy ? null : () => setState(() => _data = _load()),
        ),
      ],
    ),
    body: widget.employeeId == null
        ? const Center(
            child: Text(
              'An employee profile is required to view your timesheets.',
            ),
          )
        : FutureBuilder(
            future: _data,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return Center(child: Text('${snapshot.error}'));
              }
              final data = snapshot.requireData;
              final names = {
                for (final project in data.projects)
                  project['id']: project['name'],
              };
              final active = data.projects
                  .where((project) => project['status'] == 'Active')
                  .toList();
              return ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  if (widget.canCreate)
                    FilledButton.icon(
                      icon: const Icon(LucideIcons.plus),
                      onPressed: _busy || active.isEmpty
                          ? null
                          : () => _create(active),
                      label: const Text('New timesheet'),
                    ),
                  if (widget.canCreate && active.isEmpty)
                    const ListTile(
                      title: Text('No active projects available.'),
                    ),
                  if (data.sheets.isEmpty)
                    const ListTile(title: Text('No timesheets yet.')),
                  for (final sheet in data.sheets) _sheet(sheet, names),
                ],
              );
            },
          ),
  );
}
