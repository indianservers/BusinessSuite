import 'dart:async';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import '../core/suite_pdf.dart';
import '../core/suite_read_cache.dart';
import 'sales_order_drafts_page.dart';

Future<Json?> showGstInvoiceDraftForm(
  BuildContext context, {
  required ApiClient api,
  required Map<String, String> scopeHeaders,
}) => showDialog<Json>(
  context: context,
  barrierDismissible: false,
  builder: (_) => _GstDraftForm(api: api, scopeHeaders: scopeHeaders),
);

class _GstDraftForm extends StatefulWidget {
  const _GstDraftForm({required this.api, required this.scopeHeaders});

  final ApiClient api;
  final Map<String, String> scopeHeaders;

  @override
  State<_GstDraftForm> createState() => _GstDraftFormState();
}

class _GstDraftFormState extends State<_GstDraftForm> {
  late final _revision = widget.api.sessionRevision;
  final _operation = const Uuid().v4();
  final _lines = <Json>[];
  Json? _customer;
  Json? _pending;
  bool _saving = false;
  String? _error;

  Future<void> _chooseCustomer() async {
    final customer = await showDialog<Json>(
      context: context,
      builder: (_) => SalesRecordPicker(
        api: widget.api,
        offline: false,
        scopeHeaders: widget.scopeHeaders,
      ),
    );
    if (mounted && customer != null) setState(() => _customer = customer);
  }

  Future<void> _addLine() async {
    final line = await showDialog<Json>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _InvoiceLineDialog(save: (values) async => {...values}),
    );
    if (mounted && line != null) setState(() => _lines.add(line));
  }

  Future<void> _save() async {
    if (_saving || widget.api.sessionRevision != _revision) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    final retrying = _pending != null;
    final payload = _pending ??= {
      'request_id': _operation,
      'customer_id': _customer!['id'],
      'currency': 'INR',
      'lines': _lines,
    };
    try {
      final result = await widget.api.request(
        'POST',
        '${GstInvoicePage.listEndpoint}/manual',
        data: payload,
        scopeHeaders: widget.scopeHeaders,
      );
      if (!mounted || widget.api.sessionRevision != _revision) return;
      if (result is! Json || result['id'] is! int) {
        throw ApiFailure('Draft confirmation is unavailable.', 503);
      }
      Navigator.pop(context, result);
    } on ApiFailure catch (error) {
      if (!mounted || widget.api.sessionRevision != _revision) return;
      setState(() {
        if (!retrying &&
            !error.connectionFailure &&
            (error.status ?? 0) >= 400 &&
            (error.status ?? 0) < 500) {
          _pending = null;
        }
        _error = _pending == null
            ? error.message
            : 'Save could not be confirmed. Retry to check the same draft.';
      });
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: AlertDialog(
      title: const Text('New GST invoice draft'),
      scrollable: true,
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          OutlinedButton(
            onPressed: _pending == null ? _chooseCustomer : null,
            child: Text('${_customer?['name'] ?? 'Choose customer'}'),
          ),
          for (final line in _lines)
            ListTile(
              title: Text('${line['description']}'),
              subtitle: Text('${line['quantity']} × INR ${line['unit_price']}'),
              trailing: _pending != null
                  ? null
                  : IconButton(
                      tooltip: 'Remove line',
                      onPressed: () => setState(() => _lines.remove(line)),
                      icon: const Icon(Icons.delete_outline),
                    ),
            ),
          OutlinedButton.icon(
            onPressed: _pending == null ? _addLine : null,
            icon: const Icon(Icons.add),
            label: const Text('Add line item'),
          ),
          if (_error != null) Text(_error!),
        ],
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        FilledButton(
          onPressed: _saving || _customer == null || _lines.isEmpty
              ? null
              : _save,
          child: Text(
            _saving
                ? 'Saving…'
                : _pending == null
                ? 'Create draft'
                : 'Retry draft save',
          ),
        ),
      ],
    ),
  );
}

class GstInvoicePage extends StatefulWidget {
  const GstInvoicePage({
    super.key,
    required this.api,
    required this.id,
    this.canEdit = false,
    this.canExport = false,
    this.canIssue = false,
    this.cacheScope,
    this.scopeHeaders = const {},
    this.summary,
    this.offline = false,
    this.onChanged,
  });
  static const listEndpoint = '/srm/invoices';
  final ApiClient api;
  final int id;
  final bool canEdit;
  final bool canExport;
  final bool canIssue;
  final String? cacheScope;
  final Map<String, String> scopeHeaders;
  final Json? summary;
  final bool offline;
  final VoidCallback? onChanged;

  static String? cacheKey(
    String? scope,
    String path,
    Map<String, String> headers,
  ) {
    if (scope == null) return null;
    final keys = headers.keys.toList()..sort();
    final context = Uri(
      queryParameters: {for (final key in keys) key: headers[key]},
    ).query;
    return '$scope:$path${context.isEmpty ? '' : ':$context'}';
  }

  static const summaryFields = [
    'invoice_number',
    'status',
    'currency',
    'issue_date',
    'due_date',
    'document_status',
    'delivery_status',
    'payment_status',
    'subtotal',
    'tax_amount',
    'total_amount',
    'paid_amount',
    'balance_amount',
  ];

  @override
  State<GstInvoicePage> createState() => _GstInvoicePageState();
}

class _GstInvoicePageState extends State<GstInvoicePage> {
  late Future<(Json, bool)> _invoice = _load();
  late bool _offline = widget.offline;
  Json? _saved;
  bool _exporting = false;
  bool _issuing = false;
  String get _path => '${GstInvoicePage.listEndpoint}/${widget.id}';
  String? get _key =>
      GstInvoicePage.cacheKey(widget.cacheScope, _path, widget.scopeHeaders);

  Future<void> _saveSnapshot(Json invoice) async {
    final key = _key;
    if (key == null) return;
    try {
      final lines = (invoice['lines'] as List? ?? []).whereType<Json>();
      await SuiteReadCache.write(key, [
        {
          for (final field in GstInvoicePage.summaryFields)
            field: invoice[field],
          'lines': [
            for (final line in lines)
              {
                for (final field in const [
                  'description',
                  'item_name',
                  'quantity',
                  'line_total',
                ])
                  field: line[field],
              },
          ],
        },
      ]);
    } catch (_) {
      // A failed cache write leaves the online invoice available.
    }
  }

  Future<(Json, bool)> _load({bool reconnect = false}) async {
    final api = widget.api;
    final revision = api.sessionRevision;
    final key = _key;
    Json? cached;
    if (key != null) {
      try {
        cached = (await SuiteReadCache.read(key))?.firstOrNull;
        if (mounted && api.sessionRevision == revision) {
          setState(() => _saved = cached);
        }
      } catch (_) {}
    }
    if (api.sessionRevision != revision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    final fallback = cached ?? widget.summary;
    if (_offline && !reconnect) {
      if (fallback != null) return (fallback, true);
      throw ApiFailure('Open this invoice online to save it on this device.');
    }
    try {
      final invoice =
          await api.request('GET', _path, scopeHeaders: widget.scopeHeaders)
              as Json;
      if (api.sessionRevision != revision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      unawaited(_saveSnapshot(invoice));
      _offline = false;
      return (invoice, false);
    } on ApiFailure catch (error) {
      if (fallback != null &&
          (error.connectionFailure ||
              (error.status ?? 0) >= 500 ||
              error.status == 429)) {
        return (fallback, true);
      }
      if (key != null && const {401, 403, 404}.contains(error.status)) {
        if (mounted) setState(() => _saved = null);
        try {
          await SuiteReadCache.clear(key);
        } catch (_) {}
      }
      rethrow;
    }
  }

  void _refresh() => setState(() {
    _invoice = _load(reconnect: true);
  });

  Future<void> _notifyChanged() async {
    final key = GstInvoicePage.cacheKey(
      widget.cacheScope,
      GstInvoicePage.listEndpoint,
      widget.scopeHeaders,
    );
    if (key != null) {
      try {
        await SuiteReadCache.invalidate(key);
      } catch (_) {}
    }
    if (mounted) widget.onChanged?.call();
  }

  Future<void> _issue(Json invoice) async {
    if (_issuing) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    setState(() => _issuing = true);
    try {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Issue this invoice?'),
          content: Text(
            '${invoice['invoice_number']} · ${invoice['currency'] ?? ''} ${invoice['total_amount'] ?? ''}\n\n'
            'Issuing finalizes the invoice. Any later changes require an accounting adjustment.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Confirm issue'),
            ),
          ],
        ),
      );
      if (!mounted || confirmed != true || api.sessionRevision != revision) {
        return;
      }
      await api.request(
        'POST',
        '$_path/approve',
        scopeHeaders: widget.scopeHeaders,
      );
      if (mounted && api.sessionRevision == revision) {
        setState(() {
          _invoice = _load();
        });
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Invoice issued.')));
        await _notifyChanged();
      }
    } catch (error) {
      if (mounted && api.sessionRevision == revision) {
        setState(() {
          _invoice = _load();
        });
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _issuing = false);
    }
  }

  Future<void> _export(Json invoice) async {
    if (_exporting) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    setState(() => _exporting = true);
    try {
      final bytes = await fetchSuitePdf(
        api,
        '$_path/pdf',
        scopeHeaders: widget.scopeHeaders,
      );
      if (!mounted || api.sessionRevision != revision) return;
      final number = '${invoice['invoice_number'] ?? widget.id}'.replaceAll(
        RegExp(r'[^A-Za-z0-9._-]'),
        '_',
      );
      final saved = await FilePicker.saveFile(
        fileName: 'Invoice-$number.pdf',
        bytes: bytes,
      );
      if (mounted && saved != null) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Invoice PDF saved.')));
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<void> _editLine(Json line) async {
    final updated = await showDialog<Json>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _InvoiceLineDialog(
        line: line,
        save: (values) async =>
            await widget.api.request(
                  'PATCH',
                  '/srm/business/invoices/${widget.id}/lines/${line['id']}',
                  data: values,
                  scopeHeaders: widget.scopeHeaders,
                )
                as Json,
      ),
    );
    if (mounted && updated != null) {
      setState(() {
        _invoice = Future.value((updated, false));
      });
      await _saveSnapshot(updated);
      if (mounted) await _notifyChanged();
    }
  }

  Future<void> _addLine() async {
    final api = widget.api;
    final revision = api.sessionRevision;
    final created = await showDialog<Json>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _InvoiceLineDialog(
        save: (values) async {
          if (api.sessionRevision != revision) {
            throw ApiFailure('Your session ended. Sign in again.', 401);
          }
          return await api.request(
                'POST',
                '$_path/lines',
                data: {...values, 'source_type': 'manual'},
                scopeHeaders: widget.scopeHeaders,
              )
              as Json;
        },
      ),
    );
    if (!mounted || created == null || api.sessionRevision != revision) return;
    _refresh();
    await _notifyChanged();
  }

  Future<void> _editDates(Json invoice) async {
    final form = GlobalKey<FormState>();
    final initial = {
      'issue_date': invoice['issue_date'] as String?,
      'due_date': invoice['due_date'] as String?,
    };
    final dates = Map.of(initial);
    var saving = false;
    String? error;
    final refresh = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => StatefulBuilder(
        builder: (context, update) => PopScope(
          canPop: !saving,
          child: AlertDialog(
            title: const Text('Edit invoice dates'),
            content: SingleChildScrollView(
              child: Form(
                key: form,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (final (key, label) in const [
                      ('issue_date', 'Issue date'),
                      ('due_date', 'Due date'),
                    ])
                      TextFormField(
                        initialValue: initial[key],
                        enabled: !saving,
                        decoration: InputDecoration(
                          labelText: label,
                          hintText: 'YYYY-MM-DD',
                        ),
                        onChanged: (value) => dates[key] = value.trim().isEmpty
                            ? null
                            : value.trim(),
                        validator: (_) {
                          final text = dates[key];
                          if (text == null) return null;
                          final date = DateTime.tryParse(text);
                          if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text) ||
                              date == null ||
                              date.year < 1 ||
                              !date.toIso8601String().startsWith('${text}T')) {
                            return 'Enter a valid date as YYYY-MM-DD.';
                          }
                          return null;
                        },
                      ),
                    if (error != null) SelectableText(error!),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(context, true),
                child: const Text('Close'),
              ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        if (!form.currentState!.validate()) return;
                        final changed = {
                          for (final key in dates.keys)
                            if (dates[key] != initial[key]) key: dates[key],
                        };
                        if (changed.isEmpty) {
                          Navigator.pop(context, false);
                          return;
                        }
                        update(() {
                          saving = true;
                          error = null;
                        });
                        try {
                          await widget.api.request(
                            'PATCH',
                            _path,
                            data: changed,
                            scopeHeaders: widget.scopeHeaders,
                          );
                          if (context.mounted) Navigator.pop(context, true);
                        } catch (failure) {
                          if (context.mounted) {
                            update(() {
                              saving = false;
                              error = '$failure';
                            });
                          }
                        }
                      },
                child: Text(saving ? 'Saving…' : 'Save dates'),
              ),
            ],
          ),
        ),
      ),
    );
    if (mounted && refresh == true) {
      setState(() {
        _invoice = _load();
      });
      await _notifyChanged();
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Sales invoice')),
    body: FutureBuilder<(Json, bool)>(
      future: _invoice,
      builder: (context, snapshot) {
        final loading = snapshot.connectionState != ConnectionState.done;
        if (!loading && snapshot.hasError) {
          return ListTile(
            title: Text('${snapshot.error}'),
            trailing: TextButton(
              onPressed: _refresh,
              child: Text(_offline ? 'Reconnect' : 'Retry'),
            ),
          );
        }
        final data = loading ? null : snapshot.data;
        final invoice = data?.$1 ?? _saved ?? widget.summary;
        if (invoice == null) {
          return const Center(child: CircularProgressIndicator());
        }
        final saved = data?.$2 ?? true;
        final currency = invoice['currency'] ?? '';
        final lines = (invoice['lines'] as List? ?? []).whereType<Json>();
        final editable =
            !saved &&
            widget.canEdit &&
            const {'draft', 'pending_approval'}.contains(invoice['status']);
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${invoice['invoice_number']}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (loading) const LinearProgressIndicator(),
            if (!loading && saved)
              ListTile(
                title: Text(
                  _offline
                      ? 'Offline · Saved invoice'
                      : 'Refresh unavailable · Saved invoice',
                ),
                trailing: TextButton(
                  onPressed: _refresh,
                  child: Text(_offline ? 'Reconnect' : 'Retry'),
                ),
              ),
            if (!saved && widget.canExport)
              OutlinedButton.icon(
                onPressed: _exporting ? null : () => _export(invoice),
                icon: const Icon(Icons.picture_as_pdf_outlined),
                label: Text(_exporting ? 'Preparing PDF…' : 'Save invoice PDF'),
              ),
            for (final field in const {
              'issue_date': 'Issue date',
              'due_date': 'Due date',
            }.entries)
              if (invoice[field.key] != null)
                ListTile(
                  title: Text(field.value),
                  trailing: Text('${invoice[field.key]}'),
                ),
            if (!saved &&
                widget.canIssue &&
                invoice['document_status'] == 'draft' &&
                const {
                  'draft',
                  'pending_approval',
                  'approved',
                }.contains(invoice['status']))
              FilledButton(
                onPressed: _issuing ? null : () => _issue(invoice),
                child: Text(_issuing ? 'Issuing…' : 'Issue invoice'),
              ),
            if (editable)
              OutlinedButton(
                onPressed: _issuing ? null : () => _editDates(invoice),
                child: const Text('Edit dates'),
              ),
            for (final field in const {
              'document_status': 'Document',
              'delivery_status': 'Delivery',
              'payment_status': 'Payment',
            }.entries)
              ListTile(
                title: Text(field.value),
                trailing: Text(
                  '${invoice[field.key] ?? 'Unavailable'}'.replaceAll('_', ' '),
                ),
              ),
            const Divider(),
            for (final field in const {
              'subtotal': 'Subtotal',
              'tax_amount': 'Tax',
              'total_amount': 'Total',
              'paid_amount': 'Paid',
              'balance_amount': 'Outstanding',
            }.entries)
              if (invoice[field.key] != null)
                ListTile(
                  title: Text(field.value),
                  trailing: Text('$currency ${invoice[field.key]}'.trim()),
                ),
            const Divider(),
            Text('Line items', style: Theme.of(context).textTheme.titleMedium),
            if (editable)
              OutlinedButton.icon(
                onPressed: _issuing ? null : _addLine,
                icon: const Icon(Icons.add),
                label: const Text('Add line item'),
              ),
            if (!loading && lines.isEmpty)
              ListTile(
                title: Text(
                  saved && !invoice.containsKey('lines')
                      ? 'Line items are unavailable offline'
                      : 'No line items',
                ),
              ),
            for (final line in lines)
              ListTile(
                title: Text(
                  '${line['description'] ?? line['item_name'] ?? 'Line item'}',
                ),
                subtitle: Text(
                  'Quantity ${line['quantity'] ?? '—'}'
                  '${line['line_total'] == null ? '' : ' · $currency ${line['line_total']}'}',
                ),
                trailing:
                    editable &&
                        line['id'] is int &&
                        const {
                          null,
                          'manual',
                          'external_adjustment',
                        }.contains(line['source_type'])
                    ? IconButton(
                        tooltip: 'Edit draft line',
                        onPressed: _issuing ? null : () => _editLine(line),
                        icon: const Icon(Icons.edit_outlined),
                      )
                    : null,
              ),
          ],
        );
      },
    ),
  );
}

class _InvoiceLineDialog extends StatefulWidget {
  const _InvoiceLineDialog({this.line, required this.save});
  final Json? line;
  final Future<Json> Function(Json values) save;

  @override
  State<_InvoiceLineDialog> createState() => _InvoiceLineDialogState();
}

class _InvoiceLineDialogState extends State<_InvoiceLineDialog> {
  static const _fields = {
    'description': 'Description',
    'quantity': 'Quantity',
    'unit_price': 'Unit price',
    'discount_amount': 'Discount amount',
    'tax_amount': 'Tax amount',
  };
  final _form = GlobalKey<FormState>();
  late final _values = {
    for (final key in _fields.keys)
      key:
          '${widget.line?[key] ?? (key == 'description'
                  ? ''
                  : key == 'quantity'
                  ? 1
                  : 0)}',
  };
  bool _saving = false;
  bool _unconfirmed = false;
  String? _error;

  Future<void> _submit() async {
    if (_saving || _unconfirmed || !_form.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final invoice = await widget.save(_values);
      if (mounted) Navigator.pop(context, invoice);
    } catch (error) {
      if (mounted) {
        setState(() {
          _saving = false;
          _unconfirmed =
              widget.line == null &&
              error is ApiFailure &&
              (error.connectionFailure || (error.status ?? 0) >= 500);
          _error = _unconfirmed
              ? 'Save could not be confirmed. Refresh the invoice before adding the line again.'
              : '$error';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: AlertDialog(
      title: Text(widget.line == null ? 'Add draft line' : 'Edit draft line'),
      content: SingleChildScrollView(
        child: Form(
          key: _form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final field in _fields.entries)
                TextFormField(
                  initialValue: _values[field.key],
                  enabled: !_saving,
                  decoration: InputDecoration(labelText: field.value),
                  maxLength: field.key == 'description' ? 2000 : null,
                  keyboardType: field.key == 'description'
                      ? TextInputType.text
                      : const TextInputType.numberWithOptions(decimal: true),
                  onChanged: (value) => _values[field.key] = value.trim(),
                  validator: (_) {
                    final value = _values[field.key]!.trim();
                    if (field.key == 'description') {
                      return value.isEmpty ? 'Enter a description.' : null;
                    }
                    final number = num.tryParse(value);
                    if (number == null ||
                        !number.isFinite ||
                        !RegExp(r'^(?:\d+(?:\.\d*)?|\.\d+)$').hasMatch(value)) {
                      return 'Enter a non-negative decimal amount.';
                    }
                    return field.key == 'quantity' && number == 0
                        ? 'Enter a positive quantity.'
                        : null;
                  },
                ),
              if (_error != null) SelectableText(_error!),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        FilledButton(
          onPressed: _saving || _unconfirmed ? null : _submit,
          child: Text(_saving ? 'Saving…' : 'Save line'),
        ),
      ],
    ),
  );
}
