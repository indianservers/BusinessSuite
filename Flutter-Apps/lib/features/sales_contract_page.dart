import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';
import 'crm_customer_page.dart';
import 'gst_invoice_page.dart';
import 'sales_engagement_page.dart';
import 'sales_order_page.dart';

class SalesContractPage extends StatefulWidget {
  const SalesContractPage({
    super.key,
    required this.api,
    required this.summary,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
    required this.canEdit,
    required this.onChanged,
  });

  static const endpoint = '/srm/contracts';
  static String listCacheKey(String scope, Map<String, String> headers) =>
      '$scope:$endpoint:${headers['X-Suite-Branch'] ?? ''}';
  final ApiClient api;
  final Json summary;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;
  final bool canEdit;
  final VoidCallback onChanged;

  @override
  State<SalesContractPage> createState() => _SalesContractPageState();
}

class _SalesContractPageState extends State<SalesContractPage> {
  static const _fields = {
    'contract_number': 'Contract number',
    'status': 'Status',
    'contract_type': 'Contract type',
    'effective_date': 'Effective date',
    'expiry_date': 'Expiry date',
    'contract_value': 'Contract value',
    'customer_id': 'Customer ID',
    'sales_order_id': 'Sales order ID',
    'terms': 'Terms',
  };
  String get _path => '${SalesContractPage.endpoint}/${widget.summary['id']}';
  Json? _cached;
  String? _error;
  bool _activating = false;
  late var _detail = _load(offline: widget.offline);

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: _path,
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        onCached: (saved) {
          if (mounted) setState(() => _cached = saved);
        },
        project: (record) => {
          for (final field in ['title', 'currency', ..._fields.keys])
            field: record[field],
          if (record['sales_order'] case final Json order)
            'sales_order': {
              for (final field in ['id', 'order_number', 'title', 'status'])
                field: order[field],
            },
          if (record['engagement'] case final Json engagement)
            'engagement': {
              for (final field in ['id', 'engagement_number', 'name', 'status'])
                field: engagement[field],
            },
          'invoices': [
            for (final invoice
                in (record['invoices'] as List? ?? []).whereType<Json>())
              {
                for (final field in ['id', ...GstInvoicePage.summaryFields])
                  field: invoice[field],
              },
          ],
        },
      );

  void _refresh() => setState(() {
    _cached = null;
    _error = null;
    _detail = _load();
  });

  Future<void> _activate() async {
    if (_activating) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    setState(() {
      _activating = true;
      _error = null;
    });
    try {
      await api.request(
        'POST',
        '$_path/activate',
        scopeHeaders: widget.scopeHeaders,
      );
      if (!mounted || api.sessionRevision != revision) return;
      if (widget.cacheScope case final scope?) {
        try {
          await SuiteReadCache.invalidate(
            SalesContractPage.listCacheKey(scope, widget.scopeHeaders),
          );
        } catch (_) {
          // The contract is already active on the server.
        }
      }
      if (!mounted || api.sessionRevision != revision) return;
      _refresh();
      widget.onChanged();
    } on ApiFailure catch (error) {
      if (mounted && api.sessionRevision == revision) {
        setState(() => _error = error.message);
      }
    } finally {
      if (mounted) setState(() => _activating = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Contract details'),
      actions: [
        IconButton(
          tooltip: 'Refresh contract',
          icon: const Icon(Icons.refresh),
          onPressed: _activating ? null : _refresh,
        ),
      ],
    ),
    body: FutureBuilder(
      future: _detail,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(child: Text('${snapshot.error}'));
        }
        final loading = snapshot.connectionState != ConnectionState.done;
        final result = loading ? null : snapshot.data;
        final record = result?.record ?? _cached ?? widget.summary;
        final offline = result?.live != true;
        final customerId = record['customer_id'];
        final order = record['sales_order'] as Json?;
        final engagement = record['engagement'] as Json?;
        final invoices = (record['invoices'] as List? ?? []).whereType<Json>();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${record['title'] ?? 'Contract'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (loading) const LinearProgressIndicator(),
            if (!loading && result?.live != true)
              const ListTile(title: Text('Saved contract')),
            if (_error case final message?) ListTile(title: Text(message)),
            if (widget.canEdit &&
                result?.live == true &&
                record['status'] == 'draft')
              FilledButton(
                onPressed: _activating ? null : _activate,
                child: const Text('Activate contract'),
              ),
            for (final field in _fields.entries)
              if (record[field.key] != null)
                ListTile(
                  title: Text(field.value),
                  subtitle: SelectableText(
                    field.key == 'contract_value'
                        ? '${record['currency'] ?? ''} ${record[field.key]}'
                              .trim()
                        : '${record[field.key]}',
                  ),
                ),
            if (customerId is int ||
                order?['id'] is int ||
                engagement?['id'] is int ||
                invoices.isNotEmpty) ...[
              const Divider(),
              Text(
                'Related records',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              if (customerId is int)
                ListTile(
                  title: const Text('Open customer'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => CrmCustomerPage(
                        api: widget.api,
                        summary: {
                          'id': customerId,
                          'name': 'Customer #$customerId',
                        },
                        offline: offline,
                        cacheScope: widget.cacheScope,
                        scopeHeaders: widget.scopeHeaders,
                        salesContext: true,
                      ),
                    ),
                  ),
                ),
              if (order?['id'] is int)
                ListTile(
                  title: Text('${order!['order_number'] ?? 'Sales order'}'),
                  subtitle: const Text('Sales order'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => SalesOrderPage(
                        api: widget.api,
                        summary: order,
                        offline: offline,
                        cacheScope: widget.cacheScope,
                        scopeHeaders: widget.scopeHeaders,
                      ),
                    ),
                  ),
                ),
              if (engagement?['id'] is int)
                ListTile(
                  title: Text(
                    '${engagement!['engagement_number'] ?? 'Engagement'}',
                  ),
                  subtitle: const Text('Engagement'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => SalesEngagementPage(
                        api: widget.api,
                        summary: engagement,
                        scopeHeaders: widget.scopeHeaders,
                        cacheScope: widget.cacheScope,
                        offline: offline,
                      ),
                    ),
                  ),
                ),
              for (final invoice in invoices)
                if (invoice['id'] case final int id)
                  ListTile(
                    title: Text('${invoice['invoice_number'] ?? 'Invoice'}'),
                    subtitle: const Text('GST invoice'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => GstInvoicePage(
                          api: widget.api,
                          id: id,
                          summary: invoice,
                          offline: offline,
                          cacheScope: widget.cacheScope,
                          scopeHeaders: widget.scopeHeaders,
                        ),
                      ),
                    ),
                  ),
            ],
          ],
        );
      },
    ),
  );
}
