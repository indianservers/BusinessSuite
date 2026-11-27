import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class CrmFollowUpsPage extends StatefulWidget {
  const CrmFollowUpsPage({
    super.key,
    required this.api,
    required this.headers,
    required this.cacheScope,
    required this.offline,
    required this.canEdit,
    this.canAssign = false,
  });

  final ApiClient api;
  final Map<String, String> headers;
  final String? cacheScope;
  final bool offline;
  final bool canEdit, canAssign;

  @override
  State<CrmFollowUpsPage> createState() => _CrmFollowUpsPageState();
}

class _CrmFollowUpsPageState extends State<CrmFollowUpsPage> {
  static const _path = '/follow-ups';
  static const _size = 25;
  static const _states = [
    'Due',
    'Overdue',
    'Completed',
    'Rescheduled',
    'Missed',
    'Cancelled',
  ];
  static const _actions = {
    'assign': 'Reassign',
    'reschedule': 'Reschedule',
    'contact': 'Log contact',
    'comment': 'Add comment',
    'complete': 'Mark complete',
    'missed': 'Mark missed',
    'cancel': 'Cancel follow-up',
  };
  final _search = TextEditingController();
  late bool _offline = widget.offline;
  late var _rows = _load();
  String _term = '';
  String _status = '';
  int _page = 1;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Json _summary(Json row) => {
    for (final key in [
      'id',
      'title',
      'customer_name',
      'due_at',
      'status',
      'priority',
      'assigned_to',
    ])
      key: row[key],
  };

  Future<({Json? record, bool live})> _load() {
    final scope = widget.cacheScope;
    return loadCrmDetail(
      api: widget.api,
      path: _path,
      scope: scope == null
          ? null
          : '$scope:follow-ups:${Uri.encodeComponent(_term)}:$_status:$_page',
      headers: widget.headers,
      offline: _offline,
      query: {
        'search': _term,
        'status': _status,
        'page': _page,
        'per_page': _size,
      },
      project: (record) => {
        'total': record['total'],
        'items': [
          for (final row in (record['items'] as List).cast<Json>())
            _summary(row),
        ],
      },
    );
  }

  String _due(Json row) {
    final parsed = DateTime.tryParse('${row['due_at']}')?.toLocal();
    if (parsed == null) return '';
    final labels = MaterialLocalizations.of(context);
    return '${labels.formatCompactDate(parsed)} · ${labels.formatTimeOfDay(TimeOfDay.fromDateTime(parsed))}';
  }

  Future<void> _open(Json row, {required bool live}) async {
    final id = row['id'] as int;
    if (!live) {
      await showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          title: Text('${row['title']}'),
          content: Text(_description(row)),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
          ],
        ),
      );
      return;
    }
    final revision = widget.api.sessionRevision;
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => _FollowUpDetail(
        api: widget.api,
        path: '$_path/$id',
        headers: widget.headers,
        revision: revision,
        canEdit: widget.canEdit,
        canAssign: widget.canAssign,
      ),
    );
    if (mounted && changed == true && revision == widget.api.sessionRevision) {
      setState(() {
        _rows = _load();
      });
    }
  }

  String _description(Json row) => [
    row['customer_name'],
    _due(row),
    row['status'],
    row['priority'],
    row['assigned_to'],
  ].whereType<String>().where((value) => value.isNotEmpty).join(' · ');

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Follow-ups'),
      actions: [
        IconButton(
          tooltip: 'Refresh follow-ups',
          icon: const Icon(LucideIcons.refreshCw),
          onPressed: () => setState(() {
            _offline = false;
            _rows = _load();
          }),
        ),
      ],
    ),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
          child: TextField(
            controller: _search,
            textInputAction: TextInputAction.search,
            decoration: InputDecoration(
              labelText: 'Search follow-ups',
              suffixIcon: IconButton(
                tooltip: 'Search',
                icon: const Icon(LucideIcons.search),
                onPressed: () => _find(_search.text),
              ),
            ),
            onSubmitted: _find,
          ),
        ),
        DropdownButton<String>(
          value: _status,
          onChanged: (value) => setState(() {
            _status = value!;
            _page = 1;
            _rows = _load();
          }),
          items: [
            const DropdownMenuItem(value: '', child: Text('All statuses')),
            for (final status in _states)
              DropdownMenuItem(value: status, child: Text(status)),
          ],
        ),
        Expanded(
          child: FutureBuilder(
            future: _rows,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Center(child: CircularProgressIndicator());
              }
              final data = snapshot.data;
              final record = data?.record;
              final rows = (record?['items'] as List? ?? const []).cast<Json>();
              return ListView(
                children: [
                  if (snapshot.hasError)
                    ListTile(title: Text('${snapshot.error}'))
                  else if (record == null)
                    const ListTile(title: Text('Connect to load follow-ups.'))
                  else ...[
                    if (!data!.live)
                      const ListTile(title: Text('Saved follow-ups')),
                    if (rows.isEmpty)
                      const ListTile(title: Text('No follow-ups found')),
                    for (final row in rows)
                      ListTile(
                        title: Text('${row['title']}'),
                        subtitle: Text(_description(row)),
                        onTap: () => _open(row, live: data.live),
                      ),
                  ],
                  if (_page > 1 ||
                      (record?['total'] as int? ?? 0) > _page * _size)
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        TextButton(
                          onPressed: _page > 1 ? () => _move(-1) : null,
                          child: const Text('Previous'),
                        ),
                        Text('Page $_page'),
                        TextButton(
                          onPressed:
                              (record?['total'] as int? ?? 0) > _page * _size
                              ? () => _move(1)
                              : null,
                          child: const Text('Next'),
                        ),
                      ],
                    ),
                ],
              );
            },
          ),
        ),
      ],
    ),
  );

  void _find(String value) => setState(() {
    _term = value.trim();
    _page = 1;
    _rows = _load();
  });

  void _move(int delta) => setState(() {
    _page += delta;
    _rows = _load();
  });
}

class _FollowUpDetail extends StatefulWidget {
  const _FollowUpDetail({
    required this.api,
    required this.path,
    required this.headers,
    required this.revision,
    required this.canEdit,
    required this.canAssign,
  });

  final ApiClient api;
  final String path;
  final Map<String, String> headers;
  final int revision;
  final bool canEdit, canAssign;

  @override
  State<_FollowUpDetail> createState() => _FollowUpDetailState();
}

class _FollowUpDetailState extends State<_FollowUpDetail> {
  final _notes = TextEditingController();
  late final _record = _load();
  late String _action = widget.canEdit ? 'comment' : 'assign';
  DateTime? _newDue;
  Future<List<Json>>? _assignees;
  int? _assignee;
  String? _error;
  bool _busy = false;
  bool get _canSave =>
      !_busy &&
      _notes.text.trim().isNotEmpty &&
      (_action != 'assign' || _assignee != null) &&
      (_action != 'reschedule' || _newDue != null);

  Future<List<Json>> _loadAssignees() async {
    final result =
        await widget.api.request(
              'GET',
              '/follow-ups/options',
              scopeHeaders: widget.headers,
            )
            as Json;
    if (widget.revision != widget.api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    return (result['employees'] as List).cast<Json>();
  }

  Widget _assigneePicker(Json row) => FutureBuilder(
    future: _assignees,
    builder: (context, snapshot) {
      if (_assignees == null || snapshot.hasError) {
        return OutlinedButton(
          onPressed: () => setState(() {
            _assignees = _loadAssignees();
          }),
          child: Text(snapshot.hasError ? 'Retry assignees' : 'Load assignees'),
        );
      }
      if (!snapshot.hasData) return const LinearProgressIndicator();
      final users = snapshot.requireData.where(
        (user) => user['id'] is int && user['id'] != row['assigned_user_id'],
      );
      if (users.isEmpty) return const Text('No other assignees available.');
      return DropdownButton<int>(
        value: _assignee,
        isExpanded: true,
        hint: const Text('Choose assignee'),
        onChanged: _busy ? null : (id) => setState(() => _assignee = id),
        items: [
          for (final user in users)
            DropdownMenuItem(
              value: user['id'] as int,
              child: Text('${user['name']}', overflow: TextOverflow.ellipsis),
            ),
        ],
      );
    },
  );

  Future<void> _chooseDue(Json row) async {
    final initial =
        _newDue ??
        DateTime.tryParse('${row['due_at']}')?.toLocal() ??
        DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(initial.year - 100),
      lastDate: DateTime(initial.year + 100, 12, 31),
      helpText: 'New due date',
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(initial),
      helpText: 'New due time',
    );
    if (time == null || !mounted) return;
    setState(() {
      _newDue = DateTime(
        date.year,
        date.month,
        date.day,
        time.hour,
        time.minute,
      );
    });
  }

  Future<Json> _load() async {
    final result = await widget.api.request(
      'GET',
      widget.path,
      scopeHeaders: widget.headers,
    );
    if (widget.revision != widget.api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    return result as Json;
  }

  @override
  void dispose() {
    _notes.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final notes = _notes.text.trim();
    if (!_canSave || widget.revision != widget.api.sessionRevision) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'POST',
        '${widget.path}/actions',
        scopeHeaders: widget.headers,
        data: {
          'action': _action,
          'notes': notes,
          if (_action == 'assign') 'assigned_user_id': _assignee,
          if (_action == 'reschedule')
            'due_at': _newDue!.toUtc().toIso8601String(),
        },
      );
      if (mounted && widget.revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } catch (error) {
      if (mounted && widget.revision == widget.api.sessionRevision) {
        setState(() => _error = '$error');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder(
    future: _record,
    builder: (context, snapshot) {
      final row = snapshot.data;
      final closed = const {'Completed', 'Cancelled'}.contains(row?['status']);
      final editable =
          row != null && (widget.canEdit || (!closed && widget.canAssign));
      return AlertDialog(
        scrollable: true,
        title: Text('${row?['title'] ?? 'Follow-up'}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (snapshot.hasError) Text('${snapshot.error}'),
            if (snapshot.connectionState != ConnectionState.done)
              const LinearProgressIndicator(),
            if (row != null) ...[
              Text('${row['customer_name'] ?? ''} · ${row['status']}'),
              for (final activity
                  in (row['activities'] as List? ?? const []).cast<Json>())
                ListTile(
                  title: Text('${activity['action']}'),
                  subtitle: Text(
                    '${activity['actor_name'] ?? ''} · ${(activity['details'] as Json?)?['notes'] ?? ''}',
                  ),
                ),
            ],
            if (editable) ...[
              DropdownButton<String>(
                value: _action,
                onChanged: _busy
                    ? null
                    : (action) => setState(() {
                        _action = action!;
                        if (_action == 'assign') {
                          _assignees ??= _loadAssignees();
                        }
                      }),
                items: [
                  for (final entry in _CrmFollowUpsPageState._actions.entries)
                    if (entry.key == 'assign'
                        ? widget.canAssign && !closed
                        : widget.canEdit && (!closed || entry.key == 'comment'))
                      DropdownMenuItem(
                        value: entry.key,
                        child: Text(entry.value),
                      ),
                ],
              ),
              if (_action == 'assign') _assigneePicker(row),
              if (_action == 'reschedule')
                OutlinedButton(
                  onPressed: _busy ? null : () => _chooseDue(row),
                  child: Text(switch (_newDue) {
                    final DateTime date =>
                      '${MaterialLocalizations.of(context).formatCompactDate(date)} · ${TimeOfDay.fromDateTime(date).format(context)}',
                    null => 'Choose due date and time',
                  }),
                ),
              TextField(
                controller: _notes,
                enabled: !_busy,
                onChanged: (_) => setState(() {}),
                maxLength: 10000,
                decoration: const InputDecoration(labelText: 'Notes'),
              ),
            ],
            if (_error != null) Text(_error!),
          ],
        ),
        actions: [
          TextButton(
            onPressed: _busy ? null : () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          if (editable)
            FilledButton(
              onPressed: _canSave ? _save : null,
              child: Text(_busy ? 'Saving…' : 'Save action'),
            ),
        ],
      );
    },
  );
}
