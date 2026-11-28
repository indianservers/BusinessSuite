import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import 'gst_invoice_page.dart';
import 'invoice_receipt_dialog.dart';

class GstCollectionsPage extends StatefulWidget {
  const GstCollectionsPage({
    super.key,
    required this.api,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
    this.canExport = false,
  });

  static const endpoint = '/srm/business/collection-invoices';
  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;
  final bool canExport;

  @override
  State<GstCollectionsPage> createState() => _GstCollectionsPageState();
}

class _GstCollectionsPageState extends State<GstCollectionsPage> {
  bool _outstandingOnly = true;
  String _query = '';
  Json? _cached;
  int _generation = 0;
  late var _records = _load(offline: widget.offline);

  Future<({Json? record, bool live})> _load({bool offline = false}) {
    final generation = ++_generation;
    return loadCrmDetail(
      api: widget.api,
      path: GstCollectionsPage.endpoint,
      scope: widget.cacheScope,
      headers: widget.scopeHeaders,
      offline: offline,
      onCached: (record) {
        if (mounted && generation == _generation) {
          setState(() => _cached = record);
        }
      },
      project: (record) => {
        'items': [
          for (final invoice in _rows(record))
            {
              'id': invoice['id'],
              'customer_id': invoice['customer_id'],
              for (final field in GstInvoicePage.summaryFields)
                field: invoice[field],
              'collection_hold': invoice['collection_hold'],
            },
        ],
      },
    );
  }

  Iterable<Json> _rows(Json record) =>
      (record['items'] as List? ?? const []).whereType<Json>();

  void _refresh() => setState(() {
    _cached = null;
    _records = _load();
  });

  Future<void> _recordReceipt(Json invoice, String scope) async {
    final revision = widget.api.sessionRevision;
    final branch = invoice['branch_id'];
    final result = await showDialog<Json>(
      context: context,
      barrierDismissible: false,
      builder: (_) => InvoiceReceiptDialog(
        api: widget.api,
        invoiceId: invoice['id'] as int,
        invoice: invoice,
        scope: scope,
        headers: {
          ...widget.scopeHeaders,
          if (branch is int && branch > 0) 'X-Suite-Branch': '$branch',
        },
      ),
    );
    if (!mounted || result == null || revision != widget.api.sessionRevision) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          result['reversed'] == true
              ? 'Receipt #${result['receipt_id']} was reversed.'
              : 'Recorded receipt #${result['receipt_id']}',
        ),
      ),
    );
    _refresh();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Collections'),
      actions: [
        IconButton(
          tooltip: 'Refresh collections',
          onPressed: _refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: TextField(
            decoration: const InputDecoration(
              labelText: 'Find invoice',
              prefixIcon: Icon(Icons.search),
            ),
            onChanged: (value) =>
                setState(() => _query = value.trim().toLowerCase()),
          ),
        ),
        FilterChip(
          label: const Text('Outstanding only'),
          selected: _outstandingOnly,
          onSelected: (value) => setState(() => _outstandingOnly = value),
        ),
        Expanded(
          child: FutureBuilder(
            future: _records,
            builder: (context, snapshot) {
              final loading = snapshot.connectionState != ConnectionState.done;
              if (!loading && snapshot.hasError) {
                return Center(child: Text('${snapshot.error}'));
              }
              final record = loading ? _cached : snapshot.data?.record;
              if (record == null) {
                return Center(
                  child: loading
                      ? const CircularProgressIndicator()
                      : const Text('No collections saved on this device'),
                );
              }
              final live = !loading && snapshot.data?.live == true;
              final canRecord = live && record['can_record'] == true;
              final rows = _rows(record).where((invoice) {
                if (invoice['id'] is! int ||
                    invoice['document_status'] != 'issued') {
                  return false;
                }
                final balance =
                    num.tryParse('${invoice['balance_amount']}') ?? 0;
                return (!_outstandingOnly || balance > 0) &&
                    '${invoice['invoice_number']} ${invoice['customer_id'] ?? ''}'
                        .toLowerCase()
                        .contains(_query);
              }).toList();
              return Column(
                children: [
                  if (loading) const LinearProgressIndicator(),
                  if (!live) const Text('Saved collections'),
                  if (rows.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(16),
                      child: Text('No matching invoices'),
                    )
                  else
                    Expanded(
                      child: ListView.builder(
                        itemCount: rows.length,
                        itemBuilder: (context, index) {
                          final invoice = rows[index];
                          return ListTile(
                            title: Text('${invoice['invoice_number']}'),
                            subtitle: Text(
                              [
                                'Outstanding · ${invoice['currency']} ${invoice['balance_amount']}',
                                if (invoice['collection_hold'] == true)
                                  'Collections on hold',
                              ].join('\n'),
                            ),
                            trailing: canRecord && widget.cacheScope != null
                                ? IconButton(
                                    tooltip:
                                        'Record payment for ${invoice['invoice_number']}',
                                    icon: const Icon(
                                      Icons.receipt_long_outlined,
                                    ),
                                    onPressed: () => _recordReceipt(
                                      invoice,
                                      widget.cacheScope!,
                                    ),
                                  )
                                : const Icon(Icons.chevron_right),
                            onTap: () => Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) => GstInvoicePage(
                                  api: widget.api,
                                  id: invoice['id'] as int,
                                  scopeHeaders: widget.scopeHeaders,
                                  summary: invoice,
                                  cacheScope: widget.cacheScope,
                                  canExport: widget.canExport,
                                  offline: !live,
                                  onChanged: _refresh,
                                ),
                              ),
                            ),
                          );
                        },
                      ),
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
