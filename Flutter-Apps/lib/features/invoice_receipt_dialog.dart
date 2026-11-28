import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class InvoiceReceiptDialog extends StatefulWidget {
  const InvoiceReceiptDialog({
    super.key,
    required this.api,
    required this.invoiceId,
    required this.invoice,
    required this.scope,
    required this.headers,
  });

  final ApiClient api;
  final int invoiceId;
  final Json invoice;
  final String scope;
  final Map<String, String> headers;

  @override
  State<InvoiceReceiptDialog> createState() => _InvoiceReceiptDialogState();
}

class _InvoiceReceiptDialogState extends State<InvoiceReceiptDialog> {
  static const _storage = FlutterSecureStorage();
  static final _savingKeys = <String>{};
  final _form = GlobalKey<FormState>();
  final _amount = TextEditingController();
  final _reference = TextEditingController();
  late final _key =
      'invoice_receipt_${Uri.encodeComponent("${widget.scope}:${widget.headers['X-Suite-Branch'] ?? ''}:${widget.invoiceId}")}';
  late final _revision = widget.api.sessionRevision;
  var _method = 'bank_transfer';
  var _receiptDate = DateUtils.dateOnly(DateTime.now());
  var _loading = true;
  var _saving = false;
  var _blocked = false;
  Json? _attempt;
  String? _error;
  num get _balance => num.tryParse('${widget.invoice['balance_amount']}') ?? 0;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    try {
      final raw = await _storage.read(key: _key);
      if (!mounted) return;
      if (raw != null) {
        final saved = jsonDecode(raw) as Json;
        _amount.text = saved['amount'] as String;
        _reference.text = saved['reference'] as String;
        _method = saved['payment_method'] as String;
        _receiptDate = DateTime.parse(saved['receipt_date'] as String);
        _attempt = saved;
      }
    } catch (_) {
      _error = 'Could not read the saved payment attempt.';
      _blocked = true;
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _save() async {
    if (_saving ||
        _blocked ||
        !_form.currentState!.validate() ||
        !_savingKeys.add(_key)) {
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final existing = await _storage.read(key: _key);
      if (existing != null && _attempt == null) {
        throw ApiFailure('Reopen this invoice to load its saved payment.');
      }
      final attempt =
          _attempt ??
          {
            'request_id': const Uuid().v4(),
            'amount': _amount.text.trim(),
            'reference': _reference.text.trim(),
            'payment_method': _method,
            'receipt_date': _receiptDate.toIso8601String().split('T').first,
          };
      await _storage.write(key: _key, value: jsonEncode(attempt));
      if (widget.api.sessionRevision != _revision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      final retry = _attempt != null;
      _attempt = attempt;
      try {
        final result =
            await widget.api.request(
                  'POST',
                  '/srm/business/invoices/${widget.invoiceId}/payments',
                  scopeHeaders: widget.headers,
                  data: attempt,
                )
                as Json;
        await _storage.delete(key: _key);
        if (mounted && widget.api.sessionRevision == _revision) {
          Navigator.of(context).pop(result);
        }
      } on ApiFailure catch (error) {
        if (!retry && error.status == 422) {
          await _storage.delete(key: _key);
          _attempt = null;
        }
        rethrow;
      }
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      _savingKeys.remove(_key);
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _pickDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _receiptDate,
      firstDate: DateTime(1900),
      lastDate: DateUtils.dateOnly(DateTime.now()),
      helpText: 'Receipt date',
    );
    if (mounted && date != null) setState(() => _receiptDate = date);
  }

  @override
  void dispose() {
    _amount.dispose();
    _reference.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final locked = _loading || _saving || _blocked || _attempt != null;
    return PopScope(
      canPop: !_saving,
      child: AlertDialog(
        title: const Text('Record payment received'),
        scrollable: true,
        content: Form(
          key: _form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Outstanding · ${widget.invoice['currency']} ${widget.invoice['balance_amount']}',
              ),
              if (_attempt != null)
                const Text('A saved payment is ready to retry.'),
              if (_error case final String error) Text(error),
              TextFormField(
                controller: _amount,
                enabled: !locked,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(labelText: 'Received amount'),
                validator: (value) {
                  if (_attempt != null) return null;
                  final text = value?.trim() ?? '';
                  final amount = num.tryParse(text);
                  if (!RegExp(r'^\d{1,12}(\.\d{1,2})?$').hasMatch(text) ||
                      amount == null ||
                      amount <= 0 ||
                      amount > _balance) {
                    return 'Enter a positive amount within the outstanding balance.';
                  }
                  return null;
                },
              ),
              DropdownButtonFormField<String>(
                key: ValueKey(_method),
                initialValue: _method,
                decoration: const InputDecoration(labelText: 'Payment method'),
                items: [
                  for (final (value, label) in const [
                    ('bank_transfer', 'Bank transfer'),
                    ('upi', 'UPI'),
                    ('cash', 'Cash'),
                    ('card', 'Card'),
                    ('cheque', 'Cheque'),
                  ])
                    DropdownMenuItem(value: value, child: Text(label)),
                ],
                onChanged: locked
                    ? null
                    : (value) => setState(() => _method = value!),
              ),
              TextFormField(
                controller: _reference,
                enabled: !locked,
                maxLength: 120,
                decoration: const InputDecoration(
                  labelText: 'Payment reference',
                ),
              ),
              TextButton.icon(
                onPressed: locked ? null : _pickDate,
                icon: const Icon(Icons.date_range),
                label: Text(
                  'Receipt date · ${MaterialLocalizations.of(context).formatCompactDate(_receiptDate)}',
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: _saving ? null : () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          FilledButton(
            onPressed:
                _loading ||
                    _saving ||
                    _blocked ||
                    (_attempt == null && _balance <= 0)
                ? null
                : _save,
            child: Text(
              _attempt == null
                  ? 'Record received payment'
                  : 'Retry saved payment',
            ),
          ),
        ],
      ),
    );
  }
}
