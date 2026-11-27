import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import 'inventory_batch_page.dart';
import 'inventory_warehouse_form.dart';
import 'sales_order_drafts_page.dart';

class InventoryTrackingForm extends StatefulWidget {
  const InventoryTrackingForm({
    super.key,
    required this.api,
    required this.scopeHeaders,
    required this.serial,
  });

  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final bool serial;

  @override
  State<InventoryTrackingForm> createState() => _InventoryTrackingFormState();
}

class _InventoryTrackingFormState extends State<InventoryTrackingForm> {
  final _form = GlobalKey<FormState>();
  late final _values = <String, String>{
    'status': 'available',
    if (!widget.serial) 'unit_cost': '0',
  };
  Json? _product, _batch;
  int? _warehouse;
  late var _warehouses = _loadWarehouses();
  bool _saving = false;
  String? _error;

  Future<List<Json>> _loadWarehouses() =>
      loadActiveInventoryWarehouses(widget.api, widget.scopeHeaders);

  Future<void> _pick({bool batch = false}) async {
    final revision = widget.api.sessionRevision;
    final selected = await showDialog<Json>(
      context: context,
      builder: (_) => SalesRecordPicker(
        api: widget.api,
        offline: false,
        product: !batch,
        activeOnly: !batch,
        batchProductId: batch ? _product!['id'] as int : null,
        scopeHeaders: widget.scopeHeaders,
      ),
    );
    if (!mounted ||
        selected == null ||
        revision != widget.api.sessionRevision) {
      return;
    }
    setState(() {
      if (batch) {
        _batch = selected;
      } else {
        if (selected['id'] != _product?['id']) _batch = null;
        _product = selected;
      }
    });
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    if (_product == null) {
      setState(() => _error = 'Choose a product.');
      return;
    }
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    final data = <String, dynamic>{
      'product_id': _product!['id'],
      if (_warehouse != null) 'warehouse_id': _warehouse,
      ..._values,
      if (widget.serial && _batch != null) 'batch_id': _batch!['id'],
    }..removeWhere((_, value) => value == '');
    try {
      final result = await widget.api.request(
        'POST',
        widget.serial ? InventoryBatchPage.serials : InventoryBatchPage.batches,
        scopeHeaders: widget.scopeHeaders,
        data: data,
      );
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, result is Json ? result : <String, dynamic>{});
      }
    } on ApiFailure catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _error = error.message);
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _field(
    String key,
    String label, {
    bool required = false,
    bool decimal = false,
    bool date = false,
    int? maxLength,
  }) => TextFormField(
    initialValue: _values[key],
    enabled: !_saving,
    decoration: InputDecoration(
      labelText: label,
      hintText: date ? 'YYYY-MM-DD' : null,
    ),
    keyboardType: decimal
        ? const TextInputType.numberWithOptions(decimal: true)
        : null,
    maxLength: maxLength,
    onChanged: (text) => _values[key] = text.trim(),
    validator: (text) {
      final value = text?.trim() ?? '';
      if (value.isEmpty) return required ? 'Enter $label.' : null;
      if (decimal) {
        final number = num.tryParse(value);
        if (number == null || !number.isFinite || number < 0) {
          return 'Enter a nonnegative number.';
        }
        if (key == 'available_quantity' &&
            number > (num.tryParse(_values['quantity'] ?? '') ?? number)) {
          return 'Available quantity cannot exceed quantity.';
        }
      }
      if (date) {
        final parsed = DateTime.tryParse(value);
        if (parsed == null ||
            parsed.toIso8601String().split('T').first != value) {
          return 'Enter a valid date as YYYY-MM-DD.';
        }
        final manufacture = _values['manufacture_date'];
        if (key == 'expiry_date' &&
            manufacture != null &&
            manufacture.isNotEmpty &&
            value.compareTo(manufacture) < 0) {
          return 'Expiry cannot precede manufacture date.';
        }
      }
      return null;
    },
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.serial ? 'Register serial number' : 'Create batch'),
    ),
    body: Form(
      key: _form,
      child: FutureBuilder<List<Json>>(
        future: _warehouses,
        builder: (context, snapshot) {
          final ready =
              snapshot.connectionState == ConnectionState.done &&
              snapshot.hasData;
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                OutlinedButton(
                  onPressed: _saving ? null : _pick,
                  child: Text('${_product?['item_name'] ?? 'Choose product'}'),
                ),
                if (snapshot.hasError)
                  TextButton(
                    onPressed: () => setState(() {
                      _warehouses = _loadWarehouses();
                    }),
                    child: Text('${snapshot.error}\nRetry warehouses'),
                  )
                else if (!ready)
                  const LinearProgressIndicator()
                else
                  DropdownButtonFormField<int>(
                    isExpanded: true,
                    initialValue: _warehouse ?? 0,
                    decoration: const InputDecoration(labelText: 'Warehouse'),
                    items: [
                      const DropdownMenuItem(
                        value: 0,
                        child: Text('Use default warehouse'),
                      ),
                      for (final row in snapshot.requireData)
                        DropdownMenuItem(
                          value: row['id'] as int,
                          child: Text(
                            '${row['warehouse_name'] ?? row['name']}',
                          ),
                        ),
                    ],
                    onChanged: _saving
                        ? null
                        : (id) =>
                              setState(() => _warehouse = id == 0 ? null : id),
                  ),
                if (widget.serial) ...[
                  _field(
                    'serial_number',
                    'Serial number',
                    required: true,
                    maxLength: 160,
                  ),
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(
                      '${_batch?['batch_number'] ?? 'Choose batch (optional)'}',
                    ),
                    onTap: _saving || _product == null
                        ? null
                        : () => _pick(batch: true),
                    trailing: _batch == null
                        ? null
                        : IconButton(
                            tooltip: 'Clear batch',
                            onPressed: _saving
                                ? null
                                : () => setState(() => _batch = null),
                            icon: const Icon(Icons.clear),
                          ),
                  ),
                  _field('reference_number', 'Reference number'),
                ] else ...[
                  _field(
                    'batch_number',
                    'Batch number',
                    required: true,
                    maxLength: 120,
                  ),
                  _field('manufacture_date', 'Manufacture date', date: true),
                  _field('expiry_date', 'Expiry date', date: true),
                  _field('quantity', 'Quantity', required: true, decimal: true),
                  _field(
                    'available_quantity',
                    'Available quantity (optional)',
                    decimal: true,
                  ),
                  _field(
                    'unit_cost',
                    'Unit cost',
                    required: true,
                    decimal: true,
                  ),
                  _field('notes', 'Notes'),
                ],
                _field('received_date', 'Received date', date: true),
                _field('status', 'Status', required: true),
                if (_error case final String error) Text(error),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: !ready || _saving ? null : _save,
                  child: Text(
                    _saving
                        ? 'Saving…'
                        : widget.serial
                        ? 'Save serial'
                        : 'Save batch',
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
