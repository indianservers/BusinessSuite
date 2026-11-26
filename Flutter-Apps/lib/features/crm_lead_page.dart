import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_offline_edits.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';

class CrmLeadPage extends StatefulWidget {
  const CrmLeadPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    this.onSaved,
    this.offlineEdits,
    this.cacheScope,
  });
  static const endpoint = '/crm/lead-management/leads';
  final ApiClient api;
  final Json summary;
  final bool offline;
  final VoidCallback? onSaved;
  final CrmOfflineEdits? offlineEdits;
  final String? cacheScope;

  @override
  State<CrmLeadPage> createState() => _CrmLeadPageState();
}

class _CrmLeadPageState extends State<CrmLeadPage> {
  late Future<Json?> _lead = _load();
  Json? _saved;
  late Future<Json?> _pending = _readPending();
  int get _id => widget.summary['id'] as int;
  Future<Json?> _readPending() async {
    try {
      return await widget.offlineEdits?.pending(_id);
    } catch (_) {
      return null;
    }
  }

  Future<void> _discardDraft() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Discard the saved device edit?'),
        content: const Text('The server record will stay as it is.'),
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
    if (confirmed != true || !mounted) return;
    try {
      await widget.offlineEdits!.discard(_id);
      if (!mounted) return;
      setState(() {
        _pending = _readPending();
        if (!widget.offline) _lead = _load();
      });
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not discard the saved edit.')),
        );
      }
    }
  }

  String get _path => '${CrmLeadPage.endpoint}/${widget.summary['id']}';
  String? get _cacheKey {
    final scope = widget.cacheScope;
    return scope == null ? null : '$scope:$_path';
  }

  Future<void> _saveDetails(Json lead) async {
    final key = _cacheKey;
    if (key == null) return;
    try {
      await SuiteReadCache.write(key, [
        {
          for (final field in const [
            'first_name',
            'last_name',
            'full_name',
            'company_name',
            'status',
            'source',
            'rating',
            'version',
          ])
            if (lead[field] is String || lead[field] is int) field: lead[field],
        },
      ]);
    } catch (_) {
      // An unavailable local database leaves the current online lead usable.
    }
  }

  Future<Json?> _load() async {
    final key = _cacheKey;
    final api = widget.api;
    final revision = api.sessionRevision;
    if (key != null) {
      try {
        final records = await SuiteReadCache.read(key);
        if (mounted && revision == api.sessionRevision) {
          setState(() => _saved = records?.firstOrNull);
        }
      } catch (_) {}
    }
    if (!mounted) return null;
    if (revision != api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    if (widget.offline) return null;
    try {
      final lead = await api.request('GET', _path) as Json;
      if (revision != api.sessionRevision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      await _saveDetails(lead);
      return lead;
    } on ApiFailure catch (error) {
      if (error.connectionFailure ||
          error.status == 429 ||
          (error.status ?? 0) >= 500) {
        return null;
      }
      if (key != null && const {401, 403, 404}.contains(error.status)) {
        if (mounted) setState(() => _saved = null);
        try {
          await SuiteReadCache.clear(key);
        } catch (_) {}
      }
      rethrow;
    }
  }

  void _refresh({bool sync = false}) {
    final edits = widget.offlineEdits;
    final attempt = sync && edits != null
        ? edits.sync(widget.api, leadId: _id)
        : Future<void>.value();
    final ready = attempt.then<void>((_) {}, onError: (Object _) {});
    setState(() {
      _lead = ready.then((_) => _load());
      _pending = ready.then((_) => _readPending());
    });
  }

  Future<void> _edit(
    Json lead,
    int version, {
    required bool offline,
    Json? rejected,
  }) async {
    final fields = [
      ('first_name', 'First name', 100),
      ('last_name', 'Last name', 100),
      ('company_name', 'Company', 180),
      if (!offline) ('email', 'Email', 150),
    ];
    final initial = {
      for (final (key, _, _) in fields) key: lead[key]?.toString() ?? '',
    };
    final draft = Map.of(initial);
    final rejectedValues = rejected?['values'] as Json?;
    if (rejectedValues != null) {
      for (final key in initial.keys.where(rejectedValues.containsKey)) {
        draft[key] = rejectedValues[key]?.toString() ?? '';
      }
    }
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
            title: Text(
              rejected == null ? 'Edit lead details' : 'Review saved lead edit',
            ),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (final (key, label, maximum) in fields)
                    TextFormField(
                      initialValue: draft[key],
                      enabled: !saving,
                      maxLength: maximum,
                      keyboardType: key == 'email'
                          ? TextInputType.emailAddress
                          : null,
                      decoration: InputDecoration(
                        labelText: label,
                        helperText: rejectedValues?.containsKey(key) == true
                            ? 'On server: ${initial[key]!.isEmpty ? 'Empty' : initial[key]}'
                            : null,
                      ),
                      onChanged: (text) => draft[key] = text,
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
                        final values = <String, dynamic>{
                          for (final field in draft.entries)
                            if (field.value.trim() !=
                                initial[field.key]?.trim())
                              field.key: field.value.trim(),
                        };
                        if (values['first_name'] == '') {
                          update(() => error = 'Enter a first name.');
                          return;
                        }
                        if (values.isEmpty) {
                          Navigator.pop(context);
                          return;
                        }
                        update(() {
                          saving = true;
                          error = null;
                        });
                        try {
                          if (offline || rejected != null) {
                            await widget.offlineEdits!.enqueue(
                              _id,
                              version,
                              values,
                              rejectedVersion: rejected?['version'] as int?,
                            );
                            if (context.mounted) Navigator.pop(context, lead);
                            return;
                          }
                          final updated =
                              await widget.api.request(
                                    'PATCH',
                                    _path,
                                    data: {
                                      'values': values,
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
                child: Text(
                  saving
                      ? 'Saving…'
                      : rejected == null
                      ? 'Save'
                      : 'Save and sync',
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (result != null && mounted) {
      if (rejected != null) {
        _refresh(sync: true);
        return;
      }
      setState(() {
        if (!offline) _lead = Future.value(result);
        _pending = _readPending();
      });
      if (!offline) {
        await _saveDetails(result);
        if (mounted) widget.onSaved?.call();
      }
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
            onPressed: () => _refresh(sync: true),
            icon: const Icon(Icons.refresh),
          ),
      ],
    ),
    body: FutureBuilder<Json?>(
      future: _lead,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final loading = snapshot.connectionState != ConnectionState.done;
        final live = loading ? null : snapshot.data;
        final saved = _saved;
        final savedVersion = saved?['version'];
        final summaryVersion = widget.summary['version'];
        final lead =
            live ??
            {
              ...widget.summary,
              ...?saved,
              if (summaryVersion is int &&
                  (savedVersion is! int || summaryVersion > savedVersion))
                ...widget.summary,
            };
        final offline = live == null;
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
            if (loading && !widget.offline) const LinearProgressIndicator(),
            if (offline && (!loading || widget.offline))
              ListTile(
                title: Text(
                  '${widget.offline ? 'Offline' : 'Refresh unavailable'} · '
                  '${_saved == null ? 'Saved lead summary' : 'Saved lead details'}',
                ),
              ),
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
            FutureBuilder<Json?>(
              future: _pending,
              builder: (context, pending) {
                if (pending.connectionState != ConnectionState.done) {
                  return const SizedBox.shrink();
                }
                final draft = pending.data;
                if (draft != null) {
                  final values = draft['values'] as Json;
                  return ListTile(
                    title: Text(
                      draft['error'] == null
                          ? 'Edit saved · Awaiting sync'
                          : 'Saved edit needs review',
                    ),
                    subtitle: SelectableText(
                      [
                        for (final field in const {
                          'first_name': 'First name',
                          'last_name': 'Last name',
                          'company_name': 'Company',
                        }.entries)
                          if (values.containsKey(field.key))
                            '${field.value}: ${values[field.key]}',
                        draft['error'] ??
                            'Reopen or refresh CRM after reconnecting.',
                      ].join('\n'),
                    ),
                    trailing: draft['error'] == null
                        ? null
                        : Wrap(
                            children: [
                              if (!offline && version is int)
                                IconButton(
                                  tooltip: 'Review saved edit',
                                  icon: const Icon(Icons.edit_outlined),
                                  onPressed: () => _edit(
                                    lead,
                                    version,
                                    offline: false,
                                    rejected: draft,
                                  ),
                                ),
                              IconButton(
                                tooltip: 'Discard saved edit',
                                icon: const Icon(Icons.delete_outline),
                                onPressed: _discardDraft,
                              ),
                            ],
                          ),
                  );
                }
                if (loading ||
                    version is! int ||
                    (offline && widget.offlineEdits == null)) {
                  return const SizedBox.shrink();
                }
                return OutlinedButton(
                  onPressed: () => _edit(lead, version, offline: offline),
                  child: Text(
                    offline ? 'Edit lead offline' : 'Edit lead details',
                  ),
                );
              },
            ),
          ],
        );
      },
    ),
  );
}
