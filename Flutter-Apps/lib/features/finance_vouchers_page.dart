import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class FinanceVouchersPage extends StatefulWidget {
  const FinanceVouchersPage({
    super.key,
    required this.api,
    this.cacheScope,
    this.scopeHeaders = const {},
    this.offline = false,
  });

  final ApiClient api;
  final String? cacheScope;
  final Map<String, String> scopeHeaders;
  final bool offline;

  @override
  State<FinanceVouchersPage> createState() => _FinanceVouchersPageState();
}

class _FinanceVouchersPageState extends State<FinanceVouchersPage> {
  static const _path = '/fam/vouchers';
  late var _register = _load(offline: widget.offline);
  String _search = '';

  Json _summary(Json row) => {
    for (final key in [
      'id',
      'voucher_number',
      'voucher_date',
      'status',
      'total_debit',
      'total_credit',
      'source_module',
    ])
      key: row[key],
  };

  Future<({Json? record, bool live})> _load({required bool offline}) =>
      loadCrmDetail(
        api: widget.api,
        path: _path,
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        project: (data) => {
          'items': [
            for (final row in (data['items'] as List).cast<Json>())
              _summary(row),
          ],
        },
      );

  void _open(Json row, bool offline) {
    final id = row['id'];
    if (id is! int) return;
    final detail = loadCrmDetail(
      api: widget.api,
      path: '$_path/$id',
      scope: widget.cacheScope,
      headers: widget.scopeHeaders,
      offline: offline,
      project: (data) => {
        ..._summary(data),
        'reference_number': data['reference_number'],
        'lines': [
          for (final line in (data['lines'] as List? ?? const []).cast<Json>())
            {
              for (final key in ['ledger_id', 'debit_amount', 'credit_amount'])
                key: line[key],
            },
        ],
      },
    );
    Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(title: Text('${row['voucher_number']}')),
          body: FutureBuilder(
            future: detail,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return Center(child: Text('${snapshot.error}'));
              }
              final result = snapshot.requireData;
              final data = result.record ?? row;
              final lines = (data['lines'] as List? ?? const []).cast<Json>();
              return ListView(
                children: [
                  if (!result.live)
                    ListTile(
                      title: Text(
                        result.record == null
                            ? 'Saved voucher summary'
                            : 'Saved voucher details',
                      ),
                    ),
                  ListTile(
                    title: Text('${data['voucher_date']} · ${data['status']}'),
                    subtitle: Text('${data['source_module'] ?? ''}'),
                  ),
                  if (data['reference_number'] case final String reference)
                    ListTile(
                      title: const Text('Reference'),
                      trailing: Text(reference),
                    ),
                  ListTile(
                    title: const Text('Total debit'),
                    trailing: Text('${data['total_debit'] ?? '—'}'),
                  ),
                  ListTile(
                    title: const Text('Total credit'),
                    trailing: Text('${data['total_credit'] ?? '—'}'),
                  ),
                  ListTile(
                    title: const Text('Entry lines'),
                    subtitle: result.record == null
                        ? const Text(
                            'Open this voucher online to save its lines.',
                          )
                        : lines.isEmpty
                        ? const Text('No entry lines')
                        : null,
                  ),
                  for (final line in lines)
                    ListTile(
                      title: Text('Ledger #${line['ledger_id']}'),
                      subtitle: line['narration'] is String
                          ? Text(line['narration'] as String)
                          : null,
                      trailing: Text(
                        'Debit ${line['debit_amount'] ?? '—'}\nCredit ${line['credit_amount'] ?? '—'}',
                        textAlign: TextAlign.end,
                      ),
                    ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Voucher register'),
      actions: [
        IconButton(
          tooltip: 'Refresh vouchers',
          icon: const Icon(LucideIcons.refreshCw),
          onPressed: () => setState(() {
            _register = _load(offline: false);
          }),
        ),
      ],
    ),
    body: FutureBuilder(
      future: _register,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final result = snapshot.requireData;
        final data = result.record;
        if (data == null) {
          return const Center(
            child: Text(
              'Open the voucher register online to save it on this device.',
            ),
          );
        }
        final rows = (data['items'] as List)
            .cast<Json>()
            .where(
              (row) =>
                  [
                    row['voucher_number'],
                    row['voucher_date'],
                    row['status'],
                    row['source_module'],
                  ].whereType<String>().any(
                    (value) => value.toLowerCase().contains(_search),
                  ),
            )
            .toList();
        return Column(
          children: [
            if (!result.live) const ListTile(title: Text('Saved vouchers')),
            Padding(
              padding: const EdgeInsets.all(12),
              child: TextField(
                decoration: const InputDecoration(
                  labelText: 'Search vouchers',
                  prefixIcon: Icon(LucideIcons.search),
                ),
                onChanged: (value) =>
                    setState(() => _search = value.trim().toLowerCase()),
              ),
            ),
            Expanded(
              child: rows.isEmpty
                  ? const Center(child: Text('No matching vouchers'))
                  : ListView.builder(
                      itemCount: rows.length,
                      itemBuilder: (context, index) {
                        final row = rows[index];
                        return ListTile(
                          title: Text('${row['voucher_number']}'),
                          subtitle: Text(
                            '${row['voucher_date']} · ${row['status']}',
                          ),
                          trailing: Text('${row['source_module'] ?? ''}'),
                          onTap: () => _open(row, !result.live),
                        );
                      },
                    ),
            ),
          ],
        );
      },
    ),
  );
}
