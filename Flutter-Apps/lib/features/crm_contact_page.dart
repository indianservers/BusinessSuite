import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class CrmContactPage extends StatefulWidget {
  const CrmContactPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
    this.cacheScope,
    this.canEdit = false,
    this.onSaved,
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
  final String? cacheScope;
  final Map<String, String> scopeHeaders;
  final bool canEdit;
  final VoidCallback? onSaved;

  @override
  State<CrmContactPage> createState() => _CrmContactPageState();
}

class _CrmContactPageState extends State<CrmContactPage> {
  late Future<({Json? record, bool live})> _record = _load(
    offline: widget.offline,
  );

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: '${CrmContactPage.endpoint}/${widget.summary['id']}',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        project: (record) => {
          for (final field in [
            'full_name',
            ...CrmContactPage.summaryFields.keys,
          ])
            field: record[field],
          'timeline': [
            for (final event
                in (record['timeline'] as List? ?? const [])
                    .whereType<Json>()
                    .take(30))
              {'title': event['title'], 'occurredAt': event['occurredAt']},
          ],
        },
      );

  void _refresh() => setState(() {
    _record = _load();
  });

  Future<void> _edit(Json contact) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => CrmContactForm(
          api: widget.api,
          contact: contact,
          scopeHeaders: widget.scopeHeaders,
        ),
      ),
    );
    if (mounted && changed == true) {
      widget.onSaved?.call();
      _refresh();
    }
  }

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
    body: FutureBuilder<({Json? record, bool live})>(
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
        final data = snapshot.data?.record ?? widget.summary;
        final history = (data['timeline'] as List? ?? const [])
            .whereType<Json>();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (snapshot.connectionState != ConnectionState.done)
              const LinearProgressIndicator()
            else if (snapshot.data?.live != true)
              Text(
                snapshot.data?.record == null
                    ? 'Saved contact summary'
                    : 'Saved contact details',
              ),
            Text(
              '${data['full_name'] ?? 'Contact'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (widget.canEdit &&
                snapshot.connectionState == ConnectionState.done &&
                snapshot.data?.live == true)
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton(
                  onPressed: () => _edit(data),
                  child: const Text('Edit contact'),
                ),
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

class CrmContactForm extends StatefulWidget {
  const CrmContactForm({
    super.key,
    required this.api,
    this.contact = const {},
    required this.scopeHeaders,
  });

  final ApiClient api;
  final Json contact;
  final Map<String, String> scopeHeaders;

  @override
  State<CrmContactForm> createState() => _CrmContactFormState();
}

class _CrmContactFormState extends State<CrmContactForm> {
  static const _fields = {
    'first_name': ('First name', 100),
    'last_name': ('Last name', 100),
    'company_name': ('Company', 180),
    'job_title': ('Job title', 120),
    'email': ('Email', 150),
    'phone': ('Phone', 40),
  };
  final _form = GlobalKey<FormState>();
  final _changes = <String, dynamic>{};
  bool _saving = false;
  String? _error;
  bool get _creating => widget.contact['id'] == null;

  Future<void> _save() async {
    if (_saving || _form.currentState?.validate() != true) return;
    _changes.clear();
    _form.currentState!.save();
    if (_changes.isEmpty) {
      Navigator.pop(context, false);
      return;
    }
    if (_changes.containsKey('first_name') ||
        _changes.containsKey('last_name')) {
      final names = {...widget.contact, ..._changes};
      _changes['full_name'] = [
        names['first_name'],
        names['last_name'],
      ].whereType<String>().where((name) => name.isNotEmpty).join(' ');
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final revision = widget.api.sessionRevision;
    try {
      await widget.api.request(
        _creating ? 'POST' : 'PATCH',
        _creating
            ? CrmContactPage.endpoint
            : '${CrmContactPage.endpoint}/${widget.contact['id']}',
        scopeHeaders: widget.scopeHeaders,
        data: _changes,
      );
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(_creating ? 'New contact' : 'Edit contact')),
    body: Form(
      key: _form,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            for (final field in _fields.entries)
              TextFormField(
                initialValue: widget.contact[field.key] as String?,
                enabled: !_saving,
                maxLength: field.value.$2,
                decoration: InputDecoration(labelText: field.value.$1),
                validator: (value) =>
                    field.key == 'first_name' && (value ?? '').trim().isEmpty
                    ? 'Enter a first name'
                    : null,
                onSaved: (value) {
                  final text = value?.trim() ?? '';
                  if (text != (widget.contact[field.key] as String? ?? '')) {
                    _changes[field.key] = text.isEmpty ? null : text;
                  }
                },
              ),
            if (_error case final error?) Text(error),
            FilledButton(
              onPressed: _saving ? null : _save,
              child: Text(
                _saving
                    ? 'Saving…'
                    : _creating
                    ? 'Create contact'
                    : 'Save changes',
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
