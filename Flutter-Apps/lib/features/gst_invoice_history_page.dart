import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class GstInvoiceHistoryPage extends StatefulWidget {
  const GstInvoiceHistoryPage({
    super.key,
    required this.api,
    required this.invoiceId,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
  });

  final ApiClient api;
  final int invoiceId;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;

  @override
  State<GstInvoiceHistoryPage> createState() => _GstInvoiceHistoryPageState();
}

class _GstInvoiceHistoryPageState extends State<GstInvoiceHistoryPage> {
  Json? _cached;
  int _generation = 0;
  late var _history = _load(offline: widget.offline);

  Iterable<Json> _rows(Json invoice, String field) =>
      (invoice[field] as List? ?? const []).whereType<Json>();

  Future<({Json? record, bool live})> _load({bool offline = false}) {
    final generation = ++_generation;
    final path = '/srm/business/invoices/${widget.invoiceId}';
    final branch = widget.scopeHeaders['X-Suite-Branch'] ?? '';
    final scope = widget.cacheScope;
    return loadCrmDetail(
      api: widget.api,
      path: path,
      scope: scope,
      cacheKey: scope == null ? null : '$scope:$path:$branch:payment-history',
      headers: widget.scopeHeaders,
      offline: offline,
      onCached: (record) {
        if (mounted && generation == _generation) {
          setState(() => _cached = record);
        }
      },
      project: (record) => {
        'invoice_number': record['invoice_number'],
        'currency': record['currency'],
        'payments': [
          for (final payment in _rows(record, 'payments'))
            {
              for (final key in [
                'receipt_id',
                'amount',
                'allocated_at',
                'reversed_at',
              ])
                key: payment[key],
            },
        ],
        'deliveries': [
          for (final delivery in _rows(record, 'deliveries'))
            {
              for (final key in ['status', 'created_at', 'request_id', 'error'])
                key: delivery[key],
            },
        ],
        'history': [
          for (final event in _rows(record, 'history'))
            {
              for (final key in [
                'from_status',
                'to_status',
                'created_at',
                'notes',
              ])
                key: event[key],
            },
        ],
      },
    );
  }

  String _dateLabel(BuildContext context, String value) {
    final date = DateTime.tryParse(value)?.toLocal();
    if (date == null) return value;
    return MaterialLocalizations.of(context).formatCompactDate(date);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Invoice history'),
      actions: [
        IconButton(
          tooltip: 'Refresh invoice history',
          icon: const Icon(Icons.refresh),
          onPressed: () => setState(() {
            _cached = null;
            _history = _load();
          }),
        ),
      ],
    ),
    body: FutureBuilder(
      future: _history,
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
                : const Text('No invoice history saved on this device'),
          );
        }
        final payments = _rows(record, 'payments');
        final deliveries = _rows(record, 'deliveries');
        final history = _rows(record, 'history');
        final sectionStyle = Theme.of(context).textTheme.titleMedium;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (loading) const LinearProgressIndicator(),
            Text(
              '${record['invoice_number']}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (loading || snapshot.data?.live != true)
              const Text('Saved invoice history'),
            Text('Payments', style: sectionStyle),
            if (payments.isEmpty)
              const ListTile(title: Text('No receipts recorded')),
            for (final payment in payments)
              ListTile(
                title: Text('Receipt #${payment['receipt_id']}'),
                trailing: Text('${record['currency']} ${payment['amount']}'),
                subtitle: Text(
                  [
                    if (payment['allocated_at'] case final String date)
                      'Applied ${_dateLabel(context, date)}',
                    if (payment['reversed_at'] case final String date)
                      'Reversed ${_dateLabel(context, date)}',
                  ].join('\n'),
                ),
              ),
            const Divider(),
            Text('Delivery attempts', style: sectionStyle),
            if (deliveries.isEmpty)
              ListTile(
                title: Text(
                  record.containsKey('deliveries')
                      ? 'No delivery attempts recorded'
                      : 'No delivery history saved on this device',
                ),
              ),
            for (final delivery in deliveries)
              ListTile(
                title: Text(
                  '${delivery['status'] ?? 'Unknown status'}'.replaceAll(
                    '_',
                    ' ',
                  ),
                ),
                subtitle: Text(
                  [
                    if (delivery['created_at'] case final String date)
                      _dateLabel(context, date),
                    if (delivery['request_id'] case final String reference)
                      'Reference $reference',
                    if (delivery['error'] case final String error
                        when error.isNotEmpty)
                      error,
                  ].join('\n'),
                ),
              ),
            const Divider(),
            Text('Status history', style: sectionStyle),
            if (history.isEmpty)
              ListTile(
                title: Text(
                  record.containsKey('history')
                      ? 'No status changes recorded'
                      : 'No status history saved on this device',
                ),
              ),
            for (final event in history)
              ListTile(
                title: Text(
                  [
                    if (event['from_status'] != null &&
                        event['from_status'] != event['to_status'])
                      event['from_status'],
                    event['to_status'] ?? 'Unknown status',
                  ].join(' → ').replaceAll('_', ' '),
                ),
                subtitle: Text(
                  [
                    if (event['created_at'] case final String date)
                      _dateLabel(context, date),
                    if (event['notes'] case final String notes
                        when notes.isNotEmpty)
                      notes,
                  ].join('\n'),
                ),
              ),
          ],
        );
      },
    ),
  );
}
