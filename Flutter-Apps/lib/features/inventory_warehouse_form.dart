import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

Future<List<Json>> loadActiveInventoryWarehouses(
  ApiClient api,
  Map<String, String> scopeHeaders,
) async {
  final revision = api.sessionRevision;
  final payload = await api.request(
    'GET',
    InventoryWarehouseForm.endpoint,
    scopeHeaders: scopeHeaders,
  );
  if (api.sessionRevision != revision) {
    throw ApiFailure('Your session ended. Sign in again.', 401);
  }
  final rows = payload is Json ? payload['items'] : payload;
  return (rows as List)
      .whereType<Json>()
      .where((row) => row['id'] is int && row['active'] != false)
      .toList();
}

class InventoryWarehouseForm extends StatefulWidget {
  const InventoryWarehouseForm({
    super.key,
    required this.api,
    required this.scopeHeaders,
    this.warehouse,
  });

  static const endpoint = '/srm/inventory/warehouses';
  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final Json? warehouse;

  @override
  State<InventoryWarehouseForm> createState() => _InventoryWarehouseFormState();
}

class _InventoryWarehouseFormState extends State<InventoryWarehouseForm> {
  static const _fields = [
    (key: 'warehouse_code', label: 'Warehouse code', limit: 80, required: true),
    (
      key: 'warehouse_name',
      label: 'Warehouse name',
      limit: 180,
      required: true,
    ),
    (key: 'branch', label: 'Branch', limit: 160, required: false),
    (key: 'address', label: 'Address', limit: null, required: false),
  ];
  final _form = GlobalKey<FormState>();
  final _values = <String, String>{};
  bool _saving = false;
  String? _error;

  int? get _warehouseId => widget.warehouse?['id'] as int?;

  Future<void> _save() async {
    if (_saving || _form.currentState?.validate() != true) return;
    _form.currentState!.save();
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        _warehouseId == null ? 'POST' : 'PUT',
        _warehouseId == null
            ? InventoryWarehouseForm.endpoint
            : '${InventoryWarehouseForm.endpoint}/$_warehouseId',
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

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(_warehouseId == null ? 'New warehouse' : 'Edit warehouse'),
    ),
    body: Form(
      key: _form,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final field in _fields)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: TextFormField(
                initialValue: widget.warehouse?[field.key]?.toString(),
                enabled: !_saving,
                decoration: InputDecoration(
                  labelText: field.label,
                  border: const OutlineInputBorder(),
                ),
                maxLength: field.limit,
                maxLines: field.key == 'address' ? 3 : 1,
                validator: (value) =>
                    field.required && (value ?? '').trim().isEmpty
                    ? 'Enter ${field.label.toLowerCase()}'
                    : null,
                onSaved: (value) {
                  final text = (value ?? '').trim();
                  if (text.isEmpty) {
                    _values.remove(field.key);
                  } else {
                    _values[field.key] = text;
                  }
                },
              ),
            ),
          if (_error case final error?) Text(error),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(
              _saving
                  ? 'Saving…'
                  : _warehouseId == null
                  ? 'Create warehouse'
                  : 'Save changes',
            ),
          ),
        ],
      ),
    ),
  );
}
