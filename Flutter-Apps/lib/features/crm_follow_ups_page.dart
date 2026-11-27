import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';

class CrmFollowUpsPage extends StatefulWidget {
  const CrmFollowUpsPage({
    super.key,
    required this.api,
    required this.headers,
    required this.cacheScope,
    required this.offline,
    required this.canEdit,
    this.canAssign = false,
    this.canCreate = false,
  });

  final ApiClient api;
  final Map<String, String> headers;
  final String? cacheScope;
  final bool offline;
  final bool canEdit, canAssign, canCreate;

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
  Json? _owner;
  Json? _customer;
  int _page = 1;
  int _generation = 0;
  Json? _cachedRows;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    final revision = widget.api.sessionRevision;
    final created = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _CreateFollowUp(
        api: widget.api,
        headers: widget.headers,
        revision: revision,
      ),
    );
    if (!mounted || created != true || revision != widget.api.sessionRevision) {
      return;
    }
    setState(() {
      _page = 1;
      _rows = _load();
    });
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Follow-up scheduled.')));
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
    final generation = ++_generation;
    _cachedRows = null;
    return loadCrmDetail(
      api: widget.api,
      path: _path,
      scope: scope == null
          ? null
          : '$scope:follow-ups:${Uri.encodeComponent(_term)}:$_status:$_page'
                '${_owner == null ? '' : ':owner:${_owner!['id']}'}'
                '${_customer == null ? '' : ':customer:${_customer!['id']}'}',
      headers: widget.headers,
      offline: _offline,
      onCached: (record) {
        if (mounted && generation == _generation) {
          setState(() => _cachedRows = record);
        }
      },
      query: {
        'search': _term,
        'status': _status,
        if (_owner != null) 'assigned_user_id': _owner!['id'],
        if (_customer != null) 'customer_id': _customer!['id'],
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
    final revision = widget.api.sessionRevision;
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => _FollowUpDetail(
        api: widget.api,
        path: '$_path/$id',
        headers: widget.headers,
        summary: _summary(row),
        cacheScope: widget.cacheScope,
        offline: !live,
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

  Future<void> _showStatistics() async {
    final status = await showDialog<String>(
      context: context,
      builder: (_) => _FollowUpStatistics(
        api: widget.api,
        headers: widget.headers,
        cacheScope: widget.cacheScope,
        offline: _offline,
      ),
    );
    if (mounted && status != null) _selectStatus(status);
  }

  void _selectStatus(String status) => setState(() {
    _status = status;
    _page = 1;
    _rows = _load();
  });

  Future<void> _chooseFilter(_FollowUpFilter filter) async {
    final revision = widget.api.sessionRevision;
    final selection = await showDialog<Json>(
      context: context,
      builder: (_) => _FollowUpFilterDialog(
        api: widget.api,
        headers: widget.headers,
        cacheScope: widget.cacheScope,
        offline: _offline,
        filter: filter,
      ),
    );
    if (!mounted ||
        selection == null ||
        revision != widget.api.sessionRevision) {
      return;
    }
    setState(() {
      final selected = selection.isEmpty ? null : selection;
      switch (filter) {
        case _FollowUpFilter.owner:
          _owner = selected;
        case _FollowUpFilter.customer:
          _customer = selected;
      }
      _page = 1;
      _rows = _load();
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Follow-ups'),
      actions: [
        IconButton(
          tooltip: 'Follow-up statistics',
          icon: const Icon(LucideIcons.chartNoAxesColumnIncreasing),
          onPressed: _showStatistics,
        ),
        if (widget.canCreate)
          FutureBuilder(
            future: _rows,
            builder: (_, snapshot) => IconButton(
              tooltip: 'New follow-up',
              icon: const Icon(LucideIcons.plus),
              onPressed:
                  snapshot.connectionState == ConnectionState.done &&
                      snapshot.data?.live == true
                  ? _create
                  : null,
            ),
          ),
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
        Wrap(
          spacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            DropdownButton<String>(
              value: _status,
              onChanged: (value) => _selectStatus(value!),
              items: [
                const DropdownMenuItem(value: '', child: Text('All statuses')),
                for (final status in _states)
                  DropdownMenuItem(value: status, child: Text(status)),
              ],
            ),
            TextButton.icon(
              onPressed: () => _chooseFilter(_FollowUpFilter.owner),
              icon: const Icon(LucideIcons.user),
              label: Text(
                _owner == null ? 'All assignees' : '${_owner!['name']}',
                overflow: TextOverflow.ellipsis,
              ),
            ),
            TextButton.icon(
              onPressed: () => _chooseFilter(_FollowUpFilter.customer),
              icon: const Icon(LucideIcons.building2),
              label: Text(
                _customer == null ? 'All customers' : '${_customer!['name']}',
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        Expanded(
          child: FutureBuilder(
            future: _rows,
            builder: (context, snapshot) {
              final refreshing =
                  snapshot.connectionState != ConnectionState.done;
              final data = refreshing ? null : snapshot.data;
              final record = refreshing ? _cachedRows : data?.record;
              if (refreshing && record == null) {
                return const Center(child: CircularProgressIndicator());
              }
              final live = data?.live == true;
              final rows = (record?['items'] as List? ?? const []).cast<Json>();
              return ListView(
                children: [
                  if (snapshot.hasError)
                    ListTile(title: Text('${snapshot.error}'))
                  else if (record == null)
                    const ListTile(title: Text('Connect to load follow-ups.'))
                  else ...[
                    if (refreshing) const LinearProgressIndicator(),
                    if (!live) const ListTile(title: Text('Saved follow-ups')),
                    if (rows.isEmpty)
                      const ListTile(title: Text('No follow-ups found')),
                    for (final row in rows)
                      ListTile(
                        title: Text('${row['title']}'),
                        subtitle: Text(_description(row)),
                        onTap: refreshing ? null : () => _open(row, live: live),
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

enum _FollowUpFilter {
  owner('employees', 'assignee', 'assignees'),
  customer('customers', 'customer', 'customers');

  const _FollowUpFilter(this.collection, this.label, this.plural);
  final String collection, label, plural;
}

class _FollowUpFilterDialog extends StatefulWidget {
  const _FollowUpFilterDialog({
    required this.api,
    required this.headers,
    required this.cacheScope,
    required this.offline,
    required this.filter,
  });

  final ApiClient api;
  final Map<String, String> headers;
  final String? cacheScope;
  final bool offline;
  final _FollowUpFilter filter;

  @override
  State<_FollowUpFilterDialog> createState() => _FollowUpFilterDialogState();
}

class _FollowUpFilterDialogState extends State<_FollowUpFilterDialog> {
  late var _options = _load(offline: widget.offline);
  String _term = '';

  Future<({Json? record, bool live})> _load({required bool offline}) =>
      loadCrmDetail(
        api: widget.api,
        path: '/follow-ups/options',
        scope: widget.cacheScope,
        headers: widget.headers,
        offline: offline,
        project: (record) => {
          for (final filter in _FollowUpFilter.values)
            if (record[filter.collection] case final List rows)
              filter.collection: [
                for (final row in rows.cast<Json>())
                  {'id': row['id'], 'name': row['name']},
              ],
        },
      );

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text('Filter by ${widget.filter.label}'),
    content: SizedBox(
      width: 360,
      height: 300,
      child: Column(
        children: [
          TextField(
            decoration: InputDecoration(
              labelText: 'Search ${widget.filter.plural}',
            ),
            onChanged: (value) =>
                setState(() => _term = value.trim().toLowerCase()),
          ),
          Expanded(
            child: FutureBuilder(
              future: _options,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                final result = snapshot.data;
                final rows = result?.record?[widget.filter.collection] as List?;
                if (rows == null) {
                  return Center(
                    child: TextButton(
                      onPressed: () => setState(() {
                        _options = _load(offline: false);
                      }),
                      child: Text('Retry ${widget.filter.plural}'),
                    ),
                  );
                }
                final users = [
                  for (final user in rows.cast<Json>())
                    if (user['id'] is int &&
                        '${user['name']}'.toLowerCase().contains(_term))
                      user,
                ];
                if (users.isEmpty) {
                  return Center(
                    child: Text('No matching ${widget.filter.plural}'),
                  );
                }
                return ListView.builder(
                  itemCount: users.length,
                  itemBuilder: (context, index) => ListTile(
                    title: Text('${users[index]['name']}'),
                    onTap: () => Navigator.pop(context, users[index]),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context, <String, dynamic>{}),
        child: Text('All ${widget.filter.plural}'),
      ),
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Close'),
      ),
    ],
  );
}

class _FollowUpStatistics extends StatefulWidget {
  const _FollowUpStatistics({
    required this.api,
    required this.headers,
    required this.cacheScope,
    required this.offline,
  });

  final ApiClient api;
  final Map<String, String> headers;
  final String? cacheScope;
  final bool offline;

  @override
  State<_FollowUpStatistics> createState() => _FollowUpStatisticsState();
}

class _FollowUpStatisticsState extends State<_FollowUpStatistics> {
  late var _statistics = _load(offline: widget.offline);
  static const _labels = [
    'Total',
    'Due',
    'Overdue',
    'Completed',
    'Rescheduled',
    'Missed',
    'Upcoming 7 Days',
    'Conversion Rate',
  ];

  Future<({Json? record, bool live})> _load({required bool offline}) =>
      loadCrmDetail(
        api: widget.api,
        path: '/follow-ups/statistics',
        scope: widget.cacheScope,
        headers: widget.headers,
        offline: offline,
        project: (record) => {
          for (final label in _labels)
            if (record[label] is num) label: record[label],
        },
      );

  @override
  Widget build(BuildContext context) => FutureBuilder(
    future: _statistics,
    builder: (context, snapshot) {
      final loading = snapshot.connectionState != ConnectionState.done;
      final result = loading ? null : snapshot.data;
      final record = result?.record;
      return AlertDialog(
        title: const Text('Follow-up statistics'),
        scrollable: true,
        content: SizedBox(
          width: 320,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (loading)
                const LinearProgressIndicator()
              else if (snapshot.hasError)
                Text('${snapshot.error}')
              else if (record == null)
                const Text('Connect to load follow-up statistics.')
              else ...[
                if (!result!.live) const Text('Saved statistics'),
                for (final label in _labels)
                  if (record[label] case final num value)
                    ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      title: Text(label == 'Due' ? 'Due today' : label),
                      onTap:
                          label == 'Total' ||
                              _CrmFollowUpsPageState._states.contains(label)
                          ? () => Navigator.pop(
                              context,
                              label == 'Total' ? '' : label,
                            )
                          : null,
                      trailing: Text(
                        label == 'Conversion Rate' ? '$value%' : '$value',
                      ),
                    ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: loading
                ? null
                : () => setState(() {
                    _statistics = _load(offline: false);
                  }),
            child: const Text('Refresh'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      );
    },
  );
}

class _FollowUpDetail extends StatefulWidget {
  const _FollowUpDetail({
    required this.api,
    required this.path,
    required this.headers,
    required this.summary,
    required this.cacheScope,
    required this.offline,
    required this.revision,
    required this.canEdit,
    required this.canAssign,
  });

  final ApiClient api;
  final String path;
  final Map<String, String> headers;
  final Json summary;
  final String? cacheScope;
  final bool offline;
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
    final due = await _pickDue(context, initial);
    if (mounted && due != null) setState(() => _newDue = due);
  }

  Future<({Json? record, bool live})> _load() => loadCrmDetail(
    api: widget.api,
    path: widget.path,
    scope: widget.cacheScope,
    headers: widget.headers,
    offline: widget.offline,
    project: (record) => {
      for (final field in widget.summary.keys) field: record[field],
      'activities': [
        for (final action
            in (record['activities'] as List? ?? const []).cast<Json>().take(
              100,
            ))
          {
            for (final field in ['action', 'actor_name', 'created_at'])
              field: action[field],
          },
      ],
    },
  );

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
      if (widget.cacheScope case final String scope) {
        final branch = widget.headers['X-Suite-Branch'] ?? '';
        final key = '$scope:${widget.path}:$branch';
        try {
          await flushCrmDetailWrite(key);
          await SuiteReadCache.clear(key);
        } catch (_) {}
      }
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
      final detail = snapshot.data;
      final row = detail?.record ?? widget.summary;
      final closed = const {'Completed', 'Cancelled'}.contains(row['status']);
      final editable =
          detail?.live == true &&
          (widget.canEdit || (!closed && widget.canAssign));
      return AlertDialog(
        scrollable: true,
        title: Text('${row['title'] ?? 'Follow-up'}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (snapshot.hasError) Text('${snapshot.error}'),
            if (snapshot.connectionState != ConnectionState.done)
              const LinearProgressIndicator(),
            Text('${row['customer_name'] ?? ''} · ${row['status']}'),
            if (detail?.live == false)
              Text(
                detail?.record == null
                    ? 'Saved summary'
                    : 'Saved activity history',
              ),
            if (detail?.record != null) ...[
              for (final activity
                  in (row['activities'] as List? ?? const []).cast<Json>())
                ListTile(
                  title: Text('${activity['action']}'),
                  subtitle: Text(
                    [
                          activity['actor_name'],
                          activity['created_at'],
                          (activity['details'] as Json?)?['notes'],
                        ]
                        .whereType<String>()
                        .where((value) => value.isNotEmpty)
                        .join(' · '),
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

Future<DateTime?> _pickDue(BuildContext context, DateTime initial) async {
  final date = await showDatePicker(
    context: context,
    initialDate: initial,
    firstDate: DateTime(initial.year - 100),
    lastDate: DateTime(initial.year + 100, 12, 31),
    helpText: 'New due date',
  );
  if (date == null || !context.mounted) return null;
  final time = await showTimePicker(
    context: context,
    initialTime: TimeOfDay.fromDateTime(initial),
    helpText: 'New due time',
  );
  if (time == null) return null;
  return DateTime(date.year, date.month, date.day, time.hour, time.minute);
}

class _CreateFollowUp extends StatefulWidget {
  const _CreateFollowUp({
    required this.api,
    required this.headers,
    required this.revision,
  });

  final ApiClient api;
  final Map<String, String> headers;
  final int revision;

  @override
  State<_CreateFollowUp> createState() => _CreateFollowUpState();
}

class _CreateFollowUpState extends State<_CreateFollowUp> {
  final _title = TextEditingController();
  final _notes = TextEditingController();
  late var _options = _load();
  Json? _customer;
  DateTime? _due;
  String _priority = 'Normal';
  String _method = 'Call';
  String? _error;
  bool _saving = false;
  bool _uncertain = false;

  Future<List<Json>> _load() async {
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
    return (result['customers'] as List).cast<Json>();
  }

  @override
  void dispose() {
    _title.dispose();
    _notes.dispose();
    super.dispose();
  }

  bool get _canSave =>
      !_saving &&
      !_uncertain &&
      _customer != null &&
      _due != null &&
      _title.text.trim().isNotEmpty;

  Future<void> _save() async {
    if (!_canSave || widget.revision != widget.api.sessionRevision) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'POST',
        '/follow-ups',
        scopeHeaders: widget.headers,
        data: {
          'title': _title.text.trim(),
          'customer_id': _customer!['id'],
          'required': true,
          'type': 'date',
          'due_at': _due!.toUtc().toIso8601String(),
          'priority': _priority,
          'contact_method': _method,
          'notes': _notes.text.trim(),
        },
      );
      if (mounted && widget.revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } on ApiFailure catch (error) {
      if (mounted && widget.revision == widget.api.sessionRevision) {
        setState(() {
          _uncertain = error.connectionFailure || (error.status ?? 0) >= 500;
          _error = _uncertain
              ? 'Save could not be confirmed. Refresh Follow-ups before trying again.'
              : error.message;
        });
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _choice(
    String label,
    String value,
    List<String> options,
    ValueChanged<String> select,
  ) => DropdownButtonFormField<String>(
    initialValue: value,
    decoration: InputDecoration(labelText: label),
    onChanged: _saving ? null : (value) => setState(() => select(value!)),
    items: [
      for (final option in options)
        DropdownMenuItem(value: option, child: Text(option)),
    ],
  );

  @override
  Widget build(BuildContext context) => AlertDialog(
    scrollable: true,
    title: const Text('New follow-up'),
    content: SizedBox(
      width: 360,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          FutureBuilder(
            future: _options,
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return TextButton(
                  onPressed: () => setState(() {
                    _options = _load();
                  }),
                  child: const Text('Retry customers'),
                );
              }
              if (!snapshot.hasData) return const LinearProgressIndicator();
              final rows = snapshot.requireData;
              return Autocomplete<Json>(
                displayStringForOption: (row) => '${row['name']}',
                optionsBuilder: (text) {
                  final term = text.text.trim().toLowerCase();
                  return rows
                      .where(
                        (row) => '${row['name']}'.toLowerCase().contains(term),
                      )
                      .take(40);
                },
                fieldViewBuilder: (_, controller, focus, submitted) =>
                    TextField(
                      controller: controller,
                      focusNode: focus,
                      enabled: !_saving,
                      onChanged: (_) => setState(() => _customer = null),
                      onSubmitted: (_) => submitted(),
                      decoration: const InputDecoration(labelText: 'Customer'),
                    ),
                onSelected: (row) => setState(() => _customer = row),
              );
            },
          ),
          TextField(
            controller: _title,
            enabled: !_saving,
            onChanged: (_) => setState(() {}),
            maxLength: 220,
            decoration: const InputDecoration(
              labelText: 'Purpose / next action',
            ),
          ),
          OutlinedButton(
            onPressed: _saving
                ? null
                : () async {
                    final due = await _pickDue(context, _due ?? DateTime.now());
                    if (mounted && due != null) setState(() => _due = due);
                  },
            child: Text(switch (_due) {
              final DateTime date =>
                '${MaterialLocalizations.of(context).formatCompactDate(date)} · ${TimeOfDay.fromDateTime(date).format(context)}',
              null => 'Choose due date and time',
            }),
          ),
          _choice('Priority', _priority, const [
            'Low',
            'Normal',
            'High',
            'Urgent',
          ], (value) => _priority = value),
          _choice('Contact method', _method, const [
            'Call',
            'WhatsApp',
            'Email',
            'Visit',
          ], (value) => _method = value),
          TextField(
            controller: _notes,
            enabled: !_saving,
            maxLength: 10000,
            decoration: const InputDecoration(labelText: 'Notes'),
          ),
          if (_error != null) Text(_error!),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: _saving ? null : () => Navigator.pop(context),
        child: const Text('Close'),
      ),
      FilledButton(
        onPressed: _canSave ? _save : null,
        child: Text(_saving ? 'Saving…' : 'Schedule follow-up'),
      ),
    ],
  );
}
