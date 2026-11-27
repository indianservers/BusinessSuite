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

class _InventoryGoodsReceiptFormState extends State<InventoryGoodsReceiptForm> {
  final _form = GlobalKey<FormState>();
  Json? _line;
  String _accepted = '';
  String _rejected = '0';
  String _reference = '';
  String _tax = '0';
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
    final accepted = _milli(_accepted)!;
    final rejected = _milli(_rejected)!;
    if (accepted + rejected == 0) {
      setState(() => _error = 'Enter a received quantity above zero.');
      return;
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
          'lines': [
            {
              'purchase_order_line_id': _line!['id'],
              'quantity': _decimal(accepted + rejected),
              'accepted_quantity': _accepted,
              'rejected_quantity': _rejected,
              'tax_amount': _tax,
            },
          ],
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
    bool accepted = false,
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
      if (accepted && _line != null && value > _remaining(_line!)) {
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
                DropdownButtonFormField<int>(
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Purchase order line',
                  ),
                  validator: (id) =>
                      id == null ? 'Choose an order line.' : null,
                  items: [
                    for (final line in lines)
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
                          _line = lines.firstWhere((line) => line['id'] == id);
                        }),
                ),
                if (_line case final Json line)
                  Text('Remaining quantity: ${_decimal(_remaining(line))}'),
                _quantityField(
                  label: 'Accepted quantity',
                  initial: _accepted,
                  onChanged: (value) => _accepted = value,
                  accepted: true,
                ),
                _quantityField(
                  label: 'Rejected quantity',
                  initial: _rejected,
                  onChanged: (value) => _rejected = value,
                ),
                TextFormField(
                  initialValue: _tax,
                  enabled: !_saving,
                  decoration: const InputDecoration(labelText: 'Tax amount'),
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  onChanged: (value) => _tax = value.trim(),
                  validator: (text) {
                    final value = num.tryParse(text?.trim() ?? '');
                    return value == null || !value.isFinite || value < 0
                        ? 'Enter a nonnegative tax amount.'
                        : null;
                  },
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
}
