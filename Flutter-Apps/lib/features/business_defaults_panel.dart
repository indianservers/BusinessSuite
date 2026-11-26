import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class BusinessDefaultsPanel extends StatefulWidget {
  const BusinessDefaultsPanel({
    super.key,
    required this.api,
    required this.editable,
  });
  final ApiClient api;
  final bool editable;

  @override
  State<BusinessDefaultsPanel> createState() => _BusinessDefaultsPanelState();
}

class _BusinessDefaultsPanelState extends State<BusinessDefaultsPanel> {
  static const _path = '/access/settings/defaults/configuration';
  static const _labels = {
    'currency': 'Currency',
    'timezone': 'Timezone',
    'working_days': 'Working days',
    'fiscal_year_start_month': 'Financial year start month',
  };
  static const _applications = {
    '': 'All applications',
    'crm': 'CRM',
    'srm': 'Sales',
    'fam': 'Finance',
    'hrms': 'People & HR',
    'project_management': 'Projects & tasks',
  };
  late Future<Json> _configuration = _load();
  final _changes = <String, Object?>{};
  static const _inherit = Object();
  String _search = '';
  bool _busy = false;
  String? _error;
  String _application = '';
  int? _branch;
  int _scopeInputRevision = 0;

  Json get _scope => {
    if (_application.isNotEmpty) 'module': _application,
    if (_branch != null) 'branch_id': _branch,
  };

  Future<Json> _load() async =>
      await widget.api.request('GET', _path, query: _scope) as Json;

  Future<void> _switchScope(String application, int? branch) async {
    if (_busy || (application == _application && branch == _branch)) return;
    if (_changes.isNotEmpty) {
      final discard = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Discard unsaved default changes?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Keep editing'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Discard and switch'),
            ),
          ],
        ),
      );
      if (!mounted || _busy) return;
      if (discard != true) {
        setState(() => _scopeInputRevision++);
        return;
      }
    }
    setState(() {
      _application = application;
      _branch = branch;
      _changes.clear();
      _error = null;
      _configuration = _load();
    });
  }

  Future<void> _save(Json config) async {
    final version = config['version'];
    final company = config['companyId'];
    if (_busy || version is! int || company is! int || _changes.isEmpty) return;
    final values = <String, dynamic>{...(config['overrides'] as Json? ?? {})};
    for (final entry in _changes.entries) {
      if (identical(entry.value, _inherit)) {
        values.remove(entry.key);
      } else {
        values[entry.key] = entry.value;
      }
    }
    final currency = values['currency'];
    if (currency is String && !RegExp(r'^[A-Z]{3}$').hasMatch(currency)) {
      setState(() => _error = 'Enter a three-letter currency code.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'PUT',
        _path,
        query: _scope,
        data: {'version': version, 'values': values},
        scopeHeaders: {'X-Suite-Organization': '$company'},
      );
      if (!mounted) return;
      setState(() {
        _changes.clear();
        _configuration = _load();
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Business defaults saved.')));
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Json>(
    future: _configuration,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const Center(child: CircularProgressIndicator());
      }
      final config = snapshot.data;
      if (config == null) {
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('${snapshot.error ?? 'Could not load business defaults.'}'),
              TextButton(
                onPressed: () => setState(() {
                  _configuration = _load();
                }),
                child: const Text('Retry'),
              ),
              if (_scope.isNotEmpty)
                TextButton(
                  onPressed: () => _switchScope('', null),
                  child: const Text('Return to company defaults'),
                ),
            ],
          ),
        );
      }
      final inherited = config['inherited'] as Json? ?? {};
      final overrides = config['overrides'] as Json? ?? {};
      final enabled = widget.editable && !_busy;
      final choices = config['choices'] as Json? ?? {};
      final fields = <String, Json>{
        for (final entry in _labels.entries)
          entry.key: {'key': entry.key, 'label': entry.value},
        for (final field
            in (config['fields'] as List? ?? const []).whereType<Json>())
          if (field['key'] is String) field['key'] as String: field,
      };
      final matching = fields.values.where(
        (field) =>
            inherited.containsKey(field['key']) &&
            '${field['label']} ${field['group'] ?? ''}'.toLowerCase().contains(
              _search,
            ),
      );
      final branches = <int, String>{
        for (final branch
            in (choices['branches'] as List? ?? const []).whereType<Json>())
          if (branch['value'] is int)
            branch['value'] as int: '${branch['label']}',
      };
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            _scope.isEmpty
                ? 'Company-wide starting values for new forms.'
                : 'Custom values here override inherited defaults for this scope.',
          ),
          DropdownButtonFormField<String>(
            key: ValueKey(('application', _application, _scopeInputRevision)),
            initialValue: _application,
            decoration: const InputDecoration(labelText: 'Application'),
            items: [
              for (final entry in _applications.entries)
                DropdownMenuItem(value: entry.key, child: Text(entry.value)),
            ],
            onChanged: _busy
                ? null
                : (value) => _switchScope(value ?? '', _branch),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<int>(
            key: ValueKey(('branch', _branch, _scopeInputRevision)),
            initialValue: branches.containsKey(_branch) ? _branch : 0,
            decoration: const InputDecoration(labelText: 'Branch'),
            items: [
              const DropdownMenuItem(value: 0, child: Text('All branches')),
              for (final entry in branches.entries)
                DropdownMenuItem(value: entry.key, child: Text(entry.value)),
            ],
            onChanged: _busy
                ? null
                : (value) =>
                      _switchScope(_application, value == 0 ? null : value),
          ),
          const SizedBox(height: 12),
          TextField(
            decoration: const InputDecoration(
              labelText: 'Search defaults',
              prefixIcon: Icon(Icons.search),
            ),
            onChanged: (value) =>
                setState(() => _search = value.trim().toLowerCase()),
          ),
          if (matching.isEmpty)
            const ListTile(title: Text('No matching defaults')),
          for (final field in matching)
            _field(field, inherited, overrides, choices, enabled),
          if (_error != null)
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (widget.editable)
            FilledButton(
              onPressed: enabled && _changes.isNotEmpty
                  ? () => _save(config)
                  : null,
              child: const Text('Save defaults'),
            ),
        ],
      );
    },
  );

  Widget _field(
    Json field,
    Json inherited,
    Json overrides,
    Json choices,
    bool enabled,
  ) {
    final key = field['key'] as String;
    final label = '${field['label'] ?? key}';
    final type = field['type'];
    final custom = _changes.containsKey(key)
        ? !identical(_changes[key], _inherit)
        : overrides.containsKey(key);
    Object? effective(String name) {
      if (_changes.containsKey(name)) {
        return identical(_changes[name], _inherit)
            ? inherited[name]
            : _changes[name];
      }
      return overrides.containsKey(name) ? overrides[name] : inherited[name];
    }

    final value = effective(key);
    final options = <Object?, String>{
      if (field['default'] == null) null: 'None',
      for (final option
          in ((field['options'] ?? choices[field['reference']]) as List? ??
                  const [])
              .whereType<Json>())
        if ((key != 'stage_id' ||
                option['pipeline_id'] == effective('pipeline_id')) &&
            (key != 'department_id' ||
                effective('branch_id') == null ||
                option['branch_id'] == effective('branch_id')))
          option['value']: '${option['label']}',
    };
    void change(Object? next) => setState(() {
      if (next != value) {
        if (key == 'pipeline_id') _changes['stage_id'] = null;
        if (key == 'branch_id') _changes['department_id'] = null;
      }
      _changes[key] = next;
      _error = null;
    });
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(label),
              subtitle: Text(custom ? 'Custom value' : 'Inherited value'),
              value: custom,
              onChanged: enabled
                  ? (checked) => change(checked ? inherited[key] : _inherit)
                  : null,
            ),
            if (key == 'working_days')
              Wrap(
                spacing: 6,
                children: [
                  for (final day in [1, 2, 3, 4, 5, 6, 0])
                    FilterChip(
                      label: Text(
                        const [
                          'Sun',
                          'Mon',
                          'Tue',
                          'Wed',
                          'Thu',
                          'Fri',
                          'Sat',
                        ][day],
                      ),
                      selected: (value as List? ?? []).contains(day),
                      onSelected: enabled && custom
                          ? (selected) {
                              final updated = List<int>.from(value ?? const []);
                              selected ? updated.add(day) : updated.remove(day);
                              change(updated);
                            }
                          : null,
                    ),
                ],
              )
            else if (key == 'fiscal_year_start_month')
              DropdownButton<int>(
                value: value is int && value >= 1 && value <= 12 ? value : null,
                items: [
                  for (var month = 1; month <= 12; month++)
                    DropdownMenuItem(
                      value: month,
                      child: Text(
                        MaterialLocalizations.of(context)
                            .formatMonthYear(DateTime(2000, month))
                            .replaceFirst(' 2000', ''),
                      ),
                    ),
                ],
                onChanged: enabled && custom ? change : null,
              )
            else if (type == 'reference' || type == 'select')
              DropdownButton<Object>(
                isExpanded: true,
                value: options.containsKey(value) ? value : null,
                hint: Text(value == null ? 'None' : 'Unavailable: $value'),
                items: [
                  for (final option in options.entries)
                    DropdownMenuItem<Object>(
                      value: option.key,
                      child: Text(option.value),
                    ),
                ],
                onChanged: enabled && custom ? change : null,
              )
            else
              TextFormField(
                key: ValueKey((key, custom)),
                initialValue: '${value ?? ''}',
                readOnly: !enabled || !custom,
                keyboardType: type == 'number'
                    ? const TextInputType.numberWithOptions(decimal: true)
                    : null,
                decoration: InputDecoration(labelText: label),
                onChanged: (text) => change(
                  type == 'number' && text.trim().isNotEmpty
                      ? num.tryParse(text.trim()) ?? text.trim()
                      : type == 'number'
                      ? null
                      : type == 'currency' || key == 'currency'
                      ? text.trim().toUpperCase()
                      : text.trim(),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
