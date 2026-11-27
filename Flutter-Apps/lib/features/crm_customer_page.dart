import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class CrmCustomerPage extends StatefulWidget {
  const CrmCustomerPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
    this.cacheScope,
  });

  static const endpoint = '/master-data/company-directory/query';
  static const fields = {
    'entityKind': 'Customer type',
    'email': 'Email',
    'phone': 'Phone',
    'industry': 'Industry',
    'website': 'Website',
    'city': 'City',
    'state': 'State',
    'country': 'Country',
    'status': 'Status',
  };
  final ApiClient api;
  final Json summary;
  final bool offline;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;

  @override
  State<CrmCustomerPage> createState() => _CrmCustomerPageState();
}

class _CrmCustomerPageState extends State<CrmCustomerPage> {
  late Future<({Json? record, bool live})> _profile = _load(
    offline: widget.offline,
  );

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: '/master-data/companies/${widget.summary['id']}',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        project: (record) => {
          for (final field in ['name', ...CrmCustomerPage.fields.keys])
            field: record[field],
          'contacts': [
            for (final contact
                in (record['contacts'] as List? ?? const [])
                    .whereType<Json>()
                    .take(30))
              {'name': contact['name']},
          ],
        },
      );

  void _refresh() => setState(() {
    _profile = _load();
  });

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Customer details'),
      actions: [
        IconButton(
          tooltip: 'Refresh customer',
          icon: const Icon(Icons.refresh),
          onPressed: _refresh,
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _profile,
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
        final data = snapshot.data?.record ?? widget.summary;
        final contacts = (data['contacts'] as List? ?? const [])
            .whereType<Json>();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (snapshot.connectionState != ConnectionState.done)
              const LinearProgressIndicator()
            else if (snapshot.data?.live != true)
              const Text('Saved customer details'),
            Text(
              '${data['name'] ?? 'Customer'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            for (final field in CrmCustomerPage.fields.entries)
              if (data[field.key] case final String value when value.isNotEmpty)
                ListTile(title: Text(field.value), subtitle: Text(value)),
            if (contacts.isNotEmpty)
              Text('Contacts', style: Theme.of(context).textTheme.titleLarge),
            for (final contact in contacts)
              if (contact['name'] case final String name)
                ListTile(title: Text(name)),
          ],
        );
      },
    ),
  );
}
