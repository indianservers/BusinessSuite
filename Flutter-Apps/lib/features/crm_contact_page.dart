import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class CrmContactPage extends StatefulWidget {
  const CrmContactPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
  });

  static const endpoint = '/crm/contacts';
  static const summaryFields = {
    'company_name': 'Company',
    'job_title': 'Job title',
    'email': 'Email',
    'phone': 'Phone',
    'lifecycle_stage': 'Lifecycle stage',
    'status': 'Status',
    'next_follow_up_at': 'Next follow-up',
  };
  final ApiClient api;
  final Json summary;
  final bool offline;
  final Map<String, String> scopeHeaders;

  @override
  State<CrmContactPage> createState() => _CrmContactPageState();
}

class _CrmContactPageState extends State<CrmContactPage> {
  late Future<Json?> _record = widget.offline ? Future<Json?>.value() : _load();

  Future<Json?> _load() async {
    final revision = widget.api.sessionRevision;
    try {
      final data = await widget.api.request(
        'GET',
        '${CrmContactPage.endpoint}/${widget.summary['id']}',
        scopeHeaders: widget.scopeHeaders,
      );
      if (revision != widget.api.sessionRevision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      return data as Json;
    } on ApiFailure catch (error) {
      if (revision == widget.api.sessionRevision &&
          (error.connectionFailure ||
              error.status == 429 ||
              (error.status ?? 0) >= 500)) {
        return null;
      }
      rethrow;
    }
  }

  void _refresh() => setState(() => _record = _load());

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Contact details'),
      actions: [
        IconButton(
          tooltip: 'Refresh contact',
          icon: const Icon(Icons.refresh),
          onPressed: _refresh,
        ),
      ],
    ),
    body: FutureBuilder<Json?>(
      future: _record,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${snapshot.error}'),
                TextButton(onPressed: _refresh, child: const Text('Retry')),
              ],
            ),
          );
        }
        final data = snapshot.data ?? widget.summary;
        final history = (data['timeline'] as List? ?? const [])
            .whereType<Json>();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (snapshot.connectionState != ConnectionState.done)
              const LinearProgressIndicator()
            else if (snapshot.data == null)
              const Text('Saved contact summary'),
            Text(
              '${data['full_name'] ?? 'Contact'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            for (final field in CrmContactPage.summaryFields.entries)
              if (data[field.key] case final String value when value.isNotEmpty)
                ListTile(title: Text(field.value), subtitle: Text(value)),
            if (history.isNotEmpty)
              Text('Activity', style: Theme.of(context).textTheme.titleLarge),
            for (final event in history)
              ListTile(
                title: Text('${event['title'] ?? 'Activity'}'),
                subtitle: Text('${event['occurredAt'] ?? ''}'),
              ),
          ],
        );
      },
    ),
  );
}
