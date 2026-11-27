import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';

class MyRosterPage extends StatefulWidget {
  const MyRosterPage({
    super.key,
    required this.api,
    required this.employeeId,
    this.cacheScope,
    this.offline = false,
  });

  final ApiClient api;
  final int? employeeId;
  final String? cacheScope;
  final bool offline;

  @override
  State<MyRosterPage> createState() => _MyRosterPageState();
}

class _MyRosterPageState extends State<MyRosterPage> {
  late DateTimeRange _period = _nextWeek();
  late bool _offline = widget.offline;
  late var _roster = _load(offline: _offline);

  DateTimeRange _nextWeek() {
    final today = DateUtils.dateOnly(DateTime.now());
    return DateTimeRange(start: today, end: DateUtils.addDaysToDate(today, 7));
  }

  String _date(DateTime value) => value.toIso8601String().split('T').first;

  Future<({List<Json> rows, bool saved})> _load({required bool offline}) async {
    final employee = widget.employeeId;
    if (employee == null) return (rows: <Json>[], saved: false);
    final api = widget.api;
    final revision = api.sessionRevision;
    final from = _date(_period.start);
    final to = _date(_period.end);
    final key = widget.cacheScope == null
        ? null
        : '${widget.cacheScope}:my-roster:$employee:$from:$to';
    void checkSession() {
      if (api.sessionRevision != revision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
    }

    if (!offline) {
      try {
        final response = await api.request(
          'GET',
          '/hrms/shift-roster',
          query: {'from': from, 'to': to, 'employeeId': employee},
        );
        checkSession();
        final rows = [
          for (final row
              in (response is List
                  ? response
                  : (response as Json)['rosters'] as List))
            if (((row as Json)['employeeId'] ?? row['employee_id']) == employee)
              {
                'date': row['roster_date'] ?? row['rosterDate'],
                'shift': row['shift_name'] ?? (row['shift'] as Json?)?['name'],
                'code': row['shift_code'] ?? (row['shift'] as Json?)?['code'],
                'status': row['status'],
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
    List<Json>? saved;
    if (key != null) {
      try {
        saved = await SuiteReadCache.read(key);
      } catch (_) {}
    }
    checkSession();
    if (saved == null) throw ApiFailure('Connect to load your shift schedule.');
    return (rows: saved, saved: true);
  }

  Future<void> _changePeriod() async {
    final period = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100, 12, 31),
      initialDateRange: _period,
      helpText: 'Roster period',
    );
    if (!mounted || period == null || period == _period) return;
    final days = DateTime.utc(period.end.year, period.end.month, period.end.day)
        .difference(
          DateTime.utc(period.start.year, period.start.month, period.start.day),
        )
        .inDays;
    if (days > 62) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Choose a period of 63 days or less.')),
      );
      return;
    }
    setState(() {
      _period = period;
      _roster = _load(offline: _offline);
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('My Roster'),
      actions: [
        if (widget.employeeId != null)
          IconButton(
            tooltip: 'Refresh roster',
            onPressed: () => setState(() {
              _offline = false;
              _roster = _load(offline: _offline);
            }),
            icon: const Icon(Icons.refresh),
          ),
      ],
    ),
    body: widget.employeeId == null
        ? const Center(
            child: Text('An employee profile is required to view your roster.'),
          )
        : Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ListTile(
                leading: const Icon(Icons.calendar_today_outlined),
                title: const Text('Shift Schedule'),
                subtitle: Text(
                  '${_date(_period.start)} – ${_date(_period.end)}',
                ),
                trailing: const Icon(Icons.edit_calendar_outlined),
                onTap: _changePeriod,
              ),
              Expanded(
                child: FutureBuilder(
                  future: _roster,
                  builder: (context, snapshot) {
                    if (snapshot.connectionState != ConnectionState.done) {
                      return const Center(child: CircularProgressIndicator());
                    }
                    if (snapshot.hasError) {
                      return Center(child: Text('${snapshot.error}'));
                    }
                    final result = snapshot.requireData;
                    return ListView(
                      children: [
                        if (result.saved)
                          const ListTile(title: Text('Saved shift schedule')),
                        if (result.rows.isEmpty)
                          const ListTile(
                            title: Text('No roster found for this period.'),
                          ),
                        for (final row in result.rows)
                          ListTile(
                            title: Text('${row['shift'] ?? 'Weekly Off'}'),
                            subtitle: Text(
                              [
                                row['date'],
                                row['code'],
                              ].whereType<String>().join(' · '),
                            ),
                            trailing: Text('${row['status'] ?? 'Scheduled'}'),
                          ),
                      ],
                    );
                  },
                ),
              ),
            ],
          ),
  );
}
