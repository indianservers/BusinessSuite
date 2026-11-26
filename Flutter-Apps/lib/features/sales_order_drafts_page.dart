import 'dart:async';

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
    this.rejectedDraft,
  });
  final ApiClient api;
  final SalesOrderDrafts? drafts;
  final bool offline;
  final Json? rejectedDraft;

  @override
  State<NewSalesOrderPage> createState() => _NewSalesOrderPageState();
}

class _NewSalesOrderPageState extends State<NewSalesOrderPage> {
  final _form = GlobalKey<FormState>();
  final _operation = const Uuid().v4();
  late final _previous = widget.rejectedDraft?['payload'] as Json? ?? const {};
  late final _details = <String, String>{
    'currency': 'INR',
    for (final key in [
      'title',
      'currency',
      'terms',
      'expected_start_date',
      'expected_end_date',
    ])
      if (_previous[key] case final String value) key: value,
  };
  late final _lines = <Map<String, String>>[
    for (final line in (_previous['lines'] as List? ?? []).whereType<Json>())
      {
        for (final entry in line.entries)
          if (entry.value != null) entry.key: '${entry.value}',
      },
  ]..removeWhere((line) => line.isEmpty);
  bool _saving = false;
  String? _error;
  late Json? _customer = _previous['customer_id'] is int
      ? {
          'id': _previous['customer_id'],
          'name':
              widget.rejectedDraft?['customer_name'] ??
              'Customer #${_previous['customer_id']}',
        }
      : null;

  @override
  void initState() {
    super.initState();
    if (_lines.isEmpty) _lines.add({'quantity': '1'});
  }

  Future<void> _chooseCustomer() async {
    final customer = await showDialog<Json>(
      context: context,
      builder: (_) => _SalesRecordPicker(
        api: widget.api,
        drafts: widget.drafts,
        offline: widget.offline,
      ),
    );
    if (mounted && customer != null) setState(() => _customer = customer);
  }

  Future<void> _chooseProduct(int index) async {
    final product = await showDialog<Json>(
      context: context,
      builder: (_) => _SalesRecordPicker(
        api: widget.api,
        drafts: widget.drafts,
        offline: widget.offline,
        product: true,
      ),
    );
    if (!mounted || product == null) return;
    final rate = num.tryParse('${product['sales_rate']}');
    setState(
      () => _lines[index] = {
        ..._lines[index],
        'product_id': '${product['id']}',
        'description': product['item_name'] as String,
        'item_code': product['sku'] as String? ?? '',
        'service_type': 'product',
        if (rate != null) 'unit_price': rate.toStringAsFixed(2),
      },
    );
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    final start = _details['expected_start_date'];
    final end = _details['expected_end_date'];
    if (start != null && end != null && start.compareTo(end) > 0) {
      setState(
        () => _error = 'Expected end date must be on or after the start date.',
      );
      return;
    }
    final revision = widget.api.sessionRevision;
    final payload = <String, dynamic>{
      ..._details,
      if (_customer != null) 'customer_id': _customer!['id'],
      'currency': _details['currency']!.toUpperCase(),
      'lines': [
        for (final line in _lines)
          <String, dynamic>{
            for (final entry in line.entries)
              if (entry.value.isNotEmpty) entry.key: entry.value,
            if (line['product_id'] case final String id)
              'product_id': int.parse(id),
          },
      ],
    };
    setState(() {
      _saving = true;
      _error = null;
    });
    final drafts = widget.drafts;
    try {
      if (widget.offline && drafts != null) {
        await drafts.save(
          _operation,
          payload,
          customerName: _customer?['name'] as String?,
          replaceRejected: widget.rejectedDraft?['operation'] as String?,
        );
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
          await drafts.save(
            _operation,
            payload,
            customerName: _customer?['name'] as String?,
          );
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

  Future<void> _chooseDate(String key, String label) async {
    final selected = await showDatePicker(
      context: context,
      helpText: label,
      initialDate: DateTime.tryParse(_details[key] ?? '') ?? DateTime.now(),
      firstDate: DateTime(2000),
      lastDate: DateTime(2100, 12, 31),
    );
    if (selected == null || !mounted) return;
    setState(() {
      _details[key] = selected.toIso8601String().split('T').first;
      _error = null;
    });
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
            number > (key == 'quantity' ? 1000000000 : 99999999999) ||
            (positive && number <= 0)) {
          return 'Enter a valid $label.';
        }
      }
      return null;
    },
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.rejectedDraft == null
            ? 'New sales order'
            : 'Correct order draft',
      ),
    ),
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
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('Order schedule'),
            children: [
              for (final (key, label) in const [
                ('expected_start_date', 'Expected start date'),
                ('expected_end_date', 'Expected end date'),
              ])
                ListTile(
                  title: Text(label),
                  subtitle: Text(_details[key] ?? 'Choose date'),
                  onTap: _saving ? null : () => _chooseDate(key, label),
                  trailing: !_details.containsKey(key)
                      ? null
                      : IconButton(
                          tooltip: 'Clear $label',
                          onPressed: _saving
                              ? null
                              : () => setState(() {
                                  _details.remove(key);
                                  _error = null;
                                }),
                          icon: const Icon(Icons.close),
                        ),
                ),
            ],
          ),
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
                TextButton(
                  onPressed: _saving ? null : () => _chooseProduct(index),
                  child: Text(
                    line['product_id'] == null
                        ? 'Choose product'
                        : 'Change product',
                  ),
                ),
                _field(
                  line,
                  'quantity',
                  'Quantity',
                  decimals: 2,
                  positive: true,
                ),
                _field(line, 'unit_price', 'Unit price', decimals: 2),
                _field(
                  line,
                  'discount_amount',
                  'Discount amount',
                  decimals: 2,
                  required: false,
                ),
                _field(
                  line,
                  'tax_amount',
                  'Tax amount',
                  decimals: 2,
                  required: false,
                ),
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

class _SalesRecordPicker extends StatefulWidget {
  const _SalesRecordPicker({
    required this.api,
    this.drafts,
    required this.offline,
    this.product = false,
  });
  final ApiClient api;
  final SalesOrderDrafts? drafts;
  final bool offline;
  final bool product;

  @override
  State<_SalesRecordPicker> createState() => _SalesRecordPickerState();
}

class _SalesRecordPickerState extends State<_SalesRecordPicker> {
  late Future<List<Json>> _customers = _load('');
  String _search = '';

  Future<List<Json>> _load(String search) async {
    final drafts = widget.drafts;
    if (drafts != null) {
      if (widget.product) {
        return drafts.products(widget.api, search, offline: widget.offline);
      }
      return drafts.customers(widget.api, search, offline: widget.offline);
    }
    final revision = widget.api.sessionRevision;
    final data =
        await widget.api.request(
              'GET',
              widget.product
                  ? SalesOrderDrafts.productsEndpoint
                  : SalesOrderDrafts.customersEndpoint,
              query: widget.product
                  ? {
                      'summary_only': true,
                      'page': 1,
                      'per_page': 50,
                      if (search.isNotEmpty) 'search': search,
                    }
                  : {if (search.isNotEmpty) 'q': search},
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
    title: Text(widget.product ? 'Choose product' : 'Choose customer'),
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
              labelText: widget.product
                  ? 'Product name, SKU or barcode'
                  : 'Customer name',
              counterText: '',
              suffixIcon: IconButton(
                tooltip: widget.product
                    ? 'Search products'
                    : 'Search customers',
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
                      'No matching ${widget.offline ? 'saved ' : ''}${widget.product ? 'products' : 'customers'}',
                    ),
                  );
                }
                return ListView(
                  children: [
                    for (final row in rows)
                      if (row['id'] is int &&
                          row[widget.product ? 'item_name' : 'name'] is String)
                        ListTile(
                          title: Text(
                            row[widget.product ? 'item_name' : 'name']
                                as String,
                          ),
                          subtitle: widget.product && row['sku'] is String
                              ? Text(row['sku'] as String)
                              : null,
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
  late final StreamSubscription<String> _changes;

  @override
  void initState() {
    super.initState();
    _changes = widget.drafts.changes.listen((_) {
      if (mounted && !_syncing) {
        setState(() {
          _entries = widget.drafts.entries();
        });
      }
    });
  }

  @override
  void dispose() {
    _changes.cancel();
    super.dispose();
  }

  Future<void> _correct(Json draft) async {
    await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => NewSalesOrderPage(
          api: widget.api,
          drafts: widget.drafts,
          offline: true,
          rejectedDraft: draft,
        ),
      ),
    );
  }

  Future<void> _discard(String operation) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Discard saved order draft?'),
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
    if (ok != true || !mounted) return;
    try {
      await widget.drafts.discard(operation);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    }
  }

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
                subtitle: Text(
                  [
                    row['customer_name'],
                    row['error'] ?? 'Awaiting sync',
                  ].whereType<String>().join(' · '),
                ),
                onTap: row['status'] == 422 ? () => _correct(row) : null,
                trailing: IconButton(
                  tooltip: 'Discard order draft',
                  icon: const Icon(Icons.delete_outline),
                  onPressed: () => _discard(row['operation'] as String),
                ),
              ),
          ],
        );
      },
    ),
  );
}
