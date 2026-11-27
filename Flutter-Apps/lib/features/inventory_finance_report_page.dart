import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

enum InventoryFinanceReport {
  stockLedger('Stock Ledger', 'ledger', {
    'movement_date': 'Movement date',
    'movement_type': 'Movement type',
    'reference_number': 'Reference',
    'sku': 'SKU',
    'warehouse_name': 'Warehouse',
    'opening_quantity': 'Opening',
    'quantity_in': 'Quantity in',
    'quantity_out': 'Quantity out',
    'closing_quantity': 'Closing',
    'rate': 'Rate',
    'value': 'Value',
    'notes': 'Notes',
  }),
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
  }),
  glReconciliation(
    'GL Reconciliation',
    'gl',
    {},
    reconciliation: true,
    metrics: {
      'status': 'Status',
      'inventory_ledger_id': 'Inventory ledger',
      'stock_valuation': 'Stock valuation',
      'ledger_balance': 'Ledger balance',
      'difference': 'Difference',
    },
  ),
  grniReconciliation(
    'GRNI Reconciliation',
    'grni',
    {
      'reference_number': 'Reference',
      'grni_value': 'Receipt value',
      'purchase_bill_status': 'Purchase bill',
      'status': 'Status',
    },
    reconciliation: true,
    metrics: {
      'status': 'Status',
      'grni_outstanding': 'Goods received, not invoiced',
      'total': 'Unbilled receipts',
    },
  ),
  cogsReconciliation(
    'COGS Reconciliation',
    'cogs',
    {
      'stock_issue_value': 'Stock issue value',
      'cogs_posted': 'Cost posted',
      'difference': 'Difference',
      'status': 'Status',
    },
    reconciliation: true,
    metrics: {
      'status': 'Status',
      'stock_issue_value': 'Stock issue value',
      'cogs_posted': 'Cost posted',
      'difference': 'Difference',
    },
  ),
  gstReconciliation(
    'GST Reconciliation',
    'gst',
    {
      'hsn_code': 'HSN code',
      'gst_rate_id': 'GST rate',
      'gst_rate_configured': 'GST rate configured',
      'gst_register_lines': 'GST register lines',
      'status': 'Status',
    },
    reconciliation: true,
    metrics: {'total': 'Stock items', 'exceptions': 'Missing mappings'},
  ),
  salesReconciliation(
    'Sales Reconciliation',
    'srm',
    {},
    reconciliation: true,
    metrics: {
      'srm_sales_orders': 'Sales orders',
      'srm_invoices': 'Invoices',
      'inventory_reservations': 'Reservations',
      'posted_inventory_movements': 'Posted movements',
    },
  ),
  stockAudit(
    'Stock Movement Audit',
    'audit',
    {
      'record_type': 'Record type',
      'record_id': 'Record ID',
      'performed_at': 'Recorded at',
    },
    metrics: {'total': 'Audit entries'},
  );

  const InventoryFinanceReport(
    this.title,
    this.slug,
    this.fields, {
    this.reconciliation = false,
    this.metrics = const {},
  });
  final String title, slug;
  final Map<String, String> fields;
  final Map<String, String> metrics;
  final bool reconciliation;

  String get endpoint => switch (this) {
    stockLedger => '/srm/inventory/reports',
    stockAudit => '/fam/inventory/audit',
    _ =>
      '/fam/inventory/${reconciliation ? 'reconciliation' : 'reports'}/$slug',
  };
  String get labelField => switch (this) {
    grossMargin => 'item_name',
    stockLedger ||
    cogs ||
    grniReconciliation ||
    cogsReconciliation => 'movement_number',
    hsn => 'hsn_code',
    glReconciliation => 'inventory_ledger_id',
    gstReconciliation => 'sku',
    salesReconciliation => 'id',
    stockAudit => 'action',
  };
  bool get hasRows => this != glReconciliation && this != salesReconciliation;
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
  int _request = 0;
  static const _pageSize = 25;
  int _page = 1;
  String _search = '';
  late bool _offline = widget.offline;
  bool get _ledger => widget.report == InventoryFinanceReport.stockLedger;
  late var _report = _load(offline: widget.offline);

  Iterable<Json> _rows(Json? data) =>
      (data?['items'] as List? ?? const []).whereType<Json>();

  Future<({Json? record, bool live})> _load({bool offline = false}) {
    final request = ++_request;
    _cached = null;
    final query = _ledger
        ? <String, dynamic>{
            'report': 'ledger',
            'page': _page,
            'per_page': _pageSize,
            if (_search.isNotEmpty) 'search': _search,
          }
        : const <String, dynamic>{};
    final scope = widget.cacheScope;
    return loadCrmDetail(
      api: widget.api,
      path: widget.report.endpoint,
      scope: scope == null || !_ledger
          ? scope
          : '$scope:ledger:$_page:${Uri.encodeComponent(_search)}',
      headers: widget.scopeHeaders,
      offline: offline,
      query: query,
      onCached: (saved) {
        if (mounted && request == _request) {
          setState(() => _cached = saved);
        }
      },
      project: (data) => {
        if (_ledger) 'total': data['total'],
        'currency': _currency(data),
        'total_cogs': data['total_cogs'],
        'duplicate_deduction_guard': data['duplicate_deduction_guard'],
        for (final key in widget.report.metrics.keys) key: data[key],
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
  }

  void _changePage(int page, {String? search}) {
    setState(() {
      _page = page;
      if (search != null) _search = search.trim();
      _report = _load(offline: _offline);
    });
  }

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

  String _metric(String key, Object? value, Json? data) {
    if (value == null) return 'Not available';
    if (const {
      'stock_valuation',
      'ledger_balance',
      'difference',
      'grni_outstanding',
      'grni_value',
      'stock_issue_value',
      'cogs_posted',
    }.contains(key)) {
      final currency = _currency(data);
      return currency is String && currency.isNotEmpty
          ? '$currency ${_value(value)}'
          : 'Currency unavailable';
    }
    return _value(value);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.report.title),
      actions: [
        IconButton(
          tooltip: 'Refresh report',
          onPressed: () => setState(() {
            _offline = false;
            _report = _load();
          }),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _report,
      builder: (context, snapshot) {
        final done = snapshot.connectionState == ConnectionState.done;
        final data = done ? snapshot.data?.record : _cached;
        final rows = _rows(data).toList();
        return ListView.builder(
          padding: const EdgeInsets.all(12),
          itemCount: rows.length + 1,
          itemBuilder: (context, index) {
            if (index == 0) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_ledger)
                    TextField(
                      maxLength: 160,
                      decoration: const InputDecoration(
                        labelText: 'Search stock ledger',
                        counterText: '',
                      ),
                      textInputAction: TextInputAction.search,
                      onSubmitted: (value) => _changePage(1, search: value),
                    ),
                  if (snapshot.hasError) Text('${snapshot.error}'),
                  if (!done) const LinearProgressIndicator(),
                  if (done && !snapshot.hasError && snapshot.data?.live != true)
                    Text(data == null ? 'No saved report.' : 'Saved report'),
                  if (_ledger)
                    Wrap(
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        TextButton(
                          onPressed: done && _page > 1
                              ? () => _changePage(_page - 1)
                              : null,
                          child: const Text('Previous page'),
                        ),
                        Text('Page $_page'),
                        TextButton(
                          onPressed:
                              done &&
                                  data?['total'] is num &&
                                  _page * _pageSize < (data!['total'] as num)
                              ? () => _changePage(_page + 1)
                              : null,
                          child: const Text('Next page'),
                        ),
                      ],
                    ),
                  if (data != null && rows.isEmpty && widget.report.hasRows)
                    const Text('No records.'),
                  if (_currency(data) case final String currency)
                    Text('Currency: $currency'),
                  if (data?['total_cogs'] case final num total)
                    Text('Total COGS: $total'),
                  if (data != null)
                    for (final metric in widget.report.metrics.entries)
                      Text(
                        '${metric.value}: ${_metric(metric.key, data[metric.key], data)}',
                      ),
                  if (data?['duplicate_deduction_guard']
                      case final String guard)
                    Text(guard),
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
                        '${field.value}: ${_metric(field.key, value, data)}'
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
