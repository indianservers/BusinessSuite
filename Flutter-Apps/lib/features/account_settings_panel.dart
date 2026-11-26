import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class AccountSettingsPanel extends StatefulWidget {
  const AccountSettingsPanel({
    super.key,
    required this.api,
    required this.user,
  });
  final ApiClient api;
  final SessionUser? user;

  @override
  State<AccountSettingsPanel> createState() => _AccountSettingsPanelState();
}

class _AccountSettingsPanelState extends State<AccountSettingsPanel> {
  late Future<List<Json>> _sessions = _load();
  bool _busy = false;

  Future<void> _changePassword() async {
    final form = GlobalKey<FormState>();
    String current = '', next = '', confirmation = '';
    String? error;
    var saving = false;
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => PopScope(
          canPop: !saving,
          child: AlertDialog(
            title: const Text('Change password'),
            content: SingleChildScrollView(
              child: Form(
                key: form,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextFormField(
                      obscureText: true,
                      enabled: !saving,
                      decoration: const InputDecoration(
                        labelText: 'Current password',
                      ),
                      onChanged: (value) => current = value,
                      validator: (_) => current.isEmpty
                          ? 'Enter your current password.'
                          : null,
                    ),
                    TextFormField(
                      obscureText: true,
                      enabled: !saving,
                      decoration: const InputDecoration(
                        labelText: 'New password',
                      ),
                      onChanged: (value) => next = value,
                      validator: (_) =>
                          next.length < 8 ? 'Use at least 8 characters.' : null,
                    ),
                    TextFormField(
                      obscureText: true,
                      enabled: !saving,
                      decoration: const InputDecoration(
                        labelText: 'Confirm new password',
                      ),
                      onChanged: (value) => confirmation = value,
                      validator: (_) => confirmation != next
                          ? 'Passwords do not match.'
                          : null,
                    ),
                    if (error != null) Text(error!),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(context),
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
                          await widget.api.request(
                            'POST',
                            '/auth/change-password',
                            data: {
                              'current_password': current,
                              'new_password': next,
                            },
                          );
                          if (context.mounted) Navigator.pop(context, true);
                        } catch (failure) {
                          if (context.mounted) {
                            update(() {
                              saving = false;
                              error = failure.toString();
                            });
                          }
                        }
                      },
                child: Text(saving ? 'Saving…' : 'Change password'),
              ),
            ],
          ),
        ),
      ),
    );
    if (changed == true && mounted) {
      setState(() {
        _sessions = _load();
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Password changed.')));
    }
  }

  Future<List<Json>> _load() async =>
      (await widget.api.request('GET', '/auth/sessions/me') as List)
          .cast<Json>();

  Future<void> _revokeOthers() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign out other sessions?'),
        content: const Text('Your current session will stay signed in.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Sign out others'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted || _busy) return;
    setState(() => _busy = true);
    try {
      await widget.api.request('PUT', '/auth/sessions/me/revoke-others');
      if (mounted) {
        setState(() {
          _sessions = _load();
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Other sessions signed out.')),
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text('Your account', style: Theme.of(context).textTheme.titleLarge),
      ListTile(
        title: Text(widget.user?.email ?? ''),
        subtitle: Text(widget.user?.role ?? 'Assigned access'),
      ),
      const Divider(),
      Text('Password', style: Theme.of(context).textTheme.titleLarge),
      const Text('Your company’s password policy applies.'),
      OutlinedButton(
        onPressed: _busy ? null : _changePassword,
        child: const Text('Change password'),
      ),
      const Divider(),
      Text('Your sessions', style: Theme.of(context).textTheme.titleLarge),
      FutureBuilder<List<Json>>(
        future: _sessions,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const LinearProgressIndicator();
          }
          if (snapshot.hasError) {
            return ListTile(
              title: Text('${snapshot.error}'),
              trailing: TextButton(
                onPressed: () => setState(() {
                  _sessions = _load();
                }),
                child: const Text('Retry'),
              ),
            );
          }
          final active = (snapshot.data ?? [])
              .where((s) => '${s['status']}'.toLowerCase() == 'active')
              .toList();
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (active.isEmpty)
                const ListTile(title: Text('No active sessions')),
              for (final session in active)
                ListTile(
                  leading: const Icon(Icons.devices_outlined),
                  title: Text('${session['device_name'] ?? 'Session'}'),
                  subtitle: Text(
                    '${session['ip_address'] ?? 'IP unavailable'}',
                  ),
                ),
              OutlinedButton(
                onPressed: _busy || active.isEmpty ? null : _revokeOthers,
                child: const Text('Sign out other sessions'),
              ),
            ],
          );
        },
      ),
    ],
  );
}
