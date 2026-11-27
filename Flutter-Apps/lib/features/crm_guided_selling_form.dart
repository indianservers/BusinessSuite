import 'dart:convert';

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class CrmGuidedSellingForm extends StatefulWidget {
  const CrmGuidedSellingForm({
    super.key,
    required this.api,
    required this.scopeHeaders,
    this.flow = const {},
  });

  static const endpoint = '/crm/guided-selling-flows';
  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final Json flow;

  @override
  State<CrmGuidedSellingForm> createState() => _CrmGuidedSellingFormState();
}

class _CrmGuidedSellingFormState extends State<CrmGuidedSellingForm> {
  final _form = GlobalKey<FormState>();
  late String _name = '${widget.flow['name'] ?? ''}';
  late bool _active = widget.flow['active'] != false;
  static const _configurationFields = {
    'questions': 'question_json',
    'recommendations': 'recommendation_json',
  };
  late final _originalConfiguration = {
    for (final field in _configurationFields.entries)
      field.key: const JsonEncoder.withIndent(
        '  ',
      ).convert(widget.flow[field.key] ?? widget.flow[field.value] ?? const []),
  };
  late final _configuration = Map<String, String>.of(_originalConfiguration);
  bool _saving = false;
  String? _error;

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    final id = widget.flow['id'];
    final path = CrmGuidedSellingForm.endpoint;
    final revision = widget.api.sessionRevision;
    final configurationChanges = <String, Object?>{};
    for (final field in _configuration.keys) {
      final candidate = _configuration[field]!;
      if (id == null || candidate != _originalConfiguration[field]) {
        configurationChanges[field] = jsonDecode(candidate);
      }
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        id == null ? 'POST' : 'PATCH',
        id == null ? path : '$path/$id',
        scopeHeaders: widget.scopeHeaders,
        data: {
          if (id == null || _name != widget.flow['name']) 'name': _name,
          if (id == null || _active != (widget.flow['active'] != false))
            'active': _active,
          ...configurationChanges,
        },
      );
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } on ApiFailure catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _error = error.message);
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _configurationEditor(String field, String label) => TextFormField(
    initialValue: _configuration[field],
    enabled: !_saving,
    decoration: InputDecoration(labelText: label, alignLabelWithHint: true),
    minLines: 3,
    maxLines: 8,
    autocorrect: false,
    enableSuggestions: false,
    style: const TextStyle(fontFamily: 'monospace'),
    onChanged: (value) => setState(() => _configuration[field] = value),
    validator: (value) {
      if (value == _originalConfiguration[field]) return null;
      try {
        final decoded = jsonDecode(value ?? '');
        return decoded is List || decoded is Map
            ? null
            : 'Enter a JSON array or object.';
      } on FormatException {
        return 'Enter valid JSON.';
      }
    },
  );

  @override
  Widget build(BuildContext context) {
    final creating = widget.flow['id'] == null;
    final changed =
        creating ||
        _name != widget.flow['name'] ||
        _active != (widget.flow['active'] != false) ||
        _configuration.keys.any(
          (field) => _configuration[field] != _originalConfiguration[field],
        );
    return Scaffold(
      appBar: AppBar(
        title: Text(
          creating ? 'New guided selling flow' : 'Edit guided selling flow',
        ),
      ),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextFormField(
              initialValue: _name,
              enabled: !_saving,
              decoration: const InputDecoration(labelText: 'Name'),
              maxLength: 180,
              validator: (value) =>
                  value?.trim().isNotEmpty == true ? null : 'Enter a name.',
              onChanged: (value) => setState(() => _name = value.trim()),
            ),
            SwitchListTile(
              title: const Text('Active'),
              value: _active,
              onChanged: _saving
                  ? null
                  : (value) => setState(() => _active = value),
            ),
            ExpansionTile(
              title: const Text('Questions and recommendations'),
              maintainState: true,
              childrenPadding: const EdgeInsets.only(bottom: 16),
              children: [
                _configurationEditor('questions', 'Questions JSON'),
                const SizedBox(height: 12),
                _configurationEditor('recommendations', 'Recommendations JSON'),
              ],
            ),
            if (_error case final String error)
              Text(
                error,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            FilledButton(
              onPressed: _saving || !changed ? null : _save,
              child: Text(creating ? 'Create flow' : 'Save changes'),
            ),
          ],
        ),
      ),
    );
  }
}
