import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import 'sales_order_page.dart';

class SalesEngagementPage extends StatefulWidget {
  const SalesEngagementPage({
    super.key,
    required this.api,
    required this.summary,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
    required this.canEdit,
    required this.onChanged,
  });

  static const endpoint = '/srm/engagements';
  final ApiClient api;
  final Json summary;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;
  final bool canEdit;
  final VoidCallback onChanged;

  @override
  State<SalesEngagementPage> createState() => _SalesEngagementPageState();
}

class _SalesEngagementPageState extends State<SalesEngagementPage> {
  static const _fields = {
    'engagement_number': 'Engagement number',
    'status': 'Status',
    'billing_type': 'Billing type',
    'planned_start_date': 'Planned start',
    'planned_end_date': 'Planned end',
    'budget_amount': 'Budget',
    'pms_project_id': 'Project ID',
  };
  String get _path => '${SalesEngagementPage.endpoint}/${widget.summary['id']}';
  Json? _cached;
  String? _error;
  bool _saving = false;
  late var _detail = _load(offline: widget.offline);

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: _path,
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        onCached: (record) {
          if (mounted) setState(() => _cached = record);
        },
        project: (record) => {
          for (final key in [
            'name',
            'currency',
            'sales_order_id',
            ..._fields.keys,
          ])
            key: record[key],
        },
      );

  void _refresh() => setState(() {
    _cached = null;
    _error = null;
    _detail = _load();
  });

  Future<void> _change(String action) async {
    if (_saving) return;
    final revision = widget.api.sessionRevision;
    final reason = await showDialog<String>(
      context: context,
      builder: (_) => _LifecycleReason(action: action),
    );
    if (reason == null ||
        !mounted ||
        widget.api.sessionRevision != revision ||
        _saving) {
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'POST',
        '$_path/lifecycle/$action',
        scopeHeaders: widget.scopeHeaders,
        data: {'reason': reason},
      );
      if (!mounted || widget.api.sessionRevision != revision) return;
      _refresh();
      widget.onChanged();
    } on ApiFailure catch (error) {
      if (mounted && widget.api.sessionRevision == revision) {
        setState(() => _error = error.message);
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Engagement details'),
      actions: [
        IconButton(
          tooltip: 'Refresh engagement',
          onPressed: _saving ? null : _refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder(
      future: _detail,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final loading = snapshot.connectionState != ConnectionState.done;
        final result = loading ? null : snapshot.data;
        final record = result?.record ?? _cached ?? widget.summary;
        final live = result?.live == true;
        final status = record['status'];
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${record['name'] ?? 'Engagement'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (loading) const LinearProgressIndicator(),
            if (!loading && !live) const Text('Saved engagement'),
            if (_error case final message?) ListTile(title: Text(message)),
            for (final field in _fields.entries)
              if (record[field.key] != null)
                ListTile(
                  title: Text(field.value),
                  subtitle: Text(
                    field.key == 'budget_amount'
                        ? '${record['currency'] ?? ''} ${record[field.key]}'
                              .trim()
                        : '${record[field.key]}',
                  ),
                ),
            if (record['sales_order_id'] case final int id)
              ListTile(
                title: const Text('Open sales order'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => SalesOrderPage(
                      api: widget.api,
                      summary: {'id': id, 'order_number': 'Sales order #$id'},
                      offline: !live,
                      cacheScope: widget.cacheScope,
                      scopeHeaders: widget.scopeHeaders,
                    ),
                  ),
                ),
              ),
            if (live &&
                widget.canEdit &&
                status is String &&
                status != 'cancelled')
              for (final action
                  in status == 'closed' ? ['reopen'] : ['close', 'cancel'])
                OutlinedButton(
                  onPressed: _saving ? null : () => _change(action),
                  child: Text(_lifecycleLabel(action)),
                ),
          ],
        );
      },
    ),
  );
}

String _lifecycleLabel(String action) => switch (action) {
  'close' => 'Close engagement',
  'cancel' => 'Cancel engagement',
  _ => 'Reopen engagement',
};

class _LifecycleReason extends StatefulWidget {
  const _LifecycleReason({required this.action});
  final String action;

  @override
  State<_LifecycleReason> createState() => _LifecycleReasonState();
}

class _LifecycleReasonState extends State<_LifecycleReason> {
  String _reason = '';

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(_lifecycleLabel(widget.action)),
    content: TextField(
      autofocus: true,
      maxLength: 1000,
      decoration: const InputDecoration(labelText: 'Lifecycle reason'),
      onChanged: (value) => setState(() => _reason = value.trim()),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Back'),
      ),
      FilledButton(
        onPressed: _reason.isEmpty
            ? null
            : () => Navigator.pop(context, _reason),
        child: const Text('Confirm'),
      ),
    ],
  );
}
