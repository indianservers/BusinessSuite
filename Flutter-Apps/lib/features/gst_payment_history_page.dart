import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class GstPaymentHistoryPage extends StatefulWidget {
  const GstPaymentHistoryPage({
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
  State<GstPaymentHistoryPage> createState() => _GstPaymentHistoryPageState();
}

class _GstPaymentHistoryPageState extends State<GstPaymentHistoryPage> {
  Json? _cached;
  int _generation = 0;
  late var _history = _load(offline: widget.offline);

  Iterable<Json> _payments(Json invoice) =>
      (invoice['payments'] as List? ?? const []).whereType<Json>();

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
          for (final payment in _payments(record))
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
      title: const Text('Payment history'),
      actions: [
        IconButton(
          tooltip: 'Refresh payment history',
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
                : const Text('No payment history saved on this device'),
          );
        }
        final payments = _payments(record);
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (loading) const LinearProgressIndicator(),
            Text(
              '${record['invoice_number']}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (loading || snapshot.data?.live != true)
              const Text('Saved payment history'),
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
          ],
        );
      },
    ),
  );
}
