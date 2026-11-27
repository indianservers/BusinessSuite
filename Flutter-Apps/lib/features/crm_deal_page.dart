import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import 'crm_deal_stage_page.dart';

class CrmDealPage extends StatefulWidget {
  const CrmDealPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
    this.canMove = false,
    this.onChanged,
  });

  static const endpoint = '/crm/deal-workspace/query';
  static const summaryFields = [
    'company_name',
    'stage_name',
    'amount',
    'currency',
    'priority',
    'probability',
    'expected_close_date',
  ];
  final ApiClient api;
  final Json summary;
  final bool offline;
  final Map<String, String> scopeHeaders;
  final bool canMove;
  final VoidCallback? onChanged;

  @override
  State<CrmDealPage> createState() => _CrmDealPageState();
}

class _CrmDealPageState extends State<CrmDealPage> {
  late Future<Json?> _deal = widget.offline ? Future.value() : _load();
  Json? _movedStage;

  Future<Json?> _load() async {
    final revision = widget.api.sessionRevision;
    try {
      final record =
          await widget.api.request(
                'GET',
                '/crm/deal-workspace/${widget.summary['id']}/record',
                scopeHeaders: widget.scopeHeaders,
              )
              as Json;
      if (revision != widget.api.sessionRevision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      return record;
    } on ApiFailure catch (error) {
      if (revision == widget.api.sessionRevision &&
          (error.connectionFailure ||
              error.status == 429 ||
              (error.status ?? 0) >= 500)) {
        return null;
      }
      rethrow;
    }
  }

  void _refresh() => setState(() {
    _deal = _load();
  });

  Future<void> _reviewStage() async {
    final stage = await Navigator.of(context).push<Json>(
      MaterialPageRoute(
        builder: (_) => CrmDealStagePage(
          api: widget.api,
          id: widget.summary['id'] as int,
          scopeHeaders: widget.scopeHeaders,
        ),
      ),
    );
    if (!mounted || stage == null) return;
    _movedStage = stage;
    _refresh();
    widget.onChanged?.call();
  }

  Future<void> _edit(Json deal) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => _DealEditPage(
          api: widget.api,
          deal: deal,
          scopeHeaders: widget.scopeHeaders,
        ),
      ),
    );
    if (!mounted || changed != true) return;
    _refresh();
    widget.onChanged?.call();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Deal details'),
      actions: [
        IconButton(
          tooltip: 'Refresh deal',
          icon: const Icon(Icons.refresh),
          onPressed: _refresh,
        ),
      ],
    ),
    body: FutureBuilder<Json?>(
      future: _deal,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${snapshot.error}'),
                TextButton(onPressed: _refresh, child: const Text('Retry')),
              ],
            ),
          );
        }
        final data = snapshot.data ?? widget.summary;
        final movedStageName = _movedStage?['name'];
        final fields = {
          'Company': data['company_name'] ?? widget.summary['company_name'],
          'Stage':
              data['stage_name'] ??
              (_movedStage?['id'] == data['stage_id']
                  ? movedStageName
                  : null) ??
              (snapshot.data == null ||
                      data['stage_id'] == widget.summary['stage_id']
                  ? widget.summary['stage_name']
                  : null),
          'Status': data['status'],
          'Amount': data['amount'] == null
              ? null
              : '${data['amount']} ${data['currency'] ?? ''}'.trim(),
          'Probability': data['probability'] == null
              ? null
              : '${data['probability']}%',
          'Priority': data['priority'],
          'Expected close': data['expected_close_date'],
          'Description': data['description'],
        };
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (snapshot.connectionState != ConnectionState.done)
              const LinearProgressIndicator()
            else if (snapshot.data == null)
              const Text('Saved deal summary'),
            Text(
              '${data['name'] ?? 'Deal'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (widget.canMove &&
                snapshot.connectionState == ConnectionState.done &&
                snapshot.data != null)
              Wrap(
                spacing: 8,
                children: [
                  if (data['version'] is int)
                    OutlinedButton(
                      onPressed: () => _edit(data),
                      child: const Text('Edit deal'),
                    ),
                  OutlinedButton(
                    onPressed: _reviewStage,
                    child: const Text('Review stage move'),
                  ),
                ],
              ),
            for (final field in fields.entries)
              if (field.value != null && field.value.toString().isNotEmpty)
                ListTile(
                  title: Text(field.key),
                  subtitle: Text('${field.value}'),
                ),
          ],
        );
      },
    ),
  );
}

class _DealEditPage extends StatefulWidget {
  const _DealEditPage({
    required this.api,
    required this.deal,
    required this.scopeHeaders,
  });
  final ApiClient api;
  final Json deal;
  final Map<String, String> scopeHeaders;

  @override
  State<_DealEditPage> createState() => _DealEditPageState();
}

class _DealEditPageState extends State<_DealEditPage> {
  final _form = GlobalKey<FormState>();
  final _changes = <String, dynamic>{};
  bool _saving = false;
  String? _error;
  static const _fields = {
    'name': 'Deal name',
    'description': 'Description',
    'amount': 'Amount',
    'expected_close_date': 'Expected close date',
  };

  String? _validate(String key, String text) {
    if (key == 'name' && text.isEmpty) return 'Enter a deal name';
    if (key == 'amount' && text.isNotEmpty) {
      final amount = num.tryParse(text);
      if (amount == null || !amount.isFinite || amount < 0) {
        return 'Enter a valid amount';
      }
    }
    if (key == 'expected_close_date' && text.isNotEmpty) {
      final date = DateTime.tryParse(text);
      if (date == null || date.toIso8601String().split('T').first != text) {
        return 'Enter a date as YYYY-MM-DD';
      }
    }
    return null;
  }

  Future<void> _save() async {
    if (_saving || _form.currentState?.validate() != true) return;
    _changes.clear();
    _form.currentState!.save();
    if (_changes.isEmpty) {
      Navigator.pop(context, false);
      return;
    }
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'PATCH',
        '/crm/deals/${widget.deal['id']}',
        scopeHeaders: widget.scopeHeaders,
        data: {..._changes, 'expected_version': widget.deal['version']},
      );
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, true);
      }
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Edit deal')),
    body: Form(
      key: _form,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (final field in _fields.entries)
              TextFormField(
                initialValue: widget.deal[field.key]?.toString(),
                enabled: !_saving,
                decoration: InputDecoration(labelText: field.value),
                maxLength: field.key == 'name' ? 180 : null,
                maxLines: field.key == 'description' ? 3 : 1,
                keyboardType: field.key == 'amount'
                    ? const TextInputType.numberWithOptions(decimal: true)
                    : null,
                validator: (value) => _validate(field.key, value?.trim() ?? ''),
                onSaved: (value) {
                  final text = value?.trim() ?? '';
                  final current =
                      widget.deal[field.key]?.toString().trim() ?? '';
                  if (text == current) return;
                  _changes[field.key] = text.isEmpty
                      ? null
                      : field.key == 'amount'
                      ? num.parse(text)
                      : text;
                },
              ),
            if (_error case final error?) Text(error),
            FilledButton(
              onPressed: _saving ? null : _save,
              child: Text(_saving ? 'Saving…' : 'Save changes'),
            ),
          ],
        ),
      ),
    ),
  );
}
