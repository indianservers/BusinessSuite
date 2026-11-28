import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
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
      project: (record) => {
        for (final field in ['name', ...SalesBillingPlanPage.fields])
          field: record[field],
        'milestones': [
          for (final milestone in _rows(record, 'milestones'))
            {
              for (final field in ['name', 'status', 'due_date', 'amount'])
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
      },
    );
  }

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
    setState(() {
      _saving = true;
      _error = null;
    });
    final revision = widget.api.sessionRevision;
    try {
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
      if (confirmed != true ||
          !mounted ||
          revision != widget.api.sessionRevision) {
        return;
      }
      await widget.api.request(
        'POST',
        '$_path/$action',
        scopeHeaders: widget.scopeHeaders,
      );
      if (!mounted || revision != widget.api.sessionRevision) return;
      _refresh();
      widget.onChanged?.call();
    } catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _error = '$error');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
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
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => GstInvoicePage(
                          api: widget.api,
                          id: id,
                          scopeHeaders: widget.scopeHeaders,
                          cacheScope: widget.cacheScope,
                          summary: invoice,
                          offline: !live,
                        ),
                      ),
                    ),
                  ),
            ],
          ],
        );
      },
    ),
  );
}
