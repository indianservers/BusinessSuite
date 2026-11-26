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
  bool _saving = false;
  String? _message;

  Future<Json> _loadToday() async =>
      await widget.api.request('GET', '/attendance/today') as Json;

  String _date(DateTime date) => date.toIso8601String().split('T').first;

  Future<List<Json>> _loadHistory() async {
    final now = DateTime.now();
    final rows =
        await widget.api.request(
              'GET',
              '/attendance/my',
              query: {
                'from_date': _date(DateTime(now.year, now.month)),
                'to_date': _date(now),
              },
            )
            as List;
    return rows.cast<Json>();
  }

  void _refresh() {
    setState(() {
      _today = _loadToday();
      _history = _loadHistory();
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
        Text('This month', style: Theme.of(context).textTheme.titleLarge),
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
                title: Text('No attendance records this month'),
              );
            }
            return Column(
              children: [
                for (final row in rows)
                  ListTile(
                    title: Text(
                      '${row['attendance_date'] ?? row['date'] ?? ''}',
                    ),
                    subtitle: Text('${row['status'] ?? ''}'),
                    trailing: Text('${row['hours_worked'] ?? 0} hours'),
                  ),
              ],
            );
          },
        ),
      ],
    ),
  );
}
