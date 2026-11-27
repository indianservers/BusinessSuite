import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class CrmDealPage extends StatefulWidget {
  const CrmDealPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
  });

  static const endpoint = '/crm/deal-workspace/query';
  static const summaryFields = [
    'company_name',
    'stage_name',
    'amount',
    'currency',
    'priority',
    'probability',
    'expected_close_date',
  ];
  final ApiClient api;
  final Json summary;
  final bool offline;
  final Map<String, String> scopeHeaders;

  @override
  State<CrmDealPage> createState() => _CrmDealPageState();
}

class _CrmDealPageState extends State<CrmDealPage> {
  late Future<Json?> _deal = widget.offline ? Future.value() : _load();

  Future<Json?> _load() async {
    final revision = widget.api.sessionRevision;
    try {
      final record =
          await widget.api.request(
                'GET',
                '/crm/deal-workspace/${widget.summary['id']}/record',
                scopeHeaders: widget.scopeHeaders,
              )
              as Json;
      if (revision != widget.api.sessionRevision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      return record;
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

  void _refresh() => setState(() {
    _deal = _load();
  });

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Deal details'),
      actions: [
        IconButton(
          tooltip: 'Refresh deal',
          icon: const Icon(Icons.refresh),
          onPressed: _refresh,
        ),
      ],
    ),
    body: FutureBuilder<Json?>(
      future: _deal,
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
        final fields = {
          'Company': data['company_name'] ?? widget.summary['company_name'],
          'Stage': data['stage_name'] ?? widget.summary['stage_name'],
          'Status': data['status'],
          'Amount': data['amount'] == null
              ? null
              : '${data['amount']} ${data['currency'] ?? ''}'.trim(),
          'Probability': data['probability'] == null
              ? null
              : '${data['probability']}%',
          'Priority': data['priority'],
          'Expected close': data['expected_close_date'],
          'Description': data['description'],
        };
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (snapshot.connectionState != ConnectionState.done)
              const LinearProgressIndicator()
            else if (snapshot.data == null)
              const Text('Saved deal summary'),
            Text(
              '${data['name'] ?? 'Deal'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            for (final field in fields.entries)
              if (field.value != null && field.value.toString().isNotEmpty)
                ListTile(
                  title: Text(field.key),
                  subtitle: Text('${field.value}'),
                ),
          ],
        );
      },
    ),
  );
}
