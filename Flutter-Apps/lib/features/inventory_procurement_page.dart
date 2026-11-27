import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import 'inventory_goods_receipt_form.dart';

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
    this.onReceived,
    this.onIssued,
  });

  final ApiClient api;
  final ProcurementRecord kind;
  final Json summary;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;
  final bool canReceive;
  final bool canIssue;
  final VoidCallback? onReceived;
  final VoidCallback? onIssued;

  @override
  State<InventoryProcurementPage> createState() =>
      _InventoryProcurementPageState();
}

class _InventoryProcurementPageState extends State<InventoryProcurementPage> {
  Json? _cached;
  late var _record = _load(offline: widget.offline);
  bool _issuing = false;
  ({String reason, String version, String id})? _issueRequest;

  Iterable<Json> _lines(Json data) =>
      (data['lines'] as List? ?? const []).whereType<Json>();

  void _refresh() => setState(() {
    _record = _load();
  });

  Future<void> _issue() async {
    if (_issuing) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    final path = '/srm/documents/purchase-orders/${widget.summary['id']}';
    setState(() => _issuing = true);
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
      if (document['editable'] != true || document['removed'] == true) {
        _refresh();
        throw ApiFailure('This purchase order is no longer an issuable draft.');
      }
      final version = document['version'] as String;
      final reason = await _issueReason();
      if (reason == null || !mounted || revision != api.sessionRevision) return;
      final previous = _issueRequest;
      final request = previous?.version == version && previous?.reason == reason
          ? previous!
          : (reason: reason, version: version, id: const Uuid().v4());
      _issueRequest = request;
      await api.request(
        'POST',
        '$path/issue',
        scopeHeaders: widget.scopeHeaders,
        data: {
          'version': request.version,
          'reason': request.reason,
          'request_id': request.id,
        },
      );
      if (!mounted || revision != api.sessionRevision) return;
      _issueRequest = null;
      _refresh();
      widget.onIssued?.call();
    } on ApiFailure catch (error) {
      if (mounted && revision == api.sessionRevision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _issuing = false);
    }
  }

  Future<String?> _issueReason() {
    final form = GlobalKey<FormState>();
    var reason = '';
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Issue purchase order'),
        content: Form(
          key: form,
          child: TextFormField(
            maxLines: 3,
            maxLength: 500,
            decoration: const InputDecoration(labelText: 'Reason'),
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
            child: const Text('Confirm issue'),
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
          onReceived: widget.onReceived,
          onIssued: widget.onIssued,
        ),
      ),
    );
  }

  Future<({Json? record, bool live})> _load({bool offline = false}) {
    final kind = widget.kind;
    return loadCrmDetail(
      api: widget.api,
      path: '${kind.path}/${widget.summary['id']}',
      scope: widget.cacheScope,
      headers: widget.scopeHeaders,
      offline: offline,
      onCached: (saved) {
        if (mounted) setState(() => _cached = saved);
      },
      project: (data) => {
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
        final row = data ?? widget.summary;
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
                      onPressed: () => _receive(row),
                      child: const Text('Receive goods'),
                    ),
                  if (canIssue)
                    FilledButton(
                      onPressed: _issuing ? null : _issue,
                      child: const Text('Issue purchase order'),
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
                      onPressed: () => Navigator.of(context).push<void>(
                        MaterialPageRoute(
                          builder: (_) => InventoryProcurementPage(
                            api: widget.api,
                            kind: ProcurementRecord.order,
                            summary: {'id': row['purchase_order_id']},
                            scopeHeaders: widget.scopeHeaders,
                            cacheScope: widget.cacheScope,
                            offline: snapshot.data?.live != true,
                            canReceive: widget.canReceive,
                            canIssue: widget.canIssue,
                            onReceived: widget.onReceived,
                            onIssued: widget.onIssued,
                          ),
                        ),
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
            return ListTile(
              title: Text(
                "${line['description'] ?? line['item_code'] ?? 'Item'}",
              ),
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
