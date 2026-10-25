import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../app_controller.dart';
import '../core/models.dart';

class PeoplePage extends StatefulWidget {
  const PeoplePage({
    super.key,
    required this.controller,
    required this.workspace,
  });
  final AppController controller;
  final Workspace workspace;
  @override
  State<PeoplePage> createState() => _PeoplePageState();
}

class _PeoplePageState extends State<PeoplePage> {
  List<Json> _members = [], _invitations = [];
  String? _error;
  String _role = 'Guest';
  bool _loading = true, _busy = false;
  bool get _manages => const {'Owner', 'Admin'}.contains(_role);
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _members = [];
      _invitations = [];
      _role = 'Guest';
    });
    try {
      final repo = widget.controller.repository;
      final overview = await repo.overview(widget.workspace.id);
      final members = await repo.members(widget.workspace.id);
      final invitations = const {'Owner', 'Admin'}.contains(overview.role)
          ? await repo.invitations(widget.workspace.id)
          : <Json>[];
      if (mounted) {
        setState(() {
          _role = overview.role;
          _members = members;
          _invitations = invitations;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _action(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
      await _load();
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _invite() async {
    var email = '', role = 'Member', saving = false;
    String? error, token;
    final form = GlobalKey<FormState>();
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialog) => StatefulBuilder(
        builder: (context, update) => PopScope(
          canPop: !saving,
          child: AlertDialog(
            title: Text(token == null ? 'Invite user' : 'Invitation created'),
            content: SingleChildScrollView(
              child: Form(
                key: form,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: token != null
                      ? [
                          const Text(
                            'Share this single-use token privately with the invited user. They can sign in and choose Join workspace.',
                          ),
                          const SizedBox(height: 12),
                          SelectableText(token!),
                          TextButton.icon(
                            onPressed: () async {
                              await Clipboard.setData(
                                ClipboardData(text: token!),
                              );
                              if (context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Invitation token copied'),
                                  ),
                                );
                              }
                            },
                            icon: const Icon(Icons.copy),
                            label: const Text('Copy token'),
                          ),
                        ]
                      : [
                          TextFormField(
                            decoration: const InputDecoration(
                              labelText: 'User email',
                            ),
                            enabled: !saving,
                            keyboardType: TextInputType.emailAddress,
                            onChanged: (v) => email = v.trim(),
                            validator: (v) =>
                                v == null ||
                                    !RegExp(
                                      r'^[^\s@]+@[^\s@]+\.[^\s@]+$',
                                    ).hasMatch(v.trim())
                                ? 'Enter a valid email'
                                : null,
                          ),
                          const SizedBox(height: 16),
                          DropdownButtonFormField<String>(
                            initialValue: role,
                            decoration: const InputDecoration(
                              labelText: 'Workspace role',
                            ),
                            items:
                                [
                                      'Member',
                                      'Guest',
                                      if (_role == 'Owner') 'Admin',
                                    ]
                                    .map(
                                      (r) => DropdownMenuItem(
                                        value: r,
                                        child: Text(r),
                                      ),
                                    )
                                    .toList(),
                            onChanged: saving ? null : (r) => role = r!,
                          ),
                          if (error != null)
                            Padding(
                              padding: const EdgeInsets.only(top: 12),
                              child: Text(
                                error!,
                                style: TextStyle(
                                  color: Theme.of(context).colorScheme.error,
                                ),
                              ),
                            ),
                        ],
                ),
              ),
            ),
            actions: token != null
                ? [
                    TextButton(
                      onPressed: () => Navigator.pop(dialog),
                      child: const Text('Done'),
                    ),
                  ]
                : [
                    TextButton(
                      onPressed: saving ? null : () => Navigator.pop(dialog),
                      child: const Text('Cancel'),
                    ),
                    FilledButton(
                      onPressed: saving
                          ? null
                          : () async {
                              if (!form.currentState!.validate()) return;
                              update(() {
                                saving = true;
                                error = null;
                              });
                              try {
                                final result = await widget
                                    .controller
                                    .repository
                                    .invite(widget.workspace.id, email, role);
                                if (dialog.mounted) {
                                  update(() {
                                    token = result['token'] as String;
                                    saving = false;
                                  });
                                }
                              } catch (e) {
                                if (dialog.mounted) {
                                  update(() {
                                    saving = false;
                                    error = '$e';
                                  });
                                }
                              }
                            },
                      child: Text(saving ? 'Inviting…' : 'Create invitation'),
                    ),
                  ],
          ),
        ),
      ),
    );
    await _load();
  }

  Future<void> _memberAction(Json member, String action) async {
    if (action == 'Remove') {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialog) => AlertDialog(
          title: const Text('Remove workspace member?'),
          content: Text(
            '${member['email']} will lose access to this workspace.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialog, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialog, true),
              child: const Text('Remove'),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
      await _action(
        () => widget.controller.repository.removeMember(
          widget.workspace.id,
          member['id'] as int,
        ),
      );
    } else {
      await _action(
        () => widget.controller.repository.changeMemberRole(
          widget.workspace.id,
          member['id'] as int,
          action,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Workspace people'),
      actions: [
        IconButton(
          tooltip: 'Refresh people',
          onPressed: _loading || _busy ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: Column(
      children: [
        if (_loading || _busy) const LinearProgressIndicator(),
        if (_error != null)
          MaterialBanner(
            content: Text(_error!),
            actions: [TextButton(onPressed: _load, child: const Text('Retry'))],
          ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Text(
                widget.workspace.name,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              if (_manages)
                FilledButton.icon(
                  onPressed: _loading || _busy ? null : _invite,
                  icon: const Icon(Icons.person_add_outlined),
                  label: const Text('Invite user'),
                ),
              const SizedBox(height: 20),
              const Text('Members'),
              ..._members.map(
                (m) => ListTile(
                  title: Text(m['email'] as String),
                  subtitle: Text(m['role'] as String),
                  trailing:
                      _manages &&
                          m['role'] != 'Owner' &&
                          (_role == 'Owner' || m['role'] != 'Admin')
                      ? PopupMenuButton<String>(
                          tooltip: 'Manage ${m['email']}',
                          enabled: !_busy && !_loading,
                          onSelected: (value) => _memberAction(m, value),
                          itemBuilder: (_) => [
                            for (final role in [
                              'Member',
                              'Guest',
                              if (_role == 'Owner') 'Admin',
                            ])
                              PopupMenuItem(
                                value: role,
                                child: Text('Set $role'),
                              ),
                            const PopupMenuItem(
                              value: 'Remove',
                              child: Text('Remove member'),
                            ),
                          ],
                        )
                      : null,
                ),
              ),
              if (_manages) ...[
                const SizedBox(height: 20),
                const Text('Invitations'),
                ..._invitations.map(
                  (i) => ListTile(
                    title: Text(i['email'] as String),
                    subtitle: Text('${i['role']} · ${i['status']}'),
                    trailing: i['status'] == 'pending'
                        ? IconButton(
                            tooltip: 'Revoke invitation for ${i['email']}',
                            onPressed: _busy || _loading
                                ? null
                                : () => _action(
                                    () => widget.controller.repository
                                        .revokeInvitation(
                                          widget.workspace.id,
                                          i['id'] as int,
                                        ),
                                  ),
                            icon: const Icon(Icons.cancel_outlined),
                          )
                        : null,
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    ),
  );
}
