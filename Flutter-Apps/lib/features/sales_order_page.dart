import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class SalesOrderPage extends StatefulWidget {
  const SalesOrderPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
  });
  final ApiClient api;
  final Json summary;
  final bool offline;

  @override
  State<SalesOrderPage> createState() => _SalesOrderPageState();
}

class _SalesOrderPageState extends State<SalesOrderPage> {
  late Future<Json> _order = _load();

  Future<Json> _load() async {
    if (widget.offline) return widget.summary;
    return await widget.api.request(
          'GET',
          '/srm/sales-orders/${widget.summary['id']}',
        )
        as Json;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Sales Order Detail')),
    body: FutureBuilder<Json>(
      future: _order,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${snapshot.error}', textAlign: TextAlign.center),
                TextButton(
                  onPressed: () => setState(() => _order = _load()),
                  child: const Text('Retry'),
                ),
              ],
            ),
          );
        }
        final data = snapshot.data;
        if (data == null) {
          return const Center(child: CircularProgressIndicator());
        }
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
            if (widget.offline)
              const ListTile(title: Text('Offline · Saved order summary')),
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
            if (!widget.offline) ...[
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
                    'Quantity ${line['quantity'] ?? '—'} · Unit price $currency ${line['unit_price'] ?? '—'}',
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
