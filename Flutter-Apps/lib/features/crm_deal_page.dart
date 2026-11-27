import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import 'crm_deal_stage_page.dart';

class CrmDealPage extends StatefulWidget {
  const CrmDealPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
    this.cacheScope,
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
  final String? cacheScope;
  final Map<String, String> scopeHeaders;
  final bool canMove;
  final VoidCallback? onChanged;

  @override
  State<CrmDealPage> createState() => _CrmDealPageState();
}

class _CrmDealPageState extends State<CrmDealPage> {
  Json? _cachedDetails;
  late Future<({Json? record, bool live})> _deal = _load(
    offline: widget.offline,
  );
  Json? _movedStage;

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: '/crm/deal-workspace/${widget.summary['id']}/record',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        onCached: (record) {
          if (mounted) setState(() => _cachedDetails = record);
        },
        project: (record) => {
          for (final field in [
            'name',
            'stage_id',
            'status',
            'description',
            ...CrmDealPage.summaryFields,
          ])
            field: record[field],
        },
      );

  void _refresh() => setState(() {
    _cachedDetails = null;
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
        builder: (_) => CrmDealForm(
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
    body: FutureBuilder<({Json? record, bool live})>(
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
        final data = snapshot.data?.record ?? _cachedDetails ?? widget.summary;
        final movedStageName = _movedStage?['name'];
        final fields = {
          'Company': data['company_name'] ?? widget.summary['company_name'],
          'Stage':
              data['stage_name'] ??
              (_movedStage?['id'] == data['stage_id']
                  ? movedStageName
                  : null) ??
              (snapshot.data?.live != true ||
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
            else if (snapshot.data?.live != true)
              Text(
                snapshot.data?.record == null
                    ? 'Saved deal summary'
                    : 'Saved deal details',
              ),
            Text(
              '${data['name'] ?? 'Deal'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (widget.canMove &&
                snapshot.connectionState == ConnectionState.done &&
                snapshot.data?.live == true)
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

class CrmDealForm extends StatefulWidget {
  const CrmDealForm({
    super.key,
    required this.api,
    this.deal = const {},
    required this.scopeHeaders,
  });
  final ApiClient api;
  final Json deal;
  final Map<String, String> scopeHeaders;

  @override
  State<CrmDealForm> createState() => _CrmDealFormState();
}

class _CrmDealFormState extends State<CrmDealForm> {
  final _form = GlobalKey<FormState>();
  final _changes = <String, dynamic>{};
  bool _saving = false;
  String? _error;
  int? _pipeline, _stage;
  bool get _creating => widget.deal['id'] == null;
  late Future<List<Json>> _pipelines = _choices('pipelines');
  Future<List<Json>>? _stages;
  static const _fields = {
    'name': 'Deal name',
    'description': 'Description',
    'amount': 'Amount',
    'expected_close_date': 'Expected close date',
  };

  Future<List<Json>> _choices(String resource, [int? pipeline]) async {
    final revision = widget.api.sessionRevision;
    final items = <Json>[];
    for (var page = 1; ; page++) {
      final data =
          await widget.api.request(
                'GET',
                '/crm/deal-workspace/$resource',
                query: {'page': page, 'pipeline_id': ?pipeline},
                scopeHeaders: widget.scopeHeaders,
              )
              as Json;
      if (!mounted || revision != widget.api.sessionRevision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      items.addAll((data['items'] as List).whereType<Json>());
      if (data['pages'] is! int || page >= (data['pages'] as int)) return items;
    }
  }

  Widget _picker({
    required String label,
    required Future<List<Json>> data,
    required ValueChanged<int?> change,
    required VoidCallback retry,
    Key? key,
  }) => FutureBuilder<List<Json>>(
    key: key,
    future: data,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return TextButton(
          onPressed: retry,
          child: Text('Retry loading $label'),
        );
      }
      if (snapshot.connectionState != ConnectionState.done) {
        return ListTile(title: Text('Loading $label…'));
      }
      final items = snapshot.data ?? [];
      if (items.isEmpty) return Text('No $label choices available');
      return DropdownButtonFormField<int>(
        decoration: InputDecoration(labelText: label),
        isExpanded: true,
        items: [
          for (final row in items)
            DropdownMenuItem(
              value: row['id'] as int,
              child: Text('${row['name']}'),
            ),
        ],
        onChanged: _saving ? null : change,
        validator: (value) => value == null ? 'Required' : null,
      );
    },
  );

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
    if (_creating && (_pipeline == null || _stage == null)) return;
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
        _creating ? 'POST' : 'PATCH',
        _creating ? '/crm/deals' : '/crm/deals/${widget.deal['id']}',
        scopeHeaders: widget.scopeHeaders,
        data: {
          ..._changes,
          if (_creating) ...{
            'pipeline_id': _pipeline,
            'stage_id': _stage,
          } else
            'expected_version': widget.deal['version'],
        },
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
    appBar: AppBar(title: Text(_creating ? 'New deal' : 'Edit deal')),
    body: Form(
      key: _form,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_creating)
              _picker(
                label: 'Pipeline',
                data: _pipelines,
                retry: () => setState(() {
                  _pipelines = _choices('pipelines');
                }),
                change: (pipeline) => setState(() {
                  _pipeline = pipeline;
                  _stage = null;
                  _stages = pipeline == null
                      ? null
                      : _choices('pipeline-stages', pipeline);
                }),
              ),
            if (_stages case final stages?)
              _picker(
                key: ValueKey(_pipeline),
                label: 'Stage',
                data: stages,
                retry: () => setState(() {
                  _stages = _choices('pipeline-stages', _pipeline);
                }),
                change: (stage) => setState(() => _stage = stage),
              ),
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
              onPressed: _saving || (_creating && _stage == null)
                  ? null
                  : _save,
              child: Text(
                _saving
                    ? 'Saving…'
                    : _creating
                    ? 'Create deal'
                    : 'Save changes',
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
