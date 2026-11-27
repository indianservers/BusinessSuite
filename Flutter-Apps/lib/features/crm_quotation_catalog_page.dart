import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class CrmQuotationCatalogPage extends StatefulWidget {
  const CrmQuotationCatalogPage({
    super.key,
    required this.api,
    required this.scopeHeaders,
    required this.currency,
  });
  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final String? currency;

  @override
  State<CrmQuotationCatalogPage> createState() =>
      _CrmQuotationCatalogPageState();
}

class _CrmQuotationCatalogPageState extends State<CrmQuotationCatalogPage> {
  String _search = '';
  int _page = 1;
  late Future<Json> _results = _load();

  Future<Json> _load() async {
    final revision = widget.api.sessionRevision;
    final data =
        await widget.api.request(
              'GET',
              '/catalog/items',
              query: {'source': 'crm', 'search': _search, 'page': _page},
              scopeHeaders: widget.scopeHeaders,
            )
            as Json;
    if (revision != widget.api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    return data;
  }

  void _move(int page) => setState(() {
    _page = page;
    _results = _load();
  });

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Choose a product or service')),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: TextField(
            maxLength: 180,
            textInputAction: TextInputAction.search,
            decoration: const InputDecoration(labelText: 'Search catalog'),
            onSubmitted: (value) {
              _search = value.trim();
              _move(1);
            },
          ),
        ),
        Expanded(
          child: FutureBuilder<Json>(
            future: _results,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return Center(
                  child: TextButton(
                    onPressed: () => _move(_page),
                    child: Text('${snapshot.error}\nRetry'),
                  ),
                );
              }
              final rows = (snapshot.data?['items'] as List? ?? const [])
                  .whereType<Json>()
                  .where(
                    (item) =>
                        item['id'] is int &&
                        const {'product', 'service'}.contains(item['kind']),
                  )
                  .toList();
              return Column(
                children: [
                  Expanded(
                    child: rows.isEmpty
                        ? const Center(
                            child: Text('No products or services found'),
                          )
                        : ListView.builder(
                            itemCount: rows.length,
                            itemBuilder: (context, index) {
                              final item = rows[index];
                              final code = item['currency'] as String?;
                              final matches =
                                  widget.currency == null ||
                                  code == widget.currency;
                              return ListTile(
                                enabled: matches,
                                title: Text('${item['name']}'),
                                subtitle: Text(
                                  matches
                                      ? "${item['code'] ?? ''} · ${item['price']} ${code ?? ''}"
                                      : 'Uses a different currency',
                                ),
                                onTap: matches
                                    ? () => Navigator.pop(context, item)
                                    : null,
                              );
                            },
                          ),
                  ),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      TextButton(
                        onPressed: _page > 1 ? () => _move(_page - 1) : null,
                        child: const Text('Previous'),
                      ),
                      TextButton(
                        onPressed:
                            _page < (snapshot.data?['pages'] as int? ?? 1)
                            ? () => _move(_page + 1)
                            : null,
                        child: const Text('Next'),
                      ),
                    ],
                  ),
                ],
              );
            },
          ),
        ),
      ],
    ),
  );
}
