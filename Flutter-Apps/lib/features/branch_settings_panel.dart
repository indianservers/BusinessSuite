import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import 'branch_membership_page.dart';

class BranchSettingsPanel extends StatefulWidget {
  const BranchSettingsPanel({
    super.key,
    required this.api,
    required this.editable,
    this.actorId,
  });

  final ApiClient api;
  final bool editable;
  final int? actorId;

  @override
  State<BranchSettingsPanel> createState() => _BranchSettingsPanelState();
}

class _BranchSettingsPanelState extends State<BranchSettingsPanel> {
  late Future<Json> _branches = _load();
  String _tab = 'active';
  Future<Json> _load() async {
    final context =
        await widget.api.request('GET', '/branches/context') as Json;
    if (!widget.editable || context['manage_access'] != true) return context;
    final management =
        await widget.api.request('GET', '/branches/manage') as Json;
    return {...context, 'management': management};
  }

  Future<void> _change({
    Json? branch,
    _BranchAction action = _BranchAction.create,
  }) async {
    final created = await showDialog<String>(
      context: context,
      builder: (_) =>
          _BranchDialog(api: widget.api, branch: branch, action: action),
    );
    if (!mounted) return;
    if (created == null) {
      if (branch != null) _refresh();
      return;
    }
    _tab = switch (action) {
      _BranchAction.trash => 'trash',
      _BranchAction.protect => 'protected',
      _ => 'active',
    };
    _refresh();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(switch (action) {
          _BranchAction.create =>
            '$created created. Assign users in Users & permissions.',
          _BranchAction.rename => 'Branch renamed to $created.',
          _BranchAction.trash => '$created moved to Trash.',
          _BranchAction.protect => '$created moved to protected recovery.',
          _BranchAction.restore => '$created restored.',
        }),
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
          trailing: TextButton(onPressed: _refresh, child: const Text('Retry')),
        );
      }
      final data = snapshot.requireData;
      final management = data['management'] as Json?;
      final branches = ((management ?? data)['branches'] as List? ?? [])
          .whereType<Json>()
          .where(
            (branch) =>
                management == null ||
                branch['state'] == _tab ||
                (_tab == 'trash' && branch['state'] == 'archived'),
          );
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (widget.editable && data['manage_access'] == true)
            FilledButton.icon(
              onPressed: () => _change(),
              icon: const Icon(Icons.add),
              label: const Text('Create branch'),
            ),
          if (management != null) ...[
            ListTile(
              leading: const Icon(Icons.people_outline),
              title: const Text('Assign branch memberships'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => BranchMembershipPage(
                    api: widget.api,
                    actorId: widget.actorId,
                    branches: (data['branches'] as List? ?? [])
                        .whereType<Json>()
                        .where((branch) => branch['is_active'] == true)
                        .toList(),
                  ),
                ),
              ),
            ),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'active', label: Text('Active')),
                ButtonSegment(value: 'trash', label: Text('Trash')),
                ButtonSegment(value: 'protected', label: Text('Recovery')),
              ],
              selected: {_tab},
              onSelectionChanged: (selected) =>
                  setState(() => _tab = selected.single),
            ),
            if (_tab != 'active')
              ListTile(
                title: Text(
                  'Branches are retained for at least ${management['retention_days']} days.',
                ),
              ),
          ],
          if (branches.isEmpty)
            const ListTile(title: Text('No accessible branches')),
          for (final branch in branches)
            ListTile(
              leading: const Icon(Icons.location_on_outlined),
              title: Text('${branch['name']}'),
              subtitle: Text('${branch['code']}'),
              trailing: branch['can_manage'] == true && branch['version'] is int
                  ? PopupMenuButton<_BranchAction>(
                      tooltip: 'Manage ${branch['name']}',
                      onSelected: (action) =>
                          _change(branch: branch, action: action),
                      itemBuilder: (_) => [
                        if (_tab == 'active') ...[
                          const PopupMenuItem(
                            value: _BranchAction.rename,
                            child: Text('Rename branch'),
                          ),
                          PopupMenuItem(
                            value: _BranchAction.trash,
                            enabled: branch['can_trash'] == true,
                            child: const Text('Move to Trash'),
                          ),
                        ] else ...[
                          const PopupMenuItem(
                            value: _BranchAction.restore,
                            child: Text('Restore branch'),
                          ),
                          if (branch['state'] == 'trash')
                            const PopupMenuItem(
                              value: _BranchAction.protect,
                              child: Text('Move to protected recovery'),
                            ),
                        ],
                      ],
                    )
                  : Text(
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

enum _BranchAction {
  create('Create branch'),
  rename('Rename branch'),
  trash('Move to Trash'),
  protect('Move to protected recovery'),
  restore('Restore branch');

  const _BranchAction(this.label);
  final String label;
}

class _BranchDialog extends StatefulWidget {
  const _BranchDialog({
    required this.api,
    required this.branch,
    required this.action,
  });
  final ApiClient api;
  final Json? branch;
  final _BranchAction action;

  @override
  State<_BranchDialog> createState() => _BranchDialogState();
}

class _BranchDialogState extends State<_BranchDialog> {
  final _form = GlobalKey<FormState>();
  late final _values = <String, String>{
    if (widget.action == _BranchAction.rename)
      'name': '${widget.branch!['name']}',
  };
  bool _saving = false;
  bool _stale = false;
  String? _error;

  Future<void> _submit() async {
    if (_saving || !_form.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final branch = widget.branch;
      final action = widget.action;
      final path = branch == null ? '/branches' : '/branches/${branch['id']}';
      await widget.api.request(
        action == _BranchAction.rename ? 'PATCH' : 'POST',
        branch == null || action == _BranchAction.rename
            ? path
            : '$path/${action.name}',
        data: {
          ..._values,
          if (branch != null) 'expected_version': branch['version'],
        },
      );
      if (mounted) {
        Navigator.of(context).pop(_values['name'] ?? branch?['name']);
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = '$error';
          _stale =
              widget.branch != null &&
              error is ApiFailure &&
              error.status == 409;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: AlertDialog(
      title: Text(widget.action.label),
      content: SingleChildScrollView(
        child: Form(
          key: _form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (widget.branch != null)
                Text('${widget.branch!['name']} · ${widget.branch!['code']}'),
              if (widget.action == _BranchAction.trash)
                const Text(
                  'Users lose access until this branch is restored. Its records are retained.',
                ),
              for (final (key, label, maximum) in [
                if (widget.action == _BranchAction.create ||
                    widget.action == _BranchAction.rename)
                  ('name', 'Branch name', 150),
                if (widget.action == _BranchAction.create)
                  ('code', 'Branch code', 20),
                ('reason', 'Reason', 1000),
              ])
                TextFormField(
                  enabled: !_saving,
                  initialValue: _values[key],
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
          child: Text(_stale ? 'Close and refresh' : 'Cancel'),
        ),
        FilledButton(
          onPressed: _saving || _stale ? null : _submit,
          child: Text(_saving ? 'Saving…' : widget.action.label),
        ),
      ],
    ),
  );
}
