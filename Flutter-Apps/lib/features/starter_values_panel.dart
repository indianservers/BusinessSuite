import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class StarterValuesPanel extends StatefulWidget {
  const StarterValuesPanel({
    super.key,
    required this.api,
    required this.editable,
  });
  final ApiClient api;
  final bool editable;

  @override
  State<StarterValuesPanel> createState() => _StarterValuesPanelState();
}

class _StarterValuesPanelState extends State<StarterValuesPanel> {
  static const _base = '/access/settings/starter-values';
  late Future<Json> _catalog = _load();
  String? _applying;
  String? _message;

  Future<Json> _load() async =>
      await widget.api.request('GET', '$_base/catalog') as Json;

  Future<void> _apply(String key, String title) async {
    if (_applying != null) return;
    setState(() {
      _applying = key;
      _message = null;
    });
    try {
      final data =
          await widget.api.request(
                'POST',
                '$_base/apply',
                data: {
                  'modules': [key],
                },
              )
              as Json;
      if (mounted) {
        final total = data['total'] as int;
        _message = total == 0
            ? '$title starter values are already configured.'
            : 'Added $total starter ${total == 1 ? 'record' : 'records'} for $title.';
      }
    } catch (error) {
      if (mounted) _message = '$error';
    } finally {
      if (mounted) setState(() => _applying = null);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Json>(
    future: _catalog,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const Center(child: CircularProgressIndicator());
      }
      if (snapshot.hasError) {
        return ListTile(
          title: Text('${snapshot.error}'),
          trailing: TextButton(
            onPressed: () => setState(() {
              _catalog = _load();
            }),
            child: const Text('Retry'),
          ),
        );
      }
      final groups = (snapshot.requireData['groups'] as List).cast<Json>();
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Add starter records for enabled applications. Existing values are preserved. Review leave allowances and shifts, and configure salary amounts and taxes before running payroll.',
          ),
          if (_message != null)
            Semantics(
              liveRegion: true,
              child: ListTile(title: Text(_message!)),
            ),
          if (groups.isEmpty)
            const ListTile(
              title: Text('No supported applications are enabled.'),
            ),
          for (final group in groups)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${group['title']}',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    for (final value
                        in (group['values'] as List).cast<String>())
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text(value),
                      ),
                    if (widget.editable)
                      FilledButton(
                        onPressed: _applying != null
                            ? null
                            : () => _apply(
                                group['key'] as String,
                                group['title'] as String,
                              ),
                        child: Text(
                          _applying == group['key']
                              ? 'Adding…'
                              : 'Add starter values',
                        ),
                      ),
                  ],
                ),
              ),
            ),
        ],
      );
    },
  );
}
