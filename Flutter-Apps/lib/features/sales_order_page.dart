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
  });
  final ApiClient api;
  final Json summary;
  final bool offline;
  final String? cacheScope;
  final Map<String, String> scopeHeaders;

  @override
  State<SalesOrderPage> createState() => _SalesOrderPageState();
}

class _SalesOrderPageState extends State<SalesOrderPage> {
  Json? _saved;
  late Future<Json?> _order = _load();

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

  Future<Json?> _load() async {
    final path = '/srm/sales-orders/${widget.summary['id']}';
    final scope = widget.cacheScope;
    final branch = widget.scopeHeaders['X-Suite-Branch'];
    final key = scope == null
        ? null
        : branch == null
        ? '$scope:$path'
        : '$scope:$path:$branch';
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
    if (widget.offline || !mounted) return null;
    if (revision != widget.api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    try {
      final data =
          await widget.api.request(
                'GET',
                path,
                scopeHeaders: widget.scopeHeaders,
              )
              as Json;
      if (revision != widget.api.sessionRevision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      if (key != null) {
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
                TextButton(
                  onPressed: () => setState(() {
                    _order = _load();
                  }),
                  child: const Text('Retry'),
                ),
              ],
            ),
          );
        }
        final pending = snapshot.connectionState != ConnectionState.done;
        final detail = (pending ? null : snapshot.data) ?? _saved;
        final data = detail ?? widget.summary;
        final currency = data['currency'] ?? '';
        final lines = (data['lines'] as List? ?? []).whereType<Json>();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${data['order_number'] ?? ''}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            Text('${data['title'] ?? ''}'),
            if (pending && !widget.offline) const LinearProgressIndicator(),
            if ((widget.offline || !pending) && snapshot.data == null)
              ListTile(
                title: Text(
                  '${widget.offline ? 'Offline' : 'Refresh unavailable'} · '
                  '${detail == null ? 'Saved order summary' : 'Saved order details'}',
                ),
                trailing: widget.offline
                    ? null
                    : TextButton(
                        onPressed: () => setState(() {
                          _order = _load();
                        }),
                        child: const Text('Retry'),
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
