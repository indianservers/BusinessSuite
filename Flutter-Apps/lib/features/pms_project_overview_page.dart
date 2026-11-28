import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';

class PmsProjectOverviewPage extends StatefulWidget {
  const PmsProjectOverviewPage({
    super.key,
    required this.api,
    required this.projectId,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
  });

  final ApiClient api;
  final int projectId;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;

  @override
  State<PmsProjectOverviewPage> createState() => _PmsProjectOverviewPageState();
}

class _PmsProjectOverviewPageState extends State<PmsProjectOverviewPage> {
  static const _fields = {
    'project_key': 'Project key',
    'status': 'Status',
    'priority': 'Priority',
    'health': 'Health',
    'planned_start_date': 'Planned start',
    'planned_end_date': 'Planned end',
    'description': 'Description',
  };
  late var _project = _load(offline: widget.offline);

  Future<({Map<String, dynamic>? record, bool live})> _load({
    bool offline = false,
  }) => loadCrmDetail(
    api: widget.api,
    path: '/project-management/projects/${widget.projectId}',
    scope: widget.cacheScope,
    headers: widget.scopeHeaders,
    offline: offline,
    project: (record) => {
      for (final field in ['name', 'progress_percent', ..._fields.keys])
        field: record[field],
    },
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Delivery project'),
      actions: [
        IconButton(
          tooltip: 'Refresh project',
          onPressed: () => setState(() => _project = _load()),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder(
      future: _project,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final project = snapshot.data?.record;
        if (project == null) {
          return const Center(
            child: Text('No project overview saved on this device'),
          );
        }
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${project['name'] ?? 'Project'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (snapshot.data?.live != true)
              const ListTile(title: Text('Saved project overview')),
            if (project['progress_percent'] case final num progress)
              ListTile(
                title: const Text('Progress'),
                subtitle: Text('$progress%'),
              ),
            for (final field in _fields.entries)
              if (project[field.key] case final String value
                  when value.trim().isNotEmpty)
                ListTile(title: Text(field.value), subtitle: Text(value)),
          ],
        );
      },
    ),
  );
}
