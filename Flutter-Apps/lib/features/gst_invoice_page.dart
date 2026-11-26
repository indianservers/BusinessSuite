import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class GstInvoicePage extends StatefulWidget {
  const GstInvoicePage({
    super.key,
    required this.api,
    required this.id,
    this.canEdit = false,
  });
  static const listEndpoint = '/srm/invoices';
  final ApiClient api;
  final int id;
  final bool canEdit;

  @override
  State<GstInvoicePage> createState() => _GstInvoicePageState();
}

class _GstInvoicePageState extends State<GstInvoicePage> {
  late Future<Json> _invoice = _load();
  String get _path => '${GstInvoicePage.listEndpoint}/${widget.id}';
  Future<Json> _load() async => await widget.api.request('GET', _path) as Json;

  Future<void> _editDates(Json invoice) async {
    final form = GlobalKey<FormState>();
    final initial = {
      'issue_date': invoice['issue_date'] as String?,
      'due_date': invoice['due_date'] as String?,
    };
    final dates = Map.of(initial);
    var saving = false;
    String? error;
    final refresh = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => StatefulBuilder(
        builder: (context, update) => PopScope(
          canPop: !saving,
          child: AlertDialog(
            title: const Text('Edit invoice dates'),
            content: SingleChildScrollView(
              child: Form(
                key: form,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (final (key, label) in const [
                      ('issue_date', 'Issue date'),
                      ('due_date', 'Due date'),
                    ])
                      TextFormField(
                        initialValue: initial[key],
                        enabled: !saving,
                        decoration: InputDecoration(
                          labelText: label,
                          hintText: 'YYYY-MM-DD',
                        ),
                        onChanged: (value) => dates[key] = value.trim().isEmpty
                            ? null
                            : value.trim(),
                        validator: (_) {
                          final text = dates[key];
                          if (text == null) return null;
                          final date = DateTime.tryParse(text);
                          if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text) ||
                              date == null ||
                              date.year < 1 ||
                              !date.toIso8601String().startsWith('${text}T')) {
                            return 'Enter a valid date as YYYY-MM-DD.';
                          }
                          return null;
                        },
                      ),
                    if (error != null) SelectableText(error!),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(context, true),
                child: const Text('Close'),
              ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        if (!form.currentState!.validate()) return;
                        final changed = {
                          for (final key in dates.keys)
                            if (dates[key] != initial[key]) key: dates[key],
                        };
                        if (changed.isEmpty) {
                          Navigator.pop(context, false);
                          return;
                        }
                        update(() {
                          saving = true;
                          error = null;
                        });
                        try {
                          await widget.api.request(
                            'PATCH',
                            _path,
                            data: changed,
                          );
                          if (context.mounted) Navigator.pop(context, true);
                        } catch (failure) {
                          if (context.mounted) {
                            update(() {
                              saving = false;
                              error = '$failure';
                            });
                          }
                        }
                      },
                child: Text(saving ? 'Saving…' : 'Save dates'),
              ),
            ],
          ),
        ),
      ),
    );
    if (mounted && refresh == true) {
      setState(() {
        _invoice = _load();
      });
    }
  }

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
              'issue_date': 'Issue date',
              'due_date': 'Due date',
            }.entries)
              if (invoice[field.key] != null)
                ListTile(
                  title: Text(field.value),
                  trailing: Text('${invoice[field.key]}'),
                ),
            if (widget.canEdit &&
                const {'draft', 'pending_approval'}.contains(invoice['status']))
              OutlinedButton(
                onPressed: () => _editDates(invoice),
                child: const Text('Edit dates'),
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
