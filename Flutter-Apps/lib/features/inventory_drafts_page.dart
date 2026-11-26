import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/inventory_offline_creates.dart';
import '../core/models.dart';

class InventoryDraftsPage extends StatefulWidget {
  const InventoryDraftsPage({
    super.key,
    required this.api,
    required this.drafts,
  });
  final ApiClient api;
  final InventoryOfflineCreates drafts;

  @override
  State<InventoryDraftsPage> createState() => _InventoryDraftsPageState();
}

class _InventoryDraftsPageState extends State<InventoryDraftsPage> {
  late Future<List<Json>> _entries = widget.drafts.entries();
  var _form = GlobalKey<FormState>();
  final _scroll = ScrollController();
  String _name = '', _sku = '', _currency = '';
  final Map<String, String> _details = {};
  String? _editingOperation;
  bool _trackInventory = true;
  bool _busy = false;
  String? _message;

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  void _edit(Json entry) {
    if (_name.isNotEmpty ||
        _sku.isNotEmpty ||
        _currency.isNotEmpty ||
        _details.isNotEmpty ||
        !_trackInventory) {
      setState(
        () => _message = 'Save your current draft before editing another.',
      );
      _scroll.jumpTo(0);
      return;
    }
    _loadForm(entry);
    _scroll.jumpTo(0);
  }

  Future<void> _run(Future<void> Function() operation, String message) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await operation();
      if (mounted) {
        setState(() {
          _entries = widget.drafts.entries();
          _message = message;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _entries = widget.drafts.entries();
          _message = '$error';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _queue() async {
    if (!_form.currentState!.validate()) return;
    await _run(() async {
      await widget.drafts.enqueue({
        'kind': 'product',
        'name': _name.trim(),
        'code': _sku.trim(),
        'currency': _currency.trim().toUpperCase(),
        ..._details,
        'track_inventory': _trackInventory,
      }, replaceRejected: _editingOperation);
      if (mounted) _loadForm();
    }, 'Product draft saved on this device.');
  }

  void _loadForm([Json? entry]) {
    final product = entry?['product'] as Json? ?? {};
    setState(() {
      _form = GlobalKey<FormState>();
      _editingOperation = entry?['operation'] as String?;
      _name = product['name'] as String? ?? '';
      _sku = product['code'] as String? ?? '';
      _currency = product['currency'] as String? ?? '';
      _trackInventory = product['track_inventory'] as bool? ?? true;
      _details
        ..clear()
        ..addEntries(
          product.entries
              .where(
                (field) =>
                    !const {
                      'kind',
                      'name',
                      'code',
                      'currency',
                      'track_inventory',
                    }.contains(field.key) &&
                    field.value != null,
              )
              .map((field) => MapEntry(field.key, '${field.value}')),
        );
    });
  }

  Widget _detailField(
    String key,
    String label, {
    int? maxLength,
    int? decimalPlaces,
    num maximum = 9999999999,
    int maxLines = 1,
  }) => TextFormField(
    initialValue: _details[key],
    enabled: !_busy,
    maxLength: maxLength,
    maxLines: maxLines,
    keyboardType: decimalPlaces == null
        ? null
        : const TextInputType.numberWithOptions(decimal: true),
    decoration: InputDecoration(labelText: label),
    onChanged: (value) {
      final text = value.trim();
      if (text.isEmpty) {
        _details.remove(key);
      } else {
        _details[key] = text;
      }
    },
    validator: (value) {
      final text = value?.trim() ?? '';
      if (decimalPlaces == null || text.isEmpty) return null;
      final pattern = RegExp(
        r'^(?:\d+(?:\.\d{0,'
        '$decimalPlaces'
        r'})?|\.\d{1,'
        '$decimalPlaces'
        r'})$',
      );
      if (!pattern.hasMatch(text) || num.parse(text) > maximum) {
        return 'Enter a value from 0 to $maximum with up to $decimalPlaces decimal places.';
      }
      return null;
    },
  );

  Future<void> _discard(String operation) async {
    final discard = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Discard this product draft?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
    if (discard == true && mounted) {
      await _run(
        () => widget.drafts.discard(operation),
        'Product draft discarded.',
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Product drafts')),
    body: ListView(
      controller: _scroll,
      padding: const EdgeInsets.all(16),
      children: [
        const Text(
          'Save a product on this device and upload it when connected.',
        ),
        Form(
          key: _form,
          child: Column(
            children: [
              TextFormField(
                initialValue: _name,
                maxLength: 180,
                enabled: !_busy,
                decoration: const InputDecoration(labelText: 'Product name'),
                onChanged: (value) => _name = value,
                validator: (value) => (value ?? '').trim().isEmpty
                    ? 'Enter a product name.'
                    : null,
              ),
              TextFormField(
                initialValue: _sku,
                maxLength: 80,
                enabled: !_busy,
                decoration: const InputDecoration(labelText: 'SKU'),
                onChanged: (value) => _sku = value,
                validator: (value) =>
                    (value ?? '').trim().isEmpty ? 'Enter a SKU.' : null,
              ),
              TextFormField(
                initialValue: _currency,
                maxLength: 3,
                enabled: !_busy,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(
                  labelText: 'Currency',
                  hintText: 'INR',
                ),
                onChanged: (value) => _currency = value,
                validator: (value) =>
                    RegExp(r'^[A-Za-z]{3}$').hasMatch((value ?? '').trim())
                    ? null
                    : 'Enter a three-letter currency code.',
              ),
              _detailField('price', 'Base price', decimalPlaces: 2),
              _detailField(
                'tax',
                'GST rate (%)',
                decimalPlaces: 2,
                maximum: 100,
              ),
              _detailField('unit', 'Unit of measure', maxLength: 40),
              _detailField('hsn_code', 'HSN code', maxLength: 30),
              _detailField('barcode', 'Barcode', maxLength: 120),
              _detailField(
                'description',
                'Description',
                maxLength: 50000,
                maxLines: 3,
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Track inventory'),
                value: _trackInventory,
                onChanged: _busy
                    ? null
                    : (value) => setState(() => _trackInventory = value),
              ),
              _detailField('cost', 'Purchase cost', decimalPlaces: 2),
              _detailField('mrp', 'MRP', decimalPlaces: 2),
              _detailField('reorder_level', 'Reorder level', decimalPlaces: 3),
              FilledButton(
                onPressed: _busy ? null : _queue,
                child: Text(
                  _editingOperation == null
                      ? 'Save product draft'
                      : 'Save corrected draft',
                ),
              ),
              if (_editingOperation != null)
                TextButton(
                  onPressed: _busy ? null : () => _loadForm(),
                  child: const Text('Cancel editing'),
                ),
            ],
          ),
        ),
        if (_message != null) ListTile(title: Text(_message!)),
        const Divider(),
        FutureBuilder<List<Json>>(
          future: _entries,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return ListTile(title: Text('${snapshot.error}'));
            }
            final entries = snapshot.data;
            if (entries == null) return const LinearProgressIndicator();
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (entries.isEmpty)
                  const ListTile(title: Text('No saved product drafts')),
                for (final entry in entries)
                  ListTile(
                    title: Text('${entry['product']['name']}'),
                    subtitle: SelectableText(
                      '${entry['product']['code']} · ${entry['error'] ?? 'Awaiting sync'}',
                    ),
                    trailing: entry['error'] == null
                        ? null
                        : Wrap(
                            children: [
                              IconButton(
                                tooltip: 'Edit rejected draft',
                                icon: const Icon(Icons.edit_outlined),
                                onPressed: _busy || _editingOperation != null
                                    ? null
                                    : () => _edit(entry),
                              ),
                              IconButton(
                                tooltip: 'Discard draft',
                                icon: const Icon(Icons.delete_outline),
                                onPressed:
                                    _busy ||
                                        _editingOperation == entry['operation']
                                    ? null
                                    : () => _discard(
                                        entry['operation'] as String,
                                      ),
                              ),
                            ],
                          ),
                  ),
                if (entries.any((entry) => entry['error'] == null))
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _run(
                            () => widget.drafts.sync(
                              widget.api,
                              reportTemporaryFailure: true,
                            ),
                            'Sync checked. Any unsent drafts remain below.',
                          ),
                    child: const Text('Sync now'),
                  ),
              ],
            );
          },
        ),
      ],
    ),
  );
}
