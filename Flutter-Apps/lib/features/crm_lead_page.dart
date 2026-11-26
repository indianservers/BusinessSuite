import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class CrmLeadPage extends StatefulWidget {
  const CrmLeadPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    this.onSaved,
  });
  static const endpoint = '/crm/lead-management/leads';
  final ApiClient api;
  final Json summary;
  final bool offline;
  final VoidCallback? onSaved;

  @override
  State<CrmLeadPage> createState() => _CrmLeadPageState();
}

class _CrmLeadPageState extends State<CrmLeadPage> {
  late Future<Json> _lead = _load();
  String get _path => '${CrmLeadPage.endpoint}/${widget.summary['id']}';

  Future<Json> _load() async {
    if (widget.offline) return widget.summary;
    return await widget.api.request('GET', _path) as Json;
  }

  Future<void> _edit(Json lead, int version) async {
    var first = lead['first_name'] as String? ?? '';
    var last = lead['last_name'] as String? ?? '';
    String? error;
    var saving = false;
    var conflict = false;
    final result = await showDialog<Json>(
      context: context,
      barrierDismissible: false,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => PopScope(
          canPop: !saving,
          child: AlertDialog(
            title: const Text('Edit lead name'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    initialValue: first,
                    enabled: !saving,
                    maxLength: 100,
                    decoration: const InputDecoration(labelText: 'First name'),
                    onChanged: (text) => first = text,
                  ),
                  TextFormField(
                    initialValue: last,
                    enabled: !saving,
                    maxLength: 100,
                    decoration: const InputDecoration(labelText: 'Last name'),
                    onChanged: (text) => last = text,
                  ),
                  if (error != null) SelectableText(error!),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(context),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: saving || conflict
                    ? null
                    : () async {
                        if (first.trim().isEmpty) {
                          update(() => error = 'Enter a first name.');
                          return;
                        }
                        update(() {
                          saving = true;
                          error = null;
                        });
                        try {
                          final updated =
                              await widget.api.request(
                                    'PATCH',
                                    _path,
                                    data: {
                                      'values': {
                                        'first_name': first.trim(),
                                        'last_name': last.trim(),
                                      },
                                      'version': version,
                                    },
                                  )
                                  as Json;
                          if (context.mounted) Navigator.pop(context, updated);
                        } catch (failure) {
                          if (!context.mounted) return;
                          update(() {
                            saving = false;
                            conflict =
                                failure is ApiFailure && failure.status == 409;
                            error = conflict
                                ? 'The server rejected this version. Copy your draft, close, and refresh before editing again.'
                                : failure.toString();
                          });
                        }
                      },
                child: Text(saving ? 'Saving…' : 'Save'),
              ),
            ],
          ),
        ),
      ),
    );
    if (result != null && mounted) {
      setState(() {
        _lead = Future.value(result);
      });
      widget.onSaved?.call();
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Lead details'),
      actions: [
        if (!widget.offline)
          IconButton(
            tooltip: 'Refresh lead',
            onPressed: () => setState(() {
              _lead = _load();
            }),
            icon: const Icon(Icons.refresh),
          ),
      ],
    ),
    body: FutureBuilder<Json>(
      future: _lead,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final lead = snapshot.data;
        if (lead == null) {
          return const Center(child: CircularProgressIndicator());
        }
        final name = [
          lead['first_name'],
          lead['last_name'],
        ].whereType<String>().join(' ').trim();
        final version = lead['version'];
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              name.isNotEmpty ? name : '${lead['full_name'] ?? 'Lead'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (widget.offline)
              const ListTile(title: Text('Offline · Saved lead summary')),
            for (final field in const {
              'company_name': 'Company',
              'email': 'Email',
              'phone': 'Phone',
              'status': 'Status',
              'source': 'Source',
              'rating': 'Rating',
            }.entries)
              if (lead[field.key] != null && lead[field.key] != '')
                ListTile(
                  title: Text(field.value),
                  subtitle: SelectableText('${lead[field.key]}'),
                ),
            if (!widget.offline && version is int)
              OutlinedButton(
                onPressed: () => _edit(lead, version),
                child: const Text('Edit lead name'),
              ),
          ],
        );
      },
    ),
  );
}
