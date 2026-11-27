import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class FinancePartyPage extends StatefulWidget {
  const FinancePartyPage({
    super.key,
    required this.api,
    required this.id,
    this.summary,
    this.offline = false,
    this.cacheScope,
    this.scopeHeaders = const {},
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
  final String? cacheScope;
  final Map<String, String> scopeHeaders;

  @override
  State<FinancePartyPage> createState() => _FinancePartyPageState();
}

class _FinancePartyPageState extends State<FinancePartyPage> {
  late var _party = _load();
  Future<({Json? record, bool live})>? _outstanding;

  Future<({Json? record, bool live})> _load({bool reconnect = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: '${FinancePartyPage.endpoint}/${widget.id}',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: widget.offline && !reconnect,
        project: (record) => {
          for (final key in [
            ...FinancePartyPage.summaryFields,
            'gstin',
            'payment_terms_days',
            'credit_limit',
          ])
            if (record.containsKey(key)) key: record[key],
          'contacts': [
            for (final contact
                in (record['contacts'] as List? ?? const []).whereType<Json>())
              {
                for (final key in ['name', 'designation', 'is_primary'])
                  if (contact.containsKey(key)) key: contact[key],
              },
          ],
        },
      );

  void _refresh() => setState(() {
    _party = _load(reconnect: true);
    _outstanding = null;
  });

  void _loadOutstanding({required bool offline}) {
    setState(() {
      _outstanding = loadCrmDetail(
        api: widget.api,
        path: '${FinancePartyPage.endpoint}/${widget.id}/outstanding',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        project: (record) => {
          'openBills': record['openBills'],
          'outstanding': record['outstanding'],
          'items': [
            for (final bill
                in (record['items'] as List? ?? const []).whereType<Json>())
              {
                for (final field in [
                  'bill_number',
                  'due_date',
                  'outstanding_amount',
                ])
                  field: bill[field],
              },
          ],
        },
      );
    });
  }

  Future<({Json? record, bool live})> _loadStatement({required bool offline}) =>
      loadCrmDetail(
        api: widget.api,
        path: '${FinancePartyPage.endpoint}/${widget.id}/statement',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        project: (record) => {
          'party': {'legal_name': (record['party'] as Json?)?['legal_name']},
          'outstanding': record['outstanding'],
          'billReferences': [
            for (final row
                in (record['billReferences'] as List? ?? const [])
                    .whereType<Json>())
              {
                for (final key in [
                  'id',
                  'bill_number',
                  'status',
                  'bill_type',
                  'bill_date',
                  'due_date',
                  'original_amount',
                  'outstanding_amount',
                ])
                  key: row[key],
              },
          ],
          'allocations': [
            for (final row
                in (record['allocations'] as List? ?? const [])
                    .whereType<Json>())
              {
                for (final key in [
                  'from_bill_reference_id',
                  'to_bill_reference_id',
                  'allocation_date',
                  'allocation_type',
                  'allocated_amount',
                ])
                  key: row[key],
              },
          ],
        },
      );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Party details')),
    body: FutureBuilder(
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
        final result = loading ? null : snapshot.data;
        final live = result?.live == true;
        final party = result?.record ?? widget.summary;
        if (party == null) {
          return ListTile(
            title: const Text('Connect to load party details.'),
            trailing: TextButton(
              onPressed: _refresh,
              child: const Text('Reconnect'),
            ),
          );
        }
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
                title: Text(
                  result?.record == null
                      ? 'Saved party summary'
                      : 'Saved party details',
                ),
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
            if (live || (!loading && widget.cacheScope != null)) ...[
              const Divider(),
              OutlinedButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        _PartyStatement(load: _loadStatement, offline: !live),
                  ),
                ),
                child: const Text('View statement'),
              ),
              if (_outstanding == null)
                OutlinedButton(
                  onPressed: () => _loadOutstanding(offline: !live),
                  child: const Text('View outstanding bills'),
                )
              else
                FutureBuilder(
                  future: _outstanding,
                  builder: (context, snapshot) {
                    if (snapshot.connectionState != ConnectionState.done) {
                      return const LinearProgressIndicator();
                    }
                    if (snapshot.hasError) {
                      return ListTile(
                        title: Text('${snapshot.error}'),
                        trailing: TextButton(
                          onPressed: () => _loadOutstanding(offline: false),
                          child: const Text('Retry bills'),
                        ),
                      );
                    }
                    final result = snapshot.requireData;
                    final data = result.record;
                    if (data == null) {
                      return const ListTile(
                        title: Text(
                          'Open outstanding bills online to save them on this device.',
                        ),
                      );
                    }
                    final bills = (data['items'] as List? ?? [])
                        .whereType<Json>();
                    return Column(
                      children: [
                        ListTile(
                          title: Text(
                            result.live
                                ? 'Outstanding'
                                : 'Saved outstanding bills',
                          ),
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
  const _PartyStatement({required this.load, required this.offline});
  final Future<({Json? record, bool live})> Function({required bool offline})
  load;
  final bool offline;

  @override
  State<_PartyStatement> createState() => _PartyStatementState();
}

class _PartyStatementState extends State<_PartyStatement> {
  late var _statement = widget.load(offline: widget.offline);

  void _refresh() {
    setState(() {
      _statement = widget.load(offline: false);
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
    body: FutureBuilder(
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
        final data = snapshot.requireData;
        final statement = data.record;
        if (statement == null) {
          return const Center(
            child: Text(
              'Open this statement online to save it on this device.',
            ),
          );
        }
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
            if (!data.live) const ListTile(title: Text('Saved statement')),
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
