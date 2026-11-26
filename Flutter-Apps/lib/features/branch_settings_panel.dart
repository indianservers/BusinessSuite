import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class BranchSettingsPanel extends StatefulWidget {
  const BranchSettingsPanel({
    super.key,
    required this.api,
    required this.editable,
  });

  final ApiClient api;
  final bool editable;

  @override
  State<BranchSettingsPanel> createState() => _BranchSettingsPanelState();
}

class _BranchSettingsPanelState extends State<BranchSettingsPanel> {
  late Future<Json> _branches = _load();
  Future<Json> _load() async =>
      await widget.api.request('GET', '/branches/context') as Json;

  Future<void> _create() async {
    final created = await showDialog<String>(
      context: context,
      builder: (_) => _CreateBranchDialog(api: widget.api),
    );
    if (!mounted || created == null) return;
    _refresh();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$created created. Assign users in Users & permissions.'),
      ),
    );
  }

  void _refresh() {
    setState(() {
      _branches = _load();
    });
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Json>(
    future: _branches,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const Center(child: CircularProgressIndicator());
      }
      if (snapshot.hasError) {
        return ListTile(
          title: Text('${snapshot.error}'),
          trailing: TextButton(
            onPressed: _refresh,
            child: const Text('Retry'),
          ),
        );
      }
      final data = snapshot.requireData;
      final branches = (data['branches'] as List? ?? []).whereType<Json>();
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (widget.editable && data['manage_access'] == true)
            FilledButton.icon(
              onPressed: _create,
              icon: const Icon(Icons.add),
              label: const Text('Create branch'),
            ),
          if (branches.isEmpty)
            const ListTile(title: Text('No accessible branches')),
          for (final branch in branches)
            ListTile(
              leading: const Icon(Icons.location_on_outlined),
              title: Text('${branch['name']}'),
              subtitle: Text('${branch['code']}'),
              trailing: Text(
                branch['is_active'] != true
                    ? 'Inactive'
                    : branch['can_write'] == true
                    ? 'Can edit'
                    : 'Read-only',
              ),
            ),
        ],
      );
    },
  );
}

class _CreateBranchDialog extends StatefulWidget {
  const _CreateBranchDialog({required this.api});
  final ApiClient api;

  @override
  State<_CreateBranchDialog> createState() => _CreateBranchDialogState();
}

class _CreateBranchDialogState extends State<_CreateBranchDialog> {
  final _form = GlobalKey<FormState>();
  final _values = <String, String>{};
  bool _saving = false;
  String? _error;

  Future<void> _submit() async {
    if (_saving || !_form.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request('POST', '/branches', data: _values);
      if (mounted) Navigator.of(context).pop(_values['name']);
    } catch (error) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = '$error';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: AlertDialog(
      title: const Text('Create a branch'),
      content: SingleChildScrollView(
        child: Form(
          key: _form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final (key, label, maximum) in const [
                ('name', 'Branch name', 150),
                ('code', 'Branch code', 20),
                ('reason', 'Reason for creating branch', 1000),
              ])
                TextFormField(
                  enabled: !_saving,
                  maxLength: maximum,
                  decoration: InputDecoration(labelText: label),
                  onChanged: (value) => _values[key] = value.trim(),
                  validator: (_) {
                    final value = _values[key] ?? '';
                    if (value.isEmpty) return 'Required';
                    if (key == 'code' &&
                        !RegExp(r'^[A-Za-z0-9_-]+$').hasMatch(value)) {
                      return 'Use letters, numbers, underscores or hyphens.';
                    }
                    if (key == 'reason' && value.length < 5) {
                      return 'Enter at least five characters.';
                    }
                    return null;
                  },
                ),
              if (_error != null) SelectableText(_error!),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _saving ? null : _submit,
          child: Text(_saving ? 'Creating…' : 'Create branch'),
        ),
      ],
    ),
  );
}
