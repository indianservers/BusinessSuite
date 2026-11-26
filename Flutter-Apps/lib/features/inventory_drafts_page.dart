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
  final _form = GlobalKey<FormState>();
  String _name = '', _sku = '', _currency = '';
  bool _busy = false;
  String? _message;

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
      if (mounted) setState(() => _message = '$error');
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
      });
      if (mounted) {
        _form.currentState?.reset();
        _name = _sku = _currency = '';
      }
    }, 'Product draft saved on this device.');
  }

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
                maxLength: 180,
                enabled: !_busy,
                decoration: const InputDecoration(labelText: 'Product name'),
                onChanged: (value) => _name = value,
                validator: (value) => (value ?? '').trim().isEmpty
                    ? 'Enter a product name.'
                    : null,
              ),
              TextFormField(
                maxLength: 80,
                enabled: !_busy,
                decoration: const InputDecoration(labelText: 'SKU'),
                onChanged: (value) => _sku = value,
                validator: (value) =>
                    (value ?? '').trim().isEmpty ? 'Enter a SKU.' : null,
              ),
              TextFormField(
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
              FilledButton(
                onPressed: _busy ? null : _queue,
                child: const Text('Save product draft'),
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
                        : IconButton(
                            tooltip: 'Discard draft',
                            icon: const Icon(Icons.delete_outline),
                            onPressed: _busy
                                ? null
                                : () => _discard(entry['operation'] as String),
                          ),
                  ),
                if (entries.any((entry) => entry['error'] == null))
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _run(
                            () => widget.drafts.sync(widget.api),
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
