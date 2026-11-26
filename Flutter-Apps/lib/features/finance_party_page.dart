import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class FinancePartyPage extends StatefulWidget {
  const FinancePartyPage({
    super.key,
    required this.api,
    required this.id,
    this.summary,
    this.offline = false,
  });
  static const endpoint = '/fam/parties';
  static const summaryFields = [
    'legal_name',
    'trade_name',
    'party_code',
    'party_type',
  ];
  final ApiClient api;
  final int id;
  final Json? summary;
  final bool offline;

  @override
  State<FinancePartyPage> createState() => _FinancePartyPageState();
}

class _FinancePartyPageState extends State<FinancePartyPage> {
  late Future<Json?> _party = _load();
  Future<Json>? _outstanding;

  Future<Json> _read([String suffix = '']) async =>
      await widget.api.request(
            'GET',
            '${FinancePartyPage.endpoint}/${widget.id}$suffix',
          )
          as Json;

  Future<Json?> _load({bool reconnect = false}) async {
    if (widget.offline && !reconnect) return null;
    try {
      return await _read();
    } on ApiFailure catch (error) {
      if (widget.summary != null &&
          (error.connectionFailure ||
              error.status == 429 ||
              (error.status ?? 0) >= 500)) {
        return null;
      }
      rethrow;
    }
  }

  void _refresh() => setState(() {
    _party = _load(reconnect: true);
  });

  void _loadOutstanding() {
    setState(() {
      _outstanding = _read('/outstanding');
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Party details')),
    body: FutureBuilder<Json?>(
      future: _party,
      builder: (context, snapshot) {
        final loading = snapshot.connectionState != ConnectionState.done;
        if (loading && widget.summary == null) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return ListTile(
            title: Text('${snapshot.error}'),
            trailing: TextButton(
              onPressed: _refresh,
              child: const Text('Retry'),
            ),
          );
        }
        final live = !loading && snapshot.data != null;
        final party = (live ? snapshot.data : widget.summary) ?? const {};
        final contacts = (party['contacts'] as List? ?? []).whereType<Json>();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${party['legal_name']}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (loading) const LinearProgressIndicator(),
            if (!loading && !live)
              ListTile(
                title: const Text('Saved party summary'),
                trailing: TextButton(
                  onPressed: _refresh,
                  child: const Text('Reconnect'),
                ),
              ),
            for (final field in const {
              'party_code': 'Party code',
              'party_type': 'Party type',
              'trade_name': 'Trade name',
              'gstin': 'GSTIN',
              'email': 'Email',
              'phone': 'Phone',
              'payment_terms_days': 'Payment terms (days)',
              'credit_limit': 'Credit limit',
            }.entries)
              if (party[field.key] != null && party[field.key] != '')
                ListTile(
                  title: Text(field.value),
                  subtitle: SelectableText('${party[field.key]}'),
                ),
            if (contacts.isNotEmpty) ...[
              const Divider(),
              Text('Contacts', style: Theme.of(context).textTheme.titleMedium),
              for (final contact in contacts)
                ListTile(
                  title: Text('${contact['name']}'),
                  subtitle: Text(
                    [contact['designation'], contact['email'], contact['phone']]
                        .whereType<String>()
                        .where((value) => value.isNotEmpty)
                        .join(' · '),
                  ),
                  trailing: contact['is_primary'] == true
                      ? const Text('Primary')
                      : null,
                ),
            ],
            if (live) ...[
              const Divider(),
              OutlinedButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        _PartyStatement(load: () => _read('/statement')),
                  ),
                ),
                child: const Text('View statement'),
              ),
              if (_outstanding == null)
                OutlinedButton(
                  onPressed: _loadOutstanding,
                  child: const Text('View outstanding bills'),
                )
              else
                FutureBuilder<Json>(
                  future: _outstanding,
                  builder: (context, snapshot) {
                    if (snapshot.connectionState != ConnectionState.done) {
                      return const LinearProgressIndicator();
                    }
                    if (snapshot.hasError) {
                      return ListTile(
                        title: Text('${snapshot.error}'),
                        trailing: TextButton(
                          onPressed: _loadOutstanding,
                          child: const Text('Retry bills'),
                        ),
                      );
                    }
                    final data = snapshot.requireData;
                    final bills = (data['items'] as List? ?? [])
                        .whereType<Json>();
                    return Column(
                      children: [
                        ListTile(
                          title: const Text('Outstanding'),
                          subtitle: Text('${data['openBills']} open bills'),
                          trailing: Text('${data['outstanding']}'),
                        ),
                        for (final bill in bills)
                          ListTile(
                            title: Text('${bill['bill_number']}'),
                            subtitle: Text('Due ${bill['due_date']}'),
                            trailing: Text('${bill['outstanding_amount']}'),
                          ),
                      ],
                    );
                  },
                ),
            ],
          ],
        );
      },
    ),
  );
}

class _PartyStatement extends StatefulWidget {
  const _PartyStatement({required this.load});
  final Future<Json> Function() load;

  @override
  State<_PartyStatement> createState() => _PartyStatementState();
}

class _PartyStatementState extends State<_PartyStatement> {
  late Future<Json> _statement = widget.load();

  void _refresh() {
    setState(() {
      _statement = widget.load();
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Party statement'),
      actions: [
        IconButton(
          tooltip: 'Refresh statement',
          onPressed: _refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder<Json>(
      future: _statement,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return ListTile(
            title: Text('${snapshot.error}'),
            trailing: TextButton(
              onPressed: _refresh,
              child: const Text('Retry'),
            ),
          );
        }
        final statement = snapshot.requireData;
        final bills = (statement['billReferences'] as List? ?? [])
            .whereType<Json>()
            .toList();
        final allocations = (statement['allocations'] as List? ?? [])
            .whereType<Json>();
        final billNumbers = {
          for (final bill in bills) bill['id']: bill['bill_number'],
        };
        String reference(Object? id) => '${billNumbers[id] ?? 'Bill #$id'}';
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            ListTile(
              title: Text(
                '${(statement['party'] as Json?)?['legal_name'] ?? 'Party'}',
              ),
              subtitle: Text('Outstanding · ${statement['outstanding']}'),
            ),
            Text(
              'Bill references',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (bills.isEmpty)
              const ListTile(title: Text('No bill references')),
            for (final bill in bills)
              ListTile(
                title: Text('${bill['bill_number']} · ${bill['status']}'),
                subtitle: Text(
                  '${bill['bill_type']} · ${bill['bill_date']} · Due ${bill['due_date']}',
                ),
                trailing: Text(
                  'Original ${bill['original_amount']}\nOpen ${bill['outstanding_amount']}',
                  textAlign: TextAlign.end,
                ),
              ),
            const Divider(),
            Text('Allocations', style: Theme.of(context).textTheme.titleMedium),
            if (allocations.isEmpty)
              const ListTile(title: Text('No allocations')),
            for (final allocation in allocations)
              ListTile(
                title: Text(
                  '${reference(allocation['from_bill_reference_id'])} → ${reference(allocation['to_bill_reference_id'])}',
                ),
                subtitle: Text(
                  '${allocation['allocation_date']} · ${allocation['allocation_type']}',
                ),
                trailing: Text('${allocation['allocated_amount']}'),
              ),
          ],
        );
      },
    ),
  );
}
