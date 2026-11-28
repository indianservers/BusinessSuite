import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class PaymentRequestsPage extends StatefulWidget {
  const PaymentRequestsPage({
    super.key,
    required this.api,
    required this.sourceType,
    required this.sourceId,
    required this.scopeHeaders,
  });

  final ApiClient api;
  final String sourceType;
  final int sourceId;
  final Map<String, String> scopeHeaders;

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
  late var _records = _load();

  Future<({Json context, List<Json> items})> _load() async {
    final revision = widget.api.sessionRevision;
    final result = await Future.wait([
      for (final path in ['$_path/context', _path])
        widget.api.request(
          'GET',
          path,
          query: _source,
          scopeHeaders: widget.scopeHeaders,
        ),
    ]);
    if (revision != widget.api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    return (
      context: result.first as Json,
      items: (result.last['items'] as List).cast<Json>(),
    );
  }

  void _refresh() => setState(() {
    _records = _load();
  });

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
      _notice = null;
    });
    try {
      await widget.api.request(
        'POST',
        _path,
        scopeHeaders: widget.scopeHeaders,
        data: {
          ..._source,
          'request_id': _requestId,
          'amount': _amount.text.trim(),
          'instructions': _instructions.text.trim(),
        },
      );
      if (!mounted || revision != widget.api.sessionRevision) return;
      _requestId = const Uuid().v4();
      _amount.clear();
      _instructions.clear();
      _notice = 'Payment request saved.';
      _refresh();
    } on ApiFailure catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _error = '$error');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
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
        final source = data.context;
        final available = num.tryParse('${source['available_amount']}') ?? 0;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${source['reference']}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(
              'Available to request · ${source['currency']} ${source['available_amount']}',
            ),
            if (source['payable'] == true && available > 0)
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
            if (data.items.isEmpty) const Text('No payment requests yet'),
            for (final item in data.items)
              ListTile(
                title: Text('${item['currency']} ${item['amount']}'),
                subtitle: Text(
                  [
                    '${item['status']}'.replaceAll('_', ' '),
                    '${item['request_id']}',
                    if (item['instructions'] case final String text
                        when text.isNotEmpty)
                      text,
                  ].join('\n'),
                ),
              ),
          ],
        );
      },
    ),
  );
}
