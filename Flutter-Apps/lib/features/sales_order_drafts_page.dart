import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import '../core/sales_order_drafts.dart';

class NewSalesOrderPage extends StatefulWidget {
  const NewSalesOrderPage({
    super.key,
    required this.api,
    this.drafts,
    this.offline = false,
  });
  final ApiClient api;
  final SalesOrderDrafts? drafts;
  final bool offline;

  @override
  State<NewSalesOrderPage> createState() => _NewSalesOrderPageState();
}

class _NewSalesOrderPageState extends State<NewSalesOrderPage> {
  final _form = GlobalKey<FormState>();
  final _operation = const Uuid().v4();
  final _details = <String, String>{'currency': 'INR'};
  final _lines = <Map<String, String>>[
    {'quantity': '1'},
  ];
  bool _saving = false;
  String? _error;
  Json? _customer;

  Future<void> _chooseCustomer() async {
    final customer = await showDialog<Json>(
      context: context,
      builder: (_) => _SalesCustomerPicker(
        api: widget.api,
        drafts: widget.drafts,
        offline: widget.offline,
      ),
    );
    if (mounted && customer != null) setState(() => _customer = customer);
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    final revision = widget.api.sessionRevision;
    final payload = <String, dynamic>{
      ..._details,
      if (_customer != null) 'customer_id': _customer!['id'],
      'currency': _details['currency']!.toUpperCase(),
      'lines': [for (final line in _lines) Map<String, String>.of(line)],
    };
    setState(() {
      _saving = true;
      _error = null;
    });
    final drafts = widget.drafts;
    try {
      if (widget.offline && drafts != null) {
        await drafts.save(_operation, payload);
      } else {
        try {
          if (drafts == null) {
            await widget.api.request(
              'POST',
              SalesOrderDrafts.endpoint,
              data: payload,
              scopeHeaders: {'X-Offline-Operation': _operation},
            );
          } else {
            await drafts.submit(widget.api, _operation, payload);
          }
        } on ApiFailure catch (error) {
          if (!error.connectionFailure ||
              drafts == null ||
              revision != widget.api.sessionRevision) {
            rethrow;
          }
          await drafts.save(_operation, payload);
        }
      }
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _error = '$error');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _field(
    Map<String, String> values,
    String key,
    String label, {
    int? maxLength,
    bool required = true,
    int? decimals,
    bool positive = false,
  }) => TextFormField(
    enabled: !_saving,
    initialValue: values[key],
    maxLength: maxLength,
    decoration: InputDecoration(labelText: label),
    keyboardType: decimals == null
        ? TextInputType.text
        : const TextInputType.numberWithOptions(decimal: true),
    onChanged: (value) => values[key] = value.trim(),
    validator: (value) {
      final text = value?.trim() ?? '';
      if (text.isEmpty) return required ? 'Enter $label.' : null;
      if (key == 'currency' && !RegExp(r'^[A-Za-z]{3}$').hasMatch(text)) {
        return 'Enter a three-letter currency code.';
      }
      if (decimals != null) {
        final number = num.tryParse(text);
        if (!RegExp('^\\d+(\\.\\d{1,$decimals})?\$').hasMatch(text) ||
            number == null ||
            (positive && number <= 0)) {
          return 'Enter a valid $label.';
        }
      }
      return null;
    },
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('New sales order')),
    body: Form(
      key: _form,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _field(_details, 'title', 'Order title', maxLength: 220),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(_customer?['name'] as String? ?? 'Choose customer'),
            subtitle: _customer == null ? null : const Text('Customer'),
            onTap: _saving ? null : _chooseCustomer,
            trailing: _customer == null
                ? const Icon(Icons.chevron_right)
                : IconButton(
                    tooltip: 'Remove customer',
                    onPressed: _saving
                        ? null
                        : () => setState(() => _customer = null),
                    icon: const Icon(Icons.close),
                  ),
          ),
          _field(_details, 'currency', 'Currency', maxLength: 3),
          _field(_details, 'terms', 'Terms', required: false, maxLength: 4000),
          for (final (index, line) in _lines.indexed)
            Column(
              key: ObjectKey(line),
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('Line ${index + 1}'),
                  trailing: _lines.length > 1
                      ? IconButton(
                          tooltip: 'Remove line',
                          onPressed: _saving
                              ? null
                              : () => setState(() => _lines.removeAt(index)),
                          icon: const Icon(Icons.remove_circle_outline),
                        )
                      : null,
                ),
                _field(line, 'description', 'Description', maxLength: 500),
                _field(
                  line,
                  'quantity',
                  'Quantity',
                  decimals: 2,
                  positive: true,
                ),
                _field(line, 'unit_price', 'Unit price', decimals: 2),
              ],
            ),
          TextButton(
            onPressed: _saving
                ? null
                : () => setState(() => _lines.add({'quantity': '1'})),
            child: const Text('Add line'),
          ),
          if (_error != null) Text(_error!),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(
              _saving
                  ? 'Saving…'
                  : widget.offline
                  ? 'Save order draft'
                  : 'Create order',
            ),
          ),
        ],
      ),
    ),
  );
}

class _SalesCustomerPicker extends StatefulWidget {
  const _SalesCustomerPicker({
    required this.api,
    this.drafts,
    required this.offline,
  });
  final ApiClient api;
  final SalesOrderDrafts? drafts;
  final bool offline;

  @override
  State<_SalesCustomerPicker> createState() => _SalesCustomerPickerState();
}

class _SalesCustomerPickerState extends State<_SalesCustomerPicker> {
  late Future<List<Json>> _customers = _load('');
  String _search = '';

  Future<List<Json>> _load(String search) async {
    final drafts = widget.drafts;
    if (drafts != null) {
      return drafts.customers(widget.api, search, offline: widget.offline);
    }
    final revision = widget.api.sessionRevision;
    final data =
        await widget.api.request(
              'GET',
              SalesOrderDrafts.customersEndpoint,
              query: {if (search.isNotEmpty) 'q': search},
            )
            as Json;
    if (revision != widget.api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    return (data['items'] as List).whereType<Json>().toList();
  }

  void _searchCustomers() => setState(() {
    _customers = _load(_search.trim());
  });

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Choose customer'),
    content: SizedBox(
      width: 360,
      height: 350,
      child: Column(
        children: [
          TextField(
            maxLength: 100,
            onChanged: (value) => _search = value,
            onSubmitted: (_) => _searchCustomers(),
            textInputAction: TextInputAction.search,
            decoration: InputDecoration(
              labelText: 'Customer name',
              counterText: '',
              suffixIcon: IconButton(
                tooltip: 'Search customers',
                onPressed: _searchCustomers,
                icon: const Icon(Icons.search),
              ),
            ),
          ),
          Expanded(
            child: FutureBuilder<List<Json>>(
              future: _customers,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Center(child: Text('${snapshot.error}'));
                }
                final rows = snapshot.requireData;
                if (rows.isEmpty) {
                  return Center(
                    child: Text(
                      widget.offline
                          ? 'No matching saved customers'
                          : 'No matching customers',
                    ),
                  );
                }
                return ListView(
                  children: [
                    for (final row in rows)
                      if (row['id'] is int && row['name'] is String)
                        ListTile(
                          title: Text(row['name'] as String),
                          onTap: () => Navigator.pop(context, row),
                        ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
    ],
  );
}

class SalesOrderDraftsPage extends StatefulWidget {
  const SalesOrderDraftsPage({
    super.key,
    required this.api,
    required this.drafts,
    this.onSynced,
  });
  final ApiClient api;
  final SalesOrderDrafts drafts;
  final VoidCallback? onSynced;

  @override
  State<SalesOrderDraftsPage> createState() => _SalesOrderDraftsPageState();
}

class _SalesOrderDraftsPageState extends State<SalesOrderDraftsPage> {
  late Future<List<Json>> _entries = widget.drafts.entries();
  bool _syncing = false;

  Future<void> _sync() async {
    setState(() => _syncing = true);
    var uploaded = false;
    try {
      await widget.drafts.sync(widget.api, onUploaded: () => uploaded = true);
      if (uploaded && mounted) widget.onSynced?.call();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) {
        setState(() {
          _entries = widget.drafts.entries();
          _syncing = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Sales order drafts'),
      actions: [
        IconButton(
          tooltip: 'Sync order drafts',
          onPressed: _syncing ? null : _sync,
          icon: const Icon(Icons.sync),
        ),
      ],
    ),
    body: FutureBuilder<List<Json>>(
      future: _entries,
      builder: (context, snapshot) {
        if (_syncing || snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final rows = snapshot.requireData;
        if (rows.isEmpty) {
          return const Center(child: Text('No saved order drafts'));
        }
        return ListView(
          children: [
            for (final row in rows)
              ListTile(
                title: Text('${row['payload']['title']}'),
                subtitle: Text(row['error'] as String? ?? 'Awaiting sync'),
              ),
          ],
        );
      },
    ),
  );
}
