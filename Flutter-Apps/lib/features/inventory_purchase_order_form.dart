import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import 'inventory_warehouse_form.dart';
import 'sales_order_drafts_page.dart';

class InventoryPurchaseOrderForm extends StatefulWidget {
  const InventoryPurchaseOrderForm({
    super.key,
    required this.api,
    required this.scopeHeaders,
  });

  final ApiClient api;
  final Map<String, String> scopeHeaders;

  @override
  State<InventoryPurchaseOrderForm> createState() =>
      _InventoryPurchaseOrderFormState();
}

class _InventoryPurchaseOrderFormState
    extends State<InventoryPurchaseOrderForm> {
  final _form = GlobalKey<FormState>();
  final _values = {'quantity': '1', 'unit_price': '0', 'tax_amount': '0'};
  late var _warehouses = _loadWarehouses();
  Json? _vendor, _product;
  int? _warehouse;
  bool _saving = false;
  bool _uncertain = false;
  String? _error;

  Future<List<Json>> _loadWarehouses() =>
      loadActiveInventoryWarehouses(widget.api, widget.scopeHeaders);

  Future<void> _pick({required bool vendor}) async {
    final revision = widget.api.sessionRevision;
    final item = await showDialog<Json>(
      context: context,
      builder: (_) => SalesRecordPicker(
        api: widget.api,
        scopeHeaders: widget.scopeHeaders,
        offline: false,
        vendor: vendor,
        product: !vendor,
        activeOnly: !vendor,
      ),
    );
    if (!mounted || item == null || widget.api.sessionRevision != revision) {
      return;
    }
    setState(() {
      if (vendor) {
        _vendor = item;
      } else {
        _product = item;
      }
    });
  }

  void _unconfirmed() => setState(() {
    _uncertain = true;
    _error =
        'Draft confirmation is unavailable. Check Purchase orders before reopening this form.';
  });

  Future<void> _save() async {
    if (_saving || _uncertain || !_form.currentState!.validate()) return;
    if (_vendor == null || _product == null || _warehouse == null) {
      setState(() => _error = 'Choose a vendor, product, and warehouse.');
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
        '/srm/procurement/purchase-orders/drafts',
        scopeHeaders: widget.scopeHeaders,
        data: {
          'vendor_id': _vendor!['id'],
          'vendor_name': _vendor!['name'],
          'lines': [
            {
              'product_id': _product!['id'],
              'warehouse_id': _warehouse,
              ..._values,
            },
          ],
        },
      );
      if (!mounted || api.sessionRevision != revision) return;
      if (result is! Json ||
          result['id'] is! int ||
          result['status'] != 'draft') {
        _unconfirmed();
        return;
      }
      Navigator.pop(context, result);
    } on ApiFailure catch (error) {
      if (mounted && api.sessionRevision == revision) {
        if (error.connectionFailure || (error.status ?? 0) >= 500) {
          _unconfirmed();
        } else {
          setState(() => _error = error.message);
        }
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _number(String key, String label, {bool positive = false}) =>
      TextFormField(
        initialValue: _values[key],
        enabled: !_saving,
        decoration: InputDecoration(labelText: label),
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        onChanged: (value) => _values[key] = value.trim(),
        validator: (text) {
          final number = num.tryParse(text?.trim() ?? '');
          if (number == null || !number.isFinite || number < 0) {
            return 'Enter a nonnegative number.';
          }
          return positive && number == 0
              ? 'Quantity must be greater than zero.'
              : null;
        },
      );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('New purchase order')),
    body: Form(
      key: _form,
      child: FutureBuilder<List<Json>>(
        future: _warehouses,
        builder: (context, snapshot) => SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              OutlinedButton(
                onPressed: _saving ? null : () => _pick(vendor: true),
                child: Text("${_vendor?['name'] ?? 'Choose vendor'}"),
              ),
              OutlinedButton(
                onPressed: _saving ? null : () => _pick(vendor: false),
                child: Text("${_product?['item_name'] ?? 'Choose product'}"),
              ),
              if (snapshot.hasError)
                TextButton(
                  onPressed: () => setState(() {
                    _warehouses = _loadWarehouses();
                  }),
                  child: Text('${snapshot.error}\nRetry warehouses'),
                )
              else if (!snapshot.hasData)
                const LinearProgressIndicator()
              else
                DropdownButtonFormField<int>(
                  isExpanded: true,
                  initialValue: _warehouse,
                  decoration: const InputDecoration(labelText: 'Warehouse'),
                  items: [
                    for (final row in snapshot.requireData)
                      DropdownMenuItem(
                        value: row['id'] as int,
                        child: Text('${row['warehouse_name'] ?? row['name']}'),
                      ),
                  ],
                  onChanged: _saving
                      ? null
                      : (id) => setState(() => _warehouse = id),
                ),
              _number('quantity', 'Order quantity', positive: true),
              _number('unit_price', 'Order unit price'),
              _number('tax_amount', 'Order tax amount'),
              if (_error case final String error) Text(error),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _saving || _uncertain || !snapshot.hasData
                    ? null
                    : _save,
                child: Text(
                  _saving ? 'Saving…' : 'Create purchase order draft',
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
