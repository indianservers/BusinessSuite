import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import '../core/sales_order_drafts.dart';
import '../core/suite_read_cache.dart';
import 'inventory_warehouse_form.dart';
import 'sales_order_drafts_page.dart';

class InventoryPurchaseOrderForm extends StatefulWidget {
  const InventoryPurchaseOrderForm({
    super.key,
    required this.api,
    required this.scopeHeaders,
    this.cacheScope,
    this.offline = false,
  });

  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;

  @override
  State<InventoryPurchaseOrderForm> createState() =>
      _InventoryPurchaseOrderFormState();
}

class _PurchaseLine {
  Json? product;
  int? warehouse;
  final values = {'quantity': '1', 'unit_price': '0', 'tax_amount': '0'};
}

class _InventoryPurchaseOrderFormState
    extends State<InventoryPurchaseOrderForm> {
  final _form = GlobalKey<FormState>();
  final _lines = [_PurchaseLine()];
  late var _warehouses = _loadWarehouses();
  Json? _vendor;
  bool _saving = false;
  bool _uncertain = false;
  String? _error;

  String? get _choicesScope => widget.cacheScope == null
      ? null
      : "${widget.cacheScope}:purchase-choices:${widget.scopeHeaders['X-Suite-Branch'] ?? ''}";

  Future<List<Json>> _loadWarehouses() async {
    final scope = _choicesScope;
    final cache = scope == null ? null : '$scope:warehouses';
    if (widget.offline) {
      return cache == null ? [] : await SuiteReadCache.read(cache) ?? [];
    }
    final rows = await loadActiveInventoryWarehouses(
      widget.api,
      widget.scopeHeaders,
    );
    if (cache != null) {
      try {
        await SuiteReadCache.write(cache, [
          for (final row in rows)
            {'id': row['id'], 'warehouse_name': row['warehouse_name']},
        ]);
      } catch (_) {}
    }
    return rows;
  }

  Future<void> _pick({_PurchaseLine? line}) async {
    final vendor = line == null;
    final revision = widget.api.sessionRevision;
    final item = await showDialog<Json>(
      context: context,
      builder: (_) => SalesRecordPicker(
        api: widget.api,
        scopeHeaders: widget.scopeHeaders,
        offline: widget.offline,
        purchaseCacheScope: _choicesScope,
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
        line.product = item;
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
    if (_vendor == null) {
      setState(() => _error = 'Choose a vendor.');
      return;
    }
    final incomplete = _lines.indexWhere(
      (line) => line.product == null || line.warehouse == null,
    );
    if (incomplete >= 0) {
      setState(
        () => _error =
            'Choose a product and warehouse for item ${incomplete + 1}.',
      );
      return;
    }
    final api = widget.api;
    final revision = api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    final payload = {
      'vendor_id': _vendor!['id'],
      'vendor_name': _vendor!['name'],
      'lines': [
        for (final line in _lines)
          {
            'product_id': line.product!['id'],
            'warehouse_id': line.warehouse,
            ...line.values,
          },
      ],
    };
    try {
      if (widget.offline) {
        final scope = widget.cacheScope;
        if (scope == null) throw ApiFailure('Sign in to save a local draft.');
        await SalesOrderDrafts.purchaseOrders(scope).save(
          const Uuid().v4(),
          payload,
          branch: widget.scopeHeaders['X-Suite-Branch'],
        );
        if (mounted && api.sessionRevision == revision) {
          Navigator.pop(context, {'local': true});
        }
        return;
      }
      final result = await api.request(
        'POST',
        '/srm/procurement/purchase-orders/drafts',
        scopeHeaders: widget.scopeHeaders,
        data: payload,
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
    } catch (error) {
      if (mounted && api.sessionRevision == revision) {
        setState(() => _error = 'Unable to save the draft. $error');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _number(
    _PurchaseLine line,
    String key,
    String label, {
    bool positive = false,
  }) => TextFormField(
    initialValue: line.values[key],
    enabled: !_saving,
    decoration: InputDecoration(labelText: label),
    keyboardType: const TextInputType.numberWithOptions(decimal: true),
    onChanged: (value) => line.values[key] = value.trim(),
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

  Widget _lineEditor(int index, _PurchaseLine line, List<Json> warehouses) =>
      Card(
        key: ObjectKey(line),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(child: Text('Item ${index + 1}')),
                  if (_lines.length > 1)
                    IconButton(
                      tooltip: 'Remove item ${index + 1}',
                      icon: const Icon(Icons.delete_outline),
                      onPressed: _saving
                          ? null
                          : () => setState(() {
                              _lines.remove(line);
                            }),
                    ),
                ],
              ),
              OutlinedButton(
                onPressed: _saving ? null : () => _pick(line: line),
                child: Text(
                  "${line.product?['item_name'] ?? 'Choose product'}",
                ),
              ),
              DropdownButtonFormField<int>(
                isExpanded: true,
                initialValue: line.warehouse,
                decoration: const InputDecoration(labelText: 'Warehouse'),
                items: [
                  for (final row in warehouses)
                    DropdownMenuItem(
                      value: row['id'] as int,
                      child: Text('${row['warehouse_name'] ?? row['name']}'),
                    ),
                ],
                onChanged: _saving
                    ? null
                    : (id) => setState(() => line.warehouse = id),
              ),
              _number(line, 'quantity', 'Order quantity', positive: true),
              _number(line, 'unit_price', 'Order unit price'),
              _number(line, 'tax_amount', 'Order tax amount'),
            ],
          ),
        ),
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
                onPressed: _saving ? null : _pick,
                child: Text("${_vendor?['name'] ?? 'Choose vendor'}"),
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
              else ...[
                for (final (index, line) in _lines.indexed)
                  _lineEditor(index, line, snapshot.requireData),
                OutlinedButton.icon(
                  onPressed: _saving
                      ? null
                      : () => setState(() {
                          _lines.add(_PurchaseLine());
                        }),
                  icon: const Icon(Icons.add),
                  label: const Text('Add item'),
                ),
              ],
              if (_error case final String error) Text(error),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _saving || _uncertain || !snapshot.hasData
                    ? null
                    : _save,
                child: Text(
                  _saving
                      ? 'Saving…'
                      : widget.offline
                      ? 'Save draft offline'
                      : 'Create purchase order draft',
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
