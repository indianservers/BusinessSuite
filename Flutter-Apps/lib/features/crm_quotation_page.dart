import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import '../core/suite_pdf.dart';

class CrmQuotationPage extends StatefulWidget {
  const CrmQuotationPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
    required this.scopeHeaders,
    this.cacheScope,
  });

  static const endpoint = '/crm/quotations';
  static const fields = [
    'quote_number',
    'issue_date',
    'expiry_date',
    'approval_status',
    'status',
    'currency',
    'grand_total',
    'total_amount',
  ];
  final ApiClient api;
  final Json summary;
  final bool offline;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;

  @override
  State<CrmQuotationPage> createState() => _CrmQuotationPageState();
}

class _CrmQuotationPageState extends State<CrmQuotationPage> {
  Json? _cached;
  bool _savingPdf = false;
  late Future<({Json? record, bool live})> _quote = _load(
    offline: widget.offline,
  );

  Future<({Json? record, bool live})> _load({bool offline = false}) =>
      loadCrmDetail(
        api: widget.api,
        path: '${CrmQuotationPage.endpoint}/${widget.summary['id']}',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        onCached: (record) {
          if (mounted) setState(() => _cached = record);
        },
        project: (record) => {
          for (final field in [
            ...CrmQuotationPage.fields,
            'terms_and_conditions',
            'terms',
          ])
            field: record[field],
          'lines': [
            for (final line
                in (record['lines'] as List? ?? const []).whereType<Json>())
              {
                for (final field in [
                  'name',
                  'quantity',
                  'unit_price',
                  'line_total',
                ])
                  field: line[field],
              },
          ],
        },
      );

  void _refresh() => setState(() {
    _cached = null;
    _quote = _load();
  });

  Future<void> _savePdf(Json quote) async {
    if (_savingPdf) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    final id = widget.summary['id'];
    setState(() => _savingPdf = true);
    try {
      final bytes = await fetchSuitePdf(
        api,
        '${CrmQuotationPage.endpoint}/$id/pdf',
        query: const {'download': true},
        scopeHeaders: widget.scopeHeaders,
      );
      if (!mounted || api.sessionRevision != revision) return;
      final number = '${quote['quote_number'] ?? id}'.replaceAll(
        RegExp(r'[^A-Za-z0-9._-]'),
        '_',
      );
      final saved = await FilePicker.saveFile(
        fileName: 'Quotation-$number.pdf',
        bytes: bytes,
      );
      if (mounted && saved != null && revision == api.sessionRevision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Quotation PDF saved.')));
      }
    } catch (error) {
      if (mounted && revision == api.sessionRevision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _savingPdf = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Quotation details'),
      actions: [
        IconButton(
          tooltip: 'Refresh quotation',
          icon: const Icon(Icons.refresh),
          onPressed: _refresh,
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _quote,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: TextButton(
              onPressed: _refresh,
              child: Text('${snapshot.error}\nRetry'),
            ),
          );
        }
        final record = snapshot.data?.record ?? _cached ?? widget.summary;
        final currency = record['currency'] ?? '';
        final amount = record['grand_total'] ?? record['total_amount'];
        final fields = {
          'Status': record['status'],
          'Approval': (record['approval_status'] as String?)?.replaceAll(
            '_',
            ' ',
          ),
          'Issued': record['issue_date'],
          'Expires': record['expiry_date'],
          'Total': amount == null ? null : '$amount $currency'.trim(),
          'Terms': record['terms_and_conditions'] ?? record['terms'],
        };
        final lines = (record['lines'] as List? ?? const [])
            .whereType<Json>()
            .toList();
        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: lines.length + 1,
          itemBuilder: (context, index) {
            if (index == 0) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (snapshot.connectionState != ConnectionState.done)
                    const LinearProgressIndicator()
                  else if (snapshot.data?.live != true)
                    const Text('Saved quotation'),
                  Text(
                    '${record['quote_number'] ?? 'Quotation'}',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  if (snapshot.connectionState == ConnectionState.done &&
                      snapshot.data?.live == true)
                    OutlinedButton.icon(
                      onPressed: _savingPdf ? null : () => _savePdf(record),
                      icon: const Icon(Icons.picture_as_pdf_outlined),
                      label: Text(
                        _savingPdf ? 'Preparing PDF…' : 'Save quotation PDF',
                      ),
                    ),
                  for (final field in fields.entries)
                    if (field.value != null &&
                        field.value.toString().isNotEmpty)
                      ListTile(
                        title: Text(field.key),
                        subtitle: Text('${field.value}'),
                      ),
                  if (lines.isNotEmpty)
                    Text(
                      'Items',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                ],
              );
            }
            final line = lines[index - 1];
            return ListTile(
              title: Text('${line['name'] ?? 'Item'}'),
              subtitle: Text(
                "${line['quantity'] ?? '—'} × ${line['unit_price'] ?? '—'} $currency"
                    .trim(),
              ),
              trailing: Text("${line['line_total'] ?? '—'} $currency".trim()),
            );
          },
        );
      },
    ),
  );
}
