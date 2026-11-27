import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class CrmQuotationLinePage extends StatefulWidget {
  const CrmQuotationLinePage({
    super.key,
    required this.api,
    required this.quoteId,
    required this.scopeHeaders,
    this.line,
  });
  final ApiClient api;
  final int quoteId;
  final Map<String, String> scopeHeaders;
  final Json? line;

  @override
  State<CrmQuotationLinePage> createState() => _CrmQuotationLinePageState();
}

class _CrmQuotationLinePageState extends State<CrmQuotationLinePage> {
  final _form = GlobalKey<FormState>();
  final _values = <String, dynamic>{};
  bool _saving = false;
  String? _error;
  static const _fields = {
    'name': 'Item name',
    'quantity': 'Quantity',
    'unit_price': 'Unit price',
    'tax_rate': 'Tax rate (%)',
  };

  String? _validate(String field, String? value) {
    final text = value?.trim() ?? '';
    if (field == 'name') return text.isEmpty ? 'Enter an item name' : null;
    if (field == 'tax_rate' && text.isEmpty) return null;
    final number = num.tryParse(text);
    if (number == null || !number.isFinite || number < 0) {
      return 'Enter a valid number';
    }
    if (field == 'quantity' && number == 0) return 'Quantity must be positive';
    if (field == 'tax_rate' && number > 100) return 'Enter a rate up to 100';
    return null;
  }

  Future<void> _save() async {
    if (_saving || _form.currentState?.validate() != true) return;
    _values.clear();
    _form.currentState!.save();
    if (_values.isEmpty) {
      Navigator.pop(context, false);
      return;
    }
    final id = widget.line?['id'];
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        id == null ? 'POST' : 'PATCH',
        id == null
            ? '/crm/quotes/${widget.quoteId}/lines'
            : '/crm/quote-lines/$id',
        scopeHeaders: widget.scopeHeaders,
        data: _values,
      );
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _remove() async {
    final line = widget.line;
    if (_saving || line == null || line['id'] is! int) return;
    final revision = widget.api.sessionRevision;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove quotation item?'),
        content: Text(
          "${line['name'] ?? 'Item'} will be removed from this quotation.",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove item'),
          ),
        ],
      ),
    );
    if (!mounted ||
        confirmed != true ||
        revision != widget.api.sessionRevision) {
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'DELETE',
        "/crm/quote-lines/${line['id']}",
        scopeHeaders: widget.scopeHeaders,
      );
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.line == null ? 'Add item' : 'Edit item')),
    body: Form(
      key: _form,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (final field in _fields.entries)
              TextFormField(
                enabled: !_saving,
                initialValue:
                    widget.line?[field.key]?.toString() ??
                    (field.key == 'quantity' ? '1' : null),
                maxLength: field.key == 'name' ? 180 : null,
                keyboardType: field.key == 'name'
                    ? TextInputType.text
                    : const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(labelText: field.value),
                validator: (value) => _validate(field.key, value),
                onSaved: (value) {
                  final text = value?.trim() ?? '';
                  final previous = widget.line?[field.key]?.toString() ?? '';
                  if (widget.line == null || text != previous) {
                    _values[field.key] = field.key == 'name'
                        ? text
                        : num.tryParse(text);
                  }
                },
              ),
            if (_error case final error?) Text(error),
            FilledButton(
              onPressed: _saving ? null : _save,
              child: Text(_saving ? 'Saving…' : 'Save item'),
            ),
            if (widget.line != null)
              TextButton(
                onPressed: _saving ? null : _remove,
                child: const Text('Remove item'),
              ),
          ],
        ),
      ),
    ),
  );
}
