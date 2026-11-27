import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class FinanceVoucherForm extends StatefulWidget {
  const FinanceVoucherForm({
    super.key,
    required this.api,
    required this.headers,
    this.draft,
  });

  final ApiClient api;
  final Map<String, String> headers;
  final Json? draft;

  @override
  State<FinanceVoucherForm> createState() => _FinanceVoucherFormState();
}

class _Entry {
  _Entry({this.credit = false}) : original = const {};

  _Entry.fromJson(this.original) {
    ledger = original['ledger_id'] as int?;
    final creditAmount = '${original['credit_amount'] ?? 0}';
    credit = (num.tryParse(creditAmount) ?? 0) > 0;
    amount = credit ? creditAmount : '${original['debit_amount'] ?? 0}';
    costCenter = original['cost_center_id']?.toString() ?? '';
    narration = original['narration'] as String? ?? '';
  }

  final Json original;
  int? ledger;
  late bool credit;
  String amount = '';
  String costCenter = '';
  String narration = '';
}

class _FinanceVoucherFormState extends State<FinanceVoucherForm> {
  static final _amountPattern = RegExp(r'^\d{1,12}(?:\.\d{1,2})?$');
  final _form = GlobalKey<FormState>();
  late final _lines = widget.draft == null
      ? [_Entry(), _Entry(credit: true)]
      : (widget.draft!['lines'] as List)
            .cast<Json>()
            .map(_Entry.fromJson)
            .toList();
  late final _revision = widget.api.sessionRevision;
  late var _options = _load();
  late DateTime _date =
      DateTime.tryParse('${widget.draft?['voucher_date']}') ??
      DateUtils.dateOnly(DateTime.now());
  late int? _type = widget.draft?['voucher_type_id'] as int?;
  late String _reference = widget.draft?['reference_number'] as String? ?? '';
  late String _narration = widget.draft?['narration'] as String? ?? '';
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
      final draft = widget.draft;
      final date = _date.toIso8601String().split('T').first;
      final result = await widget.api.request(
        draft == null ? 'POST' : 'PUT',
        draft == null ? '/fam/vouchers' : '/fam/vouchers/${draft['id']}',
        scopeHeaders: widget.headers,
        data: {
          'voucher_type_id': _type,
          'voucher_date': date,
          if (draft != null) ...{
            'branch_id': draft['branch_id'],
            'reference_date': draft['reference_date'],
            if (date == draft['voucher_date']) ...{
              'financial_year_id': draft['financial_year_id'],
              'accounting_period_id': draft['accounting_period_id'],
            },
          },
          if (_reference.isNotEmpty) 'reference_number': _reference,
          if (_narration.isNotEmpty) 'narration': _narration,
          'lines': [
            for (final line in _lines)
              {
                'ledger_id': line.ledger,
                'debit_amount': line.credit ? '0' : line.amount,
                'credit_amount': line.credit ? line.amount : '0',
                for (final key in ['branch_id', 'party_id', 'tax_component_id'])
                  if (line.original[key] != null) key: line.original[key],
                if (line.costCenter.isNotEmpty)
                  'cost_center_id': int.parse(line.costCenter),
                if (line.narration.isNotEmpty) 'narration': line.narration,
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
    initialValue: options.any((option) => option['id'] == selected)
        ? selected
        : null,
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

  int _totalCents(bool credit) =>
      _lines.where((line) => line.credit == credit).fold(0, (total, line) {
        if (!_amountPattern.hasMatch(line.amount)) return total;
        final parts = line.amount.split('.');
        final cents = parts.length == 2 ? parts.last : '';
        return total +
            int.parse(parts.first) * 100 +
            int.parse(cents.padRight(2, '0'));
      });

  String _formatCents(int cents) =>
      '${cents.isNegative ? '-' : ''}${cents.abs() ~/ 100}.${(cents.abs() % 100).toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: Scaffold(
      appBar: AppBar(
        title: Text(
          widget.draft == null ? 'New voucher' : 'Edit voucher draft',
        ),
      ),
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
                    initialValue: _reference,
                    enabled: !_saving,
                    decoration: const InputDecoration(
                      labelText: 'Reference number',
                    ),
                    onChanged: (value) => _reference = value.trim(),
                  ),
                  TextFormField(
                    initialValue: _narration,
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
                              onChanged: (value) =>
                                  setState(() => line.amount = value.trim()),
                              validator: (_) =>
                                  _amountPattern.hasMatch(line.amount)
                                  ? null
                                  : 'Enter an amount with up to two decimal places.',
                            ),
                            TextFormField(
                              enabled: !_saving,
                              initialValue: line.costCenter,
                              keyboardType: TextInputType.number,
                              decoration: InputDecoration(
                                labelText: 'Cost center ${index + 1}',
                              ),
                              onChanged: (value) =>
                                  line.costCenter = value.trim(),
                              validator: (_) {
                                if (line.costCenter.isEmpty) return null;
                                final id = int.tryParse(line.costCenter);
                                return id != null && id > 0 && id <= 2147483647
                                    ? null
                                    : 'Enter a valid cost center ID.';
                              },
                            ),
                            TextFormField(
                              enabled: !_saving,
                              initialValue: line.narration,
                              decoration: InputDecoration(
                                labelText: 'Line narration ${index + 1}',
                              ),
                              onChanged: (value) =>
                                  line.narration = value.trim(),
                            ),
                            if (_lines.length > 2)
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
                  ListTile(
                    title: Text(
                      'Debit ${_formatCents(_totalCents(false))} · '
                      'Credit ${_formatCents(_totalCents(true))}',
                    ),
                    subtitle: Text(
                      'Difference ${_formatCents(_totalCents(false) - _totalCents(true))}',
                    ),
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
