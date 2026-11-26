import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class LeadSourcesPanel extends StatefulWidget {
  const LeadSourcesPanel({
    super.key,
    required this.api,
    required this.editable,
  });
  final ApiClient api;
  final bool editable;

  @override
  State<LeadSourcesPanel> createState() => _LeadSourcesPanelState();
}

class _LeadSourcesPanelState extends State<LeadSourcesPanel> {
  static const _endpoint = '/access/settings/crm-lead-sources/options';
  final _text = TextEditingController();
  List<String>? _defaults;
  bool _busy = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    await _run(() async {
      final data = await widget.api.request('GET', _endpoint) as Json;
      if (!mounted) return;
      _defaults = (data['defaults'] as List).cast<String>();
      _text.text = (data['sources'] as List).cast<String>().join('\n');
    });
  }

  Future<void> _save() async {
    final sources = _text.text
        .split('\n')
        .map((v) => v.trim())
        .where((v) => v.isNotEmpty)
        .toList();
    final unique = sources.map((v) => v.toLowerCase()).toSet();
    final maximum = unique.contains('other') ? 100 : 99;
    if (sources.isEmpty ||
        sources.length > maximum ||
        unique.length != sources.length ||
        sources.any((v) => v.length > 80)) {
      setState(
        () => _message =
            'Use unique names of up to 80 characters. Keep at most 100 sources including Other.',
      );
      return;
    }
    await _run(() async {
      final data =
          await widget.api.request('PUT', _endpoint, data: {'sources': sources})
              as Json;
      if (!mounted) return;
      _text.text = (data['sources'] as List).cast<String>().join('\n');
      _message = 'Lead sources saved.';
    });
  }

  Future<void> _run(Future<void> Function() operation) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await operation();
    } catch (error) {
      if (mounted) _message = '$error';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      if (_busy) const LinearProgressIndicator(),
      if (_defaults != null) ...[
        const Text(
          'These choices are shared by lead, contact, and deal forms. Enter one source per line.',
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _text,
          readOnly: !widget.editable || _busy,
          minLines: 5,
          maxLines: 10,
          decoration: const InputDecoration(
            labelText: 'Lead sources',
            border: OutlineInputBorder(),
          ),
        ),
        if (widget.editable)
          Wrap(
            spacing: 8,
            children: [
              FilledButton(
                onPressed: _busy ? null : _save,
                child: const Text('Save sources'),
              ),
              OutlinedButton(
                onPressed: _busy
                    ? null
                    : () => _text.text = _defaults!.join('\n'),
                child: const Text('Use starter list'),
              ),
            ],
          ),
      ] else if (!_busy)
        OutlinedButton(onPressed: _load, child: const Text('Retry')),
      if (_message != null)
        Semantics(liveRegion: true, child: ListTile(title: Text(_message!))),
    ],
  );
}
