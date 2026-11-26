import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/crm_offline_edits.dart';
import 'crm_lead_page.dart';

class CrmNewLeadPage extends StatefulWidget {
  const CrmNewLeadPage({
    super.key,
    required this.api,
    this.queue,
    this.offline = false,
    this.rejectedDraft,
  });

  final ApiClient api;
  final CrmOfflineEdits? queue;
  final bool offline;
  final Map<String, dynamic>? rejectedDraft;

  @override
  State<CrmNewLeadPage> createState() => _CrmNewLeadPageState();
}

class CrmLeadDraftsPage extends StatefulWidget {
  const CrmLeadDraftsPage({
    super.key,
    required this.queue,
    required this.api,
    this.canEdit = false,
  });
  final CrmOfflineEdits queue;
  final ApiClient api;
  final bool canEdit;

  @override
  State<CrmLeadDraftsPage> createState() => _CrmLeadDraftsPageState();
}

class _CrmLeadDraftsPageState extends State<CrmLeadDraftsPage> {
  late Future<List<Map<String, dynamic>>> _drafts = widget.queue.creations();
  bool _busy = false;

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) {
        setState(() {
          _drafts = widget.queue.creations();
          _busy = false;
        });
      }
    }
  }

  Future<void> _discard(String key) async {
    final discard = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Discard saved lead draft?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
    if (discard == true && mounted) {
      await _run(() => widget.queue.discardCreation(key));
    }
  }

  Future<void> _correct(Map<String, dynamic> draft) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => CrmNewLeadPage(
          api: widget.api,
          queue: widget.queue,
          offline: true,
          rejectedDraft: draft,
        ),
      ),
    );
    if (changed == true && mounted) {
      setState(() {
        _drafts = widget.queue.creations();
      });
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Lead drafts'),
      actions: [
        IconButton(
          tooltip: 'Sync lead drafts',
          onPressed: _busy
              ? null
              : () => _run(() => widget.queue.sync(widget.api)),
          icon: const Icon(Icons.sync),
        ),
      ],
    ),
    body: FutureBuilder<List<Map<String, dynamic>>>(
      future: _drafts,
      builder: (context, snapshot) {
        if (_busy || snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final drafts = snapshot.requireData;
        if (drafts.isEmpty) {
          return const Center(child: Text('No saved lead drafts'));
        }
        return ListView(
          children: [
            for (final draft in drafts)
              ListTile(
                title: Text('${draft['values']['full_name']}'),
                subtitle: Text(draft['error'] as String? ?? 'Awaiting sync'),
                onTap: widget.canEdit && draft['status'] == 422
                    ? () => _correct(draft)
                    : null,
                trailing: IconButton(
                  tooltip: 'Discard lead draft',
                  onPressed: () => _discard(draft['key'] as String),
                  icon: const Icon(Icons.delete_outline),
                ),
              ),
          ],
        );
      },
    ),
  );
}

class _CrmNewLeadPageState extends State<CrmNewLeadPage> {
  final _form = GlobalKey<FormState>();
  late final _values = Map<String, String>.from(
    (widget.rejectedDraft?['values'] as Map?) ?? const {},
  );
  final _operation = const Uuid().v4();
  bool _saving = false;
  String? _error;

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    final payload = {
      'values': {
        for (final entry in _values.entries)
          if (entry.value.isNotEmpty) entry.key: entry.value,
      },
    };
    try {
      final queue = widget.queue;
      if (widget.offline && queue != null) {
        await queue.enqueueCreation(
          _operation,
          payload,
          replaceRejected: widget.rejectedDraft?['key'] as String?,
        );
      } else {
        try {
          await widget.api.request(
            'POST',
            CrmLeadPage.endpoint,
            scopeHeaders:
                queue?.creationHeaders(_operation) ??
                {'X-Offline-Operation': _operation},
            data: payload,
          );
        } on ApiFailure catch (error) {
          if (!error.connectionFailure ||
              queue == null ||
              revision != widget.api.sessionRevision) {
            rethrow;
          }
          await queue.enqueueCreation(_operation, payload);
        }
      }
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.rejectedDraft == null ? 'New lead' : 'Correct lead draft',
      ),
    ),
    body: Form(
      key: _form,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final (key, label, limit, keyboard) in const [
            ('full_name', 'Full name', 220, TextInputType.name),
            ('company_name', 'Company', 180, TextInputType.text),
            ('email', 'Email', 150, TextInputType.emailAddress),
            ('phone', 'Phone', 40, TextInputType.phone),
          ])
            TextFormField(
              initialValue: _values[key],
              enabled: !_saving,
              decoration: InputDecoration(labelText: label),
              maxLength: limit,
              keyboardType: keyboard,
              onChanged: (value) => _values[key] = value.trim(),
              validator: key == 'full_name'
                  ? (value) => (value ?? '').trim().isEmpty
                        ? 'Enter the lead name.'
                        : null
                  : null,
            ),
          if (_error != null) Text(_error!),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(
              _saving
                  ? 'Saving…'
                  : widget.offline
                  ? 'Save lead draft'
                  : 'Create lead',
            ),
          ),
        ],
      ),
    ),
  );
}
