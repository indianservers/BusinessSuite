import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class InventoryBatchPage extends StatefulWidget {
  const InventoryBatchPage({
    super.key,
    required this.api,
    required this.summary,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
  });

  static const batches = '/srm/inventory/batches';
  static const serials = '/srm/inventory/serial-numbers';
  static const fields = {
    'batch_number': 'Batch number',
    'product_id': 'Product',
    'warehouse_id': 'Warehouse',
    'manufacture_date': 'Manufactured',
    'expiry_date': 'Expires',
    'quantity': 'Quantity',
    'available_quantity': 'Available quantity',
    'status': 'Status',
    'serial_count': 'Serial count',
  };
  static const serialFields = {
    'serial_number': 'Serial number',
    'product_id': 'Product',
    'batch_id': 'Batch',
    'warehouse_id': 'Warehouse',
    'received_date': 'Received',
    'reference_number': 'Reference',
    'status': 'Status',
  };

  final ApiClient api;
  final Json summary;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;

  @override
  State<InventoryBatchPage> createState() => _InventoryBatchPageState();
}

class _InventoryBatchPageState extends State<InventoryBatchPage> {
  Json? _saved;
  late var _detail = _load(offline: widget.offline);

  Future<({Json? record, bool live})> _load({required bool offline}) =>
      loadCrmDetail(
        api: widget.api,
        path: '${InventoryBatchPage.batches}/${widget.summary['id']}',
        headers: widget.scopeHeaders,
        scope: widget.cacheScope,
        offline: offline,
        onCached: (record) {
          if (mounted) setState(() => _saved = record);
        },
        project: (record) => {
          for (final field in InventoryBatchPage.fields.keys)
            field: record[field],
          'serials': [
            for (final row in _serials(record))
              {
                for (final field in InventoryBatchPage.serialFields.keys)
                  field: row[field],
              },
          ],
        },
      );

  static Iterable<Json> _serials(Json record) =>
      (record['serials'] as List? ?? const []).whereType<Json>();

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Batch details'),
      actions: [
        IconButton(
          tooltip: 'Refresh batch',
          icon: const Icon(Icons.refresh),
          onPressed: () => setState(() => _detail = _load(offline: false)),
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _detail,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final cached = snapshot.data?.record ?? _saved;
        final record = cached ?? widget.summary;
        final serials = _serials(record).toList();
        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: serials.length + 1,
          itemBuilder: (context, index) {
            if (index > 0) {
              final serial = serials[index - 1];
              return ListTile(
                title: Text('${serial['serial_number'] ?? 'Serial number'}'),
                subtitle: Text(
                  [
                    serial['status'],
                    serial['reference_number'],
                  ].whereType<String>().join(' · '),
                ),
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (snapshot.connectionState != ConnectionState.done)
                  const LinearProgressIndicator()
                else if (snapshot.data?.live != true)
                  Text(cached == null ? 'Saved batch summary' : 'Saved batch'),
                Text(
                  '${record['batch_number'] ?? 'Batch'}',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                for (final field in InventoryBatchPage.fields.entries)
                  if (field.key != 'batch_number' && record[field.key] != null)
                    ListTile(
                      title: Text(field.value),
                      subtitle: Text('${record[field.key]}'),
                    ),
                if (cached != null && serials.isEmpty)
                  const Text('No serial numbers in this batch.'),
                if (serials.isNotEmpty)
                  Text(
                    'Serial numbers',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
              ],
            );
          },
        );
      },
    ),
  );
}
