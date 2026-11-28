import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import 'sales_order_drafts_page.dart';

class InventoryPriceListForm extends StatefulWidget {
  const InventoryPriceListForm({
    super.key,
    required this.api,
    required this.scopeHeaders,
    this.canCreate = true,
  });

  static const endpoint = '/srm/pricing/price-lists';
  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final bool canCreate;

  @override
  State<InventoryPriceListForm> createState() => _InventoryPriceListFormState();
}

class _InventoryPriceListFormState extends State<InventoryPriceListForm> {
  final _form = GlobalKey<FormState>();
  final _values = <String, String>{
    'channel': 'retail',
    'customer_type': 'cash',
    'currency': 'INR',
    'priority': '100',
    'min_quantity': '1',
    'discount_percent': '0',
    'discount_amount': '0',
  };
  DateTime? _from = DateUtils.dateOnly(DateTime.now());
  DateTime? _to;
  Json? _product;
  bool _inclusive = false;
  bool _saving = false;
  bool _lookingUp = false;
  bool get _busy => _saving || _lookingUp;
  List<Json>? _lookupRows;
  bool _uncertain = false;
  String? _error;
  late final int _revision;

  @override
  void initState() {
    super.initState();
    _revision = widget.api.sessionRevision;
  }

  String _value(String key) => _values[key]?.trim() ?? '';
  String _date(DateTime date) => date.toIso8601String().split('T').first;

  Future<void> _pickProduct() async {
    final item = await showDialog<Json>(
      context: context,
      builder: (_) => SalesRecordPicker(
        api: widget.api,
        scopeHeaders: widget.scopeHeaders,
        offline: false,
        product: true,
        activeOnly: true,
      ),
    );
    if (mounted && item != null && widget.api.sessionRevision == _revision) {
      setState(() {
        _product = item;
        _lookupRows = null;
      });
    }
  }

  Future<void> _pickDate(bool end) async {
    final date = await showDatePicker(
      context: context,
      initialDate: (end ? _to : _from) ?? DateTime.now(),
      firstDate: DateTime(1900),
      lastDate: DateTime(2100),
    );
    if (!mounted || date == null) return;
    setState(() {
      if (end) {
        _to = date;
      } else {
        _from = date;
        _lookupRows = null;
      }
    });
  }

  Future<void> _save() async {
    if (!widget.canCreate ||
        _busy ||
        _uncertain ||
        !_form.currentState!.validate())
      return;
    final product = _product?['id'];
    if (product is! int || (_from != null && _to?.isBefore(_from!) == true)) {
      setState(
        () => _error = product is! int
            ? 'Choose an available product.'
            : 'Effective to must be on or after Effective from.',
      );
      return;
    }
    if (widget.api.sessionRevision != _revision) {
      setState(() => _error = 'Your session changed. Reopen the form.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'POST',
        InventoryPriceListForm.endpoint,
        scopeHeaders: widget.scopeHeaders,
        data: {
          if (_value('price_list_code').isNotEmpty)
            'price_list_code': _value('price_list_code'),
          'price_list_name': _value('price_list_name'),
          'channel': _value('channel'),
          'customer_type': _value('customer_type'),
          'currency': _value('currency').toUpperCase(),
          'priority': int.parse(_value('priority')),
          if (_from case final date?) 'effective_from': _date(date),
          if (_to case final date?) 'effective_to': _date(date),
          'active': true,
          'lines': [
            {
              'product_id': product,
              for (final key in [
                'min_quantity',
                'price',
                'discount_percent',
                'discount_amount',
              ])
                key: _value(key),
              'tax_inclusive': _inclusive,
            },
          ],
        },
      );
      if (mounted && widget.api.sessionRevision == _revision) {
        Navigator.pop(context, true);
      }
    } on ApiFailure catch (error) {
      if (!mounted) return;
      setState(() {
        _uncertain = error.status == null || error.status! >= 500;
        _error = _uncertain
            ? 'Save could not be confirmed. Reopen Price Lists to check before retrying.'
            : error.message;
      });
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _lookup() async {
    if (_busy || widget.api.sessionRevision != _revision) return;
    final product = _product?['id'];
    final quantity = num.tryParse(_value('min_quantity'));
    if (product is! int ||
        quantity == null ||
        !quantity.isFinite ||
        quantity <= 0) {
      setState(
        () => _error = product is! int
            ? 'Choose an available product.'
            : 'Enter a quantity greater than zero.',
      );
      return;
    }
    setState(() {
      _lookingUp = true;
      _error = null;
      _lookupRows = null;
    });
    try {
      final data =
          await widget.api.request(
                'POST',
                '/srm/pricing/lookup',
                scopeHeaders: widget.scopeHeaders,
                data: {
                  'product_ids': [product],
                  'quantity': _value('min_quantity'),
                  for (final key in ['channel', 'customer_type'])
                    if (_value(key).isNotEmpty) key: _value(key),
                  if (_from case final date?) 'price_date': _date(date),
                },
              )
              as Json;
      if (mounted && widget.api.sessionRevision == _revision) {
        setState(
          () => _lookupRows = (data['items'] as List? ?? const [])
              .whereType<Json>()
              .toList(),
        );
      }
    } on ApiFailure catch (error) {
      if (mounted && widget.api.sessionRevision == _revision) {
        setState(() => _error = error.message);
      }
    } finally {
      if (mounted) setState(() => _lookingUp = false);
    }
  }

  Widget _field(
    String key,
    String label, {
    int? maxLength,
    String? Function(String)? validate,
  }) => TextFormField(
    initialValue: _values[key],
    enabled: !_busy,
    maxLength: maxLength,
    keyboardType: maxLength == null
        ? const TextInputType.numberWithOptions(decimal: true, signed: true)
        : TextInputType.text,
    decoration: InputDecoration(labelText: label),
    onChanged: (value) {
      _values[key] = value;
      if (_lookupRows != null &&
          const {'channel', 'customer_type', 'min_quantity'}.contains(key)) {
        setState(() => _lookupRows = null);
      }
    },
    validator: (value) => validate?.call(value?.trim() ?? ''),
  );

  String? _required(String value) => value.isEmpty ? 'Required' : null;

  String? _amount(String value, {num minimum = 0, num? maximum}) {
    final amount = num.tryParse(value);
    if (amount == null ||
        !amount.isFinite ||
        amount < minimum ||
        (maximum != null && amount > maximum)) {
      return maximum == null
          ? 'Enter an amount of at least $minimum.'
          : 'Enter an amount between $minimum and $maximum.';
    }
    return null;
  }

  Widget _dateField(String label, DateTime? value, bool end) => ListTile(
    title: Text(label),
    subtitle: Text(value == null ? 'Choose date' : _date(value)),
    onTap: _busy ? null : () => _pickDate(end),
    trailing: value == null
        ? null
        : IconButton(
            tooltip: 'Clear $label',
            onPressed: _busy
                ? null
                : () => setState(() {
                    if (end) {
                      _to = null;
                    } else {
                      _from = null;
                      _lookupRows = null;
                    }
                  }),
            icon: const Icon(Icons.clear),
          ),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.canCreate ? 'Create price list' : 'Price lookup'),
    ),
    body: Form(
      key: _form,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (widget.canCreate) ...[
              _field(
                'price_list_code',
                'Price list code (optional)',
                maxLength: 80,
              ),
              _field(
                'price_list_name',
                'Price list name',
                maxLength: 180,
                validate: _required,
              ),
            ],
            _field('channel', 'Channel', maxLength: 80, validate: _required),
            _field(
              'customer_type',
              'Customer type',
              maxLength: 80,
              validate: _required,
            ),
            _dateField(
              widget.canCreate ? 'Effective from' : 'Price date',
              _from,
              false,
            ),
            if (widget.canCreate) ...[
              _field(
                'currency',
                'Currency',
                maxLength: 10,
                validate: _required,
              ),
              _dateField('Effective to', _to, true),
              _field(
                'priority',
                'Priority',
                validate: (value) => int.tryParse(value) == null
                    ? 'Enter a whole number.'
                    : null,
              ),
            ],
            ListTile(
              title: Text("${_product?['item_name'] ?? 'Choose product'}"),
              subtitle: _product?['sku'] is String
                  ? Text(_product!['sku'] as String)
                  : null,
              onTap: _busy ? null : _pickProduct,
              trailing: const Icon(Icons.chevron_right),
            ),
            _field(
              'min_quantity',
              widget.canCreate ? 'Minimum quantity' : 'Quantity',
              validate: (value) {
                final quantity = num.tryParse(value);
                return quantity == null || !quantity.isFinite || quantity <= 0
                    ? 'Enter a quantity greater than zero.'
                    : null;
              },
            ),
            if (widget.canCreate) ...[
              _field('price', 'Price', validate: _amount),
              _field(
                'discount_percent',
                'Discount percent',
                validate: (value) => _amount(value, maximum: 100),
              ),
              _field(
                'discount_amount',
                'Discount amount',
                validate: (value) =>
                    _amount(value, maximum: num.tryParse(_value('price'))),
              ),
              SwitchListTile(
                title: const Text('Tax inclusive price'),
                value: _inclusive,
                onChanged: _busy
                    ? null
                    : (value) => setState(() => _inclusive = value),
              ),
            ],
            if (_error case final error?)
              Text(
                error,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            if (_busy) const LinearProgressIndicator(),
            if (widget.canCreate)
              FilledButton(
                onPressed: _busy || _uncertain ? null : _save,
                child: const Text('Save price list'),
              ),
            OutlinedButton(
              onPressed: _busy ? null : _lookup,
              child: const Text('Test lookup'),
            ),
            if (_lookupRows case final rows?) ...[
              if (rows.isEmpty) const Text('No prices found.'),
              for (final row in rows)
                ListTile(
                  title: Text("${row['item_name'] ?? row['sku'] ?? 'Product'}"),
                  subtitle: Text(
                    [
                      if (row['price_list_name'] case final String name) name,
                      "Base price ${row['base_price']} ${row['currency'] ?? ''}",
                      "Net price ${row['net_price']} ${row['currency'] ?? ''}",
                    ].join('\n'),
                  ),
                ),
            ],
          ],
        ),
      ),
    ),
  );
}
