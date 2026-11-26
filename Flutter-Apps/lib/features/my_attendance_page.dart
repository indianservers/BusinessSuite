import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class MyAttendancePage extends StatefulWidget {
  const MyAttendancePage({super.key, required this.api});
  final ApiClient api;

  @override
  State<MyAttendancePage> createState() => _MyAttendancePageState();
}

class _MyAttendancePageState extends State<MyAttendancePage> {
  late Future<Json> _today = _loadToday();
  late Future<List<Json>> _history = _loadHistory();
  late Future<Json> _summary = _loadSummary();
  late DateTimeRange _period = _currentMonth();
  bool _saving = false;
  String? _message;

  Future<Json> _loadToday() async =>
      await widget.api.request('GET', '/attendance/today') as Json;

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

  Future<Json> _loadSummary() async =>
      await widget.api.request(
            'GET',
            '/attendance/summary/monthly',
            query: {'month': _period.start.month, 'year': _period.start.year},
          )
          as Json;

  Future<List<Json>> _loadHistory() async {
    final rows =
        await widget.api.request(
              'GET',
              '/attendance/my',
              query: {
                'from_date': _date(_period.start),
                'to_date': _date(_period.end),
              },
            )
            as List;
    return rows.cast<Json>();
  }

  void _refresh() {
    setState(() {
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
        FutureBuilder<Json>(
          future: _today,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const LinearProgressIndicator();
            }
            if (snapshot.hasError) {
              return ListTile(title: Text('${snapshot.error}'));
            }
            final data = snapshot.requireData;
            final row = data['attendance'] as Json? ?? data;
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
                    'Last punch · ${_punchTime(row['check_out'] ?? row['check_in'])}',
                  ),
                  trailing: Text('${row['hours_worked'] ?? 0} hours'),
                ),
                if (!checkedOut)
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
        FutureBuilder<Json>(
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
            final data = snapshot.requireData;
            final month = MaterialLocalizations.of(
              context,
            ).formatMonthYear(_period.start);
            return ListTile(
              title: Text(month),
              subtitle: Text(
                'Present ${data['present'] ?? 0} · Absent ${data['absent'] ?? 0} · '
                'Half day ${data['half_day'] ?? 0} · Overtime ${data['overtime_hours'] ?? 0} h',
              ),
            );
          },
        ),
        FutureBuilder<List<Json>>(
          future: _history,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const LinearProgressIndicator();
            }
            if (snapshot.hasError) {
              return ListTile(title: Text('${snapshot.error}'));
            }
            final rows = snapshot.requireData;
            if (rows.isEmpty) {
              return const ListTile(
                title: Text('No attendance records in this period'),
              );
            }
            return Column(
              children: [
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
