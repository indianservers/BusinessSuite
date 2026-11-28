import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/crm_offline_edits.dart';
import '../core/models.dart';

class CrmCustomerPage extends StatefulWidget {
  const CrmCustomerPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
    this.cacheScope,
    this.onChanged,
    this.salesContext = false,
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
  final VoidCallback? onChanged;
  final bool salesContext;

  @override
  State<CrmCustomerPage> createState() => _CrmCustomerPageState();
}

class _CrmCustomerPageState extends State<CrmCustomerPage> {
  late final _queue = widget.cacheScope == null || widget.salesContext
      ? null
      : CrmOfflineEdits(widget.cacheScope!);
  int get _id => widget.summary['id'] as int;
  late Future<Json?> _pending = _readPending();
  bool _working = false;
  StreamSubscription<void>? _customerUpdates;

  @override
  void initState() {
    super.initState();
    _customerUpdates = _queue?.customerUpdates(_id).listen((_) {
      if (!mounted || _working) return;
      _refresh();
      widget.onChanged?.call();
    });
  }

  @override
  void dispose() {
    _customerUpdates?.cancel();
    super.dispose();
  }

  Future<Json?> _readPending() async => _queue?.pendingCustomer(_id);
  Json? _cachedDetails;
  late Future<({Json? record, bool live})> _profile = _load(
    offline: widget.offline,
  );

  Future<({Json? record, bool live})> _load({
    bool offline = false,
  }) => loadCrmDetail(
    api: widget.api,
    path: '/master-data/companies/${widget.summary['id']}',
    scope: widget.cacheScope,
    cacheKey: widget.salesContext && widget.cacheScope != null
        ? "${widget.cacheScope}:/master-data/companies/$_id:${widget.scopeHeaders['X-Suite-Branch'] ?? ''}:srm"
        : null,
    headers: widget.scopeHeaders,
    query: widget.salesContext ? const {'source': 'srm'} : const {},
    offline: offline,
    onCached: (record) {
      if (mounted) setState(() => _cachedDetails = record);
    },
    project: (record) => {
      for (final field in [
        'id',
        'name',
        'version',
        'canEdit',
        'phone_country_code',
        ...CrmCustomerPage.fields.keys,
      ])
        field: record[field],
      'contacts': [
        for (final contact
            in (record['contacts'] as List? ?? const []).whereType<Json>().take(
              30,
            ))
          {'name': contact['name']},
      ],
    },
  );

  void _refresh() => setState(() {
    _cachedDetails = null;
    _profile = _load();
    _pending = _readPending();
  });

  Future<void> _edit(Json record, {required bool offline}) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => CrmCustomerForm(
          api: widget.api,
          scopeHeaders: widget.scopeHeaders,
          customer: record,
          offlineQueue: offline ? _queue : null,
        ),
      ),
    );
    if (!mounted || changed != true) return;
    if (offline) {
      setState(() {
        _pending = _readPending();
      });
      return;
    }
    _refresh();
    widget.onChanged?.call();
  }

  Future<void> _manageSaved({required bool discard}) async {
    if (_working) return;
    setState(() => _working = true);
    try {
      if (discard) {
        await _queue!.discardCustomer(_id);
      } else {
        await _queue!.sync(widget.api, onlyCustomer: _id);
      }
      if (mounted) {
        _refresh();
        if (!discard) widget.onChanged?.call();
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

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
        return FutureBuilder<Json?>(
          future: _pending,
          builder: (context, pendingSnapshot) {
            final pending = pendingSnapshot.data;
            final live = snapshot.data?.live == true;
            final saved = snapshot.data?.record;
            final record = saved ?? _cachedDetails ?? widget.summary;
            final data = pending != null && pending['error'] == null
                ? {...record, ...pending['body'] as Json}
                : record;
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
                if (pending != null)
                  ListTile(
                    title: Text(
                      pending['error'] == null
                          ? 'Customer edit saved · awaiting sync'
                          : 'Saved customer edit needs review',
                    ),
                    subtitle: pending['error'] == null
                        ? null
                        : Text('${pending['error']}'),
                    trailing: TextButton(
                      onPressed: _working
                          ? null
                          : () =>
                                _manageSaved(discard: pending['error'] != null),
                      child: Text(
                        pending['error'] == null ? 'Sync now' : 'Discard',
                      ),
                    ),
                  ),
                if (!widget.salesContext &&
                    snapshot.connectionState == ConnectionState.done &&
                    pendingSnapshot.connectionState == ConnectionState.done &&
                    !pendingSnapshot.hasError &&
                    pending == null &&
                    (live || _queue != null) &&
                    saved?['canEdit'] == true &&
                    saved?['id'] is int &&
                    saved?['version'] is String)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: OutlinedButton(
                      onPressed: () => _edit(saved!, offline: !live),
                      child: const Text('Edit customer'),
                    ),
                  ),
                for (final field in CrmCustomerPage.fields.entries)
                  if (data[field.key] case final String value
                      when value.isNotEmpty)
                    ListTile(title: Text(field.value), subtitle: Text(value)),
                if (contacts.isNotEmpty)
                  Text(
                    'Contacts',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                for (final contact in contacts)
                  if (contact['name'] case final String name)
                    ListTile(title: Text(name)),
              ],
            );
          },
        );
      },
    ),
  );
}

class CrmCustomerForm extends StatefulWidget {
  const CrmCustomerForm({
    super.key,
    required this.api,
    required this.scopeHeaders,
    this.customer = const {},
    this.offlineQueue,
  });

  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final Json customer;
  final CrmOfflineEdits? offlineQueue;

  @override
  State<CrmCustomerForm> createState() => _CrmCustomerFormState();
}

class _CrmCustomerFormState extends State<CrmCustomerForm> {
  final _form = GlobalKey<FormState>();
  final _changes = <String, dynamic>{};
  bool _saving = false;
  String? _error;
  bool get _creating => widget.customer['id'] == null;
  String get _initialKind =>
      widget.customer['entityKind'] == 'Company' ? 'Company' : 'Individual';
  late String _kind = _initialKind;
  static const _fields = {
    'name': ('Customer name', 180),
    'email': ('Email', 150),
    'phone': ('Phone', 40),
    'phone_country_code': ('Phone country code', 5),
    'website': ('Website', 200),
    'industry': ('Industry', 120),
  };

  Future<void> _save() async {
    if (_saving || _form.currentState?.validate() != true) return;
    _changes.clear();
    _form.currentState!.save();
    if (_creating || _kind != _initialKind) {
      _changes['entityKind'] = _kind;
    }
    if (_changes.isEmpty) {
      Navigator.pop(context, false);
      return;
    }
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final payload = {
        ..._changes,
        'name': _changes['name'] ?? widget.customer['name'],
        if (_creating)
          'roles': const ['Customer']
        else
          'version': widget.customer['version'],
      };
      if (widget.offlineQueue case final queue?) {
        await queue.enqueueCustomer(
          widget.customer['id'] as int,
          payload,
          widget.scopeHeaders['X-Suite-Branch'] ?? '',
        );
      } else {
        await widget.api.request(
          _creating ? 'POST' : 'PATCH',
          _creating
              ? '/master-data/companies'
              : '/master-data/companies/${widget.customer['id']}',
          query: const {'source': 'crm'},
          scopeHeaders: widget.scopeHeaders,
          data: payload,
        );
      }
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on StateError catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(_creating ? 'New customer' : 'Edit customer')),
    body: Form(
      key: _form,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            DropdownButtonFormField<String>(
              decoration: const InputDecoration(labelText: 'Customer type'),
              initialValue: _kind,
              items: const [
                DropdownMenuItem(
                  value: 'Individual',
                  child: Text('Individual'),
                ),
                DropdownMenuItem(value: 'Company', child: Text('Company')),
              ],
              onChanged: _saving
                  ? null
                  : (kind) => setState(() => _kind = kind!),
            ),
            for (final field in _fields.entries)
              TextFormField(
                enabled: !_saving,
                initialValue: widget.customer[field.key]?.toString(),
                decoration: InputDecoration(labelText: field.value.$1),
                maxLength: field.value.$2,
                validator: (value) =>
                    field.key == 'name' && (value?.trim().isEmpty ?? true)
                    ? 'Enter a customer name'
                    : null,
                onSaved: (value) {
                  final text = value?.trim() ?? '';
                  if (text !=
                      (widget.customer[field.key]?.toString().trim() ?? '')) {
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
                    ? 'Create customer'
                    : widget.offlineQueue == null
                    ? 'Save changes'
                    : 'Save edit offline',
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
