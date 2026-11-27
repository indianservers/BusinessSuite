import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class CrmTaskPage extends StatefulWidget {
  const CrmTaskPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
    this.cacheScope,
  });

  static const endpoint = '/project-management/tasks';
  static const fields = {
    'status': 'Status',
    'priority': 'Priority',
    'due_date': 'Due date',
    'assignee_name': 'Assignee',
    'description': 'Description',
  };
  final ApiClient api;
  final Json summary;
  final bool offline;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;

  @override
  State<CrmTaskPage> createState() => _CrmTaskPageState();
}

class _CrmTaskPageState extends State<CrmTaskPage> {
  late Future<({Json? record, bool live})> _task = _load(
    offline: widget.offline,
  );

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: '${CrmTaskPage.endpoint}/${widget.summary['id']}',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        project: (record) => {
          for (final field in ['title', ...CrmTaskPage.fields.keys])
            field: record[field],
        },
      );

  void _refresh() => setState(() {
    _task = _load();
  });

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Task details'),
      actions: [
        IconButton(
          tooltip: 'Refresh task',
          icon: const Icon(Icons.refresh),
          onPressed: _refresh,
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _task,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: TextButton(
              onPressed: _refresh,
              child: Text('${snapshot.error}\nRetry'),
            ),
          );
        }
        final data = snapshot.data?.record ?? widget.summary;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (snapshot.connectionState != ConnectionState.done)
              const LinearProgressIndicator()
            else if (snapshot.data?.live != true)
              const Text('Saved task details'),
            Text(
              '${data['title'] ?? 'Task'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            for (final field in CrmTaskPage.fields.entries)
              if ((data[field.key] ?? widget.summary[field.key])
                  case final String value when value.isNotEmpty)
                ListTile(title: Text(field.value), subtitle: Text(value)),
          ],
        );
      },
    ),
  );
}
