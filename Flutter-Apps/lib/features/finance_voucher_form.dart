import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class FinanceVoucherForm extends StatefulWidget {
  const FinanceVoucherForm({
    super.key,
    required this.api,
    required this.headers,
  });

  final ApiClient api;
  final Map<String, String> headers;

  @override
  State<FinanceVoucherForm> createState() => _FinanceVoucherFormState();
}

class _Entry {
  _Entry({this.credit = false});

  int? ledger;
  bool credit;
  String amount = '';
}

class _FinanceVoucherFormState extends State<FinanceVoucherForm> {
  final _form = GlobalKey<FormState>();
  final _lines = [_Entry(), _Entry(credit: true)];
  late final _revision = widget.api.sessionRevision;
  late var _options = _load();
  DateTime _date = DateUtils.dateOnly(DateTime.now());
  int? _type;
  String _reference = '';
  String _narration = '';
  String? _error;
  bool _saving = false;
  bool _unconfirmed = false;

  Future<({List<Json> types, List<Json> ledgers})> _load() async {
    Future<List<Json>> get(String path) async {
      final result =
          await widget.api.request('GET', path, scopeHeaders: widget.headers)
              as Json;
      return (result['items'] as List)
          .cast<Json>()
          .where((row) => row['active'] == true)
          .toList();
    }

    final lists = await Future.wait([
      get('/fam/voucher-types'),
      get('/fam/ledgers'),
    ]);
    if (widget.api.sessionRevision != _revision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    return (types: lists[0], ledgers: lists[1]);
  }

  Future<void> _chooseDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(1900),
      lastDate: DateTime(2100, 12, 31),
    );
    if (mounted && date != null) setState(() => _date = date);
  }

  Future<void> _save() async {
    if (_saving ||
        _unconfirmed ||
        widget.api.sessionRevision != _revision ||
        !_form.currentState!.validate()) {
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final result = await widget.api.request(
        'POST',
        '/fam/vouchers',
        scopeHeaders: widget.headers,
        data: {
          'voucher_type_id': _type,
          'voucher_date': _date.toIso8601String().split('T').first,
          if (_reference.isNotEmpty) 'reference_number': _reference,
          if (_narration.isNotEmpty) 'narration': _narration,
          'lines': [
            for (final line in _lines)
              {
                'ledger_id': line.ledger,
                'debit_amount': line.credit ? '0' : line.amount,
                'credit_amount': line.credit ? line.amount : '0',
              },
          ],
        },
      );
      if (!mounted || widget.api.sessionRevision != _revision) return;
      if (result is! Json || result['id'] is! int) {
        throw ApiFailure('Voucher confirmation is unavailable.', 503);
      }
      Navigator.pop(context, result);
    } on ApiFailure catch (error) {
      if (!mounted || widget.api.sessionRevision != _revision) return;
      setState(() {
        _unconfirmed = error.connectionFailure || (error.status ?? 0) >= 500;
        _error = _unconfirmed
            ? 'Save could not be confirmed. Refresh the register before creating another voucher.'
            : error.message;
      });
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  DropdownButtonFormField<int> _picker({
    required String label,
    required String nameKey,
    required List<Json> options,
    required int? selected,
    required ValueChanged<int?> onChanged,
  }) => DropdownButtonFormField<int>(
    initialValue: selected,
    isExpanded: true,
    decoration: InputDecoration(labelText: label),
    items: [
      for (final option in options)
        DropdownMenuItem(
          value: option['id'] as int,
          child: Text('${option[nameKey]}', overflow: TextOverflow.ellipsis),
        ),
    ],
    onChanged: _saving ? null : onChanged,
    validator: (value) => value == null ? 'Choose a $label.' : null,
  );

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: Scaffold(
      appBar: AppBar(title: const Text('New voucher')),
      body: FutureBuilder(
        future: _options,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return ListTile(
              title: Text('${snapshot.error}'),
              trailing: TextButton(
                onPressed: () => setState(() {
                  _options = _load();
                }),
                child: const Text('Retry'),
              ),
            );
          }
          final options = snapshot.requireData;
          return Form(
            key: _form,
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _picker(
                    label: 'Voucher type',
                    nameKey: 'voucher_type_name',
                    options: options.types,
                    selected: _type,
                    onChanged: (id) => _type = id,
                  ),
                  OutlinedButton(
                    onPressed: _saving ? null : _chooseDate,
                    child: Text(
                      'Voucher date · ${_date.toIso8601String().split('T').first}',
                    ),
                  ),
                  TextFormField(
                    enabled: !_saving,
                    decoration: const InputDecoration(
                      labelText: 'Reference number',
                    ),
                    onChanged: (value) => _reference = value.trim(),
                  ),
                  TextFormField(
                    enabled: !_saving,
                    decoration: const InputDecoration(labelText: 'Narration'),
                    onChanged: (value) => _narration = value.trim(),
                  ),
                  for (final (index, line) in _lines.indexed)
                    Card(
                      key: ObjectKey(line),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          children: [
                            _picker(
                              label: 'Ledger ${index + 1}',
                              nameKey: 'ledger_name',
                              options: options.ledgers,
                              selected: line.ledger,
                              onChanged: (id) => line.ledger = id,
                            ),
                            SwitchListTile(
                              title: Text(line.credit ? 'Credit' : 'Debit'),
                              value: line.credit,
                              onChanged: _saving
                                  ? null
                                  : (value) =>
                                        setState(() => line.credit = value),
                            ),
                            TextFormField(
                              initialValue: line.amount,
                              enabled: !_saving,
                              keyboardType:
                                  const TextInputType.numberWithOptions(
                                    decimal: true,
                                  ),
                              decoration: InputDecoration(
                                labelText: 'Amount ${index + 1}',
                              ),
                              onChanged: (value) => line.amount = value.trim(),
                              validator: (_) =>
                                  RegExp(
                                    r'^\d{1,12}(?:\.\d{1,2})?$',
                                  ).hasMatch(line.amount)
                                  ? null
                                  : 'Enter an amount with up to two decimal places.',
                            ),
                            if (_lines.length > 1)
                              TextButton(
                                onPressed: _saving
                                    ? null
                                    : () => setState(() => _lines.remove(line)),
                                child: const Text('Remove line'),
                              ),
                          ],
                        ),
                      ),
                    ),
                  OutlinedButton(
                    onPressed: _saving
                        ? null
                        : () => setState(() => _lines.add(_Entry())),
                    child: const Text('Add entry line'),
                  ),
                  if (_error != null) Text(_error!),
                  FilledButton(
                    onPressed: _saving || _unconfirmed ? null : _save,
                    child: Text(_saving ? 'Saving…' : 'Save voucher draft'),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    ),
  );
}
