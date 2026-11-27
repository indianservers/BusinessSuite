import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import '../core/suite_pdf.dart';
import 'commercial_document_history_page.dart';
import 'inventory_goods_receipt_form.dart';

enum _OrderAction {
  issue('Issue purchase order', 'Confirm issue'),
  revise('Create revision draft', 'Create revised draft'),
  cancel('Cancel purchase order', 'Confirm cancellation'),
  edit('Modify draft with reason', 'Save draft changes'),
  archive('Archive purchase order draft', 'Confirm archive');

  const _OrderAction(this.title, this.confirm);
  final String title, confirm;
}

enum ProcurementRecord {
  order(
    'Purchase orders',
    '/srm/procurement/purchase-orders',
    'po_number',
    {'order_date': 'Order date', 'expected_date': 'Expected date'},
    {'received_quantity': 'Received'},
  ),
  receipt(
    'Goods receipts',
    '/srm/procurement/grn',
    'grn_number',
    {
      'receipt_date': 'Receipt date',
      'reference_number': 'Reference',
      'purchase_order_id': 'Purchase order',
    },
    {'accepted_quantity': 'Accepted', 'rejected_quantity': 'Rejected'},
  );

  const ProcurementRecord(
    this.title,
    this.path,
    this.number,
    this.headerFields,
    this.receiptQuantities,
  );
  final String title, path, number;
  final Map<String, String> headerFields, receiptQuantities;

  Map<String, String> get fields => {
    'vendor_name': 'Supplier',
    'status': 'Status',
    ...headerFields,
    'subtotal': 'Subtotal',
    'tax_amount': 'Tax',
    'total_amount': 'Total',
    'notes': 'Notes',
  };

  Map<String, String> get lineFields => {
    'quantity': 'Quantity',
    ...receiptQuantities,
    'unit_price': 'Unit price',
    'tax_amount': 'Tax',
    'line_total': 'Total',
  };
}

class InventoryProcurementPage extends StatefulWidget {
  const InventoryProcurementPage({
    super.key,
    required this.api,
    required this.kind,
    required this.summary,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
    this.canReceive = false,
    this.canIssue = false,
    this.canExport = false,
    this.canArchive = false,
    this.archived = false,
    this.onReceived,
    this.onOrderChanged,
  });

  final ApiClient api;
  final ProcurementRecord kind;
  final Json summary;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;
  final bool canReceive;
  final bool canIssue;
  final bool canExport;
  final bool canArchive, archived;
  final VoidCallback? onReceived;
  final VoidCallback? onOrderChanged;

  @override
  State<InventoryProcurementPage> createState() =>
      _InventoryProcurementPageState();
}

class _InventoryProcurementPageState extends State<InventoryProcurementPage> {
  Json? _cached;
  late var _record = _load(offline: widget.offline);
  bool _changingOrder = false;
  bool _savingPdf = false;
  late bool _archived = widget.archived;
  final _requests =
      <
        _OrderAction,
        ({
          String reason,
          String version,
          String id,
          Json changes,
          List<Json>? lines,
        })
      >{};

  Iterable<Json> _lines(Json data) =>
      (data['lines'] as List? ?? const []).whereType<Json>();

  void _refresh() => setState(() {
    _record = _load();
  });

  String get _documentPath =>
      '/srm/documents/purchase-orders/${widget.summary['id']}';

  void _openOrder(int id, bool offline) => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) => InventoryProcurementPage(
        api: widget.api,
        kind: ProcurementRecord.order,
        summary: {'id': id},
        scopeHeaders: widget.scopeHeaders,
        cacheScope: widget.cacheScope,
        offline: offline,
        canReceive: widget.canReceive,
        canIssue: widget.canIssue,
        canExport: widget.canExport,
        canArchive: widget.canArchive,
        onReceived: widget.onReceived,
        onOrderChanged: widget.onOrderChanged,
      ),
    ),
  );

  void _openHistory({required bool offline}) =>
      Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => CommercialDocumentHistoryPage(
            api: widget.api,
            path: _documentPath,
            offline: offline,
            scopeHeaders: widget.scopeHeaders,
            cacheScope: widget.cacheScope,
            relatedDocumentTooltip: 'Open related purchase order',
            onOpenDocument: _openOrder,
          ),
        ),
      );

  Future<void> _savePdf(Json order) async {
    if (_savingPdf) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    setState(() => _savingPdf = true);
    try {
      final bytes = await fetchSuitePdf(
        api,
        '$_documentPath/pdf',
        scopeHeaders: widget.scopeHeaders,
      );
      if (!mounted || revision != api.sessionRevision) return;
      final number = '${order['po_number'] ?? widget.summary['id']}'.replaceAll(
        RegExp(r'[^A-Za-z0-9._-]'),
        '_',
      );
      final saved = await FilePicker.saveFile(
        fileName: 'Purchase-order-$number.pdf',
        bytes: bytes,
      );
      if (mounted && saved != null && revision == api.sessionRevision) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Purchase order PDF saved.')),
        );
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

  Future<void> _changeOrder(_OrderAction action, {int? lineId}) async {
    if (_changingOrder) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    final path = _documentPath;
    setState(() => _changingOrder = true);
    try {
      final document = await api.request(
        'GET',
        path,
        scopeHeaders: widget.scopeHeaders,
      );
      if (!mounted || revision != api.sessionRevision) return;
      if (document is! Json || document['version'] is! String) {
        throw ApiFailure('The purchase order version is unavailable.');
      }
      if (document['removed'] == true ||
          ((action == _OrderAction.issue ||
                  action == _OrderAction.edit ||
                  action == _OrderAction.archive) &&
              document['editable'] != true) ||
          (action == _OrderAction.cancel && document['editable'] != false)) {
        _refresh();
        throw ApiFailure(
          'This action is unavailable for the current purchase order.',
        );
      }
      final version = document['version'] as String;
      final record = document['record'];
      if (action == _OrderAction.edit && record is! Json) {
        throw ApiFailure('The draft details are unavailable.');
      }
      final input = await _actionInput(
        action,
        record is Json ? record : const {},
        lineId: lineId,
      );
      if (input == null || !mounted || revision != api.sessionRevision) return;
      final previous = _requests[action];
      final request =
          previous?.version == version &&
              previous?.reason == input.reason &&
              mapEquals(previous?.changes, input.changes) &&
              jsonEncode(previous?.lines) == jsonEncode(input.lines)
          ? previous!
          : (
              reason: input.reason,
              version: version,
              id: const Uuid().v4(),
              changes: input.changes,
              lines: input.lines,
            );
      _requests[action] = request;
      final response = await api.request(
        switch (action) {
          _OrderAction.edit => 'PATCH',
          _OrderAction.archive => 'DELETE',
          _ => 'POST',
        },
        action == _OrderAction.edit || action == _OrderAction.archive
            ? path
            : '$path/${action.name}',
        scopeHeaders: widget.scopeHeaders,
        data: {
          'version': request.version,
          'reason': request.reason,
          'request_id': request.id,
          if (action == _OrderAction.edit) 'changes': request.changes,
          if (request.lines != null) 'lines': request.lines,
        },
      );
      if (!mounted || revision != api.sessionRevision) return;
      int? revisedId;
      if (action == _OrderAction.revise) {
        final draft = response is Json ? response['record'] : null;
        if (draft is! Json || draft['id'] is! int) {
          throw ApiFailure('The revision could not be confirmed. Try again.');
        }
        revisedId = draft['id'] as int;
      }
      _requests.remove(action);
      if (action == _OrderAction.archive) _archived = true;
      _refresh();
      widget.onOrderChanged?.call();
      if (revisedId != null) _openOrder(revisedId, false);
    } on ApiFailure catch (error) {
      if (mounted && revision == api.sessionRevision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _changingOrder = false);
    }
  }

  Future<({String reason, Json changes, List<Json>? lines})?> _actionInput(
    _OrderAction action,
    Json record, {
    int? lineId,
  }) {
    final form = GlobalKey<FormState>();
    var reason = '';
    final editing = action == _OrderAction.edit && lineId == null;
    final orderLines = _lines(record).toList();
    final selected = orderLines
        .where((line) => line['id'] == lineId)
        .firstOrNull;
    if (lineId != null && selected == null) {
      throw ApiFailure('This line has changed. Refresh before editing.');
    }
    const labels = {
      'description': 'Description',
      'quantity': 'Quantity',
      'unit_price': 'Unit price',
      'tax_amount': 'Tax amount',
    };
    final values = {
      if (selected != null)
        for (final key in labels.keys) key: '${selected[key] ?? ''}',
    };
    final original = Map<String, String>.of(values);
    final existingDate = record['expected_date']?.toString() ?? '';
    final existingNotes = record['notes']?.toString() ?? '';
    var date = existingDate;
    var notes = existingNotes;
    return showDialog<({String reason, Json changes, List<Json>? lines})>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(lineId == null ? action.title : 'Modify draft item'),
        scrollable: true,
        content: Form(
          key: form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (editing) ...[
                TextFormField(
                  initialValue: existingDate,
                  decoration: const InputDecoration(
                    labelText: 'Expected date',
                    hintText: 'YYYY-MM-DD',
                  ),
                  onChanged: (value) => date = value.trim(),
                  validator: (_) {
                    if (date.isEmpty) return null;
                    final parsed = DateTime.tryParse(date);
                    return parsed?.toIso8601String().split('T').first == date
                        ? null
                        : 'Enter a valid date as YYYY-MM-DD.';
                  },
                ),
                TextFormField(
                  initialValue: existingNotes,
                  decoration: const InputDecoration(labelText: 'Notes'),
                  maxLines: 4,
                  maxLength: 10000,
                  onChanged: (value) => notes = value,
                ),
              ],
              for (final field in original.entries)
                TextFormField(
                  initialValue: field.value,
                  decoration: InputDecoration(labelText: labels[field.key]),
                  maxLength: field.key == 'description' ? 2000 : null,
                  keyboardType: field.key == 'description'
                      ? null
                      : const TextInputType.numberWithOptions(decimal: true),
                  onChanged: (value) => values[field.key] = value.trim(),
                  validator: (_) {
                    final text = values[field.key]!;
                    if (field.key == 'description') {
                      return text.isEmpty ? 'Enter a line description.' : null;
                    }
                    final value = num.tryParse(text);
                    if (value == null || !value.isFinite || value < 0) {
                      return 'Enter a nonnegative number.';
                    }
                    return field.key == 'quantity' &&
                            (value == 0 || value > 1000000)
                        ? 'Enter a quantity above zero and at most one million.'
                        : null;
                  },
                ),
              TextFormField(
                maxLines: 3,
                maxLength: 500,
                decoration: InputDecoration(
                  labelText: 'Reason',
                  helperText: switch (action) {
                    _OrderAction.revise =>
                      'The original remains in the register.',
                    _OrderAction.cancel =>
                      'The order stays in the register as cancelled.',
                    _OrderAction.archive =>
                      'Find this draft under Archived orders.',
                    _OrderAction.issue || _OrderAction.edit => null,
                  },
                ),
                onChanged: (value) => reason = value.trim(),
                validator: (_) => reason.length < 5
                    ? 'Enter at least five characters.'
                    : null,
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
              if (!form.currentState!.validate()) return;
              final changes = <String, dynamic>{
                if (editing && date != existingDate)
                  'expected_date': date.isEmpty ? null : date,
                if (editing && notes != existingNotes) 'notes': notes,
              };
              final lineChanges = <String, dynamic>{
                for (final field in values.entries)
                  if (field.value != original[field.key])
                    field.key: field.value,
              };
              Navigator.pop(
                context,
                action == _OrderAction.edit &&
                        changes.isEmpty &&
                        lineChanges.isEmpty
                    ? null
                    : (
                        reason: reason,
                        changes: changes,
                        lines: lineChanges.isEmpty
                            ? null
                            : [
                                for (final line in orderLines)
                                  {
                                    'id': line['id'],
                                    if (line['id'] == lineId) ...lineChanges,
                                  },
                              ],
                      ),
              );
            },
            child: Text(action.confirm),
          ),
        ],
      ),
    );
  }

  Future<void> _receive(Json order) async {
    final api = widget.api;
    final revision = api.sessionRevision;
    final receipt = await Navigator.of(context).push<Json>(
      MaterialPageRoute(
        builder: (_) => InventoryGoodsReceiptForm(
          api: api,
          order: {...order, 'id': widget.summary['id']},
          scopeHeaders: widget.scopeHeaders,
        ),
      ),
    );
    if (!mounted || receipt == null || api.sessionRevision != revision) return;
    _refresh();
    widget.onReceived?.call();
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => InventoryProcurementPage(
          api: api,
          kind: ProcurementRecord.receipt,
          summary: receipt,
          scopeHeaders: widget.scopeHeaders,
          cacheScope: widget.cacheScope,
          offline: false,
          canReceive: widget.canReceive,
          canIssue: widget.canIssue,
          canExport: widget.canExport,
          canArchive: widget.canArchive,
          onReceived: widget.onReceived,
          onOrderChanged: widget.onOrderChanged,
        ),
      ),
    );
  }

  Future<({Json? record, bool live})> _load({bool offline = false}) {
    final kind = widget.kind;
    final archived = _archived;
    final scope = widget.cacheScope;
    return loadCrmDetail(
      api: widget.api,
      path: archived ? _documentPath : '${kind.path}/${widget.summary['id']}',
      scope: archived && scope != null ? '$scope:archived-order' : scope,
      headers: widget.scopeHeaders,
      offline: offline,
      onCached: (saved) {
        if (mounted) setState(() => _cached = saved);
      },
      project: (payload) {
        final data = archived
            ? payload['record'] as Json? ?? const {}
            : payload;
        final record = {
          for (final key in [kind.number, ...kind.fields.keys]) key: data[key],
          'lines': [
            for (final line in _lines(data))
              {
                for (final key in [
                  'description',
                  'item_code',
                  ...kind.lineFields.keys,
                ])
                  key: line[key],
              },
          ],
        };
        return archived ? {'record': record} : record;
      },
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.kind == ProcurementRecord.order
            ? 'Purchase order'
            : 'Goods receipt',
      ),
      actions: [
        if (widget.kind == ProcurementRecord.order)
          FutureBuilder<({Json? record, bool live})>(
            future: _record,
            builder: (context, snapshot) => IconButton(
              tooltip: 'Document history',
              icon: const Icon(Icons.history),
              onPressed:
                  snapshot.connectionState == ConnectionState.done &&
                      !snapshot.hasError
                  ? () => _openHistory(offline: snapshot.data?.live != true)
                  : null,
            ),
          ),
        IconButton(
          tooltip: 'Refresh record',
          icon: const Icon(Icons.refresh),
          onPressed: _refresh,
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _record,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final kind = widget.kind;
        final data = snapshot.data?.record ?? _cached;
        final archivedRecord = data?['record'];
        final row =
            (_archived
                ? (archivedRecord is Json ? archivedRecord : null)
                : data) ??
            widget.summary;
        final lines = _lines(row).toList();
        final done = snapshot.connectionState == ConnectionState.done;
        final canReceive =
            widget.canReceive &&
            kind == ProcurementRecord.order &&
            done &&
            snapshot.data?.live == true &&
            const {'ordered', 'partially_received'}.contains(row['status']);
        final canIssue =
            widget.canIssue &&
            kind == ProcurementRecord.order &&
            lines.isNotEmpty &&
            done &&
            snapshot.data?.live == true &&
            const {'draft', 'created', 'planned'}.contains(row['status']);
        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: lines.length + 1,
          itemBuilder: (context, index) {
            if (index == 0) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (!done)
                    const LinearProgressIndicator()
                  else if (snapshot.data?.live != true)
                    Text(data == null ? 'Saved summary' : 'Saved record'),
                  Text(
                    '${row[kind.number] ?? 'Procurement record'}',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  if (canReceive)
                    FilledButton(
                      onPressed: _changingOrder ? null : () => _receive(row),
                      child: const Text('Receive goods'),
                    ),
                  if (canIssue)
                    FilledButton(
                      onPressed: _changingOrder
                          ? null
                          : () => _changeOrder(_OrderAction.issue),
                      child: const Text('Issue purchase order'),
                    ),
                  if (widget.canIssue &&
                      kind == ProcurementRecord.order &&
                      done &&
                      snapshot.data?.live == true &&
                      const {
                        'draft',
                        'created',
                        'planned',
                      }.contains(row['status']))
                    OutlinedButton(
                      onPressed: _changingOrder
                          ? null
                          : () => _changeOrder(_OrderAction.edit),
                      child: const Text('Modify draft with reason'),
                    ),
                  if (widget.canArchive &&
                      kind == ProcurementRecord.order &&
                      done &&
                      snapshot.data?.live == true &&
                      const {
                        'draft',
                        'created',
                        'planned',
                      }.contains(row['status']))
                    OutlinedButton(
                      onPressed: _changingOrder
                          ? null
                          : () => _changeOrder(_OrderAction.archive),
                      child: const Text('Archive draft'),
                    ),
                  if (widget.canReceive &&
                      kind == ProcurementRecord.order &&
                      done &&
                      snapshot.data?.live == true &&
                      !const {'deleted', 'archived'}.contains(row['status']))
                    OutlinedButton(
                      onPressed: _changingOrder
                          ? null
                          : () => _changeOrder(_OrderAction.revise),
                      child: const Text('Create revision draft'),
                    ),
                  if (widget.canIssue &&
                      kind == ProcurementRecord.order &&
                      done &&
                      snapshot.data?.live == true &&
                      row['status'] == 'ordered')
                    OutlinedButton(
                      onPressed: _changingOrder
                          ? null
                          : () => _changeOrder(_OrderAction.cancel),
                      child: const Text('Cancel with reason'),
                    ),
                  if (widget.canExport &&
                      kind == ProcurementRecord.order &&
                      done &&
                      snapshot.data?.live == true)
                    OutlinedButton.icon(
                      onPressed: _savingPdf ? null : () => _savePdf(row),
                      icon: const Icon(Icons.picture_as_pdf_outlined),
                      label: Text(
                        _savingPdf
                            ? 'Preparing PDF…'
                            : 'Save purchase order PDF',
                      ),
                    ),
                  for (final field in kind.fields.entries)
                    if (row[field.key] case final Object value)
                      ListTile(
                        title: Text(field.value),
                        subtitle: Text('$value'),
                      ),
                  if (kind == ProcurementRecord.receipt &&
                      row['purchase_order_id'] is int)
                    TextButton(
                      onPressed: () => _openOrder(
                        row['purchase_order_id'] as int,
                        snapshot.data?.live != true,
                      ),
                      child: const Text('Open purchase order'),
                    ),
                  if (lines.isNotEmpty)
                    Text(
                      'Items',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                ],
              );
            }
            final line = lines[index - 1];
            final id = line['id'];
            final name =
                "${line['description'] ?? line['item_code'] ?? 'Item'}";
            return ListTile(
              title: Text(name),
              trailing: canIssue && id is int
                  ? IconButton(
                      tooltip: 'Edit $name',
                      icon: const Icon(Icons.edit_outlined),
                      onPressed: _changingOrder
                          ? null
                          : () => _changeOrder(_OrderAction.edit, lineId: id),
                    )
                  : null,
              subtitle: Text(
                [
                  for (final field in kind.lineFields.entries)
                    if (line[field.key] case final Object value)
                      '${field.value}: $value',
                ].join(' · '),
              ),
            );
          },
        );
      },
    ),
  );
}
