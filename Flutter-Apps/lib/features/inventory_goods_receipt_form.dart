import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class InventoryGoodsReceiptForm extends StatefulWidget {
  const InventoryGoodsReceiptForm({
    super.key,
    required this.api,
    required this.order,
    required this.scopeHeaders,
  });

  final ApiClient api;
  final Json order;
  final Map<String, String> scopeHeaders;

  @override
  State<InventoryGoodsReceiptForm> createState() =>
      _InventoryGoodsReceiptFormState();
}

class _ReceiptLine {
  Json? orderLine;
  String accepted = '';
  String rejected = '0';
  String tax = '0';
}

class _InventoryGoodsReceiptFormState extends State<InventoryGoodsReceiptForm> {
  final _form = GlobalKey<FormState>();
  final _lines = [_ReceiptLine()];
  String _reference = '';
  bool _saving = false;
  bool _confirmationUnknown = false;
  String? _error;

  static final _quantity = RegExp(r'^\d{1,11}(?:\.\d{1,3})?$');

  static int? _milli(Object? value) {
    final text = '$value'.trim();
    if (!_quantity.hasMatch(text)) return null;
    final parts = text.split('.');
    return int.parse(parts.first) * 1000 +
        (parts.length == 1 ? 0 : int.parse(parts.last.padRight(3, '0')));
  }

  static int _remaining(Json line) =>
      (_milli(line['quantity']) ?? 0) -
      (_milli(line['received_quantity']) ?? 0);

  static String _decimal(int value) =>
      '${value ~/ 1000}.${(value % 1000).toString().padLeft(3, '0')}';

  Future<void> _save() async {
    if (_saving || _confirmationUnknown || !_form.currentState!.validate()) {
      return;
    }
    final entries = <Json>[];
    for (final (index, line) in _lines.indexed) {
      final received = _milli(line.accepted)! + _milli(line.rejected)!;
      if (received == 0 || received > 99999999999999) {
        setState(
          () =>
              _error = 'Enter a valid received quantity for item ${index + 1}.',
        );
        return;
      }
      entries.add({
        'purchase_order_line_id': line.orderLine!['id'],
        'quantity': _decimal(received),
        'accepted_quantity': line.accepted,
        'rejected_quantity': line.rejected,
        'tax_amount': line.tax,
      });
    }
    final api = widget.api;
    final revision = api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final result = await api.request(
        'POST',
        '/srm/procurement/grn',
        scopeHeaders: widget.scopeHeaders,
        data: {
          'purchase_order_id': widget.order['id'],
          if (_reference.isNotEmpty) 'reference_number': _reference,
          'lines': entries,
        },
      );
      if (mounted && revision == api.sessionRevision) {
        if (result is! Json || result['id'] is! int) {
          _showUnconfirmedReceipt();
          return;
        }
        Navigator.pop(context, result);
      }
    } on ApiFailure catch (error) {
      if (mounted && revision == api.sessionRevision) {
        if (error.connectionFailure || (error.status ?? 0) >= 500) {
          _showUnconfirmedReceipt();
        } else {
          setState(() => _error = error.message);
        }
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _showUnconfirmedReceipt() => setState(() {
    _confirmationUnknown = true;
    _error =
        'Receipt confirmation is unavailable. Check Goods receipts before reopening this form.';
  });

  Widget _quantityField({
    required String label,
    required String initial,
    required ValueChanged<String> onChanged,
    int? remaining,
  }) => TextFormField(
    initialValue: initial,
    enabled: !_saving,
    decoration: InputDecoration(labelText: label),
    keyboardType: const TextInputType.numberWithOptions(decimal: true),
    onChanged: (text) => onChanged(text.trim()),
    validator: (text) {
      final value = _milli(text);
      if (value == null) {
        return 'Enter a nonnegative quantity with up to three decimals.';
      }
      if (remaining != null && value > remaining) {
        return 'Accepted quantity exceeds the remaining quantity.';
      }
      return null;
    },
  );

  @override
  Widget build(BuildContext context) {
    final lines = (widget.order['lines'] as List? ?? const [])
        .whereType<Json>()
        .where((line) => line['id'] is int && _remaining(line) > 0)
        .toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Receive goods')),
      body: Form(
        key: _form,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('${widget.order['po_number'] ?? 'Purchase order'}'),
              if (lines.isEmpty)
                const Text(
                  'There are no remaining order quantities to receive.',
                )
              else ...[
                for (final (index, line) in _lines.indexed)
                  _lineEditor(index, line, lines),
                if (_lines.length < lines.length)
                  OutlinedButton.icon(
                    onPressed: _saving
                        ? null
                        : () => setState(() {
                            _lines.add(_ReceiptLine());
                          }),
                    icon: const Icon(Icons.add),
                    label: const Text('Add receipt item'),
                  ),
                TextFormField(
                  enabled: !_saving,
                  decoration: const InputDecoration(
                    labelText: 'Reference number',
                  ),
                  maxLength: 120,
                  onChanged: (value) => _reference = value.trim(),
                ),
                if (_error case final String error) Text(error),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _saving || _confirmationUnknown ? null : _save,
                  child: Text(_saving ? 'Posting…' : 'Post goods receipt'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _lineEditor(int index, _ReceiptLine draft, List<Json> lines) {
    final selected = {
      for (final line in _lines)
        if (line != draft) line.orderLine?['id'],
    };
    return Card(
      key: ObjectKey(draft),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_lines.length > 1)
              Row(
                children: [
                  Expanded(child: Text('Receipt item ${index + 1}')),
                  IconButton(
                    tooltip: 'Remove receipt item ${index + 1}',
                    icon: const Icon(Icons.delete_outline),
                    onPressed: _saving
                        ? null
                        : () => setState(() {
                            _lines.remove(draft);
                          }),
                  ),
                ],
              ),
            DropdownButtonFormField<int>(
              isExpanded: true,
              initialValue: draft.orderLine?['id'] as int?,
              decoration: const InputDecoration(
                labelText: 'Purchase order line',
              ),
              validator: (id) => id == null ? 'Choose an order line.' : null,
              items: [
                for (final line in lines)
                  if (!selected.contains(line['id']))
                    DropdownMenuItem(
                      value: line['id'] as int,
                      child: Text(
                        "${line['description'] ?? line['item_code'] ?? 'Item'}",
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
              ],
              onChanged: _saving
                  ? null
                  : (id) => setState(() {
                      draft.orderLine = lines.firstWhere(
                        (line) => line['id'] == id,
                      );
                    }),
            ),
            if (draft.orderLine case final Json line)
              Text('Remaining quantity: ${_decimal(_remaining(line))}'),
            _quantityField(
              label: 'Accepted quantity',
              initial: draft.accepted,
              onChanged: (value) => draft.accepted = value,
              remaining: draft.orderLine == null
                  ? null
                  : _remaining(draft.orderLine!),
            ),
            _quantityField(
              label: 'Rejected quantity',
              initial: draft.rejected,
              onChanged: (value) => draft.rejected = value,
            ),
            TextFormField(
              initialValue: draft.tax,
              enabled: !_saving,
              decoration: const InputDecoration(labelText: 'Tax amount'),
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              onChanged: (value) => draft.tax = value.trim(),
              validator: (text) {
                final value = num.tryParse(text?.trim() ?? '');
                return value == null || !value.isFinite || value < 0
                    ? 'Enter a nonnegative tax amount.'
                    : null;
              },
            ),
          ],
        ),
      ),
    );
  }
}
