import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import '../core/suite_pdf.dart';

class CrmQuotationPage extends StatefulWidget {
  const CrmQuotationPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
    this.cacheScope,
    this.canManage = false,
    this.canApprove = false,
    this.onChanged,
  });

  static const endpoint = '/crm/quotations';
  static const fields = [
    'quote_number',
    'issue_date',
    'expiry_date',
    'approval_status',
    'status',
    'currency',
    'grand_total',
    'total_amount',
  ];
  final ApiClient api;
  final Json summary;
  final bool offline;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool canManage;
  final bool canApprove;
  final VoidCallback? onChanged;

  @override
  State<CrmQuotationPage> createState() => _CrmQuotationPageState();
}

class _CrmQuotationPageState extends State<CrmQuotationPage> {
  Json? _cached;
  bool _savingPdf = false;
  bool _changingStatus = false;
  late Future<({Json? record, bool live})> _quote = _load(
    offline: widget.offline,
  );

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: '${CrmQuotationPage.endpoint}/${widget.summary['id']}',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        onCached: (record) {
          if (mounted) setState(() => _cached = record);
        },
        project: (record) => {
          for (final field in [
            ...CrmQuotationPage.fields,
            'terms_and_conditions',
            'terms',
            'converted_srm_sales_order_id',
          ])
            field: record[field],
          'lines': [
            for (final line
                in (record['lines'] as List? ?? const []).whereType<Json>())
              {
                for (final field in [
                  'name',
                  'quantity',
                  'unit_price',
                  'line_total',
                ])
                  field: line[field],
              },
          ],
        },
      );

  void _refresh() => setState(() {
    _cached = null;
    _quote = _load();
  });

  Future<void> _savePdf(Json quote) async {
    if (_savingPdf) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    final id = widget.summary['id'];
    setState(() => _savingPdf = true);
    try {
      final bytes = await fetchSuitePdf(
        api,
        '${CrmQuotationPage.endpoint}/$id/pdf',
        query: const {'download': true},
        scopeHeaders: widget.scopeHeaders,
      );
      if (!mounted || api.sessionRevision != revision) return;
      final number = '${quote['quote_number'] ?? id}'.replaceAll(
        RegExp(r'[^A-Za-z0-9._-]'),
        '_',
      );
      final saved = await FilePicker.saveFile(
        fileName: 'Quotation-$number.pdf',
        bytes: bytes,
      );
      if (mounted && saved != null && revision == api.sessionRevision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Quotation PDF saved.')));
      }
    } catch (error) {
      if (mounted && revision == api.sessionRevision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _savingPdf = false);
    }
  }

  Future<void> _changeStatus(String action, String label, Json quote) async {
    if (_changingStatus) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('$label?'),
        content: Text(
          [
            "Quotation ${quote['quote_number'] ?? widget.summary['id']}",
            if (action == 'accept')
              'This records the customer’s acceptance and creates or links commercial records in Sales & POS.',
          ].join('\n\n'),
        ),
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
    if (!mounted || confirmed != true || api.sessionRevision != revision) {
      return;
    }
    setState(() => _changingStatus = true);
    try {
      await api.request(
        'POST',
        '/crm/quotes/${widget.summary['id']}/$action',
        scopeHeaders: widget.scopeHeaders,
        data: const <String, dynamic>{},
      );
      if (!mounted || api.sessionRevision != revision) return;
      _refresh();
      widget.onChanged?.call();
    } on ApiFailure catch (error) {
      if (mounted && api.sessionRevision == revision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _changingStatus = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Quotation details'),
      actions: [
        IconButton(
          tooltip: 'Refresh quotation',
          icon: const Icon(Icons.refresh),
          onPressed: _refresh,
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _quote,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: TextButton(
              onPressed: _refresh,
              child: Text('${snapshot.error}\nRetry'),
            ),
          );
        }
        final record = snapshot.data?.record ?? _cached ?? widget.summary;
        final live =
            snapshot.connectionState == ConnectionState.done &&
            snapshot.data?.live == true;
        final status = record['status']?.toString().toLowerCase();
        final currency = record['currency'] ?? '';
        final amount = record['grand_total'] ?? record['total_amount'];
        final fields = {
          'Status': record['status'],
          'Approval': (record['approval_status'] as String?)?.replaceAll(
            '_',
            ' ',
          ),
          'Issued': record['issue_date'],
          'Expires': record['expiry_date'],
          'Total': amount == null ? null : '$amount $currency'.trim(),
          'Terms': record['terms_and_conditions'] ?? record['terms'],
          'Sales order': record['converted_srm_sales_order_id'],
        };
        final lines = (record['lines'] as List? ?? const [])
            .whereType<Json>()
            .toList();
        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: lines.length + 1,
          itemBuilder: (context, index) {
            if (index == 0) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (snapshot.connectionState != ConnectionState.done)
                    const LinearProgressIndicator()
                  else if (snapshot.data?.live != true)
                    const Text('Saved quotation'),
                  Text(
                    '${record['quote_number'] ?? 'Quotation'}',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  if (live)
                    OutlinedButton.icon(
                      onPressed: _savingPdf ? null : () => _savePdf(record),
                      icon: const Icon(Icons.picture_as_pdf_outlined),
                      label: Text(
                        _savingPdf ? 'Preparing PDF…' : 'Save quotation PDF',
                      ),
                    ),
                  if (live &&
                      widget.canManage &&
                      const {'draft', 'rejected'}.contains(status))
                    FilledButton(
                      onPressed: _changingStatus
                          ? null
                          : () => _changeStatus(
                              'submit',
                              'Submit for approval',
                              record,
                            ),
                      child: const Text('Submit for approval'),
                    ),
                  if (live && widget.canApprove && status == 'pending approval')
                    Wrap(
                      spacing: 8,
                      children: [
                        FilledButton(
                          onPressed: _changingStatus
                              ? null
                              : () => _changeStatus(
                                  'approve',
                                  'Approve quotation',
                                  record,
                                ),
                          child: const Text('Approve quotation'),
                        ),
                        OutlinedButton(
                          onPressed: _changingStatus
                              ? null
                              : () => _changeStatus(
                                  'reject',
                                  'Reject quotation',
                                  record,
                                ),
                          child: const Text('Reject quotation'),
                        ),
                      ],
                    ),
                  if (live &&
                      widget.canManage &&
                      const {'sent', 'approved'}.contains(status))
                    if (record['deal_id'] is int)
                      FilledButton(
                        onPressed: _changingStatus
                            ? null
                            : () => _changeStatus(
                                'accept',
                                'Accept and convert',
                                record,
                              ),
                        child: const Text('Accept and convert'),
                      )
                    else
                      const Text(
                        'Link a CRM deal before converting this quotation.',
                      ),
                  for (final field in fields.entries)
                    if (field.value != null &&
                        field.value.toString().isNotEmpty)
                      ListTile(
                        title: Text(field.key),
                        subtitle: Text('${field.value}'),
                      ),
                  if (lines.isNotEmpty)
                    Text(
                      'Items',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                ],
              );
            }
            final line = lines[index - 1];
            return ListTile(
              title: Text('${line['name'] ?? 'Item'}'),
              subtitle: Text(
                "${line['quantity'] ?? '—'} × ${line['unit_price'] ?? '—'} $currency"
                    .trim(),
              ),
              trailing: Text("${line['line_total'] ?? '—'} $currency".trim()),
            );
          },
        );
      },
    ),
  );
}
