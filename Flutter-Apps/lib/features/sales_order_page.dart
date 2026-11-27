import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/inventory_stock_receipts.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';

class SalesOrderPage extends StatefulWidget {
  const SalesOrderPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    this.cacheScope,
    this.scopeHeaders = const {},
    this.canEdit = false,
    this.onChanged,
    this.invoiceBuilder,
  });
  final ApiClient api;
  final Json summary;
  final bool offline;
  final String? cacheScope;
  final Map<String, String> scopeHeaders;
  final bool canEdit;
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

  Future<void> _cacheDetails(Json data) async {
    final key = _cacheKey;
    if (key == null) return;
    final lines = (data['lines'] as List? ?? []).whereType<Json>();
    try {
      await SuiteReadCache.write(key, [
        {
          for (final field in _orderFields) field: data[field],
          'lines': [
            for (final line in lines)
              {for (final field in _lineFields) field: line[field]},
          ],
          for (final entry in _linkedRecords.entries)
            if (data[entry.key] case final Json record)
              entry.key: {
                entry.value.$2: record[entry.value.$2],
                'status': record['status'],
              },
        },
      ]);
    } catch (_) {
      // Online detail remains available if its cache cannot be written.
    }
  }

  Future<Json?> _load({bool reconnect = false}) async {
    final key = _cacheKey;
    final revision = widget.api.sessionRevision;
    if (key != null) {
      try {
        final snapshot = await SuiteReadCache.snapshot(key);
        if (mounted &&
            revision == widget.api.sessionRevision &&
            snapshot != null &&
            snapshot.rows.length == 1) {
          final saved = snapshot.rows.single;
          setState(() => _saved = saved);
          if (!reconnect &&
              !_offline &&
              !widget.canEdit &&
              widget.invoiceBuilder == null &&
              !snapshot.invalidated) {
            final age = DateTime.now().difference(snapshot.savedAt);
            if (!age.isNegative && age < SuiteReadCache.reuseWindow) {
              return saved;
            }
          }
        }
      } catch (_) {
        // Cached detail is optional when local storage is unavailable.
      }
    }
    if ((_offline && !reconnect) || !mounted) return null;
    if (revision != widget.api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    try {
      final data =
          await widget.api.request(
                'GET',
                _path,
                scopeHeaders: widget.scopeHeaders,
              )
              as Json;
      if (revision != widget.api.sessionRevision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      await _cacheDetails(data);
      _offline = false;
      return data;
    } on ApiFailure catch (error) {
      if (error.status == null ||
          error.status == 429 ||
          (error.status ?? 0) >= 500) {
        return null;
      }
      if (key != null && const {401, 403, 404}.contains(error.status)) {
        _saved = null;
        try {
          await SuiteReadCache.clear(key);
        } catch (_) {}
      }
      rethrow;
    }
  }

  void _refresh() => setState(() {
    _order = _load(reconnect: true);
  });

  Future<void> _createInvoice() async {
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
      setState(() => _invoice = invoice);
      final scope = widget.cacheScope;
      if (scope != null) {
        try {
          await SuiteReadCache.invalidate('$scope:/srm/invoices');
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
                          _createInvoice();
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
            if (!pending && snapshot.data == null)
              ListTile(
                title: Text(
                  '${_offline ? 'Offline' : 'Refresh unavailable'} · '
                  '${detail == null ? 'Saved order summary' : 'Saved order details'}',
                ),
                trailing: TextButton(
                  onPressed: _refresh,
                  child: Text(_offline ? 'Reconnect' : 'Retry'),
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
                    ListTile(
                      title: Text(entry.value.$1),
                      subtitle: Text(
                        [record[entry.value.$2], record['status']]
                            .whereType<String>()
                            .where((value) => value.isNotEmpty)
                            .join(' · '),
                      ),
                    ),
              ],
            ],
          ],
        );
      },
    ),
  );
}
