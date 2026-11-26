import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class PowerEnvironmentPage extends StatefulWidget {
  const PowerEnvironmentPage({
    super.key,
    required this.api,
    required this.environment,
  });

  static const endpoint = '/power-apps/environments';
  final ApiClient api;
  final String environment;

  @override
  State<PowerEnvironmentPage> createState() => _PowerEnvironmentPageState();
}

class _PowerEnvironmentPageState extends State<PowerEnvironmentPage> {
  late Future<Json> _overview = _load();

  Future<Json> _load() async {
    final revision = widget.api.sessionRevision;
    final data =
        await widget.api.request(
              'GET',
              '/power-apps/overview',
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
    appBar: AppBar(title: Text('Power Apps · ${widget.environment}')),
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
                ),
          ],
        );
      },
    ),
  );
}
