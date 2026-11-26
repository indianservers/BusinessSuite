import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import 'crm_lead_page.dart';

class CrmNewLeadPage extends StatefulWidget {
  const CrmNewLeadPage({super.key, required this.api});

  final ApiClient api;

  @override
  State<CrmNewLeadPage> createState() => _CrmNewLeadPageState();
}

class _CrmNewLeadPageState extends State<CrmNewLeadPage> {
  final _form = GlobalKey<FormState>();
  final _values = <String, String>{};
  final _operation = const Uuid().v4();
  bool _saving = false;
  String? _error;

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'POST',
        CrmLeadPage.endpoint,
        scopeHeaders: {'X-Offline-Operation': _operation},
        data: {
          'values': {
            for (final entry in _values.entries)
              if (entry.value.isNotEmpty) entry.key: entry.value,
          },
        },
      );
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } on ApiFailure catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('New lead')),
    body: Form(
      key: _form,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final (key, label, limit, keyboard) in const [
            ('full_name', 'Full name', 220, TextInputType.name),
            ('company_name', 'Company', 180, TextInputType.text),
            ('email', 'Email', 150, TextInputType.emailAddress),
            ('phone', 'Phone', 40, TextInputType.phone),
          ])
            TextFormField(
              enabled: !_saving,
              decoration: InputDecoration(labelText: label),
              maxLength: limit,
              keyboardType: keyboard,
              onChanged: (value) => _values[key] = value.trim(),
              validator: key == 'full_name'
                  ? (value) => (value ?? '').trim().isEmpty
                        ? 'Enter the lead name.'
                        : null
                  : null,
            ),
          if (_error != null) Text(_error!),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(_saving ? 'Saving…' : 'Create lead'),
          ),
        ],
      ),
    ),
  );
}
