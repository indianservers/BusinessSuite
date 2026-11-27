import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/crm_offline_edits.dart';
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
  Json? _pending;
  StreamSubscription<bool>? _taskUpdates;
  bool _readingPending = true;
  late final CrmOfflineEdits? _queue = widget.cacheScope == null
      ? null
      : CrmOfflineEdits.withTaskSnapshots(widget.cacheScope!);
  int get _id => widget.summary['id'] as int;
  static const _statuses = [
    'Backlog',
    'To Do',
    'In Progress',
    'In Review',
    'Blocked',
    'Done',
    'Cancelled',
  ];
  Json? _cachedDetails;
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
        onCached: (record) {
          if (mounted) setState(() => _cachedDetails = record);
        },
        project: (record) => {
          for (final field in [
            'title',
            'updated_at',
            ...CrmTaskPage.fields.keys,
          ])
            field: record[field],
        },
      );

  void _refresh() => setState(() {
    _cachedDetails = null;
    _error = null;
    _task = _load();
    _readPending();
  });

  @override
  void initState() {
    super.initState();
    _readPending();
    _taskUpdates = _queue?.taskUpdates(_id).listen((synced) {
      if (!mounted || _saving) return;
      if (synced) {
        widget.onChanged?.call();
        _refresh();
      } else {
        _readPending();
      }
    });
  }

  @override
  void dispose() {
    _taskUpdates?.cancel();
    super.dispose();
  }

  Future<void> _readPending() async {
    try {
      final pending = await _queue?.pendingTask(_id);
      if (mounted) setState(() => _pending = pending);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not read the saved task change.');
      }
    } finally {
      if (mounted) setState(() => _readingPending = false);
    }
  }

  Future<void> _discardRejected() async {
    try {
      await _queue?.discardTask(_id);
      if (mounted) _refresh();
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not clear the rejected change.');
      }
    }
  }

  Future<void> _changeStatus(Json task, {required bool live}) async {
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
      if (_queue case final queue?) {
        await queue.enqueueTaskStatus(
          _id,
          status,
          task['updated_at'] as String,
          widget.scopeHeaders['X-Suite-Branch'] ?? '',
        );
        if (live && revision == widget.api.sessionRevision) {
          await queue.sync(widget.api, onlyTask: _id);
        }
        await _readPending();
        if (_pending != null) return;
      } else {
        await widget.api.request(
          'PATCH',
          '${CrmTaskPage.endpoint}/$_id',
          scopeHeaders: widget.scopeHeaders,
          data: {'status': status, 'expected_updated_at': task['updated_at']},
        );
      }
      if (!mounted || revision != widget.api.sessionRevision) return;
      widget.onChanged?.call();
      _refresh();
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not save the task change.');
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
        final data = snapshot.data?.record ?? _cachedDetails ?? widget.summary;
        final live = snapshot.data?.live == true;
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
                !_readingPending &&
                _pending == null &&
                snapshot.connectionState == ConnectionState.done &&
                (live || _queue != null) &&
                data['updated_at'] is String)
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton(
                  onPressed: _saving
                      ? null
                      : () => _changeStatus(data, live: live),
                  child: Text(_saving ? 'Saving…' : 'Change status'),
                ),
              ),
            if (_pending case final pending?)
              ListTile(
                title: Text("Saved status ${pending['body']['status']}"),
                subtitle: Text(
                  pending['error'] as String? ?? 'Waiting to sync',
                ),
                trailing: pending['error'] == null
                    ? null
                    : TextButton(
                        onPressed: _discardRejected,
                        child: const Text('Clear rejected change'),
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
