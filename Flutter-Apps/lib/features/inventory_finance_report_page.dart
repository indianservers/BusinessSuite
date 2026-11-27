import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

enum InventoryFinanceReport {
  grossMargin('Gross Margin', 'gross-margin', {
    'sku': 'SKU',
    'revenue_status': 'Revenue attribution',
    'revenue': 'Revenue',
    'cogs': 'COGS',
    'gross_margin': 'Gross margin',
    'gross_margin_percent': 'Gross margin %',
  }),
  cogs('COGS Report', 'cogs', {
    'movement_date': 'Movement date',
    'movement_type': 'Movement type',
    'cogs_value': 'COGS',
    'voucher_posted': 'Voucher posted',
    'status': 'Status',
  }),
  hsn('HSN Summary', 'hsn-summary', {
    'items': 'Items',
    'quantity': 'Quantity',
    'stock_value': 'Stock value',
  });

  const InventoryFinanceReport(this.title, this.slug, this.fields);
  final String title, slug;
  final Map<String, String> fields;

  String get endpoint => '/fam/inventory/reports/$slug';
  String get labelField => switch (this) {
    grossMargin => 'item_name',
    cogs => 'movement_number',
    hsn => 'hsn_code',
  };
}

class InventoryFinanceReportPage extends StatefulWidget {
  const InventoryFinanceReportPage({
    super.key,
    required this.api,
    required this.report,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
  });

  final ApiClient api;
  final InventoryFinanceReport report;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;

  @override
  State<InventoryFinanceReportPage> createState() =>
      _InventoryFinanceReportPageState();
}

class _InventoryFinanceReportPageState
    extends State<InventoryFinanceReportPage> {
  Json? _cached;
  late var _report = _load(offline: widget.offline);

  Iterable<Json> _rows(Json? data) =>
      (data?['items'] as List? ?? const []).whereType<Json>();

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: widget.report.endpoint,
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        onCached: (saved) {
          if (mounted) setState(() => _cached = saved);
        },
        project: (data) => {
          'currency': _currency(data),
          'total_cogs': data['total_cogs'],
          'items': [
            for (final row in _rows(data))
              {
                for (final key in [
                  widget.report.labelField,
                  ...widget.report.fields.keys,
                ])
                  key: row[key],
              },
          ],
        },
      );

  String _value(Object value) => switch (value) {
    true => 'Yes',
    false => 'No',
    _ => '$value',
  };

  Object? _currency(Json? data) {
    final attribution = data?['attribution'];
    return data?['currency'] ??
        (attribution is Json ? attribution['currency'] : null);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.report.title),
      actions: [
        IconButton(
          tooltip: 'Refresh report',
          onPressed: () => setState(() => _report = _load()),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _report,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final done = snapshot.connectionState == ConnectionState.done;
        final data = snapshot.data?.record ?? _cached;
        final rows = _rows(data).toList();
        return ListView.builder(
          padding: const EdgeInsets.all(12),
          itemCount: rows.length + 1,
          itemBuilder: (context, index) {
            if (index == 0) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (!done) const LinearProgressIndicator(),
                  if (done && snapshot.data?.live != true)
                    Text(data == null ? 'No saved report.' : 'Saved report'),
                  if (data != null && rows.isEmpty) const Text('No records.'),
                  if (_currency(data) case final String currency)
                    Text('Currency: $currency'),
                  if (data?['total_cogs'] case final num total)
                    Text('Total COGS: $total'),
                ],
              );
            }
            final row = rows[index - 1];
            return Card(
              child: ListTile(
                title: Text("${row[widget.report.labelField] ?? 'Record'}"),
                subtitle: Text(
                  [
                    for (final field in widget.report.fields.entries)
                      if (row[field.key] case final Object value)
                        '${field.value}: ${_value(value)}'
                      else if (field.key == 'gross_margin' ||
                          field.key == 'gross_margin_percent')
                        '${field.value}: Not available',
                  ].join('\n'),
                ),
              ),
            );
          },
        );
      },
    ),
  );
}
