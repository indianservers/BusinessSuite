import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import '../app_controller.dart';
import '../core/models.dart';
import 'pms_catalog.dart';

class PickedUpload {
  PickedUpload(this.name, this.bytes);
  final String name;
  final Uint8List bytes;
}

String? validateContract(Json schema, dynamic value, [String label = 'Form']) {
  if (schema['format'] == 'binary') {
    if (value is! PickedUpload) return 'Choose a file for $label';
    if (value.bytes.isEmpty) return 'The file cannot be empty';
    if (value.bytes.length > 3 * 1024 * 1024) {
      return 'Files must be at most 3 MB';
    }
    return null;
  }
  if (value == null && schema['nullable'] == true) return null;
  if (schema['variants'] is List) {
    for (final variant in schema['variants']) {
      if (validateContract(Map<String, dynamic>.from(variant), value, label) ==
          null) {
        return null;
      }
    }
    return 'Choose a valid value type for $label';
  }
  if (schema['type'] == 'object' || schema.containsKey('properties')) {
    if (value is! Map) return '$label is required';
    final properties = (schema['properties'] as Map?) ?? {};
    for (final key in (schema['required'] as List? ?? [])) {
      if (!value.containsKey(key) ||
          ((value[key] == null || value[key] == '') &&
              (properties[key] as Map?)?['nullable'] != true)) {
        return '${fieldLabel(key)} is required';
      }
    }
    for (final key in value.keys) {
      if (properties[key] is Map) {
        final error = validateContract(
          Map<String, dynamic>.from(properties[key]),
          value[key],
          fieldLabel(key),
        );
        if (error != null) return error;
      }
    }
  } else if (value != null) {
    if (schema['type'] == 'string' && value is! String) {
      return '$label must be text';
    }
    if (schema['type'] == 'boolean' && value is! bool) {
      return '$label must be yes or no';
    }
    if (schema['type'] == 'array' && value is! List) {
      return '$label must be a list';
    }
    if (schema['enum'] is List && !(schema['enum'] as List).contains(value)) {
      return 'Choose a valid $label';
    }
    if (value is String) {
      if (value.length < (schema['minLength'] as num? ?? 0)) {
        return '$label is too short';
      }
      if (schema['maxLength'] != null && value.length > schema['maxLength']) {
        return '$label is too long';
      }
      if (schema['format'] == 'email' &&
          !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(value)) {
        return 'Enter a valid email';
      }
      if (schema['format'] == 'date' && DateTime.tryParse(value) == null) {
        return 'Enter a valid date';
      }
      if (schema['pattern'] is String &&
          !RegExp(schema['pattern']).hasMatch(value)) {
        return '$label has an invalid format';
      }
    }
    final number = value is num
        ? value
        : schema['decimalString'] == true
        ? num.tryParse('$value')
        : null;
    if (schema['type'] == 'integer' && value is! int) {
      return '$label must be a whole number';
    }
    if (schema['type'] == 'number' && number == null) {
      return '$label must be a number';
    }
    if (number != null) {
      if (schema['minimum'] != null && number < schema['minimum']) {
        return '$label must be at least ${schema['minimum']}';
      }
      if (schema['maximum'] != null && number > schema['maximum']) {
        return '$label must be at most ${schema['maximum']}';
      }
      if (schema['exclusiveMinimum'] != null &&
          number <= schema['exclusiveMinimum']) {
        return '$label must be greater than ${schema['exclusiveMinimum']}';
      }
    }
    if (value is List) {
      if (value.length < (schema['minItems'] as num? ?? 0)) {
        return 'Add more $label';
      }
      if (schema['maxItems'] != null && value.length > schema['maxItems']) {
        return 'Too many $label';
      }
      for (final item in value) {
        final error = validateContract(
          Map<String, dynamic>.from(schema['items'] ?? {}),
          item,
          label,
        );
        if (error != null) return error;
      }
    }
  }
  return null;
}

class ContractFields extends StatelessWidget {
  const ContractFields({
    super.key,
    required this.schema,
    required this.values,
    required this.onChanged,
    required this.controller,
    required this.scope,
    this.initial = const {},
    this.disabled = false,
    this.preserveNulls = false,
    this.onReferenceSelected,
  });
  final Json schema, values, initial;
  final ValueChanged<Json> onChanged;
  final AppController controller;
  final Map<String, dynamic> scope;
  final bool disabled, preserveNulls;
  final void Function(String, Json)? onReferenceSelected;
  @override
  Widget build(BuildContext context) {
    final fields = Map<String, dynamic>.from(schema['properties'] ?? {});
    final required = (schema['required'] as List? ?? []).cast<String>();
    final sorted = fields.keys.toList()
      ..sort((a, b) {
        const primary = [
          'title',
          'name',
          'body',
          'description',
          'start_date',
          'end_date',
          'due_date',
          'log_date',
          'duration_minutes',
          'status',
          'priority',
        ];
        int weight(String key) => required.contains(key)
            ? -100 + primary.indexOf(key)
            : primary.contains(key)
            ? primary.indexOf(key)
            : 100;
        return weight(a).compareTo(weight(b));
      });
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final key in sorted)
          if (!((fields[key]['format'] == 'uuid' ||
                  key.endsWith('_hash') ||
                  key == 'base_version') &&
              values[key] != null))
            if ((fields[key] as Map)['readOnly'] != true)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: ContractField(
                  key: ValueKey(key),
                  name: key,
                  schema: Map<String, dynamic>.from(fields[key]),
                  requiredField: required.contains(key),
                  value: values.containsKey(key) ? values[key] : initial[key],
                  controller: controller,
                  scope: scope,
                  disabled: disabled,
                  onReferenceSelected: (record) =>
                      onReferenceSelected?.call(key, record),
                  onChanged: (value) {
                    final next = {...values};
                    if (value == null && !preserveNulls) {
                      next.remove(key);
                    } else {
                      next[key] = value;
                    }
                    onChanged(next);
                  },
                ),
              ),
      ],
    );
  }
}

class ContractField extends StatefulWidget {
  const ContractField({
    super.key,
    required this.name,
    required this.schema,
    required this.value,
    required this.onChanged,
    required this.controller,
    required this.scope,
    this.requiredField = false,
    this.disabled = false,
    this.onReferenceSelected,
  });
  final String name;
  final Json schema;
  final dynamic value;
  final ValueChanged<dynamic> onChanged;
  final AppController controller;
  final Map<String, dynamic> scope;
  final bool requiredField, disabled;
  final ValueChanged<Json>? onReferenceSelected;
  @override
  State<ContractField> createState() => _ContractFieldState();
}

class _ContractFieldState extends State<ContractField> {
  int? _variant;
  String get label =>
      '${fieldLabel(widget.name)}${widget.requiredField ? ' *' : ''}';
  bool get reference =>
      widget.name.endsWith('_id') ||
      const {
        'wid',
        'rid',
        'mid',
        'fid',
        'did',
        'uid',
        'projectId',
        'taskId',
        'workspaceId',
        'sprintId',
        'epicId',
        'assigneeId',
        'reporterId',
      }.contains(widget.name);
  Future<void> _chooseReference() async {
    String? error;
    List<Json>? choices;
    final future =
        referenceOptions(widget.name, widget.scope, widget.controller)
            .then((v) {
              choices = v;
            })
            .catchError((Object e) {
              error = '$e';
            });
    if (!mounted) return;
    var query = '';
    final selection = await showModalBottomSheet<Json>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => SizedBox(
          height: MediaQuery.sizeOf(context).height * .75,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                Text(
                  'Choose ${fieldLabel(widget.name)}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 16),
                TextField(
                  decoration: const InputDecoration(labelText: 'Search'),
                  onChanged: (s) => update(() => query = s),
                ),
                Expanded(
                  child: FutureBuilder<void>(
                    future: future,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) {
                        return const Center(child: CircularProgressIndicator());
                      }
                      if (error != null) return Center(child: Text(error!));
                      final rows = choices!
                          .where(
                            (r) => '${r['name']}'.toLowerCase().contains(
                              query.toLowerCase(),
                            ),
                          )
                          .toList();
                      if (rows.isEmpty) {
                        return const Center(
                          child: Text(
                            'No matching records are available in this scope.',
                          ),
                        );
                      }
                      return ListView(
                        children: rows
                            .map(
                              (r) => ListTile(
                                title: Text('${r['name']}'),
                                onTap: () => Navigator.pop(context, r),
                              ),
                            )
                            .toList(),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    if (selection != null && mounted) {
      setState(() => _referenceName = '${selection['name']}');
      widget.onChanged(selection['id']);
      if (selection['record'] is Map) {
        widget.onReferenceSelected?.call(
          Map<String, dynamic>.from(selection['record']),
        );
      }
    }
  }

  String? _referenceName;
  Future<void> _date() async {
    final parsed = DateTime.tryParse('${widget.value}') ?? DateTime.now();
    final old = widget.schema['format'] == 'date-time'
        ? parsed.toLocal()
        : parsed;
    final selected = await showDatePicker(
      context: context,
      initialDate: old,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (selected == null || !mounted) return;
    if (widget.schema['format'] == 'date-time') {
      final time = await showTimePicker(
        context: context,
        initialTime: TimeOfDay.fromDateTime(old),
      );
      if (time == null) return;
      widget.onChanged(
        DateTime(
          selected.year,
          selected.month,
          selected.day,
          time.hour,
          time.minute,
        ).toUtc().toIso8601String(),
      );
    } else {
      widget.onChanged(selected.toIso8601String().split('T').first);
    }
  }

  Future<void> _arrayItem([int? editIndex]) async {
    final item = Map<String, dynamic>.from(widget.schema['items'] ?? {});
    dynamic value = editIndex == null
        ? null
        : (widget.value as List)[editIndex];
    if (item['type'] == 'object') {
      value = Map<String, dynamic>.from(value ?? {});
    }
    final saved = await showDialog<bool>(
      context: context,
      builder: (dialog) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: Text(
            '${editIndex == null ? 'Add' : 'Edit'} ${fieldLabel(widget.name)}',
          ),
          content: SizedBox(
            width: 440,
            child: SingleChildScrollView(
              child:
                  item['type'] == 'object' &&
                      (item['properties'] as Map? ?? {}).isNotEmpty
                  ? ContractFields(
                      schema: item,
                      values: Map<String, dynamic>.from(value),
                      onChanged: (v) => update(() => value = v),
                      controller: widget.controller,
                      scope: widget.scope,
                    )
                  : ContractField(
                      name:
                          const {
                            'participants',
                            'member_ids',
                          }.contains(widget.name)
                          ? 'user_id'
                          : widget.name.replaceFirst(RegExp(r'_ids$'), '_id'),
                      schema: item,
                      value: value,
                      onChanged: (v) => update(() => value = v),
                      controller: widget.controller,
                      scope: widget.scope,
                    ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialog, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final error = validateContract(item, value, label);
                if (error == null && value != null) {
                  Navigator.pop(dialog, true);
                } else {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(error ?? 'Enter a value')),
                  );
                }
              },
              child: Text(editIndex == null ? 'Add' : 'Save item'),
            ),
          ],
        ),
      ),
    );
    if (saved == true) {
      final items = List<dynamic>.from(widget.value as List? ?? []);
      if (editIndex == null) {
        items.add(value);
      } else {
        items[editIndex] = value;
      }
      widget.onChanged(items);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.schema['variants'] is List) {
      final variants = (widget.schema['variants'] as List)
          .map((v) => Map<String, dynamic>.from(v))
          .toList();
      final inferred = widget.value is bool
          ? 'boolean'
          : widget.value is num
          ? 'number'
          : widget.value is List
          ? 'array'
          : widget.value is Map
          ? 'object'
          : 'string';
      final index =
          _variant ??
          variants
              .indexWhere((v) => v['type'] == inferred)
              .clamp(0, variants.length - 1);
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          DropdownButtonFormField<int>(
            initialValue: index,
            decoration: InputDecoration(
              labelText: '${fieldLabel(widget.name)} type',
            ),
            items: [
              for (var i = 0; i < variants.length; i++)
                DropdownMenuItem(
                  value: i,
                  child: Text('${variants[i]['type']}'),
                ),
            ],
            onChanged: widget.disabled
                ? null
                : (v) {
                    setState(() => _variant = v);
                    widget.onChanged(
                      v != null && variants[v]['type'] == 'boolean'
                          ? false
                          : null,
                    );
                  },
          ),
          const SizedBox(height: 12),
          ContractField(
            key: ValueKey('variant-$index'),
            name: widget.name,
            schema: variants[index],
            value: widget.value,
            onChanged: widget.onChanged,
            controller: widget.controller,
            scope: widget.scope,
            disabled: widget.disabled,
            requiredField: widget.requiredField,
          ),
          if (widget.schema['nullable'] == true)
            TextButton(
              onPressed: widget.disabled ? null : () => widget.onChanged(null),
              child: const Text('Clear value'),
            ),
        ],
      );
    }
    final schema = widget.schema, type = schema['type'];
    if (schema['format'] == 'binary') {
      return OutlinedButton.icon(
        onPressed: widget.disabled
            ? null
            : () async {
                try {
                  final picked = await FilePicker.pickFile();
                  if (picked == null) return;
                  final length = await picked.length();
                  if (length != null && length > 3 * 1024 * 1024) {
                    throw StateError(
                      'Files must be at most 3 MB for this deployment.',
                    );
                  }
                  final bytes = await picked.readAsBytes();
                  if (bytes.length > 3 * 1024 * 1024) {
                    throw StateError('File is too large.');
                  }
                  widget.onChanged(PickedUpload(picked.name, bytes));
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(
                      context,
                    ).showSnackBar(SnackBar(content: Text('$e')));
                  }
                }
              },
        icon: const Icon(Icons.attach_file),
        label: Text(
          widget.value is PickedUpload
              ? (widget.value as PickedUpload).name
              : 'Choose $label',
        ),
      );
    }
    if (type == 'boolean') {
      return SwitchListTile(
        contentPadding: EdgeInsets.zero,
        title: Text(label),
        value: widget.value == true,
        onChanged: widget.disabled ? null : widget.onChanged,
      );
    }
    if (schema['enum'] is List) {
      return DropdownButtonFormField<dynamic>(
        key: ValueKey('${widget.name}-${widget.value}'),
        initialValue: widget.value,
        decoration: InputDecoration(labelText: label),
        isExpanded: true,
        items: (schema['enum'] as List)
            .map((v) => DropdownMenuItem(value: v, child: Text('$v')))
            .toList(),
        onChanged: widget.disabled ? null : widget.onChanged,
      );
    }
    if (type == 'object' || schema.containsKey('properties')) {
      final fields = Map<String, dynamic>.from(schema['properties'] ?? {});
      if (fields.isNotEmpty) {
        return ExpansionTile(
          title: Text(label),
          initiallyExpanded: widget.requiredField,
          children: [
            ContractFields(
              schema: schema,
              values: Map<String, dynamic>.from(widget.value ?? {}),
              onChanged: widget.onChanged,
              controller: widget.controller,
              scope: widget.scope,
              disabled: widget.disabled,
            ),
          ],
        );
      }
      return _DictionaryField(
        label: label,
        value: Map<String, dynamic>.from(widget.value ?? {}),
        onChanged: widget.onChanged,
        disabled: widget.disabled,
      );
    }
    if (type == 'array') {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(label),
          for (final (index, value) in (widget.value as List? ?? []).indexed)
            ListTile(
              title: Text(
                value is Map
                    ? recordTitle(Map<String, dynamic>.from(value))
                    : '$value',
              ),
              onTap: widget.disabled ? null : () => _arrayItem(index),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    tooltip: 'Move item up',
                    onPressed: widget.disabled || index == 0
                        ? null
                        : () {
                            final items = List<dynamic>.from(widget.value);
                            final v = items.removeAt(index);
                            items.insert(index - 1, v);
                            widget.onChanged(items);
                          },
                    icon: const Icon(Icons.arrow_upward),
                  ),
                  IconButton(
                    tooltip: 'Move item down',
                    onPressed:
                        widget.disabled ||
                            index == (widget.value as List).length - 1
                        ? null
                        : () {
                            final items = List<dynamic>.from(widget.value);
                            final v = items.removeAt(index);
                            items.insert(index + 1, v);
                            widget.onChanged(items);
                          },
                    icon: const Icon(Icons.arrow_downward),
                  ),
                  IconButton(
                    tooltip: 'Remove item',
                    onPressed: widget.disabled
                        ? null
                        : () {
                            final items = List<dynamic>.from(widget.value);
                            items.removeAt(index);
                            widget.onChanged(items);
                          },
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
            ),
          OutlinedButton.icon(
            onPressed: widget.disabled ? null : _arrayItem,
            icon: const Icon(Icons.add),
            label: const Text('Add item'),
          ),
        ],
      );
    }
    if (reference && type != 'string') {
      return InputDecorator(
        decoration: InputDecoration(labelText: label),
        child: Row(
          children: [
            Expanded(
              child: Text(
                _referenceName ??
                    (widget.value == null
                        ? 'Choose a record'
                        : 'Selected record ${widget.value}'),
              ),
            ),
            if (widget.value != null)
              IconButton(
                tooltip: 'Clear selection',
                onPressed: widget.disabled
                    ? null
                    : () => widget.onChanged(null),
                icon: const Icon(Icons.clear),
              ),
            IconButton(
              tooltip: 'Choose ${fieldLabel(widget.name)}',
              onPressed: widget.disabled ? null : _chooseReference,
              icon: const Icon(Icons.search),
            ),
          ],
        ),
      );
    }
    if (schema['format'] == 'date' || schema['format'] == 'date-time') {
      return InputDecorator(
        decoration: InputDecoration(labelText: label),
        child: Row(
          children: [
            Expanded(
              child: Text(
                widget.value == null ? 'Choose a date' : '${widget.value}',
              ),
            ),
            if (widget.value != null)
              IconButton(
                tooltip: 'Clear date',
                onPressed: widget.disabled
                    ? null
                    : () => widget.onChanged(null),
                icon: const Icon(Icons.clear),
              ),
            IconButton(
              tooltip: 'Choose ${fieldLabel(widget.name)}',
              onPressed: widget.disabled ? null : _date,
              icon: const Icon(Icons.calendar_today),
            ),
          ],
        ),
      );
    }
    final multiline = const {
      'body',
      'description',
      'notes',
      'content',
      'goal',
      'mitigation_plan',
      'contingency_plan',
      'remarks',
      'review_notes',
    }.contains(widget.name);
    final secret = RegExp(
      'password|token|secret|api_key',
    ).hasMatch(widget.name);
    return TextFormField(
      key: ValueKey('input-${widget.name}'),
      initialValue: widget.value?.toString() ?? '',
      enabled: !widget.disabled,
      decoration: InputDecoration(labelText: label),
      obscureText: secret,
      maxLines: secret
          ? 1
          : multiline
          ? 4
          : 1,
      keyboardType: type == 'integer' || type == 'number'
          ? const TextInputType.numberWithOptions(decimal: true, signed: true)
          : multiline
          ? TextInputType.multiline
          : TextInputType.text,
      onChanged: (text) {
        if (text.isEmpty) {
          widget.onChanged(
            type == 'string' && schema['nullable'] != true ? '' : null,
          );
        } else if (type == 'integer') {
          widget.onChanged(int.tryParse(text) ?? text);
        } else if (type == 'number' && schema['decimalString'] != true) {
          widget.onChanged(num.tryParse(text) ?? text);
        } else {
          widget.onChanged(text);
        }
      },
    );
  }
}

class _DictionaryField extends StatelessWidget {
  const _DictionaryField({
    required this.label,
    required this.value,
    required this.onChanged,
    required this.disabled,
  });
  final String label;
  final Json value;
  final ValueChanged<dynamic> onChanged;
  final bool disabled;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(label),
      for (final entry in value.entries)
        ListTile(
          title: Text(fieldLabel(entry.key)),
          subtitle: Text('${entry.value}'),
          trailing: IconButton(
            tooltip: 'Remove property',
            onPressed: disabled
                ? null
                : () {
                    final next = {...value}..remove(entry.key);
                    onChanged(next);
                  },
            icon: const Icon(Icons.close),
          ),
        ),
      OutlinedButton(
        onPressed: disabled
            ? null
            : () async {
                var name = '', text = '', kind = 'Text';
                final saved = await showDialog<bool>(
                  context: context,
                  builder: (dialog) => AlertDialog(
                    title: const Text('Add property'),
                    content: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        TextField(
                          decoration: const InputDecoration(
                            labelText: 'Property name',
                          ),
                          onChanged: (v) => name = v,
                        ),
                        TextField(
                          decoration: const InputDecoration(labelText: 'Value'),
                          onChanged: (v) => text = v,
                        ),
                        DropdownButtonFormField<String>(
                          initialValue: kind,
                          items: const ['Text', 'Number', 'Yes / no']
                              .map(
                                (v) =>
                                    DropdownMenuItem(value: v, child: Text(v)),
                              )
                              .toList(),
                          onChanged: (v) => kind = v!,
                        ),
                      ],
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(dialog, false),
                        child: const Text('Cancel'),
                      ),
                      FilledButton(
                        onPressed: () =>
                            Navigator.pop(dialog, name.trim().isNotEmpty),
                        child: const Text('Add'),
                      ),
                    ],
                  ),
                );
                if (saved == true) {
                  onChanged({
                    ...value,
                    name.trim(): kind == 'Number'
                        ? num.tryParse(text) ?? text
                        : kind == 'Yes / no'
                        ? text.toLowerCase() == 'true' ||
                              text.toLowerCase() == 'yes'
                        : text,
                  });
                }
              },
        child: const Text('Add property'),
      ),
    ],
  );
}
