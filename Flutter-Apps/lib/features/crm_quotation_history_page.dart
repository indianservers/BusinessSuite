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
    final after = (entry['after'] as Json?)?['record'] as Json?;
    return {
      for (final field in ['action', 'created_at', 'actor_id', 'reason'])
        field: entry[field],
      'related_id':
          after?['source_id'] ??
          (entry['action'] == 'revision_created' ? (after?['id']) : null),
    };
  }

  void _refresh() => setState(() => _history = _load());

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
            return ListTile(
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
          },
        );
      },
    ),
  );
}
