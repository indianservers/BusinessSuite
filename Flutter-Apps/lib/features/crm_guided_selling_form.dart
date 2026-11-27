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
  bool _saving = false;
  String? _error;

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    final id = widget.flow['id'];
    final path = CrmGuidedSellingForm.endpoint;
    final revision = widget.api.sessionRevision;
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
          if (id == null) 'questions': [],
          if (id == null) 'recommendations': [],
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

  @override
  Widget build(BuildContext context) {
    final creating = widget.flow['id'] == null;
    final changed =
        creating ||
        _name != widget.flow['name'] ||
        _active != (widget.flow['active'] != false);
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
