import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class FinancePartyPage extends StatefulWidget {
  const FinancePartyPage({super.key, required this.api, required this.id});
  static const endpoint = '/fam/parties';
  final ApiClient api;
  final int id;

  @override
  State<FinancePartyPage> createState() => _FinancePartyPageState();
}

class _FinancePartyPageState extends State<FinancePartyPage> {
  late Future<Json> _party = _read();
  Future<Json>? _outstanding;

  Future<Json> _read([String suffix = '']) async =>
      await widget.api.request(
            'GET',
            '${FinancePartyPage.endpoint}/${widget.id}$suffix',
          )
          as Json;

  void _loadOutstanding() {
    setState(() {
      _outstanding = _read('/outstanding');
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Party details')),
    body: FutureBuilder<Json>(
      future: _party,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return ListTile(
            title: Text('${snapshot.error}'),
            trailing: TextButton(
              onPressed: () => setState(() {
                _party = _read();
              }),
              child: const Text('Retry'),
            ),
          );
        }
        final party = snapshot.requireData;
        final contacts = (party['contacts'] as List? ?? []).whereType<Json>();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${party['legal_name']}',
              style: Theme.of(context).textTheme.headlineSmall,
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
            const Divider(),
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
        );
      },
    ),
  );
}
