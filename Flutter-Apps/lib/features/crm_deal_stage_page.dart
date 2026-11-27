import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class CrmDealStagePage extends StatefulWidget {
  const CrmDealStagePage({
    super.key,
    required this.api,
    required this.id,
    required this.scopeHeaders,
  });
  final ApiClient api;
  final int id;
  final Map<String, String> scopeHeaders;

  @override
  State<CrmDealStagePage> createState() => _CrmDealStagePageState();
}

class _CrmDealStagePageState extends State<CrmDealStagePage> {
  final _form = GlobalKey<FormState>();
  final _values = <String, String>{};
  late Future<Json> _plan = _load();
  Json? _stage;
  String _reason = '';
  String _review = '';
  bool _saving = false;
  String? _error;
  static const _numbers = {'company_id', 'contact_id', 'amount'};
  static const _dates = {'expected_close_date', 'next_follow_up_at'};
  String get _path => '/crm/productivity/deals/${widget.id}';

  Future<Json> _load() async =>
      await widget.api.request(
            'GET',
            '$_path/stages',
            scopeHeaders: widget.scopeHeaders,
          )
          as Json;

  Future<void> _move(Json plan, Json stage, List<String> required) async {
    if (_saving || _form.currentState?.validate() != true) return;
    _form.currentState!.save();
    if (plan['version'] is! int) return;
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'POST',
        '$_path/transition',
        scopeHeaders: widget.scopeHeaders,
        data: {
          'expected_version': plan['version'],
          'stage_id': stage['id'],
          'corrections': {
            for (final field in required)
              field: switch (field) {
                'amount' => num.parse(_values[field]!),
                'company_id' || 'contact_id' => int.parse(_values[field]!),
                'next_follow_up_at' => DateTime.parse(
                  _values[field]!,
                ).toUtc().toIso8601String(),
                _ => _values[field],
              },
          },
          'lost_reason': stage['is_lost'] == true ? _reason : '',
          'reactivate_at': stage['is_lost'] == true && _review.isNotEmpty
              ? DateTime.parse(_review).toUtc().toIso8601String()
              : null,
        },
      );
      if (mounted && revision == widget.api.sessionRevision) {
        Navigator.pop(context, stage);
      }
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String? _validate(String field, String? value) {
    final text = value?.trim() ?? '';
    if (text.isEmpty) return 'Required';
    if (field == 'amount' && num.tryParse(text)?.isFinite != true) {
      return 'Enter a number';
    }
    if (_numbers.contains(field) &&
        field != 'amount' &&
        (int.tryParse(text) ?? 0) <= 0) {
      return 'Enter a valid record ID';
    }
    if (_dates.contains(field) && DateTime.tryParse(text) == null) {
      return 'Enter an ISO date';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Review stage move')),
    body: FutureBuilder<Json>(
      future: _plan,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: TextButton(
              onPressed: () => setState(() {
                _plan = _load();
              }),
              child: Text('${snapshot.error}\nRetry'),
            ),
          );
        }
        final plan = snapshot.data;
        if (plan == null) {
          return const Center(child: CircularProgressIndicator());
        }
        final stages = (plan['stages'] as List)
            .whereType<Json>()
            .where((stage) => stage['id'] != plan['current_stage_id'])
            .toList();
        final stage = _stage;
        final required = (stage?['required'] as List? ?? const [])
            .whereType<String>()
            .toList();
        final initial = plan['values'] as Json? ?? const {};
        return Form(
          key: _form,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                DropdownButtonFormField<Json>(
                  decoration: const InputDecoration(
                    labelText: 'Destination stage',
                  ),
                  isExpanded: true,
                  items: [
                    for (final option in stages)
                      DropdownMenuItem(
                        value: option,
                        child: Text('${option['name']}'),
                      ),
                  ],
                  onChanged: _saving
                      ? null
                      : (value) => setState(() {
                          _stage = value;
                          _error = null;
                        }),
                ),
                if (stages.isEmpty)
                  const Text('No other stages in this pipeline.'),
                if (stage?['approval_required'] == true)
                  const Text(
                    'An approved deal request is required before entry.',
                  ),
                for (final key in [
                  'recommended_actions',
                  'completion_criteria',
                ])
                  if (stage?[key] case final String text when text.isNotEmpty)
                    Text(text),
                for (final field in required)
                  TextFormField(
                    key: ValueKey('${stage?['id']}:$field'),
                    initialValue: initial[field]?.toString(),
                    enabled: !_saving,
                    decoration: InputDecoration(
                      labelText: field.replaceAll('_', ' '),
                      helperText: _dates.contains(field)
                          ? 'Use YYYY-MM-DD or ISO date and time'
                          : null,
                    ),
                    validator: (value) => _validate(field, value),
                    onSaved: (value) => _values[field] = value!.trim(),
                  ),
                if (stage?['is_lost'] == true) ...[
                  TextFormField(
                    enabled: !_saving,
                    maxLength: 1000,
                    decoration: const InputDecoration(labelText: 'Lost reason'),
                    validator: (value) => (value?.trim().length ?? 0) < 5
                        ? 'Enter at least five characters'
                        : null,
                    onSaved: (value) => _reason = value!.trim(),
                  ),
                  TextFormField(
                    enabled: !_saving,
                    decoration: const InputDecoration(
                      labelText: 'Reactivation review date',
                      helperText:
                          'Optional. Use YYYY-MM-DD or ISO date and time',
                    ),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) return null;
                      return DateTime.tryParse(
                                value.trim(),
                              )?.isAfter(DateTime.now()) ==
                              true
                          ? null
                          : 'Enter a future date';
                    },
                    onSaved: (value) => _review = value?.trim() ?? '',
                  ),
                ],
                if (_error case final error?) Text(error),
                FilledButton(
                  onPressed: _saving || stage == null || plan['version'] is! int
                      ? null
                      : () => _move(plan, stage, required),
                  child: Text(_saving ? 'Saving…' : 'Move deal'),
                ),
              ],
            ),
          ),
        );
      },
    ),
  );
}
