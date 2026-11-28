import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import '../core/suite_pdf.dart';
import 'crm_quotation_line_page.dart';
import 'crm_quotation_draft_page.dart';
import 'commercial_document_history_page.dart';
import 'payment_requests_page.dart';
import 'sales_order_page.dart';

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
    this.canSend = false,
    this.canCreateRevision = false,
    this.canCancel = false,
    this.canViewSalesOrder = false,
    this.onChanged,
  });

  static const endpoint = CrmQuotationDraftPage.endpoint;
  static const fields = [
    'quote_number',
    'issue_date',
    'expiry_date',
    'approval_status',
    'status',
    'version_number',
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
  final bool canSend;
  final bool canCreateRevision;
  final bool canCancel;
  final bool canViewSalesOrder;
  final VoidCallback? onChanged;

  @override
  State<CrmQuotationPage> createState() => _CrmQuotationPageState();
}

class _CrmQuotationPageState extends State<CrmQuotationPage> {
  Json? _cached;
  bool _savingPdf = false;
  bool _changingStatus = false;
  ({String action, String reason, String version, String id})? _documentRequest;
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
            'sent_at',
            'sentVersionNumber',
            'sentVersionEvidence',
          ])
            field: record[field],
          'versions': [
            for (final version
                in (record['versions'] as List? ?? const []).whereType<Json>())
              {
                'version_number': version['version_number'],
                'created_at': version['created_at'],
              },
          ],
          'approvals': [
            for (final approval
                in (record['approvals'] as List? ?? const []).whereType<Json>())
              {
                'status': approval['status'],
                'comments': approval['comments'],
                'decided_at': approval['decided_at'],
              },
          ],
          'lines': [
            for (final line
                in (record['lines'] as List? ?? const []).whereType<Json>())
              {
                for (final field in [
                  'name',
                  'quantity',
                  'unit_price',
                  'line_total',
                  'discount_amount',
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

  String get _documentPath =>
      '/srm/documents/quotations/${widget.summary['id']}';

  Future<void> _openQuotation(Json record, {required bool offline}) =>
      Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => CrmQuotationPage(
            api: widget.api,
            summary: record,
            offline: offline,
            scopeHeaders: widget.scopeHeaders,
            cacheScope: widget.cacheScope,
            canManage: widget.canManage,
            canApprove: widget.canApprove,
            canSend: widget.canSend,
            canCreateRevision: widget.canCreateRevision,
            canCancel: widget.canCancel,
            canViewSalesOrder: widget.canViewSalesOrder,
            onChanged: widget.onChanged,
          ),
        ),
      );

  void _openDocumentHistory({required bool offline}) =>
      Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => CommercialDocumentHistoryPage(
            api: widget.api,
            path: _documentPath,
            offline: offline,
            scopeHeaders: widget.scopeHeaders,
            cacheScope: widget.cacheScope,
            relatedDocumentTooltip: 'Open related quotation',
            onOpenDocument: (id, offline) =>
                _openQuotation({'id': id}, offline: offline),
          ),
        ),
      );

  Future<void> _actOnDocument({required bool cancel}) async {
    if (_changingStatus) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    final path = _documentPath;
    final headers = widget.scopeHeaders;
    final action = cancel ? 'cancel' : 'revise';
    setState(() => _changingStatus = true);
    try {
      final document = await api.request('GET', path, scopeHeaders: headers);
      if (!mounted || api.sessionRevision != revision) return;
      if (document is! Json ||
          document['removed'] == true ||
          document['version'] is! String ||
          (cancel && document['editable'] == true)) {
        throw ApiFailure(
          'This action is unavailable for the current quotation.',
        );
      }
      final version = document['version'] as String;
      final reason = await _requestDocumentReason(cancel: cancel);
      if (!mounted || reason == null || api.sessionRevision != revision) return;
      final previous = _documentRequest;
      final request =
          previous?.action == action &&
              previous?.reason == reason &&
              previous?.version == version
          ? previous!
          : (
              action: action,
              reason: reason,
              version: version,
              id: const Uuid().v4(),
            );
      _documentRequest = request;
      final result = await api.request(
        'POST',
        '$path/$action',
        scopeHeaders: headers,
        data: {
          'reason': request.reason,
          'version': request.version,
          'request_id': request.id,
        },
      );
      if (!mounted || api.sessionRevision != revision) return;
      final record = result is Json ? result['record'] : null;
      if (record is! Json || record['id'] is! int) {
        throw ApiFailure(
          'The quotation change could not be confirmed. Try again.',
        );
      }
      _documentRequest = null;
      widget.onChanged?.call();
      if (cancel) {
        _refresh();
        return;
      }
      await _openQuotation(record, offline: false);
    } on ApiFailure catch (error) {
      if (mounted && api.sessionRevision == revision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _changingStatus = false);
    }
  }

  Future<String?> _requestDocumentReason({required bool cancel}) {
    final form = GlobalKey<FormState>();
    var reason = '';
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(cancel ? 'Cancel quotation' : 'Create revision draft'),
        content: Form(
          key: form,
          child: TextFormField(
            decoration: InputDecoration(
              labelText: 'Reason',
              helperText: cancel
                  ? 'The quotation stays in the register as cancelled.'
                  : 'The original stays in the register.',
            ),
            maxLength: 500,
            maxLines: 3,
            onChanged: (value) => reason = value.trim(),
            validator: (_) =>
                reason.length < 5 ? 'Enter at least five characters.' : null,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              if (form.currentState!.validate()) Navigator.pop(context, reason);
            },
            child: Text(
              cancel ? 'Confirm cancellation' : 'Create revised draft',
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _editLine({required String? currency, Json? line}) async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => CrmQuotationLinePage(
          api: widget.api,
          quoteId: widget.summary['id'] as int,
          scopeHeaders: widget.scopeHeaders,
          line: line,
          currency: currency,
        ),
      ),
    );
    if (!mounted || saved != true) return;
    _refresh();
    widget.onChanged?.call();
  }

  Future<void> _editQuote(Json quote) async {
    final result = await Navigator.of(context).push<Json>(
      MaterialPageRoute(
        builder: (_) => CrmQuotationDraftPage(
          api: widget.api,
          quote: {...quote, 'id': widget.summary['id']},
          scopeHeaders: widget.scopeHeaders,
        ),
      ),
    );
    if (!mounted || result == null) return;
    _refresh();
    widget.onChanged?.call();
  }

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
            if (action == 'send')
              'This generates the PDF and marks the quotation as Sent.',
            if (action == 'new-version')
              'This keeps the current version in history and starts a new draft for approval.',
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
    if (!mounted ||
        confirmed != true ||
        _changingStatus ||
        api.sessionRevision != revision) {
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
        FutureBuilder<({Json? record, bool live})>(
          future: _quote,
          builder: (context, snapshot) => IconButton(
            tooltip: 'Document history',
            icon: const Icon(Icons.history),
            onPressed:
                snapshot.connectionState == ConnectionState.done &&
                    !snapshot.hasError
                ? () =>
                      _openDocumentHistory(offline: snapshot.data?.live != true)
                : null,
          ),
        ),
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
        final approval = record['approval_status']?.toString().toLowerCase();
        final readyToSend =
            (status == 'approved' || approval == 'not_required') &&
            !const {
              'sent',
              'accepted',
              'declined',
              'converted',
            }.contains(status);
        final canEditLines =
            live &&
            widget.canManage &&
            const {'draft', 'rejected'}.contains(status);
        final currency = record['currency'] ?? '';
        final amount = record['grand_total'] ?? record['total_amount'];
        final fields = {
          'Status': record['status'],
          'Version': record['version_number'],
          'Marked sent': record['sent_at'],
          'Sent version': record['sentVersionNumber'],
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
        final versions = (record['versions'] as List? ?? const [])
            .whereType<Json>();
        final approvals = (record['approvals'] as List? ?? const [])
            .whereType<Json>();
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
                  if (live && widget.canManage)
                    if (widget.summary['id'] case final int id)
                      PaymentRequestButton(
                        api: widget.api,
                        sourceType: 'crm_quotation',
                        sourceId: id,
                        scopeHeaders: widget.scopeHeaders,
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
                  if (live && widget.canSend && readyToSend)
                    FilledButton(
                      onPressed: _changingStatus
                          ? null
                          : () => _changeStatus(
                              'send',
                              'Mark quotation as sent',
                              record,
                            ),
                      child: const Text('Mark quotation as sent'),
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
                  if (record['sentVersionEvidence'] case final String evidence)
                    Text(evidence),
                  if (versions.isNotEmpty || approvals.isNotEmpty)
                    ExpansionTile(
                      title: const Text('Version and approval history'),
                      children: [
                        for (final version in versions)
                          ListTile(
                            title: Text('Version ${version['version_number']}'),
                            subtitle: Text('${version['created_at'] ?? ''}'),
                          ),
                        for (final approval in approvals)
                          ListTile(
                            title: Text('Approval · ${approval['status']}'),
                            subtitle: Text(
                              [approval['decided_at'], approval['comments']]
                                  .whereType<String>()
                                  .where((s) => s.isNotEmpty)
                                  .join('\n'),
                            ),
                          ),
                      ],
                    ),
                  if (canEditLines)
                    OutlinedButton(
                      onPressed: _changingStatus
                          ? null
                          : () => _changeStatus(
                              'new-version',
                              'Create new version',
                              record,
                            ),
                      child: const Text('Create new version'),
                    ),
                  if (live &&
                      widget.canCreateRevision &&
                      !const {'deleted', 'archived'}.contains(status))
                    OutlinedButton(
                      onPressed: _changingStatus
                          ? null
                          : () => _actOnDocument(cancel: false),
                      child: const Text('Create revision draft'),
                    ),
                  if (live &&
                      widget.canCancel &&
                      record['converted_srm_sales_order_id'] == null &&
                      const {
                        'pending approval',
                        'approved',
                        'sent',
                        'accepted',
                      }.contains(status))
                    OutlinedButton(
                      onPressed: _changingStatus
                          ? null
                          : () => _actOnDocument(cancel: true),
                      child: const Text('Cancel with reason'),
                    ),
                  if (widget.canViewSalesOrder &&
                      record['converted_srm_sales_order_id'] is int)
                    OutlinedButton(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => SalesOrderPage(
                            api: widget.api,
                            summary: {
                              'id': record['converted_srm_sales_order_id'],
                            },
                            offline: !live,
                            cacheScope: widget.cacheScope,
                            scopeHeaders: widget.scopeHeaders,
                          ),
                        ),
                      ),
                      child: const Text('Open sales order'),
                    ),
                  if (lines.isNotEmpty)
                    Text(
                      'Items',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  if (canEditLines)
                    OutlinedButton(
                      onPressed: _changingStatus
                          ? null
                          : () => _editQuote(record),
                      child: const Text('Edit quotation'),
                    ),
                  if (canEditLines)
                    OutlinedButton.icon(
                      onPressed: _changingStatus
                          ? null
                          : () => _editLine(
                              currency: record['currency'] as String?,
                            ),
                      icon: const Icon(Icons.add),
                      label: const Text('Add item'),
                    ),
                ],
              );
            }
            final line = lines[index - 1];
            final discount = num.tryParse('${line['discount_amount'] ?? ''}');
            return ListTile(
              title: Text('${line['name'] ?? 'Item'}'),
              subtitle: Text(
                [
                  "${line['quantity'] ?? '—'} × ${line['unit_price'] ?? '—'} $currency"
                      .trim(),
                  if (discount != null && discount > 0)
                    'Discount $discount $currency'.trim(),
                ].join('\n'),
              ),
              trailing: Text("${line['line_total'] ?? '—'} $currency".trim()),
              onTap: canEditLines && !_changingStatus && line['id'] is int
                  ? () => _editLine(
                      currency: record['currency'] as String?,
                      line: line,
                    )
                  : null,
            );
          },
        );
      },
    ),
  );
}
