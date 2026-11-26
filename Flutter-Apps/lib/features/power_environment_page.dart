import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class PowerEnvironmentPage extends StatefulWidget {
  const PowerEnvironmentPage({
    super.key,
    required this.api,
    required this.environment,
  }) : _automationId = null;

  const PowerEnvironmentPage._automation({
    required this.api,
    required this.environment,
    required int id,
  }) : _automationId = id;

  static const endpoint = '/power-apps/environments';
  final ApiClient api;
  final String environment;
  final int? _automationId;

  @override
  State<PowerEnvironmentPage> createState() => _PowerEnvironmentPageState();
}

class _PowerEnvironmentPageState extends State<PowerEnvironmentPage> {
  late Future<Json> _overview = _load();

  Future<Json> _load() async {
    final revision = widget.api.sessionRevision;
    final automation = widget._automationId;
    final data =
        await widget.api.request(
              'GET',
              automation == null
                  ? '/power-apps/overview'
                  : '/power-apps/automations/$automation',
              query: {'environment': widget.environment},
            )
            as Json;
    if (revision != widget.api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    return data;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget._automationId == null
            ? 'Power Apps · ${widget.environment}'
            : 'Automation details',
      ),
    ),
    body: FutureBuilder<Json>(
      future: _overview,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return ListTile(
            title: Text('${snapshot.error}'),
            trailing: TextButton(
              onPressed: () => setState(() {
                _overview = _load();
              }),
              child: const Text('Retry'),
            ),
          );
        }
        final data = snapshot.requireData;
        if (widget._automationId != null) return _AutomationDetails(data: data);
        final counts = data['counts'] as Json? ?? const {};
        final recent = (data['recent'] as List? ?? [])
            .whereType<Json>()
            .toList();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            for (final metric in const {
              'total_apps': 'Apps',
              'active_automations': 'Active automations',
              'pending_approvals': 'Pending approvals',
              'form_submissions': 'Form submissions',
              'workflow_executions': 'Workflow executions',
              'failed_runs': 'Failed runs',
            }.entries)
              if (counts[metric.key] case final num value)
                ListTile(title: Text(metric.value), trailing: Text('$value')),
            const Divider(),
            Text(
              'Recent resources',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (recent.isEmpty)
              const ListTile(title: Text('No recent resources')),
            for (final resource in recent)
              if (resource['name'] case final String name)
                ListTile(
                  title: Text(name),
                  subtitle: Text(
                    [
                      resource['application_id'],
                      resource['status'],
                    ].whereType<String>().join(' · '),
                  ),
                  onTap:
                      resource['application_id'] == 'automations' &&
                          resource['id'] is int
                      ? () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => PowerEnvironmentPage._automation(
                              api: widget.api,
                              environment: widget.environment,
                              id: resource['id'] as int,
                            ),
                          ),
                        )
                      : null,
                ),
          ],
        );
      },
    ),
  );
}

class _AutomationDetails extends StatelessWidget {
  const _AutomationDetails({required this.data});
  final Json data;

  @override
  Widget build(BuildContext context) {
    final definition = data['definition'] as Json? ?? const {};
    final trigger = definition['trigger'] as Json?;
    final nodes = (definition['nodes'] as List? ?? []).whereType<Json>();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          '${data['name'] ?? 'Automation'}',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        if (data['description'] case final String description
            when description.isNotEmpty)
          Text(description),
        for (final (label, value) in [
          ('Status', data['status']),
          ('Version', data['version']),
          ('Trigger', trigger?['type']),
        ])
          if (value != null)
            ListTile(title: Text(label), subtitle: Text('$value')),
        const Divider(),
        Text('Workflow steps', style: Theme.of(context).textTheme.titleMedium),
        if (nodes.isEmpty) const ListTile(title: Text('No workflow steps')),
        for (final node in nodes)
          ListTile(
            title: Text('${node['label'] ?? node['id'] ?? 'Step'}'),
            subtitle: Text(
              [node['type'], node['component']].whereType<String>().join(' · '),
            ),
          ),
      ],
    );
  }
}
