import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';

typedef _AttendanceSnapshot = ({List<Json> rows, bool saved});

class MyAttendancePage extends StatefulWidget {
  const MyAttendancePage({
    super.key,
    required this.api,
    this.cacheScope,
    this.offline = false,
  });
  final ApiClient api;
  final String? cacheScope;
  final bool offline;

  @override
  State<MyAttendancePage> createState() => _MyAttendancePageState();
}

class _MyAttendancePageState extends State<MyAttendancePage> {
  late bool _offline = widget.offline;
  late var _today = _loadToday();
  late var _history = _loadHistory();
  late var _summary = _loadSummary();
  late DateTimeRange _period = _currentMonth();
  bool _saving = false;
  String? _message;

  Future<_AttendanceSnapshot> _read(
    String path,
    String period,
    List<String> fields, {
    Json query = const {},
  }) async {
    final api = widget.api;
    final revision = api.sessionRevision;
    final scope = widget.cacheScope;
    final key = scope == null ? null : '$scope:$path:$period';
    void checkSession() {
      if (revision != api.sessionRevision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
    }

    if (!_offline) {
      try {
        final result = await api.request('GET', path, query: query);
        checkSession();
        final records = result is List
            ? result.cast<Json>()
            : [(result as Json)['attendance'] as Json? ?? result];
        final rows = <Json>[
          for (final row in records)
            {
              for (final field in fields)
                if (row.containsKey(field)) field: row[field],
            },
        ];
        if (key != null) {
          try {
            await SuiteReadCache.write(key, rows);
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
    if (rows == null) throw ApiFailure('Connect to load attendance.');
    return (rows: rows, saved: true);
  }

  static const _punchFields = ['check_in', 'check_out', 'hours_worked'];

  Future<_AttendanceSnapshot> _loadToday() =>
      _read('/attendance/today', _date(DateTime.now()), _punchFields);

  String _date(DateTime date) => date.toIso8601String().split('T').first;

  DateTimeRange _currentMonth() {
    final now = DateTime.now();
    return DateTimeRange(
      start: DateTime(now.year, now.month),
      end: DateUtils.dateOnly(now),
    );
  }

  Future<void> _changePeriod() async {
    final selected = await showDateRangePicker(
      context: context,
      firstDate: DateTime(1900),
      lastDate: DateUtils.dateOnly(DateTime.now()),
      initialDateRange: _period,
      helpText: 'Attendance period',
    );
    if (selected == null || !mounted || selected == _period) return;
    setState(() {
      _period = selected;
      _history = _loadHistory();
      _summary = _loadSummary();
    });
  }

  Future<_AttendanceSnapshot> _loadSummary() => _read(
    '/attendance/summary/monthly',
    '${_period.start.year}-${_period.start.month}',
    const ['present', 'absent', 'half_day', 'overtime_hours'],
    query: {'month': _period.start.month, 'year': _period.start.year},
  );

  Future<_AttendanceSnapshot> _loadHistory() {
    final start = _date(_period.start);
    final end = _date(_period.end);
    return _read(
      '/attendance/my',
      '$start:$end',
      const [
        ..._punchFields,
        'attendance_date',
        'date',
        'status',
        'overtime_hours',
        'total_hours',
      ],
      query: {'from_date': start, 'to_date': end},
    );
  }

  void _refresh() {
    setState(() {
      _offline = false;
      _today = _loadToday();
      _history = _loadHistory();
      _summary = _loadSummary();
    });
  }

  Future<void> _punch(bool checkOut) async {
    if (_saving) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await api.request(
        'POST',
        checkOut ? '/attendance/check-out' : '/attendance/check-in',
        data: {if (!checkOut) 'source': 'Mobile'},
      );
      if (mounted && api.sessionRevision == revision) {
        _message = checkOut ? 'Checked out.' : 'Checked in.';
      }
    } catch (error) {
      if (mounted && api.sessionRevision == revision) _message = '$error';
    } finally {
      if (mounted) {
        if (api.sessionRevision == revision) _refresh();
        setState(() => _saving = false);
      }
    }
  }

  String _punchTime(Object? value) {
    final time = value is String ? DateTime.tryParse(value)?.toLocal() : null;
    if (time == null) return 'No punch today';
    return MaterialLocalizations.of(
      context,
    ).formatTimeOfDay(TimeOfDay.fromDateTime(time));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('My Attendance'),
      actions: [
        IconButton(
          tooltip: 'Refresh attendance',
          icon: const Icon(Icons.refresh),
          onPressed: _saving ? null : _refresh,
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Today', style: Theme.of(context).textTheme.titleLarge),
        FutureBuilder<_AttendanceSnapshot>(
          future: _today,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const LinearProgressIndicator();
            }
            if (snapshot.hasError) {
              return ListTile(title: Text('${snapshot.error}'));
            }
            final data = snapshot.requireData;
            final row = data.rows.single;
            final checkedIn = row['check_in'] != null;
            final checkedOut = row['check_out'] != null;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ListTile(
                  title: Text(
                    checkedOut
                        ? 'Checked out'
                        : checkedIn
                        ? 'Checked in'
                        : 'Not checked in',
                  ),
                  subtitle: Text(
                    '${data.saved ? 'Saved · ' : ''}Last punch · ${_punchTime(row['check_out'] ?? row['check_in'])}',
                  ),
                  trailing: Text('${row['hours_worked'] ?? 0} hours'),
                ),
                if (!checkedOut && !data.saved)
                  FilledButton(
                    onPressed: _saving ? null : () => _punch(checkedIn),
                    child: Text(
                      _saving
                          ? 'Saving…'
                          : checkedIn
                          ? 'Check Out'
                          : 'Check In',
                    ),
                  ),
              ],
            );
          },
        ),
        if (_message != null)
          Semantics(liveRegion: true, child: ListTile(title: Text(_message!))),
        const Divider(),
        Text(
          'Attendance history',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        OutlinedButton.icon(
          onPressed: _changePeriod,
          icon: const Icon(Icons.date_range_outlined),
          label: Text('${_date(_period.start)} – ${_date(_period.end)}'),
        ),
        FutureBuilder<_AttendanceSnapshot>(
          future: _summary,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const LinearProgressIndicator();
            }
            if (snapshot.hasError) {
              return ListTile(
                title: const Text('Monthly summary unavailable'),
                trailing: TextButton(
                  onPressed: () => setState(() {
                    _summary = _loadSummary();
                  }),
                  child: const Text('Retry summary'),
                ),
              );
            }
            final result = snapshot.requireData;
            final data = result.rows.single;
            final month = MaterialLocalizations.of(
              context,
            ).formatMonthYear(_period.start);
            return ListTile(
              title: Text(month),
              subtitle: Text(
                '${result.saved ? 'Saved · ' : ''}Present ${data['present'] ?? 0} · Absent ${data['absent'] ?? 0} · '
                'Half day ${data['half_day'] ?? 0} · Overtime ${data['overtime_hours'] ?? 0} h',
              ),
            );
          },
        ),
        FutureBuilder<_AttendanceSnapshot>(
          future: _history,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const LinearProgressIndicator();
            }
            if (snapshot.hasError) {
              return ListTile(title: Text('${snapshot.error}'));
            }
            final result = snapshot.requireData;
            final rows = result.rows;
            if (rows.isEmpty) {
              return const ListTile(
                title: Text('No attendance records in this period'),
              );
            }
            return Column(
              children: [
                if (result.saved)
                  const ListTile(title: Text('Saved attendance history')),
                for (final row in rows)
                  ListTile(
                    title: Text(
                      '${row['attendance_date'] ?? row['date'] ?? ''}',
                    ),
                    subtitle: Text(
                      [
                        row['status'],
                        if (row['check_in'] != null)
                          'In ${_punchTime(row['check_in'])}',
                        if (row['check_out'] != null)
                          'Out ${_punchTime(row['check_out'])}',
                        if (row['overtime_hours'] != null)
                          'Overtime ${row['overtime_hours']} h',
                      ].whereType<String>().join(' · '),
                    ),
                    trailing: Text(
                      '${row['hours_worked'] ?? row['total_hours'] ?? 0} hours',
                    ),
                  ),
              ],
            );
          },
        ),
      ],
    ),
  );
}
