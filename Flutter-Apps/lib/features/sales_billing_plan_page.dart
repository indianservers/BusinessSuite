import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';
import 'gst_invoice_page.dart';

class SalesBillingPlanPage extends StatefulWidget {
  const SalesBillingPlanPage({
    super.key,
    required this.api,
    required this.summary,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
    required this.canEdit,
    this.canApprove = false,
    this.canCreateInvoice = false,
    this.canExportInvoice = false,
    this.onChanged,
  });

  static const endpoint = '/srm/billing-plans';
  static const fields = [
    'billing_type',
    'currency',
    'total_amount',
    'status',
    'invoiced_value',
    'balance_value',
    'recurrence_rule',
  ];

  final ApiClient api;
  final Json summary;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;
  final bool canEdit;
  final bool canApprove;
  final bool canCreateInvoice;
  final bool canExportInvoice;
  final VoidCallback? onChanged;

  @override
  State<SalesBillingPlanPage> createState() => _SalesBillingPlanPageState();
}

class _SalesBillingPlanPageState extends State<SalesBillingPlanPage> {
  String get _path =>
      '${SalesBillingPlanPage.endpoint}/${widget.summary['id']}';
  Json? _cached;
  String? _error;
  bool _saving = false;
  int _loadRevision = 0;
  DateTimeRange? _eligibilityRange;
  late var _detail = _load(offline: widget.offline);

  Future<({Json? record, bool live})> _load({bool offline = false}) {
    final revision = ++_loadRevision;
    return loadCrmDetail(
      api: widget.api,
      path: _path,
      scope: widget.cacheScope,
      headers: widget.scopeHeaders,
      offline: offline,
      onCached: (record) {
        if (mounted && revision == _loadRevision) {
          setState(() => _cached = record);
        }
      },
      project: _projectPlan,
    );
  }

  Json _projectPlan(Json record) => {
    for (final field in ['name', ...SalesBillingPlanPage.fields])
      field: record[field],
    'milestones': [
      for (final milestone in _rows(record, 'milestones'))
        {
          for (final field in ['id', 'name', 'status', 'due_date', 'amount'])
            field: milestone[field],
        },
    ],
    'invoices': [
      for (final invoice in _rows(record, 'invoices'))
        {
          'id': invoice['id'],
          for (final field in GstInvoicePage.summaryFields)
            field: invoice[field],
        },
    ],
  };

  List<Json> _rows(Json record, String key) =>
      (record[key] as List? ?? const []).whereType<Json>().toList();

  void _refresh() => setState(() {
    _cached = null;
    _error = null;
    _detail = _load();
  });

  Future<void> _checkEligibility() async {
    final today = DateUtils.dateOnly(DateTime.now());
    final revision = widget.api.sessionRevision;
    final range = await showDateRangePicker(
      context: context,
      helpText: 'Billing eligibility dates',
      saveText: 'Check eligibility',
      firstDate: DateTime(1900),
      lastDate: DateTime(9999, 12, 31),
      initialDateRange:
          _eligibilityRange ?? DateTimeRange(start: today, end: today),
    );
    if (range == null || !mounted || revision != widget.api.sessionRevision) {
      return;
    }
    _eligibilityRange = range;
    final result = _loadEligibility(range, revision);
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Billing eligibility'),
        scrollable: true,
        content: FutureBuilder(
          future: result,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const LinearProgressIndicator();
            }
            if (snapshot.hasError) return Text('${snapshot.error}');
            final milestones = snapshot.data!;
            if (milestones.isEmpty) {
              return const Text('No eligible milestones in this period.');
            }
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  milestones.length == 1
                      ? '1 eligible milestone'
                      : '${milestones.length} eligible milestones',
                ),
                for (final milestone in milestones)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text('${milestone['name']}'),
                    subtitle: Text(
                      [
                        milestone['due_date'],
                        milestone['amount'],
                      ].whereType<Object>().join(' · '),
                    ),
                  ),
              ],
            );
          },
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Future<List<Json>> _loadEligibility(DateTimeRange range, int revision) async {
    final result =
        await widget.api.request(
              'GET',
              '$_path/eligibility',
              query: {
                'date_from': range.start.toIso8601String().split('T').first,
                'date_to': range.end.toIso8601String().split('T').first,
              },
              scopeHeaders: widget.scopeHeaders,
            )
            as Json;
    if (revision != widget.api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    return (result['milestones'] as List).cast<Json>();
  }

  Future<void> _change(String action, String label) async {
    if (_saving) return;
    final revision = widget.api.sessionRevision;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('$label billing plan?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(label),
          ),
        ],
      ),
    );
    if (confirmed == true &&
        mounted &&
        revision == widget.api.sessionRevision) {
      await _mutate('POST', '$_path/$action');
    }
  }

  Future<void> _amend(Json milestone, int id) async {
    final revision = widget.api.sessionRevision;
    final data = await showDialog<Json>(
      context: context,
      builder: (_) => _MilestoneAmendment(milestone: milestone),
    );
    if (data != null && mounted && revision == widget.api.sessionRevision) {
      await _mutate('PATCH', '/srm/billing-milestones/$id', data: data);
    }
  }

  Future<Json?> _mutate(
    String method,
    String path, {
    Json? data,
    Future<void> Function(Json)? saveResult,
  }) async {
    if (_saving) return null;
    setState(() {
      _saving = true;
      _error = null;
    });
    final revision = widget.api.sessionRevision;
    try {
      final result =
          await widget.api.request(
                method,
                path,
                data: data,
                scopeHeaders: widget.scopeHeaders,
              )
              as Json?;
      if (revision != widget.api.sessionRevision) return null;
      if (result != null && saveResult != null) await saveResult(result);
      if (!mounted || revision != widget.api.sessionRevision) return null;
      _refresh();
      widget.onChanged?.call();
      return result;
    } catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _error = '$error');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
    return null;
  }

  void _openInvoice(Json invoice, int id, {required bool live}) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => GstInvoicePage(
          api: widget.api,
          id: id,
          scopeHeaders: widget.scopeHeaders,
          cacheScope: widget.cacheScope,
          summary: invoice,
          offline: !live,
          canEdit: widget.canCreateInvoice,
          canIssue: widget.canApprove,
          canExport: widget.canExportInvoice,
          onChanged: _refresh,
        ),
      ),
    );
  }

  Future<void> _saveDraft(Json plan, int milestoneId, Json invoice) async {
    final scope = widget.cacheScope;
    final invoiceId = invoice['id'];
    if (scope == null || invoiceId is! int) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    if (invoice['lines'] is List) {
      await GstInvoicePage.saveSnapshot(
        GstInvoicePage.cacheKey(
          scope,
          '${GstInvoicePage.listEndpoint}/$invoiceId',
          widget.scopeHeaders,
        ),
        invoice,
      );
    }
    final branch = widget.scopeHeaders['X-Suite-Branch'] ?? '';
    final key = '$scope:$_path:$branch';
    try {
      await flushCrmDetailWrite(key);
      if (revision != api.sessionRevision) return;
      await SuiteReadCache.write(key, [
        _projectPlan({
          ...plan,
          'invoiced_value': null,
          'balance_value': null,
          'milestones': [
            for (final milestone in _rows(plan, 'milestones'))
              if (milestone['id'] == milestoneId)
                {...milestone, 'status': 'invoiced'}
              else
                milestone,
          ],
          'invoices': [
            invoice,
            for (final linked in _rows(plan, 'invoices'))
              if (linked['id'] != invoiceId) linked,
          ],
        }),
      ]);
    } catch (_) {
      // The shared backend has already created the draft.
    }
  }

  Widget? _milestoneActions(Json plan, Json milestone, bool live) {
    final id = milestone['id'];
    final status = milestone['status'];
    if (!live ||
        id is! int ||
        milestone['invoice_draft_id'] != null ||
        status == 'invoiced') {
      return null;
    }
    final ready = const {'approved', 'ready', 'completed'}.contains(status);
    final actions = [
      if (widget.canEdit) ('amend', 'Amend milestone'),
      if (widget.canApprove && !ready) ('approve', 'Approve milestone'),
      if (widget.canCreateInvoice && ready) ('draft', 'Generate invoice draft'),
    ];
    if (actions.isEmpty) return null;
    return PopupMenuButton<String>(
      tooltip: 'Actions for ${milestone['name']}',
      enabled: !_saving,
      itemBuilder: (_) => [
        for (final (action, label) in actions)
          PopupMenuItem(value: action, child: Text(label)),
      ],
      onSelected: (action) async {
        switch (action) {
          case 'amend':
            await _amend(milestone, id);
          case 'approve':
            await _mutate('POST', '/srm/billing-milestones/$id/approve');
          case 'draft':
            final invoice = await _mutate(
              'POST',
              '/srm/invoices/draft-from-billing-milestone/$id',
              saveResult: (invoice) => _saveDraft(plan, id, invoice),
            );
            if (!mounted) return;
            if (invoice?['id'] case final int invoiceId) {
              _openInvoice(invoice!, invoiceId, live: true);
            }
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Billing plan'),
      actions: [
        IconButton(
          tooltip: 'Refresh billing plan',
          onPressed: _saving ? null : _refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder(
      future: _detail,
      builder: (context, snapshot) {
        final loading = snapshot.connectionState != ConnectionState.done;
        if (!loading && snapshot.hasError) {
          return Center(child: Text('${snapshot.error}'));
        }
        final detail = loading ? _cached : snapshot.data?.record;
        if (loading && detail == null) {
          return const Center(child: CircularProgressIndicator());
        }
        final record = detail ?? widget.summary;
        final live = !loading && snapshot.data?.live == true;
        final milestones = _rows(record, 'milestones');
        final invoices = _rows(record, 'invoices');
        final actions = switch (record['status']) {
          'draft' => const [('activate', 'Activate')],
          'paused' => const [('activate', 'Resume')],
          'active' => const [('pause', 'Pause'), ('complete', 'Complete')],
          _ => const <(String, String)>[],
        };
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (loading) const LinearProgressIndicator(),
            Text(
              '${record['name']}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (!live)
              Text(
                detail == null ? 'Saved plan summary' : 'Saved billing plan',
              ),
            for (final (key, label) in const [
              ('status', 'Status'),
              ('billing_type', 'Billing type'),
              ('total_amount', 'Plan total'),
              ('invoiced_value', 'Invoiced'),
              ('balance_value', 'Balance'),
              ('recurrence_rule', 'Recurrence'),
            ])
              if (record[key] != null)
                ListTile(
                  title: Text(label),
                  subtitle: Text(
                    const {
                          'total_amount',
                          'invoiced_value',
                          'balance_value',
                        }.contains(key)
                        ? '${record['currency'] ?? ''} ${record[key]}'.trim()
                        : '${record[key]}',
                  ),
                ),
            if (_error case final String error) Text(error),
            if (live && widget.canEdit)
              Wrap(
                spacing: 8,
                children: [
                  for (final (action, label) in actions)
                    OutlinedButton(
                      onPressed: _saving ? null : () => _change(action, label),
                      child: Text('$label billing plan'),
                    ),
                ],
              ),
            if (detail != null) ...[
              const ListTile(title: Text('Billing milestones')),
              if (live)
                OutlinedButton.icon(
                  onPressed: _saving ? null : _checkEligibility,
                  icon: const Icon(Icons.date_range),
                  label: const Text('Check billing eligibility'),
                ),
              if (milestones.isEmpty)
                const ListTile(title: Text('No milestones')),
              for (final milestone in milestones)
                ListTile(
                  title: Text('${milestone['name']}'),
                  subtitle: Text(
                    [
                      milestone['status'],
                      milestone['amount'],
                      milestone['due_date'],
                    ].whereType<Object>().join(' · '),
                  ),
                  trailing: _milestoneActions(record, milestone, live),
                ),
              const ListTile(title: Text('Invoices')),
              if (invoices.isEmpty) const ListTile(title: Text('No invoices')),
              for (final invoice in invoices)
                if (invoice['id'] case final int id)
                  ListTile(
                    title: Text('${invoice['invoice_number'] ?? id}'),
                    subtitle: Text(
                      '${invoice['currency'] ?? ''} ${invoice['total_amount'] ?? ''}'
                          .trim(),
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _openInvoice(invoice, id, live: live),
                  ),
            ],
          ],
        );
      },
    ),
  );
}

class _MilestoneAmendment extends StatefulWidget {
  const _MilestoneAmendment({required this.milestone});

  final Json milestone;

  @override
  State<_MilestoneAmendment> createState() => _MilestoneAmendmentState();
}

class _MilestoneAmendmentState extends State<_MilestoneAmendment> {
  final _form = GlobalKey<FormState>();
  late String _amount = '${widget.milestone['amount']}';
  late DateTime? _due = DateTime.tryParse('${widget.milestone['due_date']}');
  String _reason = '';

  Future<void> _pickDueDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _due ?? DateTime.now(),
      firstDate: DateTime(1),
      lastDate: DateTime(9999, 12, 31),
    );
    if (mounted && date != null) setState(() => _due = date);
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text('Amend ${widget.milestone['name']}'),
    scrollable: true,
    content: Form(
      key: _form,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextFormField(
            initialValue: _amount,
            decoration: const InputDecoration(labelText: 'Milestone amount'),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            onChanged: (value) => _amount = value.trim(),
            validator: (_) =>
                RegExp(r'^\d{1,12}(\.\d{1,2})?$').hasMatch(_amount)
                ? null
                : 'Enter a non-negative amount with up to 2 decimals.',
          ),
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              TextButton(
                onPressed: _pickDueDate,
                child: Text(
                  _due == null
                      ? 'Set due date'
                      : MaterialLocalizations.of(
                          context,
                        ).formatCompactDate(_due!),
                ),
              ),
              if (_due != null)
                IconButton(
                  tooltip: 'Clear due date',
                  onPressed: () => setState(() => _due = null),
                  icon: const Icon(Icons.clear),
                ),
            ],
          ),
          TextFormField(
            decoration: const InputDecoration(labelText: 'Amendment reason'),
            maxLength: 1000,
            maxLines: 2,
            onChanged: (value) => _reason = value.trim(),
            validator: (_) => _reason.isEmpty ? 'Enter a reason.' : null,
          ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: () {
          if (!_form.currentState!.validate()) return;
          Navigator.pop(context, {
            'amount': _amount,
            'due_date': _due?.toIso8601String().split('T').first,
            'reason': _reason,
            'expected_amount': '${widget.milestone['amount']}',
            'expected_due_date': widget.milestone['due_date'],
          });
        },
        child: const Text('Save amendment'),
      ),
    ],
  );
}
