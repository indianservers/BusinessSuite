import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import 'gst_invoice_page.dart';
import 'invoice_receipt_dialog.dart';

class GstCollectionsPage extends StatefulWidget {
  const GstCollectionsPage({
    super.key,
    required this.api,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
    this.canExport = false,
  });

  static const endpoint = '/srm/business/collection-invoices';
  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;
  final bool canExport;

  @override
  State<GstCollectionsPage> createState() => _GstCollectionsPageState();
}

class _GstCollectionsPageState extends State<GstCollectionsPage> {
  bool _outstandingOnly = true;
  String _query = '';
  Json? _cached;
  int _generation = 0;
  late var _records = _load(offline: widget.offline);

  Future<({Json? record, bool live})> _load({bool offline = false}) {
    final generation = ++_generation;
    return loadCrmDetail(
      api: widget.api,
      path: GstCollectionsPage.endpoint,
      scope: widget.cacheScope,
      headers: widget.scopeHeaders,
      offline: offline,
      onCached: (record) {
        if (mounted && generation == _generation) {
          setState(() => _cached = record);
        }
      },
      project: (record) => {
        'items': [
          for (final invoice in _rows(record))
            {
              'id': invoice['id'],
              'customer_id': invoice['customer_id'],
              for (final field in GstInvoicePage.summaryFields)
                field: invoice[field],
              'collection_hold': invoice['collection_hold'],
              'collection_hold_reason': invoice['collection_hold_reason'],
              'collection_resume_at': invoice['collection_resume_at'],
            },
        ],
      },
    );
  }

  Iterable<Json> _rows(Json record) =>
      (record['items'] as List? ?? const []).whereType<Json>();

  void _refresh() => setState(() {
    _cached = null;
    _records = _load();
  });

  Future<void> _recordReceipt(Json invoice, String scope) async {
    final revision = widget.api.sessionRevision;
    final result = await showDialog<Json>(
      context: context,
      barrierDismissible: false,
      builder: (_) => InvoiceReceiptDialog(
        api: widget.api,
        invoiceId: invoice['id'] as int,
        invoice: invoice,
        scope: scope,
        headers: _invoiceHeaders(invoice),
      ),
    );
    if (!mounted || result == null || revision != widget.api.sessionRevision) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          result['reversed'] == true
              ? 'Receipt #${result['receipt_id']} was reversed.'
              : 'Recorded receipt #${result['receipt_id']}',
        ),
      ),
    );
    _refresh();
  }

  Map<String, String> _invoiceHeaders(Json invoice) => {
    ...widget.scopeHeaders,
    if (invoice['branch_id'] case final int branch when branch > 0)
      'X-Suite-Branch': '$branch',
  };

  Future<void> _control(Json invoice) async {
    final hold = invoice['collection_hold'] != true;
    final revision = widget.api.sessionRevision;
    final api = widget.api;
    final form = GlobalKey<FormState>();
    final headers = _invoiceHeaders(invoice);
    var saving = false;
    var reason = '';
    String? error;
    DateTime? resumeAt;
    final saved = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => StatefulBuilder(
        builder: (context, update) => PopScope(
          canPop: !saving,
          child: AlertDialog(
            title: Text(hold ? 'Pause collections' : 'Resume collections'),
            scrollable: true,
            content: Form(
              key: form,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    enabled: !saving,
                    decoration: const InputDecoration(labelText: 'Reason'),
                    maxLength: 500,
                    onChanged: (value) => reason = value.trim(),
                    validator: (_) => reason.runes.length < 3
                        ? 'Enter at least three characters.'
                        : null,
                  ),
                  if (hold)
                    TextButton(
                      onPressed: saving
                          ? null
                          : () async {
                              final today = DateUtils.dateOnly(DateTime.now());
                              final date = await showDatePicker(
                                context: context,
                                initialDate: resumeAt ?? today,
                                firstDate: today,
                                lastDate: DateTime(9999, 12, 30),
                              );
                              if (!context.mounted || date == null) return;
                              final time = await showTimePicker(
                                context: context,
                                initialTime: TimeOfDay.fromDateTime(
                                  resumeAt ?? DateTime.now(),
                                ),
                              );
                              if (!context.mounted || time == null) return;
                              update(
                                () => resumeAt = DateTime(
                                  date.year,
                                  date.month,
                                  date.day,
                                  time.hour,
                                  time.minute,
                                ),
                              );
                            },
                      child: Text(
                        resumeAt == null
                            ? 'Schedule resume'
                            : 'Resume ${MaterialLocalizations.of(context).formatCompactDate(resumeAt!)} ${TimeOfDay.fromDateTime(resumeAt!).format(context)}',
                      ),
                    ),
                  if (resumeAt != null)
                    TextButton(
                      onPressed: saving
                          ? null
                          : () => update(() => resumeAt = null),
                      child: const Text('Clear scheduled resume'),
                    ),
                  if (error != null) Text(error!),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(context),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        if (!form.currentState!.validate()) return;
                        if (resumeAt?.isAfter(DateTime.now()) == false) {
                          update(() => error = 'Choose a future resume time.');
                          return;
                        }
                        if (api.sessionRevision != revision) {
                          update(
                            () => error = 'Your session ended. Sign in again.',
                          );
                          return;
                        }
                        update(() {
                          saving = true;
                          error = null;
                        });
                        try {
                          await api.request(
                            'PUT',
                            '/srm/collections/${invoice['id']}/control',
                            scopeHeaders: headers,
                            data: {
                              'hold': hold,
                              'reason': reason,
                              'resume_at': resumeAt?.toUtc().toIso8601String(),
                            },
                          );
                          if (context.mounted) Navigator.pop(context, true);
                        } on ApiFailure catch (failure) {
                          if (context.mounted) {
                            update(() {
                              saving = false;
                              error = '$failure';
                            });
                          }
                        }
                      },
                child: Text(hold ? 'Pause' : 'Resume'),
              ),
            ],
          ),
        ),
      ),
    );
    if (mounted && saved == true && api.sessionRevision == revision) _refresh();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Collections'),
      actions: [
        IconButton(
          tooltip: 'Refresh collections',
          onPressed: _refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: TextField(
            decoration: const InputDecoration(
              labelText: 'Find invoice',
              prefixIcon: Icon(Icons.search),
            ),
            onChanged: (value) =>
                setState(() => _query = value.trim().toLowerCase()),
          ),
        ),
        FilterChip(
          label: const Text('Outstanding only'),
          selected: _outstandingOnly,
          onSelected: (value) => setState(() => _outstandingOnly = value),
        ),
        Expanded(
          child: FutureBuilder(
            future: _records,
            builder: (context, snapshot) {
              final loading = snapshot.connectionState != ConnectionState.done;
              if (!loading && snapshot.hasError) {
                return Center(child: Text('${snapshot.error}'));
              }
              final record = loading ? _cached : snapshot.data?.record;
              if (record == null) {
                return Center(
                  child: loading
                      ? const CircularProgressIndicator()
                      : const Text('No collections saved on this device'),
                );
              }
              final live = !loading && snapshot.data?.live == true;
              final canRecord = live && record['can_record'] == true;
              final rows = _rows(record).where((invoice) {
                if (invoice['id'] is! int ||
                    invoice['document_status'] != 'issued') {
                  return false;
                }
                final balance =
                    num.tryParse('${invoice['balance_amount']}') ?? 0;
                return (!_outstandingOnly || balance > 0) &&
                    '${invoice['invoice_number']} ${invoice['customer_id'] ?? ''}'
                        .toLowerCase()
                        .contains(_query);
              }).toList();
              return Column(
                children: [
                  if (loading) const LinearProgressIndicator(),
                  if (!live) const Text('Saved collections'),
                  if (rows.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(16),
                      child: Text('No matching invoices'),
                    )
                  else
                    Expanded(
                      child: ListView.builder(
                        itemCount: rows.length,
                        itemBuilder: (context, index) {
                          final invoice = rows[index];
                          final resume = DateTime.tryParse(
                            '${invoice['collection_resume_at']}',
                          )?.toLocal();
                          return ListTile(
                            title: Text('${invoice['invoice_number']}'),
                            subtitle: Text(
                              [
                                'Outstanding · ${invoice['currency']} ${invoice['balance_amount']}',
                                if (invoice['collection_hold'] == true)
                                  'Collections on hold',
                                if (invoice['collection_hold'] == true) ...[
                                  if (invoice['collection_hold_reason']
                                      case final String reason)
                                    reason,
                                  if (resume != null)
                                    'Resumes ${MaterialLocalizations.of(context).formatCompactDate(resume)} ${TimeOfDay.fromDateTime(resume).format(context)}',
                                ],
                              ].join('\n'),
                            ),
                            trailing: canRecord
                                ? Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      if (widget.cacheScope != null)
                                        IconButton(
                                          tooltip:
                                              'Record payment for ${invoice['invoice_number']}',
                                          icon: const Icon(
                                            Icons.receipt_long_outlined,
                                          ),
                                          onPressed: () => _recordReceipt(
                                            invoice,
                                            widget.cacheScope!,
                                          ),
                                        ),
                                      IconButton(
                                        tooltip:
                                            invoice['collection_hold'] == true
                                            ? 'Resume collections for ${invoice['invoice_number']}'
                                            : 'Pause collections for ${invoice['invoice_number']}',
                                        icon: Icon(
                                          invoice['collection_hold'] == true
                                              ? Icons.play_circle_outline
                                              : Icons.pause_circle_outline,
                                        ),
                                        onPressed: () => _control(invoice),
                                      ),
                                    ],
                                  )
                                : const Icon(Icons.chevron_right),
                            onTap: () => Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) => GstInvoicePage(
                                  api: widget.api,
                                  id: invoice['id'] as int,
                                  scopeHeaders: widget.scopeHeaders,
                                  summary: invoice,
                                  cacheScope: widget.cacheScope,
                                  canExport: widget.canExport,
                                  offline: !live,
                                  onChanged: _refresh,
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                ],
              );
            },
          ),
        ),
      ],
    ),
  );
}
