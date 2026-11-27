import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';

class FinanceVouchersPage extends StatefulWidget {
  const FinanceVouchersPage({
    super.key,
    required this.api,
    this.cacheScope,
    this.scopeHeaders = const {},
    this.offline = false,
    this.canPost = false,
  });

  final ApiClient api;
  final String? cacheScope;
  final Map<String, String> scopeHeaders;
  final bool offline;
  final bool canPost;

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
    final revision = widget.api.sessionRevision;
    Future<({Json? record, bool live})> loadDetail({
      required bool offline,
    }) => loadCrmDetail(
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
    var detail = loadDetail(offline: offline);
    var posting = false;
    String? error;
    Future<void> post(
      BuildContext context,
      StateSetter update,
      Json voucher,
    ) async {
      if (posting || widget.api.sessionRevision != revision) return;
      update(() {
        posting = true;
        error = null;
      });
      try {
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (dialog) => AlertDialog(
            title: const Text('Post this voucher?'),
            content: Text(
              '${voucher['voucher_number']} · Debit ${voucher['total_debit']} · Credit ${voucher['total_credit']}\n\n'
              'Posting records the entries in the ledger.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialog),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialog, true),
                child: const Text('Confirm posting'),
              ),
            ],
          ),
        );
        if (confirmed != true ||
            !context.mounted ||
            widget.api.sessionRevision != revision) {
          return;
        }
        await widget.api.request(
          'POST',
          '$_path/$id/post',
          scopeHeaders: widget.scopeHeaders,
        );
        if (widget.api.sessionRevision != revision) return;
        if (widget.cacheScope case final String scope) {
          final branch = widget.scopeHeaders['X-Suite-Branch'] ?? '';
          for (final path in [_path, '$_path/$id']) {
            final key = '$scope:$path:$branch';
            try {
              await flushCrmDetailWrite(key);
              await SuiteReadCache.clear(key);
            } catch (_) {}
          }
        }
        if (mounted) {
          setState(() {
            _register = _load(offline: false);
          });
        }
        if (context.mounted) {
          update(() {
            detail = loadDetail(offline: false);
          });
        }
      } on ApiFailure catch (failure) {
        if (!context.mounted || widget.api.sessionRevision != revision) return;
        update(() {
          error = failure.message;
          if (failure.connectionFailure ||
              (failure.status ?? 0) >= 500 ||
              failure.status == 409) {
            detail = loadDetail(offline: false);
          }
        });
      } finally {
        if (context.mounted) update(() => posting = false);
      }
    }

    Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => StatefulBuilder(
          builder: (context, update) => Scaffold(
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
                final debit = num.tryParse('${data['total_debit']}');
                final credit = num.tryParse('${data['total_credit']}');
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
                      title: Text(
                        '${data['voucher_date']} · ${data['status']}',
                      ),
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
                    if (error != null) ListTile(title: Text(error!)),
                    if (widget.canPost &&
                        result.live &&
                        data['status'] == 'draft')
                      ListTile(
                        title: FilledButton(
                          onPressed:
                              posting ||
                                  debit == null ||
                                  debit <= 0 ||
                                  debit != credit ||
                                  lines.isEmpty
                              ? null
                              : () => post(context, update, data),
                          child: Text(posting ? 'Posting…' : 'Post voucher'),
                        ),
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
