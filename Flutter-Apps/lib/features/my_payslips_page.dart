import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import '../core/suite_pdf.dart';

class MyPayslipsPage extends StatefulWidget {
  const MyPayslipsPage({super.key, required this.api});

  final ApiClient api;

  @override
  State<MyPayslipsPage> createState() => _MyPayslipsPageState();
}

class _MyPayslipsPageState extends State<MyPayslipsPage> {
  late DateTime _period = DateTime.now();
  late var _history = _loadHistory();
  late var _slip = _loadSlip();
  final _question = TextEditingController();
  String? _financialYear;
  bool _sending = false;
  bool _downloading = false;
  bool get _busy => _sending || _downloading;

  @override
  void dispose() {
    _question.dispose();
    super.dispose();
  }

  Future<List<Json>> _loadHistory() async =>
      (await widget.api.request('GET', '/payroll/my-payslips') as List)
          .cast<Json>();

  Future<Json?> _loadSlip() async {
    try {
      return await widget.api.request(
            'GET',
            '/payroll/payslip',
            query: {'month': _period.month, 'year': _period.year},
          )
          as Json;
    } on ApiFailure catch (error) {
      if (error.status == 404) return null;
      rethrow;
    }
  }

  String _month(DateTime date) =>
      MaterialLocalizations.of(context).formatMonthYear(date);

  void _select(int month, int year) {
    if (month == _period.month && year == _period.year) return;
    setState(() {
      _period = DateTime(year, month);
      _question.clear();
      _slip = _loadSlip();
    });
  }

  void _refresh() => setState(() {
    _history = _loadHistory();
    _slip = _loadSlip();
  });

  String _amount(Object? amount, Object? currency) {
    final value = num.tryParse('$amount');
    return value == null
        ? '—'
        : '${currency ?? 'INR'} ${value.toStringAsFixed(2)}';
  }

  void _notice(String message) => ScaffoldMessenger.of(
    context,
  ).showSnackBar(SnackBar(content: Text(message)));

  Future<void> _download(int id) async {
    final revision = widget.api.sessionRevision;
    final year = _period.year;
    final month = _period.month.toString().padLeft(2, '0');
    setState(() => _downloading = true);
    try {
      final bytes = await fetchSuitePdf(widget.api, '/payroll/payslip/$id/pdf');
      if (!mounted || revision != widget.api.sessionRevision) return;
      final file = await FilePicker.saveFile(
        fileName: 'payslip-$year-$month.pdf',
        bytes: bytes,
      );
      if (mounted && file != null && revision == widget.api.sessionRevision) {
        _notice('Payslip PDF saved.');
      }
    } catch (_) {
      if (mounted && revision == widget.api.sessionRevision) {
        _notice('Could not download the payslip. Please retry.');
      }
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  Future<void> _sendQuery(int id) async {
    final revision = widget.api.sessionRevision;
    final question = _question.text.trim();
    if (_busy || question.isEmpty) return;
    setState(() => _sending = true);
    try {
      await widget.api.request(
        'POST',
        '/payroll/payslip-queries',
        data: {
          'payroll_record_id': id,
          'subject': 'Payslip query: ${_month(_period)}',
          'description': question,
          'priority': 'Medium',
        },
      );
      if (!mounted || revision != widget.api.sessionRevision) return;
      _question.clear();
      _notice('Payslip query sent to Payroll.');
    } catch (_) {
      if (mounted && revision == widget.api.sessionRevision) {
        _notice('Query could not send. Your question is retained.');
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Widget _historyCard(List<Json> rows) {
    final years = rows
        .map((row) => row['financial_year'])
        .whereType<String>()
        .toSet();
    final selected = years.contains(_financialYear) ? _financialYear : null;
    return Card(
      child: ExpansionTile(
        title: const Text('Available payslips'),
        children: [
          if (years.isNotEmpty)
            DropdownButton<String>(
              value: selected ?? '',
              onChanged: (year) => setState(() => _financialYear = year),
              items: [
                const DropdownMenuItem(
                  value: '',
                  child: Text('All financial years'),
                ),
                for (final year in years)
                  DropdownMenuItem(value: year, child: Text(year)),
              ],
            ),
          for (final row in rows)
            if ((selected == null || row['financial_year'] == selected) &&
                row['month'] is int &&
                row['year'] is int)
              ListTile(
                title: Text(
                  _month(DateTime(row['year'] as int, row['month'] as int)),
                ),
                subtitle: Text(_amount(row['net_salary'], row['currency'])),
                onTap: _busy
                    ? null
                    : () => _select(row['month'] as int, row['year'] as int),
              ),
        ],
      ),
    );
  }

  Widget _details(Json slip) {
    final currency = slip['currency'];
    final id = slip['payroll_record_id'] ?? slip['record_id'] ?? slip['id'];
    final employee = slip['employee'] as Json?;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Net pay · ${_month(_period)}'),
            Text(
              _amount(slip['net_salary'], currency),
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            Text('${slip['payroll_status'] ?? slip['status'] ?? 'Locked'}'),
            if (id is int)
              OutlinedButton.icon(
                onPressed: _busy ? null : () => _download(id),
                icon: const Icon(LucideIcons.download),
                label: Text(_downloading ? 'Preparing PDF…' : 'Download PDF'),
              ),
            ExpansionTile(
              title: const Text('Earnings, deductions & employee details'),
              children: [
                if (employee != null)
                  ListTile(
                    title: Text(
                      [
                        employee['first_name'],
                        employee['last_name'],
                      ].whereType<String>().join(' '),
                    ),
                    subtitle: Text(
                      '${employee['employee_id'] ?? '—'} · Working days ${slip['working_days'] ?? '—'}',
                    ),
                  ),
                for (final (key, label) in const [
                  ('earnings', 'Earnings'),
                  ('deductions', 'Deductions'),
                  ('reimbursements', 'Reimbursements'),
                  ('employer_contributions', 'Employer Contributions'),
                ])
                  if ((slip[key] as List?) case final List lines
                      when lines.isNotEmpty)
                    ExpansionTile(
                      title: Text(label),
                      children: [
                        for (final line in lines.cast<Json>())
                          ListTile(
                            title: Text(
                              '${line['component_name'] ?? line['name'] ?? 'Component'}',
                            ),
                            trailing: Text(_amount(line['amount'], currency)),
                          ),
                      ],
                    ),
                if (slip['ytd'] case final Json totals)
                  ExpansionTile(
                    title: Text(
                      'Year to Date · ${slip['ytd_period_label'] ?? slip['financial_year'] ?? 'Financial year'}',
                    ),
                    children: [
                      for (final total in totals.entries)
                        ListTile(
                          title: Text(total.key.replaceAll('_', ' ')),
                          trailing: Text(_amount(total.value, currency)),
                        ),
                    ],
                  ),
              ],
            ),
            if (id is int) ...[
              TextField(
                controller: _question,
                enabled: !_sending,
                onChanged: (_) => setState(() {}),
                maxLength: 4000,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: 'Question about this payslip?',
                ),
              ),
              FilledButton(
                onPressed: _busy || _question.text.trim().isEmpty
                    ? null
                    : () => _sendQuery(id),
                child: Text(_sending ? 'Sending…' : 'Send query to Payroll'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('My Payslips'),
      actions: [
        IconButton(
          tooltip: 'Refresh payslips',
          onPressed: _busy ? null : _refresh,
          icon: const Icon(LucideIcons.refreshCw),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(12),
      children: [
        Text('Payslip Period', style: Theme.of(context).textTheme.titleMedium),
        Wrap(
          spacing: 16,
          children: [
            DropdownButton<int>(
              value: _period.month,
              onChanged: _busy
                  ? null
                  : (month) => _select(month!, _period.year),
              items: [
                for (var month = 1; month <= 12; month++)
                  DropdownMenuItem(
                    value: month,
                    child: Text(_month(DateTime(_period.year, month))),
                  ),
              ],
            ),
            DropdownButton<int>(
              value: _period.year,
              onChanged: _busy ? null : (year) => _select(_period.month, year!),
              items: [
                for (var year = 2020; year <= 2100; year++)
                  DropdownMenuItem(value: year, child: Text('$year')),
              ],
            ),
          ],
        ),
        FutureBuilder(
          future: _history,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return const Text(
                'Payslip history could not load. Use Refresh to retry.',
              );
            }
            if (snapshot.data case final List<Json> rows) {
              return rows.isEmpty
                  ? const Text('No published payslips in history.')
                  : _historyCard(rows);
            }
            return const SizedBox.shrink();
          },
        ),
        FutureBuilder(
          future: _slip,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const LinearProgressIndicator();
            }
            if (snapshot.hasError) {
              return const Text(
                'Could not load your payslip. Use Refresh to retry.',
              );
            }
            final slip = snapshot.data;
            return slip == null
                ? ListTile(
                    title: Text('No payslip available for ${_month(_period)}.'),
                  )
                : _details(slip);
          },
        ),
      ],
    ),
  );
}
