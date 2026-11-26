import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class GstInvoicePage extends StatefulWidget {
  const GstInvoicePage({super.key, required this.api, required this.id});
  static const listEndpoint = '/srm/invoices';
  final ApiClient api;
  final int id;

  @override
  State<GstInvoicePage> createState() => _GstInvoicePageState();
}

class _GstInvoicePageState extends State<GstInvoicePage> {
  late Future<Json> _invoice = _load();
  Future<Json> _load() async =>
      await widget.api.request(
            'GET',
            '${GstInvoicePage.listEndpoint}/${widget.id}',
          )
          as Json;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Sales invoice')),
    body: FutureBuilder<Json>(
      future: _invoice,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return ListTile(
            title: Text('${snapshot.error}'),
            trailing: TextButton(
              onPressed: () => setState(() {
                _invoice = _load();
              }),
              child: const Text('Retry'),
            ),
          );
        }
        final invoice = snapshot.requireData;
        final currency = invoice['currency'] ?? '';
        final lines = (invoice['lines'] as List? ?? []).whereType<Json>();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${invoice['invoice_number']}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            for (final field in const {
              'document_status': 'Document',
              'delivery_status': 'Delivery',
              'payment_status': 'Payment',
            }.entries)
              ListTile(
                title: Text(field.value),
                trailing: Text(
                  '${invoice[field.key] ?? 'Unavailable'}'.replaceAll('_', ' '),
                ),
              ),
            const Divider(),
            for (final field in const {
              'subtotal': 'Subtotal',
              'tax_amount': 'Tax',
              'total_amount': 'Total',
              'paid_amount': 'Paid',
              'balance_amount': 'Outstanding',
            }.entries)
              if (invoice[field.key] != null)
                ListTile(
                  title: Text(field.value),
                  trailing: Text('$currency ${invoice[field.key]}'.trim()),
                ),
            const Divider(),
            Text('Line items', style: Theme.of(context).textTheme.titleMedium),
            if (lines.isEmpty) const ListTile(title: Text('No line items')),
            for (final line in lines)
              ListTile(
                title: Text(
                  '${line['description'] ?? line['item_name'] ?? 'Line item'}',
                ),
                subtitle: Text('Quantity ${line['quantity'] ?? '—'}'),
                trailing: line['line_total'] == null
                    ? null
                    : Text('$currency ${line['line_total']}'.trim()),
              ),
          ],
        );
      },
    ),
  );
}
