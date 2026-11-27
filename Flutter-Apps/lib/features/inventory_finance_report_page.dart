import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import '../core/suite_pdf.dart';

const _movementFields = {
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
  'created_by': 'Created by',
  'posted_by': 'Posted by',
  'notes': 'Notes',
  'status': 'Status',
};

enum InventoryFinanceReport {
  stockLedger('Stock Ledger', 'ledger', _movementFields, movementReport: true),
  salesMovements(
    'Sales Movement',
    'sales',
    _movementFields,
    movementReport: true,
  ),
  purchaseMovements(
    'Purchase Movements',
    'purchases',
    _movementFields,
    movementReport: true,
  ),
  stockAdjustments(
    'Stock Adjustments',
    'adjustments',
    _movementFields,
    movementReport: true,
  ),
  stockTransfers(
    'Stock Transfers',
    'transfers',
    _movementFields,
    movementReport: true,
  ),
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
    this.movementReport = false,
    this.metrics = const {},
  });
  final String title, slug;
  final Map<String, String> fields;
  final Map<String, String> metrics;
  final bool reconciliation;
  final bool movementReport;

  String get endpoint => switch (this) {
    _ when movementReport => '/srm/inventory/reports',
    stockAudit => '/fam/inventory/audit',
    _ =>
      '/fam/inventory/${reconciliation ? 'reconciliation' : 'reports'}/$slug',
  };
  String get labelField => switch (this) {
    grossMargin => 'item_name',
    stockLedger ||
    salesMovements ||
    purchaseMovements ||
    stockAdjustments ||
    stockTransfers => 'movement_number',
    cogs || grniReconciliation || cogsReconciliation => 'movement_number',
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
    this.initialFilters = const {},
    this.initialSearch = '',
    this.movementId,
  });

  final ApiClient api;
  final InventoryFinanceReport report;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;
  final Map<String, String> initialFilters;
  final String initialSearch;
  final int? movementId;

  @override
  State<InventoryFinanceReportPage> createState() =>
      _InventoryFinanceReportPageState();
}

class _InventoryFinanceReportPageState
    extends State<InventoryFinanceReportPage> {
  Json? _cached;
  int _request = 0;
  int _pageSize = 25;
  int _page = 1;
  late String _search = widget.initialSearch;
  late Map<String, String> _filters = widget.initialFilters;
  late bool _offline = widget.offline;
  bool _exporting = false;
  bool get _ledger => widget.report.movementReport;
  late var _report = _load(offline: widget.offline);

  Iterable<Json> _rows(Json? data) =>
      (data?['items'] as List? ?? const []).whereType<Json>();

  Json get _ledgerQuery => {
    'report': widget.report.slug,
    'page': _page,
    'per_page': _pageSize,
    if (_search.isNotEmpty) 'search': _search,
    ..._filters,
    if (widget.movementId case final int id) 'movement_id': id,
  };

  Future<({Json? record, bool live})> _load({bool offline = false}) {
    final request = ++_request;
    _cached = null;
    final scope = widget.cacheScope;
    final movement = widget.movementId == null
        ? ''
        : ':movement:${widget.movementId}';
    final ledgerScope =
        '$scope:${widget.report.slug}$movement:$_page:${Uri.encodeComponent(_search)}';
    return loadCrmDetail(
      api: widget.api,
      path: widget.report.endpoint,
      scope: scope == null || !_ledger
          ? scope
          : _filters.isEmpty && _pageSize == 25
          ? ledgerScope
          : '$ledgerScope:$_pageSize:${Uri.encodeComponent(jsonEncode(_filters))}',
      headers: widget.scopeHeaders,
      offline: offline,
      query: _ledger ? _ledgerQuery : const {},
      onCached: (saved) {
        if (mounted && request == _request) {
          setState(() => _cached = saved);
        }
      },
      project: (data) => {
        if (_ledger) 'total': data['total'],
        if (_ledger) 'as_of': data['as_of'],
        if (_ledger) 'warnings': data['warnings'],
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
                if (_ledger) 'movement_id',
              ])
                key: row[key],
            },
        ],
      },
    );
  }

  Future<void> _exportLedger(String format) async {
    if (_exporting || _offline) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    final path = widget.report.endpoint;
    final headers = widget.scopeHeaders;
    final query = {..._ledgerQuery, 'export_format': format};
    setState(() => _exporting = true);
    try {
      final bytes = format == 'pdf'
          ? await fetchSuitePdf(api, path, query: query, scopeHeaders: headers)
          : await _fetchLedgerSpreadsheet(api, path, query, headers);
      if (!mounted || revision != api.sessionRevision) return;
      final saved = await FilePicker.saveFile(
        fileName: 'inventory-srm-${widget.report.slug}.$format',
        bytes: bytes,
        mimeType: format == 'pdf'
            ? 'application/pdf'
            : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      );
      if (mounted && saved != null && revision == api.sessionRevision) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Inventory report export saved.')),
        );
      }
    } catch (error) {
      if (mounted && revision == api.sessionRevision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<Uint8List> _fetchLedgerSpreadsheet(
    ApiClient api,
    String path,
    Json query,
    Map<String, String> headers,
  ) async {
    final response =
        await api.request(
              'GET',
              path,
              query: query,
              scopeHeaders: headers,
              responseType: ResponseType.bytes,
              returnResponse: true,
            )
            as Response;
    final data = response.data;
    if (response.statusCode != 200 ||
        data is! List<int> ||
        data.length < 4 ||
        data[0] != 0x50 ||
        data[1] != 0x4b ||
        data[2] != 3 ||
        data[3] != 4) {
      throw ApiFailure('The server did not return a spreadsheet.');
    }
    return Uint8List.fromList(data);
  }

  void _openMovement(int id) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => InventoryFinanceReportPage(
          api: widget.api,
          report: InventoryFinanceReport.stockLedger,
          scopeHeaders: widget.scopeHeaders,
          cacheScope: widget.cacheScope,
          offline: _offline,
          initialFilters: _filters,
          initialSearch: _search,
          movementId: id,
        ),
      ),
    );
  }

  void _changePage(
    int page, {
    String? search,
    int? pageSize,
    Map<String, String>? filters,
  }) {
    setState(() {
      _page = page;
      if (search != null) _search = search.trim();
      if (pageSize != null) _pageSize = pageSize;
      if (filters != null) _filters = filters;
      _report = _load(offline: _offline);
    });
  }

  Future<void> _editFilters() async {
    final filters = await showModalBottomSheet<Map<String, String>>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => _LedgerFilters(values: _filters),
    );
    if (mounted && filters != null) _changePage(1, filters: filters);
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
      title: Text(
        widget.movementId == null ? widget.report.title : 'Stock Movement',
      ),
      actions: [
        IconButton(
          tooltip: 'Refresh report',
          onPressed: () => setState(() {
            _offline = false;
            _report = _load();
          }),
          icon: const Icon(Icons.refresh),
        ),
        if (_ledger)
          PopupMenuButton<String>(
            tooltip: 'Export stock ledger',
            enabled: !_offline && !_exporting,
            icon: const Icon(Icons.download),
            onSelected: _exportLedger,
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'xlsx', child: Text('Export Excel')),
              PopupMenuItem(value: 'pdf', child: Text('Export PDF')),
            ],
          ),
        if (_ledger)
          IconButton(
            tooltip: 'Stock ledger filters',
            onPressed: _editFilters,
            icon: Badge(
              isLabelVisible: _filters.isNotEmpty,
              label: Text('${_filters.length}'),
              child: const Icon(Icons.filter_list),
            ),
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
                    TextFormField(
                      initialValue: _search,
                      maxLength: 160,
                      decoration: const InputDecoration(
                        labelText: 'Search stock ledger',
                        counterText: '',
                      ),
                      textInputAction: TextInputAction.search,
                      onFieldSubmitted: (value) =>
                          _changePage(1, search: value),
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
                        DropdownButton<int>(
                          value: _pageSize,
                          onChanged: !done
                              ? null
                              : (value) {
                                  if (value != null) {
                                    _changePage(1, pageSize: value);
                                  }
                                },
                          items: [
                            for (final size in [25, 50, 100])
                              DropdownMenuItem(
                                value: size,
                                child: Text('$size per page'),
                              ),
                          ],
                        ),
                      ],
                    ),
                  if (data != null && rows.isEmpty && widget.report.hasRows)
                    const Text('No records.'),
                  if (_ledger && data?['as_of'] is String)
                    Text('Posted movements · As of ${data!['as_of']}'),
                  if (data?['warnings'] case final List warnings)
                    if (_ledger && warnings.whereType<String>().isNotEmpty)
                      ExpansionTile(
                        title: const Text('Calculation basis and limitations'),
                        children: [
                          for (final warning in warnings.whereType<String>())
                            ListTile(title: Text(warning)),
                        ],
                      ),
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
            final movement = row['movement_id'];
            return Card(
              child: ListTile(
                trailing:
                    _ledger && widget.movementId == null && movement is int
                    ? IconButton(
                        tooltip: 'View source movement',
                        icon: const Icon(Icons.chevron_right),
                        onPressed: () => _openMovement(movement),
                      )
                    : null,
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

class _LedgerFilters extends StatefulWidget {
  const _LedgerFilters({required this.values});

  final Map<String, String> values;

  @override
  State<_LedgerFilters> createState() => _LedgerFiltersState();
}

class _LedgerFiltersState extends State<_LedgerFilters> {
  final _form = GlobalKey<FormState>();
  late final _values = Map<String, String>.of(widget.values);

  static const _fields = {
    'start_date': 'From',
    'end_date': 'To',
    'product_id': 'Product ID',
    'warehouse_id': 'Warehouse ID',
    'category': 'Category ID',
    'transaction_type': 'Transaction type',
  };

  String? _validate(String key, String input) {
    final value = input.trim();
    if (value.isEmpty) return null;
    if (key.endsWith('_date')) {
      final date = DateTime.tryParse(value);
      if (date == null ||
          date.year < 1 ||
          date.toIso8601String().split('T').first != value) {
        return 'Enter a date as YYYY-MM-DD.';
      }
      final from = _values['start_date'] ?? '';
      if (key == 'end_date' && from.isNotEmpty && value.compareTo(from) < 0) {
        return 'Choose a date on or after From.';
      }
    }
    if (key.endsWith('_id') && (int.tryParse(value) ?? 0) < 1) {
      return 'Enter a positive ID.';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(
      16,
      16,
      16,
      MediaQuery.viewInsetsOf(context).bottom + 16,
    ),
    child: Form(
      key: _form,
      child: ListView(
        shrinkWrap: true,
        children: [
          Text(
            'Stock ledger filters',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          for (final field in _fields.entries)
            TextFormField(
              initialValue: _values[field.key],
              decoration: InputDecoration(
                labelText: field.value,
                hintText: field.key.endsWith('_date') ? 'YYYY-MM-DD' : null,
              ),
              keyboardType: field.key.endsWith('_id')
                  ? TextInputType.number
                  : null,
              inputFormatters: [
                if (field.key.endsWith('_id'))
                  FilteringTextInputFormatter.digitsOnly,
                LengthLimitingTextInputFormatter(switch (field.key) {
                  'category' => 180,
                  'transaction_type' => 80,
                  _ => 10,
                }),
              ],
              onChanged: (value) => _values[field.key] = value.trim(),
              validator: (value) => _validate(field.key, value ?? ''),
            ),
          Wrap(
            spacing: 8,
            children: [
              OutlinedButton(
                onPressed: () =>
                    Navigator.pop(context, const <String, String>{}),
                child: const Text('Clear filters'),
              ),
              FilledButton(
                onPressed: () {
                  if (!_form.currentState!.validate()) return;
                  Navigator.pop(context, {
                    for (final key in _fields.keys)
                      if ((_values[key] ?? '').isNotEmpty) key: _values[key]!,
                  });
                },
                child: const Text('Apply filters'),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}
