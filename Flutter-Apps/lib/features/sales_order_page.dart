import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/inventory_stock_receipts.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';
import 'gst_invoice_page.dart';
import 'payment_requests_page.dart';
import 'pms_project_overview_page.dart';
import 'sales_billing_plan_page.dart';
import 'sales_contract_page.dart';
import 'sales_engagement_page.dart';

class SalesOrderPage extends StatefulWidget {
  const SalesOrderPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    this.cacheScope,
    this.scopeHeaders = const {},
    this.canEdit = false,
    this.canManageBilling = false,
    this.canApproveInvoices = false,
    this.canExportInvoices = false,
    this.onChanged,
    this.invoiceBuilder,
  });
  final ApiClient api;
  final Json summary;
  final bool offline;
  final String? cacheScope;
  final Map<String, String> scopeHeaders;
  final bool canEdit;
  final bool canManageBilling;
  final bool canApproveInvoices;
  final bool canExportInvoices;
  final VoidCallback? onChanged;
  final Widget Function(Json)? invoiceBuilder;

  @override
  State<SalesOrderPage> createState() => _SalesOrderPageState();
}

class _SalesOrderPageState extends State<SalesOrderPage> {
  Json? _saved;
  late bool _offline = widget.offline;
  late Future<Json?> _order = _load();
  bool _saving = false;
  bool _refreshFailed = false;
  String? _actionError;
  Json? _invoice;
  String get _path => '/srm/sales-orders/${widget.summary['id']}';

  static const _orderFields = [
    'order_number',
    'title',
    'currency',
    'status',
    'expected_start_date',
    'expected_end_date',
    'subtotal',
    'discount_amount',
    'tax_amount',
    'total_amount',
    'terms',
  ];
  static const _lineFields = [
    'product_id',
    'description',
    'item_code',
    'quantity',
    'unit_price',
    'discount_amount',
    'tax_amount',
    'line_total',
  ];
  static const _linkedRecords = {
    'contract': ('Contract', 'contract_number'),
    'engagement': ('Engagement', 'engagement_number'),
    'billing_plan': ('Billing plan', 'name'),
    'pms_project': ('Project', 'name'),
  };

  String? get _cacheKey {
    final scope = widget.cacheScope;
    final branch = widget.scopeHeaders['X-Suite-Branch'];
    return scope == null
        ? null
        : branch == null
        ? '$scope:$_path'
        : '$scope:$_path:$branch';
  }

  Json _projectDetails(Json data) => {
    for (final field in _orderFields) field: data[field],
    'lines': [
      for (final line in (data['lines'] as List? ?? []).whereType<Json>())
        {for (final field in _lineFields) field: line[field]},
    ],
    'invoices': [
      for (final invoice in (data['invoices'] as List? ?? []).whereType<Json>())
        {
          'id': invoice['id'],
          for (final field in GstInvoicePage.summaryFields)
            field: invoice[field],
        },
    ],
    for (final entry in _linkedRecords.entries)
      if (data[entry.key] case final Json record)
        entry.key: {
          'id': record['id'],
          if (entry.key == 'engagement') 'name': record['name'],
          entry.value.$2: record[entry.value.$2],
          'status': record['status'],
          if (entry.key == 'billing_plan')
            for (final field in SalesBillingPlanPage.fields)
              field: record[field],
        },
  };

  Future<void> _cacheDetails(Json data) async {
    final key = _cacheKey;
    if (key == null) return;
    try {
      await flushCrmDetailWrite(key);
      await SuiteReadCache.write(key, [_projectDetails(data)]);
    } catch (_) {
      // Online detail remains available if its cache cannot be written.
    }
  }

  Future<Json?> _load({bool reconnect = false}) async {
    final api = widget.api;
    final revision = api.sessionRevision;
    var refreshFailed = false;
    try {
      final result = await loadCrmDetail(
        api: api,
        path: _path,
        scope: widget.cacheScope,
        cacheKey: _cacheKey,
        headers: widget.scopeHeaders,
        offline: _offline && !reconnect,
        reuseFresh:
            !reconnect && !widget.canEdit && widget.invoiceBuilder == null,
        onCached: (saved) {
          if (mounted) setState(() => _saved = saved);
        },
        onRefreshFailed: () => refreshFailed = true,
        project: _projectDetails,
      );
      if (!mounted || revision != api.sessionRevision) return null;
      _refreshFailed = refreshFailed;
      if (!result.live) {
        setState(() => _saved = result.record);
        return null;
      }
      _offline = false;
      return result.record;
    } on ApiFailure catch (error) {
      if (mounted && const {401, 403, 404}.contains(error.status)) {
        setState(() => _saved = null);
      }
      rethrow;
    }
  }

  void _refresh() => setState(() {
    _order = _load(reconnect: true);
  });

  Future<void> _createInvoice(Json order) async {
    if (_saving || _invoice != null) return;
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _actionError = null;
    });
    try {
      final invoice =
          await widget.api.request(
                'POST',
                '/srm/invoices/draft-from-sales-order/${widget.summary['id']}',
                scopeHeaders: widget.scopeHeaders,
              )
              as Json;
      if (!mounted || revision != widget.api.sessionRevision) return;
      if (invoice['id'] is! int) {
        throw ApiFailure(
          'The backend did not return the invoice ID. Check the invoice list.',
        );
      }
      final scope = widget.cacheScope;
      final invoices = (order['invoices'] as List? ?? []).whereType<Json>();
      final updated = {
        ...order,
        'invoices': [
          invoice,
          for (final linked in invoices)
            if (linked['id'] != invoice['id']) linked,
        ],
      };
      if (invoice['lines'] is List) {
        await GstInvoicePage.saveSnapshot(
          GstInvoicePage.cacheKey(
            scope,
            '${GstInvoicePage.listEndpoint}/${invoice['id']}',
            widget.scopeHeaders,
          ),
          invoice,
        );
      }
      if (revision != widget.api.sessionRevision) return;
      await _cacheDetails(updated);
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _invoice = invoice);
      }
      if (scope != null) {
        try {
          final key = GstInvoicePage.cacheKey(
            scope,
            GstInvoicePage.listEndpoint,
            widget.scopeHeaders,
          );
          if (key != null) await SuiteReadCache.invalidate(key);
        } catch (_) {}
      }
    } on ApiFailure catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _actionError = error.toString());
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _changeStatus(Json order, String action, String label) async {
    final revision = widget.api.sessionRevision;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(label),
        content: Text('Order ${order['order_number']}'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(label),
          ),
        ],
      ),
    );
    if (confirmed != true ||
        !mounted ||
        _saving ||
        revision != widget.api.sessionRevision) {
      return;
    }
    setState(() {
      _saving = true;
      _actionError = null;
    });
    try {
      final updated =
          await widget.api.request(
                'POST',
                '$_path/$action',
                scopeHeaders: widget.scopeHeaders,
              )
              as Json;
      if (!mounted || revision != widget.api.sessionRevision) return;
      final detail = {...order, ...updated};
      setState(() {
        _order = Future.value(detail);
      });
      widget.onChanged?.call();
      if (action == 'confirm') {
        if (widget.cacheScope case final String scope) {
          await InventoryStockReceipts(scope).invalidateLists(
            products: [
              for (final line
                  in (order['lines'] as List? ?? []).whereType<Json>())
                if (line['product_id'] case final int product) product,
            ],
          );
        }
        if (!mounted || revision != widget.api.sessionRevision) return;
      }
      await _cacheDetails(detail);
    } on ApiFailure catch (error) {
      if (!mounted || revision != widget.api.sessionRevision) return;
      setState(() {
        _actionError = error.toString();
        if (error.connectionFailure) _order = _load(reconnect: true);
      });
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Sales Order Detail')),
    body: FutureBuilder<Json?>(
      future: _order,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${snapshot.error}', textAlign: TextAlign.center),
                TextButton(onPressed: _refresh, child: const Text('Retry')),
              ],
            ),
          );
        }
        final pending = snapshot.connectionState != ConnectionState.done;
        final detail = (pending ? null : snapshot.data) ?? _saved;
        final data = detail ?? widget.summary;
        final currency = data['currency'] ?? '';
        final lines = (data['lines'] as List? ?? []).whereType<Json>();
        final action = switch (snapshot.data?['status']) {
          'draft' => ('submit', 'Submit order for approval'),
          'approved' => ('confirm', 'Confirm sales order'),
          _ => null,
        };
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${data['order_number'] ?? ''}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            Text('${data['title'] ?? ''}'),
            if (_actionError != null) Text(_actionError!),
            if (!pending &&
                snapshot.data != null &&
                widget.canManageBilling &&
                widget.summary['id'] is int)
              OutlinedButton.icon(
                icon: const Icon(Icons.payments_outlined),
                label: const Text('Request payment'),
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => PaymentRequestsPage(
                      api: widget.api,
                      sourceType: 'srm_order',
                      sourceId: widget.summary['id'] as int,
                      scopeHeaders: widget.scopeHeaders,
                    ),
                  ),
                ),
              ),
            if (!pending && widget.canEdit && action != null)
              OutlinedButton(
                onPressed: _saving
                    ? null
                    : () => _changeStatus(data, action.$1, action.$2),
                child: Text(action.$2),
              ),
            if (!pending &&
                snapshot.data != null &&
                widget.invoiceBuilder != null)
              OutlinedButton(
                onPressed: _saving
                    ? null
                    : () {
                        final invoice = _invoice;
                        if (invoice == null) {
                          _createInvoice(data);
                          return;
                        }
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => widget.invoiceBuilder!(invoice),
                          ),
                        );
                      },
                child: Text(
                  _invoice == null ? 'Create invoice draft' : 'Open invoice',
                ),
              ),
            if (pending) const LinearProgressIndicator(),
            for (final invoice
                in (data['invoices'] as List? ?? []).whereType<Json>())
              if (invoice['id'] case final int id)
                ListTile(
                  title: Text('${invoice['invoice_number'] ?? 'Invoice #$id'}'),
                  subtitle: Text('${invoice['status'] ?? ''}'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => GstInvoicePage(
                        api: widget.api,
                        id: id,
                        summary: invoice,
                        scopeHeaders: widget.scopeHeaders,
                        cacheScope: widget.cacheScope,
                        offline: pending || snapshot.data == null,
                        canEdit: widget.invoiceBuilder != null,
                        canIssue: widget.canApproveInvoices,
                        canExport: widget.canExportInvoices,
                      ),
                    ),
                  ),
                ),
            if (!pending && snapshot.data == null)
              ListTile(
                title: Text(
                  '${_offline
                      ? 'Offline · '
                      : _refreshFailed
                      ? 'Refresh unavailable · '
                      : ''}'
                  '${detail == null ? 'Saved order summary' : 'Saved order details'}',
                ),
                trailing: TextButton(
                  onPressed: _refresh,
                  child: Text(
                    _offline
                        ? 'Reconnect'
                        : _refreshFailed
                        ? 'Retry'
                        : 'Refresh',
                  ),
                ),
              ),
            for (final field in const {
              'status': 'Status',
              'expected_start_date': 'Expected start',
              'expected_end_date': 'Expected end',
            }.entries)
              if (data[field.key] != null)
                ListTile(
                  title: Text(field.value),
                  trailing: Text('${data[field.key]}'),
                ),
            const Divider(),
            for (final field in const {
              'subtotal': 'Subtotal',
              'discount_amount': 'Discount',
              'tax_amount': 'Tax',
              'total_amount': 'Total',
            }.entries)
              if (data[field.key] != null)
                ListTile(
                  title: Text(field.value),
                  trailing: Text('$currency ${data[field.key]}'.trim()),
                ),
            if (detail != null) ...[
              if (data['terms'] case final String terms
                  when terms.trim().isNotEmpty)
                ListTile(title: const Text('Terms'), subtitle: Text(terms)),
              const Divider(),
              Text(
                'Line items',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              if (lines.isEmpty) const ListTile(title: Text('No line items')),
              for (final line in lines)
                ListTile(
                  title: Text(
                    '${line['description'] ?? line['item_code'] ?? 'Line item'}',
                  ),
                  subtitle: Text(
                    [
                      'Quantity ${line['quantity'] ?? '—'} · Unit price $currency ${line['unit_price'] ?? '—'}',
                      if (line['discount_amount'] != null)
                        'Discount $currency ${line['discount_amount']}',
                      if (line['tax_amount'] != null)
                        'Tax $currency ${line['tax_amount']}',
                    ].join('\n'),
                  ),
                  trailing: line['line_total'] == null
                      ? null
                      : Text('$currency ${line['line_total']}'),
                ),
              if (_linkedRecords.keys.any((key) => data[key] is Json)) ...[
                const Divider(),
                Text(
                  'Linked records',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                for (final entry in _linkedRecords.entries)
                  if (data[entry.key] case final Json record)
                    _linkedTile(
                      entry,
                      record,
                      offline: pending || snapshot.data == null,
                    ),
              ],
            ],
          ],
        );
      },
    ),
  );

  Widget _linkedTile(
    MapEntry<String, (String, String)> entry,
    Json record, {
    required bool offline,
  }) {
    final page = _linkedPage(entry.key, record, offline: offline);
    return ListTile(
      title: Text(entry.value.$1),
      subtitle: Text(
        [
          record[entry.value.$2],
          record['status'],
        ].whereType<String>().where((value) => value.isNotEmpty).join(' · '),
      ),
      trailing: page == null ? null : const Icon(Icons.chevron_right),
      onTap: page == null
          ? null
          : () => Navigator.of(
              context,
            ).push(MaterialPageRoute<void>(builder: (_) => page)),
    );
  }

  Widget? _linkedPage(String kind, Json record, {required bool offline}) {
    final id = record['id'];
    if (id is! int) return null;
    return switch (kind) {
      'contract' => SalesContractPage(
        api: widget.api,
        summary: record,
        scopeHeaders: widget.scopeHeaders,
        cacheScope: widget.cacheScope,
        offline: offline,
        canEdit: widget.canManageBilling,
        onChanged: _refresh,
      ),
      'engagement' => SalesEngagementPage(
        api: widget.api,
        summary: record,
        scopeHeaders: widget.scopeHeaders,
        cacheScope: widget.cacheScope,
        offline: offline,
      ),
      'billing_plan' => SalesBillingPlanPage(
        api: widget.api,
        summary: record,
        scopeHeaders: widget.scopeHeaders,
        cacheScope: widget.cacheScope,
        offline: offline,
        canEdit: widget.canManageBilling,
        canApprove: widget.canApproveInvoices,
        canCreateInvoice: widget.invoiceBuilder != null,
        canExportInvoice: widget.canExportInvoices,
        onChanged: _refresh,
      ),
      'pms_project' => PmsProjectOverviewPage(
        api: widget.api,
        projectId: id,
        scopeHeaders: widget.scopeHeaders,
        cacheScope: widget.cacheScope,
        offline: offline,
      ),
      _ => null,
    };
  }
}
