import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class CrmQuotationDraftPage extends StatefulWidget {
  const CrmQuotationDraftPage({
    super.key,
    required this.api,
    this.deal = const {},
    required this.scopeHeaders,
    this.quote,
  });

  final ApiClient api;
  final Json deal;
  final Map<String, String> scopeHeaders;
  final Json? quote;
  static const endpoint = '/crm/quotations';

  @override
  State<CrmQuotationDraftPage> createState() => _CrmQuotationDraftPageState();
}

class _CrmQuotationDraftPageState extends State<CrmQuotationDraftPage> {
  final _form = GlobalKey<FormState>();
  bool get _editing => widget.quote?['id'] is int;
  late final _number = TextEditingController(
    text:
        widget.quote?['quote_number']?.toString() ??
        'QT-${DateTime.now().microsecondsSinceEpoch}',
  );
  late final _issued = TextEditingController(
    text:
        widget.quote?['issue_date']?.toString() ??
        DateTime.now().toIso8601String().split('T').first,
  );
  late final _expires = TextEditingController(
    text: widget.quote?['expiry_date']?.toString(),
  );
  late final _terms = TextEditingController(
    text: (widget.quote?['terms_and_conditions'] ?? widget.quote?['terms'])
        ?.toString(),
  );
  bool _saving = false;
  String? _error;

  DateTime? _date(String? value) {
    final text = value?.trim() ?? '';
    final date = DateTime.tryParse(text);
    return date != null && date.toIso8601String().split('T').first == text
        ? date
        : null;
  }

  Future<void> _save() async {
    if (_saving || _form.currentState?.validate() != true) return;
    final quote = widget.quote;
    final changes = <String, dynamic>{};
    if (_editing && quote != null) {
      if (_issued.text.trim() != quote['issue_date']) {
        changes['issue_date'] = _issued.text.trim();
        changes['quote_date'] = _issued.text.trim();
      }
      if (_expires.text.trim() != quote['expiry_date']) {
        changes['expiry_date'] = _expires.text.trim();
        changes['valid_until'] = _expires.text.trim();
      }
      if (_terms.text.trim() !=
          (quote['terms_and_conditions'] ?? quote['terms'] ?? '')) {
        changes['terms'] = _terms.text.trim();
        changes['terms_and_conditions'] = _terms.text.trim();
      }
      if (changes.isEmpty) {
        Navigator.pop(context);
        return;
      }
    }
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final result =
          await widget.api.request(
                _editing ? 'PATCH' : 'POST',
                _editing
                    ? '${CrmQuotationDraftPage.endpoint}/${quote!['id']}'
                    : CrmQuotationDraftPage.endpoint,
                scopeHeaders: widget.scopeHeaders,
                data: _editing
                    ? changes
                    : {
                        'quote_number': _number.text.trim(),
                        'issue_date': _issued.text.trim(),
                        'expiry_date': _expires.text.trim(),
                        'deal_id': widget.deal['id'],
                        if (widget.deal['company_id'] case final int id)
                          'company_id': id,
                        if (widget.deal['contact_id'] case final int id)
                          'contact_id': id,
                        if (widget.deal['currency'] case final String currency)
                          'currency': currency,
                        if (_terms.text.trim().isNotEmpty)
                          'terms': _terms.text.trim(),
                        'status': 'Draft',
                      },
              )
              as Json;
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, result);
      }
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  void dispose() {
    _number.dispose();
    _issued.dispose();
    _expires.dispose();
    _terms.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(_editing ? 'Edit quotation' : 'New quotation')),
    body: Form(
      key: _form,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (!_editing) Text('${widget.deal['name'] ?? 'CRM deal'}'),
            TextFormField(
              controller: _number,
              readOnly: _editing,
              enabled: !_saving,
              maxLength: 60,
              decoration: const InputDecoration(labelText: 'Quotation number'),
              validator: (value) => (value?.trim().isEmpty ?? true)
                  ? 'Enter a quotation number'
                  : null,
            ),
            TextFormField(
              controller: _issued,
              enabled: !_saving,
              decoration: const InputDecoration(
                labelText: 'Issue date',
                hintText: 'YYYY-MM-DD',
              ),
              validator: (value) =>
                  _date(value) == null ? 'Enter a valid issue date' : null,
            ),
            TextFormField(
              controller: _expires,
              enabled: !_saving,
              decoration: const InputDecoration(
                labelText: 'Expiry date',
                hintText: 'YYYY-MM-DD',
              ),
              validator: (value) {
                final expiry = _date(value);
                final issue = _date(_issued.text);
                if (expiry == null) return 'Enter a valid expiry date';
                return issue != null && expiry.isBefore(issue)
                    ? 'Expiry must be on or after the issue date'
                    : null;
              },
            ),
            TextFormField(
              controller: _terms,
              enabled: !_saving,
              maxLines: 3,
              decoration: const InputDecoration(labelText: 'Terms'),
            ),
            if (_error case final error?) Text(error),
            FilledButton(
              onPressed: _saving ? null : _save,
              child: Text(
                _saving
                    ? 'Saving…'
                    : _editing
                    ? 'Save changes'
                    : 'Create draft quotation',
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
