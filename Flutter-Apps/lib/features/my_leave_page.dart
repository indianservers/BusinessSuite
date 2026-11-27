import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';

typedef _LeaveSnapshot = ({List<Json> rows, bool saved});

class MyLeavePage extends StatefulWidget {
  const MyLeavePage({
    super.key,
    required this.api,
    this.cacheScope,
    this.offline = false,
  });
  final ApiClient api;
  final String? cacheScope;
  final bool offline;

  @override
  State<MyLeavePage> createState() => _MyLeavePageState();
}

class _MyLeavePageState extends State<MyLeavePage> {
  static const _pageSize = 20;
  late bool _offline = widget.offline;
  late var _balances = _readBalances();
  late var _requests = _readRequests();
  int _page = 1;
  bool _applying = false;
  bool _cancelling = false;

  Future<List<Json>> _read(String path, {Json? query}) async =>
      (await widget.api.request('GET', path, query: query) as List)
          .cast<Json>();

  Future<_LeaveSnapshot> _readSnapshot(
    String path,
    String segment,
    List<String> fields, {
    Json? query,
  }) async {
    final api = widget.api;
    final revision = api.sessionRevision;
    final scope = widget.cacheScope;
    final key = scope == null ? null : '$scope:$path:$segment';
    void checkSession() {
      if (revision != api.sessionRevision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
    }

    if (!_offline) {
      try {
        final rows = await _read(path, query: query);
        checkSession();
        if (key != null) {
          try {
            await SuiteReadCache.write(key, [
              for (final row in rows)
                {
                  for (final field in fields) field: row[field],
                  if (row['leave_type'] case final Json type)
                    'leave_type': {'name': type['name']},
                },
            ]);
          } catch (_) {}
        }
        checkSession();
        return (rows: rows, saved: false);
      } on ApiFailure catch (error) {
        if (key != null && const {401, 403, 404}.contains(error.status)) {
          try {
            await SuiteReadCache.clear(key);
          } catch (_) {}
        }
        if (!error.connectionFailure && (error.status ?? 0) < 500) rethrow;
      }
    }
    List<Json>? rows;
    if (key != null) {
      try {
        rows = await SuiteReadCache.read(key);
      } catch (_) {}
    }
    checkSession();
    if (rows == null) throw ApiFailure('Connect to load your leave records.');
    return (rows: rows, saved: true);
  }

  Future<_LeaveSnapshot> _readBalances() {
    final year = DateTime.now().year;
    return _readSnapshot(
      '/leave/balance',
      '$year',
      const ['leave_type_id', 'used', 'pending', 'available'],
      query: {'year': year},
    );
  }

  Future<_LeaveSnapshot> _readRequests() => _readSnapshot(
    '/leave/my-requests',
    '$_page',
    const ['leave_type_id', 'from_date', 'to_date', 'days_count', 'status'],
    query: {'page': _page, 'per_page': _pageSize},
  );

  void _refresh() {
    setState(() {
      _offline = false;
      _balances = _readBalances();
      _requests = _readRequests();
    });
  }

  Future<void> _apply() async {
    if (_applying) return;
    setState(() => _applying = true);
    try {
      final types = (await _read(
        '/leave/types',
      )).where((type) => type['is_active'] == true).toList();
      if (!mounted) return;
      if (types.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No active leave types are available.')),
        );
        return;
      }
      final applied = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => _LeaveRequestDialog(api: widget.api, types: types),
      );
      if (applied == true && mounted) {
        _page = 1;
        _refresh();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Leave request submitted.')),
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _applying = false);
    }
  }

  String _name(Json row) =>
      '${(row['leave_type'] as Json?)?['name'] ?? 'Leave type ${row['leave_type_id']}'}';

  Future<void> _openRequest(Json row, {required bool saved}) async {
    if (_cancelling) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(_name(row)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('${row['from_date']} – ${row['to_date']}'),
              Text('${row['days_count']} days · ${row['status']}'),
              if (row['reason'] case final String reason when reason.isNotEmpty)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Reason'),
                  subtitle: Text(reason),
                ),
              if (row['review_remarks'] case final String remarks
                  when remarks.isNotEmpty)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Review remarks'),
                  subtitle: Text(remarks),
                ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          if (!saved && row['status'] == 'Pending' && row['id'] is int)
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Cancel request'),
            ),
        ],
      ),
    );
    if (!mounted ||
        confirmed != true ||
        _cancelling ||
        api.sessionRevision != revision) {
      return;
    }
    final cancel = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel this leave request?'),
        content: const Text('The request will be withdrawn from approval.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Keep request'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Confirm cancellation'),
          ),
        ],
      ),
    );
    if (!mounted ||
        cancel != true ||
        _cancelling ||
        api.sessionRevision != revision) {
      return;
    }
    setState(() => _cancelling = true);
    try {
      await api.request('PUT', '/leave/requests/${row['id']}/cancel');
      if (mounted && api.sessionRevision == revision) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Leave request cancelled.')),
        );
      }
    } catch (error) {
      if (mounted && api.sessionRevision == revision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) {
        setState(() => _cancelling = false);
        if (api.sessionRevision == revision) _refresh();
      }
    }
  }

  Widget _section(
    Future<_LeaveSnapshot> future,
    Widget Function(List<Json>, bool saved) content, {
    VoidCallback? onBack,
  }) => FutureBuilder<_LeaveSnapshot>(
    future: future,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const LinearProgressIndicator();
      }
      if (snapshot.hasError) {
        return ListTile(
          title: Text('${snapshot.error}'),
          trailing: onBack == null
              ? null
              : TextButton(onPressed: onBack, child: const Text('Previous')),
        );
      }
      final result = snapshot.requireData;
      return content(result.rows, result.saved);
    },
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('My Leave'),
      actions: [
        IconButton(
          onPressed: _refresh,
          tooltip: 'Refresh leave',
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        FutureBuilder<_LeaveSnapshot>(
          future: _requests,
          builder: (context, snapshot) => FilledButton(
            onPressed:
                _applying ||
                    snapshot.connectionState != ConnectionState.done ||
                    snapshot.data?.saved != false
                ? null
                : _apply,
            child: Text(_applying ? 'Loading…' : 'Apply for leave'),
          ),
        ),
        Text('Leave balances', style: Theme.of(context).textTheme.titleLarge),
        _section(
          _balances,
          (rows, saved) => Column(
            children: [
              if (saved) const ListTile(title: Text('Saved leave balances')),
              if (rows.isEmpty)
                const ListTile(title: Text('No leave balances')),
              for (final row in rows)
                ListTile(
                  title: Text(_name(row)),
                  subtitle: Text(
                    'Used ${row['used']} · Pending ${row['pending']}',
                  ),
                  trailing: Text('${row['available']} days available'),
                ),
            ],
          ),
        ),
        const Divider(),
        Text('My requests', style: Theme.of(context).textTheme.titleLarge),
        _section(
          _requests,
          (rows, saved) => Column(
            children: [
              if (saved) const ListTile(title: Text('Saved leave requests')),
              if (rows.isEmpty)
                const ListTile(title: Text('No leave requests on this page')),
              for (final row in rows)
                ListTile(
                  title: Text(_name(row)),
                  subtitle: Text(
                    '${row['from_date']} – ${row['to_date']} · ${row['days_count']} days',
                  ),
                  trailing: Text('${row['status']}'),
                  onTap: _cancelling
                      ? null
                      : () => _openRequest(row, saved: saved),
                ),
              if (_page > 1 || rows.length == _pageSize)
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    TextButton(
                      onPressed: _page > 1 ? () => _go(-1) : null,
                      child: const Text('Previous'),
                    ),
                    Text('Page $_page'),
                    TextButton(
                      onPressed: rows.length == _pageSize ? () => _go(1) : null,
                      child: const Text('Next'),
                    ),
                  ],
                ),
            ],
          ),
          onBack: _page > 1 ? () => _go(-1) : null,
        ),
      ],
    ),
  );

  void _go(int offset) {
    setState(() {
      _page += offset;
      _requests = _readRequests();
    });
  }
}

class _LeaveRequestDialog extends StatefulWidget {
  const _LeaveRequestDialog({required this.api, required this.types});
  final ApiClient api;
  final List<Json> types;

  @override
  State<_LeaveRequestDialog> createState() => _LeaveRequestDialogState();
}

class _LeaveRequestDialogState extends State<_LeaveRequestDialog> {
  int? _type;
  DateTimeRange? _period;
  String _reason = '';
  bool _halfDay = false;
  bool _saving = false;
  String? _error;

  String _date(DateTime date) => date.toIso8601String().split('T').first;

  Future<void> _pickDates() async {
    final now = DateTime.now();
    final dates = await showDateRangePicker(
      context: context,
      initialDateRange: _period,
      firstDate: DateTime(now.year - 5),
      lastDate: DateTime(now.year + 5, 12, 31),
      helpText: 'Leave dates',
    );
    if (mounted && dates != null) {
      setState(() {
        _period = dates;
        if (dates.start != dates.end) _halfDay = false;
      });
    }
  }

  Future<void> _submit() async {
    final dates = _period;
    if (_saving || dates == null || _type == null) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'POST',
        '/leave/apply',
        data: {
          'leave_type_id': _type,
          'from_date': _date(dates.start),
          'to_date': _date(dates.end),
          'is_half_day': _halfDay,
          if (_reason.isNotEmpty) 'reason': _reason,
        },
      );
      if (mounted) Navigator.pop(context, true);
    } catch (error) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = '$error';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final dates = _period;
    final selected = widget.types
        .where((type) => type['id'] == _type)
        .firstOrNull;
    return PopScope(
      canPop: !_saving,
      child: AlertDialog(
        title: const Text('Apply for leave'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<int>(
                initialValue: _type,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Leave type'),
                items: [
                  for (final type in widget.types)
                    DropdownMenuItem(
                      value: type['id'] as int,
                      child: Text('${type['name']}'),
                    ),
                ],
                onChanged: _saving
                    ? null
                    : (value) => setState(() {
                        _type = value;
                        _halfDay = false;
                      }),
              ),
              OutlinedButton(
                onPressed: _saving ? null : _pickDates,
                child: Text(
                  dates == null
                      ? 'Choose leave dates'
                      : '${_date(dates.start)} – ${_date(dates.end)}',
                ),
              ),
              if (dates != null &&
                  dates.start == dates.end &&
                  selected?['half_day_allowed'] == true)
                CheckboxListTile(
                  title: const Text('Half day'),
                  value: _halfDay,
                  onChanged: _saving
                      ? null
                      : (value) => setState(() => _halfDay = value == true),
                ),
              TextField(
                enabled: !_saving,
                decoration: const InputDecoration(labelText: 'Reason'),
                onChanged: (value) => _reason = value.trim(),
              ),
              if (_error != null) SelectableText(_error!),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: _saving ? null : () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: _saving || _type == null || dates == null
                ? null
                : _submit,
            child: Text(_saving ? 'Submitting…' : 'Submit request'),
          ),
        ],
      ),
    );
  }
}
