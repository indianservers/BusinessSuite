import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import 'sales_order_drafts_page.dart';

class InventoryPriceListForm extends StatefulWidget {
  const InventoryPriceListForm({
    super.key,
    required this.api,
    required this.scopeHeaders,
  });

  static const endpoint = '/srm/pricing/price-lists';
  final ApiClient api;
  final Map<String, String> scopeHeaders;

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
      setState(() => _product = item);
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
      }
    });
  }

  Future<void> _save() async {
    if (_saving || _uncertain || !_form.currentState!.validate()) return;
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

  Widget _field(
    String key,
    String label, {
    int? maxLength,
    String? Function(String)? validate,
  }) => TextFormField(
    initialValue: _values[key],
    enabled: !_saving,
    maxLength: maxLength,
    keyboardType: maxLength == null
        ? const TextInputType.numberWithOptions(decimal: true, signed: true)
        : TextInputType.text,
    decoration: InputDecoration(labelText: label),
    onChanged: (value) => _values[key] = value,
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
    onTap: _saving ? null : () => _pickDate(end),
    trailing: value == null
        ? null
        : IconButton(
            tooltip: 'Clear $label',
            onPressed: _saving
                ? null
                : () => setState(() {
                    if (end) {
                      _to = null;
                    } else {
                      _from = null;
                    }
                  }),
            icon: const Icon(Icons.clear),
          ),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Create price list')),
    body: Form(
      key: _form,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
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
            _field('channel', 'Channel', maxLength: 80, validate: _required),
            _field(
              'customer_type',
              'Customer type',
              maxLength: 80,
              validate: _required,
            ),
            _field('currency', 'Currency', maxLength: 10, validate: _required),
            _dateField('Effective from', _from, false),
            _dateField('Effective to', _to, true),
            _field(
              'priority',
              'Priority',
              validate: (value) =>
                  int.tryParse(value) == null ? 'Enter a whole number.' : null,
            ),
            ListTile(
              title: Text("${_product?['item_name'] ?? 'Choose product'}"),
              subtitle: _product?['sku'] is String
                  ? Text(_product!['sku'] as String)
                  : null,
              onTap: _saving ? null : _pickProduct,
              trailing: const Icon(Icons.chevron_right),
            ),
            _field(
              'min_quantity',
              'Minimum quantity',
              validate: (value) {
                final quantity = num.tryParse(value);
                return quantity == null || !quantity.isFinite || quantity <= 0
                    ? 'Enter a quantity greater than zero.'
                    : null;
              },
            ),
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
              onChanged: _saving
                  ? null
                  : (value) => setState(() => _inclusive = value),
            ),
            if (_error case final error?)
              Text(
                error,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            if (_saving) const LinearProgressIndicator(),
            FilledButton(
              onPressed: _saving || _uncertain ? null : _save,
              child: const Text('Save price list'),
            ),
          ],
        ),
      ),
    ),
  );
}
