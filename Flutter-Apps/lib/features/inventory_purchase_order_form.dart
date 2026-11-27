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
    this.rejectedDraft,
  });

  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;
  final Json? rejectedDraft;

  @override
  State<InventoryPurchaseOrderForm> createState() =>
      _InventoryPurchaseOrderFormState();
}

class _PurchaseLine {
  _PurchaseLine([Json? saved]) {
    if (saved?['product_id'] case final int id) {
      product = {'id': id, 'item_name': 'Product #$id'};
    }
    warehouse = saved?['warehouse_id'] as int?;
    for (final key in values.keys) {
      if (saved?[key] case final Object value) values[key] = '$value';
    }
  }

  Json? product;
  int? warehouse;
  final values = {'quantity': '1', 'unit_price': '0', 'tax_amount': '0'};
}

class _InventoryPurchaseOrderFormState
    extends State<InventoryPurchaseOrderForm> {
  final _form = GlobalKey<FormState>();
  Json? get _savedPayload => widget.rejectedDraft?['payload'] as Json?;
  late final _details = <String, String>{
    for (final key in ['order_date', 'expected_date', 'notes'])
      if (_savedPayload?[key] case final String value) key: value,
  };
  late final _lines = [
    for (final line
        in (_savedPayload?['lines'] as List? ?? const []).whereType<Json>())
      _PurchaseLine(line),
    if (_savedPayload == null) _PurchaseLine(),
  ];
  late var _warehouses = _loadWarehouses();
  late Json? _vendor = _savedPayload == null
      ? null
      : {
          'id': _savedPayload!['vendor_id'],
          'name': _savedPayload!['vendor_name'],
        };
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

  Future<void> _chooseDate(String key, String label) async {
    final selected = await showDatePicker(
      context: context,
      helpText: label,
      initialDate: DateTime.tryParse(_details[key] ?? '') ?? DateTime.now(),
      firstDate: DateTime(2000),
      lastDate: DateTime(2100, 12, 31),
    );
    if (selected == null || !mounted) return;
    setState(() => _details[key] = selected.toIso8601String().split('T').first);
  }

  Widget _dateField(String key, String label) => Row(
    children: [
      Expanded(
        child: OutlinedButton(
          onPressed: _saving ? null : () => _chooseDate(key, label),
          child: Text([label, ?_details[key]].join(' · ')),
        ),
      ),
      if (_details.containsKey(key))
        IconButton(
          tooltip: 'Clear ${label.toLowerCase()}',
          icon: const Icon(Icons.clear),
          onPressed: _saving
              ? null
              : () => setState(() => _details.remove(key)),
        ),
    ],
  );

  Future<void> _save() async {
    if (_saving || _uncertain || !_form.currentState!.validate()) return;
    if (_vendor == null) {
      setState(() => _error = 'Choose a vendor.');
      return;
    }
    if (_lines.isEmpty) {
      setState(() => _error = 'Add at least one item.');
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
    final scope = widget.cacheScope;
    final drafts = scope == null
        ? null
        : SalesOrderDrafts.purchaseOrders(scope);
    final branch = widget.scopeHeaders['X-Suite-Branch'];
    final operation = const Uuid().v4();
    setState(() {
      _saving = true;
      _error = null;
    });
    final payload = {
      'vendor_id': _vendor!['id'],
      'vendor_name': _vendor!['name'],
      for (final detail in _details.entries)
        if (detail.value.isNotEmpty) detail.key: detail.value,
      'lines': [
        for (final line in _lines)
          {
            'product_id': line.product!['id'],
            'warehouse_id': line.warehouse,
            ...line.values,
          },
      ],
    };
    Future<void> saveLocally() async {
      if (drafts == null) throw ApiFailure('Sign in to save a local draft.');
      if (api.sessionRevision != revision) return;
      await drafts.save(
        operation,
        payload,
        branch: branch,
        replaceRejected: widget.rejectedDraft?['operation'] as String?,
      );
      if (mounted && api.sessionRevision == revision) {
        Navigator.pop(context, {'local': true});
      }
    }

    try {
      if (widget.offline || widget.rejectedDraft != null) {
        await saveLocally();
        return;
      }
      final Object? result;
      try {
        result = drafts == null
            ? await api.request(
                'POST',
                '${SalesOrderDrafts.purchaseOrdersEndpoint}/drafts',
                scopeHeaders: widget.scopeHeaders,
                data: payload,
              )
            : await drafts.submit(api, operation, payload, branch: branch);
      } on ApiFailure catch (error) {
        if (drafts == null ||
            (!error.connectionFailure && (error.status ?? 0) < 500)) {
          rethrow;
        }
        try {
          await saveLocally();
        } catch (_) {
          if (mounted && api.sessionRevision == revision) _unconfirmed();
        }
        return;
      }
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

  Widget _lineEditor(
    int index,
    _PurchaseLine line,
    List<Json> warehouses,
  ) => Card(
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
            child: Text("${line.product?['item_name'] ?? 'Choose product'}"),
          ),
          DropdownButtonFormField<int>(
            isExpanded: true,
            initialValue: warehouses.any((row) => row['id'] == line.warehouse)
                ? line.warehouse
                : null,
            decoration: const InputDecoration(labelText: 'Warehouse'),
            validator: (id) => id == null ? 'Choose a warehouse.' : null,
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
    appBar: AppBar(
      title: Text(
        widget.rejectedDraft == null
            ? 'New purchase order'
            : 'Correct purchase order draft',
      ),
    ),
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
                _dateField('order_date', 'Order date'),
                _dateField('expected_date', 'Expected date'),
                TextFormField(
                  initialValue: _details['notes'],
                  decoration: const InputDecoration(labelText: 'Notes'),
                  minLines: 2,
                  maxLines: 4,
                  enabled: !_saving,
                  onChanged: (value) => _details['notes'] = value.trim(),
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
                      : widget.rejectedDraft != null
                      ? 'Save corrected draft'
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
