import 'package:flutter/material.dart';

import '../core/api_client.dart';
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
  });
  final ApiClient api;
  final Json summary;
  final bool offline;
  final String? cacheScope;
  final Map<String, String> scopeHeaders;
  final bool canEdit;
  final VoidCallback? onChanged;

  @override
  State<SalesOrderPage> createState() => _SalesOrderPageState();
}

class _SalesOrderPageState extends State<SalesOrderPage> {
  Json? _saved;
  late bool _offline = widget.offline;
  late Future<Json?> _order = _load();
  bool _saving = false;
  String? _actionError;
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
    'description',
    'item_code',
    'quantity',
    'unit_price',
    'discount_amount',
    'tax_amount',
    'line_total',
  ];

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
        final rows = await SuiteReadCache.read(key);
        if (mounted &&
            revision == widget.api.sessionRevision &&
            rows?.length == 1) {
          setState(() => _saved = rows!.single);
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
            ],
          ],
        );
      },
    ),
  );
}
