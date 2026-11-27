import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class CrmQuotationHistoryPage extends StatefulWidget {
  const CrmQuotationHistoryPage({
    super.key,
    required this.api,
    required this.path,
    required this.offline,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.onOpenQuotation,
  });

  final ApiClient api;
  final String path;
  final bool offline;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final void Function(int id, bool offline) onOpenQuotation;

  @override
  State<CrmQuotationHistoryPage> createState() =>
      _CrmQuotationHistoryPageState();
}

class _CrmQuotationHistoryPageState extends State<CrmQuotationHistoryPage> {
  static const _fields = {
    'quote_number': 'Quotation number',
    'number': 'Document number',
    'status': 'Status',
    'currency': 'Currency',
    'issue_date': 'Issued',
    'expiry_date': 'Expires',
    'subtotal': 'Subtotal',
    'discount_total': 'Discount',
    'tax_total': 'Tax',
    'grand_total': 'Grand total',
    'total_amount': 'Total',
    'notes': 'Notes',
    'terms': 'Terms',
    'terms_and_conditions': 'Terms and conditions',
  };

  Json? _cached;
  late var _history = _load(offline: widget.offline);

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: widget.path,
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        project: (record) => {'history': _entries(record).map(_entry).toList()},
        onCached: (saved) {
          if (mounted) setState(() => _cached = saved);
        },
      );

  Iterable<Json> _entries(Json? record) =>
      (record?['history'] as List? ?? const []).whereType<Json>();

  Json _entry(Json entry) {
    final after = entry['after'] is Json ? entry['after'] as Json : null;
    final record = after?['record'] is Json ? after!['record'] as Json : after;
    return {
      for (final field in ['action', 'created_at', 'actor_id', 'reason'])
        field: entry[field],
      'related_id':
          record?['source_id'] ??
          (entry['action'] == 'revision_created' ? (record?['id']) : null),
      'before': _snapshot(entry['before']),
      'after': _snapshot(record),
    };
  }

  Json _snapshot(Object? value) {
    if (value is! Json) return {};
    return {
      for (final key in _fields.keys)
        if (value[key] case final String text when text.isNotEmpty)
          key: text
        else if (value[key] is num)
          key: value[key],
      if (value['lines'] case final List lines)
        'lines': [
          for (final line in lines.whereType<Json>())
            {
              'name': line['name'] ?? line['description'],
              'quantity': line['quantity'],
              'unit_price': line['unit_price'],
              'total': line['line_total'] ?? line['total_amount'],
            },
        ],
    };
  }

  Widget _savedValues(String heading, Json values) => Padding(
    padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(heading, style: Theme.of(context).textTheme.titleSmall),
        for (final field in _fields.entries)
          if (values[field.key] != null)
            SelectableText('${field.value}: ${values[field.key]}'),
        for (final line
            in (values['lines'] as List? ?? const []).whereType<Json>())
          SelectableText(
            "${line['name'] ?? 'Item'} · ${line['quantity'] ?? '—'} × ${line['unit_price'] ?? '—'} · Total ${line['total'] ?? '—'}",
          ),
      ],
    ),
  );

  void _refresh() => setState(() {
    _history = _load();
  });

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Document history'),
      actions: [
        IconButton(
          tooltip: 'Refresh document history',
          onPressed: _refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _history,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final done = snapshot.connectionState == ConnectionState.done;
        final record = snapshot.data?.record ?? _cached;
        final live = done && snapshot.data?.live == true;
        final entries = _entries(record)
            .map(
              (entry) =>
                  entry.containsKey('related_id') ? entry : _entry(entry),
            )
            .toList();
        return ListView.builder(
          itemCount: entries.length + 1,
          itemBuilder: (context, index) {
            if (index == 0) {
              if (!done) return const LinearProgressIndicator();
              if (record == null) {
                return const ListTile(
                  title: Text('No saved document history.'),
                );
              }
              if (entries.isEmpty) {
                return const ListTile(title: Text('No document history yet.'));
              }
              return live
                  ? const SizedBox.shrink()
                  : const ListTile(title: Text('Saved document history'));
            }
            final entry = entries[index - 1];
            final related = entry['related_id'];
            final tile = ListTile(
              title: Text(switch (entry['action']) {
                'document_cancelled' => 'Document cancelled',
                'revision_created' => 'Revision created',
                'revised_from' => 'Revised from original',
                final String action => action.replaceAll('_', ' '),
                _ => 'Document updated',
              }),
              subtitle: Text(
                [
                  '${entry['created_at'] ?? ''} · ${entry['actor_id'] == null ? 'System' : "User ${entry['actor_id']}"}',
                  if (entry['reason'] case final String reason) reason,
                ].join('\n'),
              ),
              trailing: related is int
                  ? IconButton(
                      tooltip: 'Open related quotation',
                      onPressed: () => widget.onOpenQuotation(related, !live),
                      icon: const Icon(Icons.open_in_new),
                    )
                  : null,
            );
            final before = entry['before'] as Json?;
            final after = entry['after'] as Json?;
            if (before?.isNotEmpty != true && after?.isNotEmpty != true) {
              return tile;
            }
            return Column(
              children: [
                tile,
                ExpansionTile(
                  title: const Text('View saved values'),
                  children: [
                    if (before != null && before.isNotEmpty)
                      _savedValues('Before', before),
                    if (after != null && after.isNotEmpty)
                      _savedValues('After', after),
                  ],
                ),
              ],
            );
          },
        );
      },
    ),
  );
}
