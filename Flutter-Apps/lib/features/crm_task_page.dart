import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class CrmTaskPage extends StatefulWidget {
  const CrmTaskPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
    this.cacheScope,
    this.canEdit = false,
    this.onChanged,
  });

  static const endpoint = '/project-management/tasks';
  static const fields = {
    'status': 'Status',
    'priority': 'Priority',
    'due_date': 'Due date',
    'assignee_name': 'Assignee',
    'description': 'Description',
  };
  final ApiClient api;
  final Json summary;
  final bool offline;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool canEdit;
  final VoidCallback? onChanged;

  @override
  State<CrmTaskPage> createState() => _CrmTaskPageState();
}

class _CrmTaskPageState extends State<CrmTaskPage> {
  bool _saving = false;
  String? _error;
  static const _statuses = [
    'Backlog',
    'To Do',
    'In Progress',
    'In Review',
    'Blocked',
    'Done',
    'Cancelled',
  ];
  late Future<({Json? record, bool live})> _task = _load(
    offline: widget.offline,
  );

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: '${CrmTaskPage.endpoint}/${widget.summary['id']}',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        project: (record) => {
          for (final field in ['title', ...CrmTaskPage.fields.keys])
            field: record[field],
        },
      );

  void _refresh() => setState(() {
    _error = null;
    _task = _load();
  });

  Future<void> _changeStatus(Json task) async {
    final status = await showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('Change task status'),
        children: [
          for (final status in _statuses)
            if (status != task['status'])
              SimpleDialogOption(
                onPressed: () => Navigator.pop(context, status),
                child: Text(status),
              ),
        ],
      ),
    );
    if (!mounted || status == null) return;
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'PATCH',
        '${CrmTaskPage.endpoint}/${widget.summary['id']}',
        scopeHeaders: widget.scopeHeaders,
        data: {'status': status, 'expected_updated_at': task['updated_at']},
      );
      if (!mounted || revision != widget.api.sessionRevision) return;
      widget.onChanged?.call();
      _refresh();
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Task details'),
      actions: [
        IconButton(
          tooltip: 'Refresh task',
          icon: const Icon(Icons.refresh),
          onPressed: _saving ? null : _refresh,
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _task,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: TextButton(
              onPressed: _refresh,
              child: Text('${snapshot.error}\nRetry'),
            ),
          );
        }
        final data = snapshot.data?.record ?? widget.summary;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (snapshot.connectionState != ConnectionState.done)
              const LinearProgressIndicator()
            else if (snapshot.data?.live != true)
              const Text('Saved task details'),
            Text(
              '${data['title'] ?? 'Task'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (widget.canEdit &&
                snapshot.connectionState == ConnectionState.done &&
                snapshot.data?.live == true &&
                data['updated_at'] is String)
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton(
                  onPressed: _saving ? null : () => _changeStatus(data),
                  child: Text(_saving ? 'Saving…' : 'Change status'),
                ),
              ),
            if (_error case final error?) Text(error),
            for (final field in CrmTaskPage.fields.entries)
              if ((data[field.key] ?? widget.summary[field.key])
                  case final String value when value.isNotEmpty)
                ListTile(title: Text(field.value), subtitle: Text(value)),
          ],
        );
      },
    ),
  );
}
