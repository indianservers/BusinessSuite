import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';

Future<({Json record, bool live})> _readPaymentSnapshot({
  required ApiClient api,
  required String? key,
  required bool offline,
  required Future<Json> Function() load,
  required Json Function(Json) project,
}) async {
  final revision = api.sessionRevision;
  if (!offline) {
    try {
      final record = await load();
      if (revision == api.sessionRevision && key != null) {
        try {
          await SuiteReadCache.write(key, [project(record)]);
        } catch (_) {
          // The live payment information is already available.
        }
      }
      if (revision != api.sessionRevision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      return (record: record, live: true);
    } on ApiFailure catch (error) {
      if (const {401, 403, 404}.contains(error.status) && key != null) {
        try {
          await SuiteReadCache.clear(key);
        } catch (_) {}
      }
      if (key == null ||
          (!error.connectionFailure && (error.status ?? 0) < 500)) {
        rethrow;
      }
    }
  }
  final saved = key == null
      ? null
      : (await SuiteReadCache.read(key))?.firstOrNull;
  if (revision != api.sessionRevision) {
    throw ApiFailure('Your session ended. Sign in again.', 401);
  }
  if (saved == null) {
    throw ApiFailure('No payment information saved on this device.');
  }
  return (record: saved, live: false);
}

String? _paymentCacheKey(
  String? scope,
  Map<String, String> headers,
  String resource,
) => scope == null
    ? null
    : "$scope:payments:${headers['X-Suite-Branch'] ?? ''}:$resource";

enum _PaymentSource {
  invoice('srm_invoice', 'Issued invoice', '/srm/business/collection-invoices'),
  order('srm_order', 'Sales / POS order', '/srm/sales-orders'),
  deal('crm_deal', 'CRM deal', '/crm/deals'),
  quotation('crm_quotation', 'CRM quotation', '/crm/quotations');

  const _PaymentSource(this.key, this.label, this.endpoint);
  final String key;
  final String label;
  final String endpoint;
}

class PaymentSourceDirectory extends StatefulWidget {
  const PaymentSourceDirectory({
    super.key,
    required this.api,
    required this.scopeHeaders,
    this.crm = false,
    this.cacheScope,
    this.offline = false,
  });

  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final bool crm;
  final String? cacheScope;
  final bool offline;

  @override
  State<PaymentSourceDirectory> createState() => _PaymentSourceDirectoryState();
}

class _PaymentSourceDirectoryState extends State<PaymentSourceDirectory> {
  late final _sources = widget.crm
      ? const [_PaymentSource.deal, _PaymentSource.quotation]
      : const [_PaymentSource.invoice, _PaymentSource.order];
  late var _source = _sources.first;
  late var _offline = widget.offline;
  final _search = TextEditingController();
  late var _records = _load(offline: widget.offline);

  Future<({Json record, bool live})> _load({bool offline = false}) {
    final source = _source;
    return _readPaymentSnapshot(
      api: widget.api,
      key: _paymentCacheKey(
        widget.cacheScope,
        widget.scopeHeaders,
        'sources:${source.key}',
      ),
      offline: offline,
      load: () async => {'items': await _loadSources(source)},
      project: (record) => {
        'items': [
          for (final row in (record['items'] as List).cast<Json>())
            {
              for (final field in [
                'id',
                'invoice_number',
                'order_number',
                'quote_number',
                'name',
                'title',
              ])
                if (row.containsKey(field)) field: row[field],
            },
        ],
      },
    );
  }

  Future<List<Json>> _loadSources(_PaymentSource source) async {
    final result = await widget.api.request(
      'GET',
      source.endpoint,
      query: {
        'per_page': 100,
        if (source == _PaymentSource.order) 'summary_only': true,
      },
      scopeHeaders: widget.scopeHeaders,
    );
    final rows = (result is List ? result : result['items']) as List;
    return [
      for (final row in rows.cast<Json>())
        if (source != _PaymentSource.invoice ||
            row['document_status'] == 'issued')
          row,
    ];
  }

  void _refresh({bool offline = false}) => setState(() {
    _offline = offline;
    _records = _load(offline: offline);
  });

  String _label(Json row) =>
      '${row['invoice_number'] ?? row['order_number'] ?? row['quote_number'] ?? row['name'] ?? row['title'] ?? "Record #${row['id']}"}';

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Payment requests')),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              DropdownButtonFormField<_PaymentSource>(
                initialValue: _source,
                decoration: const InputDecoration(labelText: 'Payment source'),
                items: [
                  for (final source in _sources)
                    DropdownMenuItem(value: source, child: Text(source.label)),
                ],
                onChanged: (source) {
                  if (source == null || _source == source) return;
                  _source = source;
                  _search.clear();
                  _refresh(offline: _offline);
                },
              ),
              TextField(
                controller: _search,
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search),
                  labelText: 'Find payment source',
                ),
                onChanged: (_) => setState(() {}),
              ),
            ],
          ),
        ),
        Expanded(
          child: FutureBuilder(
            future: _records,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return ListTile(
                  title: Text('${snapshot.error}'),
                  trailing: TextButton(
                    onPressed: _refresh,
                    child: const Text('Retry'),
                  ),
                );
              }
              final saved = !snapshot.data!.live;
              final query = _search.text.trim().toLowerCase();
              final matches = (snapshot.data!.record['items'] as List)
                  .cast<Json>()
                  .where(
                    (row) =>
                        row['id'] is int &&
                        '${_label(row)} ${row['title'] ?? ''} ${row['name'] ?? ''}'
                            .toLowerCase()
                            .contains(query),
                  )
                  .toList();
              if (matches.isEmpty) {
                return const Center(child: Text('No matching records'));
              }
              final source = _source;
              return ListView.builder(
                itemCount: matches.length + (saved ? 1 : 0),
                itemBuilder: (context, index) {
                  if (saved && index == 0) {
                    return ListTile(
                      title: const Text('Saved payment sources'),
                      trailing: TextButton(
                        onPressed: _refresh,
                        child: const Text('Reconnect'),
                      ),
                    );
                  }
                  final row = matches[index - (saved ? 1 : 0)];
                  return ListTile(
                    title: Text(_label(row)),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => PaymentRequestsPage(
                          api: widget.api,
                          sourceType: source.key,
                          sourceId: row['id'] as int,
                          scopeHeaders: widget.scopeHeaders,
                          cacheScope: widget.cacheScope,
                          offline: saved,
                        ),
                      ),
                    ),
                  );
                },
              );
            },
          ),
        ),
      ],
    ),
  );
}

class PaymentRequestButton extends StatelessWidget {
  const PaymentRequestButton({
    super.key,
    required this.api,
    required this.sourceType,
    required this.sourceId,
    required this.scopeHeaders,
    this.cacheScope,
  });

  final ApiClient api;
  final String sourceType;
  final int sourceId;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
    icon: const Icon(Icons.payments_outlined),
    label: const Text('Request payment'),
    onPressed: () => Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PaymentRequestsPage(
          api: api,
          sourceType: sourceType,
          sourceId: sourceId,
          scopeHeaders: scopeHeaders,
          cacheScope: cacheScope,
        ),
      ),
    ),
  );
}

class PaymentRequestsPage extends StatefulWidget {
  const PaymentRequestsPage({
    super.key,
    required this.api,
    required this.sourceType,
    required this.sourceId,
    required this.scopeHeaders,
    this.cacheScope,
    this.offline = false,
  });

  final ApiClient api;
  final String sourceType;
  final int sourceId;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;

  @override
  State<PaymentRequestsPage> createState() => _PaymentRequestsPageState();
}

class _PaymentRequestsPageState extends State<PaymentRequestsPage> {
  static const _path = '/payment-requests';
  final _form = GlobalKey<FormState>();
  final _amount = TextEditingController();
  final _instructions = TextEditingController();
  var _requestId = const Uuid().v4();
  bool _saving = false;
  String? _error;
  String? _notice;
  Json get _source => {
    'source_type': widget.sourceType,
    'source_id': widget.sourceId,
  };
  late var _records = _load(offline: widget.offline);

  Future<({Json record, bool live})> _load({bool offline = false}) =>
      _readPaymentSnapshot(
        api: widget.api,
        key: _paymentCacheKey(
          widget.cacheScope,
          widget.scopeHeaders,
          '${widget.sourceType}:${widget.sourceId}',
        ),
        offline: offline,
        load: _loadLive,
        project: (record) => {
          'context': {'reference': record['context']['reference']},
          'items': [
            for (final row in (record['items'] as List).cast<Json>())
              {
                for (final field in [
                  'currency',
                  'amount',
                  'status',
                  'request_id',
                ])
                  field: row[field],
              },
          ],
        },
      );

  Future<Json> _loadLive() async {
    final result = await Future.wait([
      for (final path in ['$_path/context', _path])
        widget.api.request(
          'GET',
          path,
          query: _source,
          scopeHeaders: widget.scopeHeaders,
        ),
    ]);
    return {
      'context': result.first as Json,
      'items': result.last['items'] as List,
    };
  }

  void _refresh() => setState(() {
    _records = _load();
  });

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    await _post(
      _path,
      notice: 'Payment request saved.',
      data: {
        ..._source,
        'request_id': _requestId,
        'amount': _amount.text.trim(),
        'instructions': _instructions.text.trim(),
      },
    );
  }

  Future<void> _post(String path, {required String notice, Json? data}) async {
    if (_saving) return;
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
      _notice = null;
    });
    try {
      await widget.api.request(
        'POST',
        path,
        scopeHeaders: widget.scopeHeaders,
        data: data,
      );
      if (!mounted || revision != widget.api.sessionRevision) return;
      if (data != null) {
        _requestId = const Uuid().v4();
        _amount.clear();
        _instructions.clear();
      }
      _notice = notice;
      _refresh();
    } on ApiFailure catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _error = '$error');
        if (data == null) _refresh();
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _cancel(int id) async {
    final revision = widget.api.sessionRevision;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel payment request?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep request'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Cancel request'),
          ),
        ],
      ),
    );
    if (!mounted ||
        confirmed != true ||
        revision != widget.api.sessionRevision) {
      return;
    }
    await _post('$_path/$id/cancel', notice: 'Payment request cancelled.');
  }

  Future<void> _copy(Json item) async {
    final url = Uri.tryParse('${item['payment_url'] ?? ''}');
    final instructions = item['instructions'];
    try {
      await Clipboard.setData(
        ClipboardData(
          text: [
            'Please arrange payment of ${item['currency']} ${item['amount']} for ${item['reference']}.',
            'Payment request reference: ${item['request_id']}',
            if (url != null && url.scheme == 'https' && url.host.isNotEmpty)
              'Pay securely: $url',
            if (instructions is String && instructions.isNotEmpty) instructions,
          ].join('\n'),
        ),
      );
      if (mounted) setState(() => _notice = 'Payment request text copied.');
    } on PlatformException {
      if (mounted) {
        setState(() => _error = 'Could not copy the payment request.');
      }
    }
  }

  Widget _requestCard(Json item, Json source, {required bool connected}) {
    final status = item['status'];
    final active = !const {
      'cancelled',
      'expired',
      'gateway_paid',
      'receipt_recorded',
    }.contains(status);
    final hasLink =
        item['payment_url'] is String &&
        (item['payment_url'] as String).isNotEmpty;
    final id = item['id'];
    final receipt = item['receipt_id'];
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            title: Text('${item['currency']} ${item['amount']}'),
            subtitle: Text(
              [
                switch (status) {
                  'gateway_paid' => 'Gateway reports paid · receipt pending',
                  'receipt_recorded' => 'Matched to recorded receipt',
                  _ => '$status'.replaceAll('_', ' '),
                },
                '${item['request_id']}',
                if (item['instructions'] case final String text
                    when text.isNotEmpty)
                  text,
              ].join('\n'),
            ),
          ),
          if (id is int)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Wrap(
                spacing: 8,
                children: [
                  if (active && !hasLink && connected)
                    TextButton(
                      onPressed: _saving
                          ? null
                          : () => _post(
                              '$_path/$id/link',
                              notice: 'Payment link updated.',
                            ),
                      child: Text(
                        const {
                              'creating_link',
                              'reconciliation_required',
                            }.contains(status)
                            ? 'Reconcile original link'
                            : 'Generate payment link',
                      ),
                    ),
                  if (active)
                    TextButton(
                      onPressed: _saving ? null : () => _copy(item),
                      child: const Text('Copy request text'),
                    ),
                  if (active && status != 'partially_paid')
                    TextButton(
                      onPressed: _saving ? null : () => _cancel(id),
                      child: const Text('Cancel request'),
                    ),
                  if (hasLink && connected && receipt == null)
                    TextButton(
                      onPressed: _saving
                          ? null
                          : () => _post(
                              '$_path/$id/refresh',
                              notice: 'Provider status checked.',
                            ),
                      child: const Text('Check provider status'),
                    ),
                  if (receipt == null && source['can_match_receipt'] == true)
                    TextButton(
                      onPressed: _saving
                          ? null
                          : () => _post(
                              '$_path/$id/reconcile-receipt',
                              notice: 'Recorded receipt matched.',
                            ),
                      child: const Text('Match recorded receipt'),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _amount.dispose();
    _instructions.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Payment requests'),
      actions: [
        IconButton(
          tooltip: 'Refresh payment requests',
          onPressed: _saving ? null : _refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder(
      future: _records,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final data = snapshot.data!;
        final source = data.record['context'] as Json;
        final items = (data.record['items'] as List).cast<Json>();
        final gateway = source['gateway'] as Json?;
        final connected = gateway?['connected'] == true;
        final available = num.tryParse('${source['available_amount']}') ?? 0;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${source['reference']}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (!data.live)
              const Text('Saved payment requests · Refresh to reconnect')
            else if (!connected)
              const Text('No online payment gateway connected.')
            else if (gateway?['test_mode'] == true)
              const Text('Gateway test mode'),
            if (data.live)
              Text(
                'Available to request · ${source['currency']} ${source['available_amount']}',
              ),
            if (data.live && source['payable'] == true && available > 0)
              Form(
                key: _form,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextFormField(
                      controller: _amount,
                      enabled: !_saving,
                      decoration: const InputDecoration(
                        labelText: 'Amount to request',
                      ),
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      validator: (value) {
                        final amount = value?.trim() ?? '';
                        if (!RegExp(
                          r'^\d{1,12}(\.\d{1,2})?$',
                        ).hasMatch(amount)) {
                          return 'Enter an amount with up to two decimal places.';
                        }
                        final number = num.parse(amount);
                        if (number <= 0 || number > available) {
                          return 'Enter an amount within the available balance.';
                        }
                        return null;
                      },
                    ),
                    TextFormField(
                      controller: _instructions,
                      enabled: !_saving,
                      maxLength: 2000,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        labelText: 'Payment instructions',
                      ),
                    ),
                    FilledButton(
                      onPressed: _saving ? null : _save,
                      child: Text(_saving ? 'Saving…' : 'Save payment request'),
                    ),
                  ],
                ),
              )
            else if (source['guidance'] case final String guidance)
              Text(guidance),
            if (_notice case final String notice) Text(notice),
            if (_error case final String error) Text(error),
            const Divider(),
            if (items.isEmpty) const Text('No payment requests yet'),
            for (final item in items)
              _requestCard(item, source, connected: connected),
          ],
        );
      },
    ),
  );
}
