import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class BranchMembershipPage extends StatefulWidget {
  const BranchMembershipPage({
    super.key,
    required this.api,
    required this.branches,
    required this.actorId,
  });
  final ApiClient api;
  final List<Json> branches;
  final int? actorId;

  @override
  State<BranchMembershipPage> createState() => _BranchMembershipPageState();
}

class _BranchMembershipPageState extends State<BranchMembershipPage> {
  late Future<List<Json>> _members = _load();
  Future<List<Json>> _load() async =>
      ((await widget.api.request('GET', '/branches/access/users')) as List)
          .whereType<Json>()
          .where(
            (member) =>
                member['id'] is int &&
                member['id'] != widget.actorId &&
                member['is_superuser'] != true,
          )
          .toList();

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Branch memberships')),
    body: FutureBuilder<List<Json>>(
      future: _members,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return ListTile(
            title: Text('${snapshot.error}'),
            trailing: TextButton(
              onPressed: () => setState(() {
                _members = _load();
              }),
              child: const Text('Retry'),
            ),
          );
        }
        final members = snapshot.data;
        if (members == null) {
          return const Center(child: CircularProgressIndicator());
        }
        if (members.isEmpty) {
          return const Center(child: Text('No eligible company members'));
        }
        return ListView.builder(
          itemCount: members.length,
          itemBuilder: (context, index) {
            final member = members[index];
            return ListTile(
              title: Text('${member['email']}'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => _MemberPolicy(
                    api: widget.api,
                    member: member,
                    branches: widget.branches,
                  ),
                ),
              ),
            );
          },
        );
      },
    ),
  );
}

class _MemberPolicy extends StatefulWidget {
  const _MemberPolicy({
    required this.api,
    required this.member,
    required this.branches,
  });
  final ApiClient api;
  final Json member;
  final List<Json> branches;

  @override
  State<_MemberPolicy> createState() => _MemberPolicyState();
}

class _MemberPolicyState extends State<_MemberPolicy> {
  Json? _policy;
  final _reason = TextEditingController();
  bool _busy = true;
  bool _stale = false;
  String? _message;
  String get _path => '/branches/access/${widget.member['id']}';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final policy = await widget.api.request('GET', _path) as Json;
      if (!mounted) return;
      setState(() {
        _policy = policy;
        _stale = false;
        _reason.clear();
      });
    } catch (error) {
      if (mounted) setState(() => _message = '$error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save(Json policy) async {
    final reason = _reason.text.trim();
    if (_busy || _stale || reason.length < 5) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final saved =
          await widget.api.request(
                'PUT',
                _path,
                data: {
                  for (final key in const [
                    'all_branches',
                    'manage_access',
                    'use_home_branch',
                    'grants',
                  ])
                    key: policy[key],
                  'expected_version': policy['version'],
                  'reason': reason,
                },
              )
              as Json;
      if (!mounted) return;
      setState(() {
        _policy = saved;
        _reason.clear();
        _message = 'Branch memberships saved.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _message = '$error';
        _stale = error is ApiFailure && error.status == 409;
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final policy = _policy;
    final grants = (policy?['grants'] as List? ?? []).cast<Json>();
    final enabled = !_busy && !_stale;
    return Scaffold(
      appBar: AppBar(title: Text('${widget.member['email']}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_busy) const LinearProgressIndicator(),
          if (_message != null) ListTile(title: Text(_message!)),
          if (!_busy && (_stale || policy == null))
            OutlinedButton(
              onPressed: _load,
              child: Text(_stale ? 'Reload server policy' : 'Retry'),
            ),
          if (policy != null) ...[
            SwitchListTile(
              title: const Text("Allow employee's home branch"),
              value: policy['use_home_branch'] == true,
              onChanged: enabled
                  ? (value) => setState(() => policy['use_home_branch'] = value)
                  : null,
            ),
            for (final branch in widget.branches)
              _branchRow(branch, grants, policy, enabled),
            TextField(
              controller: _reason,
              enabled: enabled,
              maxLength: 1000,
              decoration: const InputDecoration(
                labelText: 'Reason for membership change',
              ),
              onChanged: (_) => setState(() {}),
            ),
            FilledButton(
              onPressed: enabled && _reason.text.trim().length >= 5
                  ? () => _save(policy)
                  : null,
              child: const Text('Save branch memberships'),
            ),
          ],
        ],
      ),
    );
  }

  Widget _branchRow(Json branch, List<Json> grants, Json policy, bool enabled) {
    final id = branch['id'];
    final grant = grants.where((row) => row['branch_id'] == id).firstOrNull;
    final hasModuleRoles = grant?['module_grants'] != null;
    return Column(
      children: [
        CheckboxListTile(
          title: Text('${branch['name']}'),
          subtitle: hasModuleRoles
              ? const Text('Module roles are assigned')
              : null,
          value: grant != null,
          onChanged: enabled && !hasModuleRoles
              ? (selected) => setState(() {
                  policy['grants'] = [
                    ...grants.where((row) => row['branch_id'] != id),
                    if (selected == true) {'branch_id': id, 'can_write': false},
                  ];
                })
              : null,
        ),
        if (grant != null)
          SwitchListTile(
            title: const Text('Allow permitted writes'),
            value: grant['can_write'] == true,
            onChanged: enabled && branch['can_write'] == true
                ? (value) => setState(() => grant['can_write'] = value)
                : null,
          ),
      ],
    );
  }
}
