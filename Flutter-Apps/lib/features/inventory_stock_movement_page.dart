import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class InventoryStockMovementPage extends StatefulWidget {
  const InventoryStockMovementPage({
    super.key,
    required this.api,
    required this.productId,
    required this.scopeHeaders,
  });

  final ApiClient api;
  final int productId;
  final Map<String, String> scopeHeaders;

  @override
  State<InventoryStockMovementPage> createState() =>
      _InventoryStockMovementPageState();
}

class _InventoryStockMovementPageState
    extends State<InventoryStockMovementPage> {
  final _form = GlobalKey<FormState>();
  final _quantity = TextEditingController();
  final _rate = TextEditingController();
  final _reference = TextEditingController();
  late Future<dynamic> _warehouses = _loadWarehouses();
  int? _warehouse;
  String _type = 'stock_in';
  String? _error;
  bool _saving = false;
  ({String id, Json payload})? _uncertainAttempt;
  bool get _locked => _saving || _uncertainAttempt != null;

  Future<dynamic> _loadWarehouses() => widget.api.request(
    'GET',
    '/srm/inventory/warehouses',
    scopeHeaders: widget.scopeHeaders,
  );

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    final session = widget.api.sessionRevision;
    final attempt =
        _uncertainAttempt ??
        (
          id: const Uuid().v4(),
          payload: <String, dynamic>{
            'product_id': widget.productId,
            'warehouse_id': _warehouse,
            'movement_type': _type,
            'quantity': _quantity.text.trim(),
            if (_rate.text.trim().isNotEmpty) 'rate': _rate.text.trim(),
            if (_reference.text.trim().isNotEmpty)
              'reference_number': _reference.text.trim(),
          },
        );
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'POST',
        '/srm/inventory/stock-movements/offline-create',
        scopeHeaders: {
          ...widget.scopeHeaders,
          'X-Offline-Operation': attempt.id,
        },
        data: attempt.payload,
      );
      if (!mounted || session != widget.api.sessionRevision) return;
      Navigator.pop(context, true);
    } on ApiFailure catch (error) {
      if (mounted) {
        setState(() {
          if (error.connectionFailure || (error.status ?? 0) >= 500) {
            _uncertainAttempt = attempt;
            _error =
                'Could not confirm the movement. Retry this same movement or check the product ledger.';
          } else {
            _error = error.message;
          }
        });
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  void dispose() {
    _quantity.dispose();
    _rate.dispose();
    _reference.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: Scaffold(
      appBar: AppBar(title: const Text('Record stock movement')),
      body: FutureBuilder(
        future: _warehouses,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          final data = snapshot.data;
          if (data is! Json || data['items'] is! List) {
            return Center(
              child: TextButton(
                onPressed: () => setState(() {
                  _warehouses = _loadWarehouses();
                }),
                child: const Text('Retry loading warehouses'),
              ),
            );
          }
          final items = (data['items'] as List).whereType<Json>().toList();
          if (items.isEmpty) {
            return const Center(child: Text('No active warehouses'));
          }
          return Form(
            key: _form,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                DropdownButtonFormField<String>(
                  initialValue: _type,
                  decoration: const InputDecoration(labelText: 'Movement'),
                  items: const [
                    DropdownMenuItem(
                      value: 'stock_in',
                      child: Text('Stock in'),
                    ),
                    DropdownMenuItem(
                      value: 'stock_out',
                      child: Text('Stock out'),
                    ),
                  ],
                  onChanged: _locked
                      ? null
                      : (value) => setState(() => _type = value!),
                ),
                DropdownButtonFormField<int>(
                  initialValue: _warehouse,
                  decoration: const InputDecoration(labelText: 'Warehouse'),
                  items: [
                    for (final item in items)
                      DropdownMenuItem(
                        value: item['id'] as int,
                        child: Text('${item['warehouse_name']}'),
                      ),
                  ],
                  validator: (value) =>
                      value == null ? 'Choose a warehouse' : null,
                  onChanged: _locked ? null : (value) => _warehouse = value,
                ),
                TextFormField(
                  controller: _quantity,
                  enabled: !_locked,
                  decoration: const InputDecoration(labelText: 'Quantity'),
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  validator: (text) {
                    final quantity = double.tryParse(text?.trim() ?? '');
                    return quantity != null && quantity.isFinite && quantity > 0
                        ? null
                        : 'Enter a quantity greater than zero';
                  },
                ),
                TextFormField(
                  controller: _rate,
                  enabled: !_locked,
                  decoration: const InputDecoration(
                    labelText: 'Rate (optional)',
                  ),
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  validator: (text) {
                    if (text == null || text.trim().isEmpty) return null;
                    final rate = double.tryParse(text.trim());
                    return rate != null && rate.isFinite && rate >= 0
                        ? null
                        : 'Enter a non-negative rate';
                  },
                ),
                TextFormField(
                  controller: _reference,
                  enabled: !_locked,
                  decoration: const InputDecoration(
                    labelText: 'Reference (optional)',
                  ),
                ),
                if (_error != null) Text(_error!),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _saving ? null : _save,
                  child: Text(
                    _saving
                        ? 'Saving…'
                        : _uncertainAttempt == null
                        ? 'Save movement'
                        : 'Retry same movement',
                  ),
                ),
              ],
            ),
          );
        },
      ),
    ),
  );
}
