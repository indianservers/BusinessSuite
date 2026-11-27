import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';
import 'crm_deal_page.dart';
import 'crm_deal_stage_page.dart';

class CrmPipelinePage extends StatefulWidget {
  const CrmPipelinePage({
    super.key,
    required this.api,
    required this.scopeHeaders,
    required this.cacheScope,
    required this.offline,
    required this.dealBuilder,
    this.canMove = false,
    this.onDealChanged,
  });

  final ApiClient api;
  final Map<String, String> scopeHeaders;
  final String? cacheScope;
  final bool offline;
  final Widget Function(Json, bool, VoidCallback) dealBuilder;
  final bool canMove;
  final VoidCallback? onDealChanged;

  @override
  State<CrmPipelinePage> createState() => _CrmPipelinePageState();
}

class _CrmPipelinePageState extends State<CrmPipelinePage> {
  static const _pageSize = 25;
  late bool _offline = widget.offline;
  late var _pipelines = _list('/crm/pipelines', const {'per_page': '100'});
  Future<({Json? record, bool live})>? _stages, _deals;
  int? _pipeline, _stage;
  int _page = 1;
  String _search = '';

  Future<({Json? record, bool live})> _list(
    String path,
    Map<String, String> query, {
    Set<String>? fields,
  }) => loadCrmDetail(
    api: widget.api,
    path: Uri(path: path, queryParameters: query).toString(),
    scope: query.containsKey('search') ? null : widget.cacheScope,
    headers: widget.scopeHeaders,
    offline: _offline,
    project: (data) => {
      'total': data['total'],
      'items': [
        for (final row in _items(data))
          if (fields == null)
            row
          else
            {for (final field in fields) field: row[field]},
      ],
    },
  );

  static List<Json> _items(Json? record) =>
      (record?['items'] as List? ?? const []).whereType<Json>().toList();

  void _loadDeals(int pipeline, int? stage, int page) {
    _deals = _list(
      '/crm/deals',
      {
        'pipeline_id': '$pipeline',
        if (stage != null) 'stage_id': '$stage',
        'page': '$page',
        'per_page': '$_pageSize',
        if (_search.isNotEmpty) 'search': _search,
      },
      fields: {
        'id',
        'name',
        'status',
        'contact_name',
        'owner_name',
        ...CrmDealPage.summaryFields,
      },
    );
  }

  void _selectPipeline(int pipeline) {
    _pipeline = pipeline;
    _stage = null;
    _page = 1;
    _stages = _list('/crm/pipeline-stages', {
      'pipeline_id': '$pipeline',
      'sort_by': 'position',
      'sort_order': 'asc',
      'per_page': '100',
    });
    _loadDeals(pipeline, null, 1);
  }

  void _reloadDeals(int pipeline, int? stage, int page) => setState(() {
    _stage = stage;
    _page = page;
    _loadDeals(pipeline, stage, page);
  });

  Future<void> _moveDeal(int id, int pipeline) async {
    final result = await Navigator.of(context).push<Json>(
      MaterialPageRoute(
        builder: (_) => CrmDealStagePage(
          api: widget.api,
          id: id,
          scopeHeaders: widget.scopeHeaders,
        ),
      ),
    );
    if (!mounted || result == null) return;
    _reloadDeals(pipeline, _stage, _page);
    widget.onDealChanged?.call();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Pipeline'),
      actions: [
        IconButton(
          tooltip: 'Refresh pipeline',
          icon: const Icon(Icons.refresh),
          onPressed: () => setState(() {
            _offline = false;
            _pipeline = null;
            _search = '';
            _pipelines = _list('/crm/pipelines', const {'per_page': '100'});
          }),
        ),
      ],
    ),
    body: FutureBuilder<({Json? record, bool live})>(
      future: _pipelines,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        final pipelines = _items(
          snapshot.data?.record,
        ).where((row) => row['id'] is int).toList();
        if (pipelines.isEmpty) {
          return Center(
            child: Text(
              snapshot.data?.live == true
                  ? 'No pipelines.'
                  : 'No saved pipelines.',
            ),
          );
        }
        final pipeline =
            _pipeline ??
            (pipelines.firstWhere(
                  (row) => row['is_default'] == true,
                  orElse: () => pipelines.first,
                )['id']
                as int);
        if (_pipeline == null) _selectPipeline(pipeline);
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: DropdownButton<int>(
                isExpanded: true,
                value: pipeline,
                items: [
                  for (final row in pipelines)
                    DropdownMenuItem(
                      value: row['id'] as int,
                      child: Text('${row['name']}'),
                    ),
                ],
                onChanged: (id) {
                  if (id != null && id != _pipeline) {
                    setState(() => _selectPipeline(id));
                  }
                },
              ),
            ),
            FutureBuilder<({Json? record, bool live})>(
              key: ValueKey(pipeline),
              future: _stages,
              builder: (context, stages) {
                if (stages.hasError) return Text('${stages.error}');
                final rows = _items(
                  stages.data?.record,
                ).where((row) => row['id'] is int);
                return SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
                  child: Row(
                    spacing: 8,
                    children: [
                      ChoiceChip(
                        label: const Text('All stages'),
                        selected: _stage == null,
                        onSelected: (selected) {
                          if (selected) _reloadDeals(pipeline, null, 1);
                        },
                      ),
                      for (final row in rows)
                        ChoiceChip(
                          label: Text('${row['name']}'),
                          selected: _stage == row['id'],
                          onSelected: (selected) {
                            if (selected) {
                              _reloadDeals(pipeline, row['id'] as int, 1);
                            }
                          },
                        ),
                    ],
                  ),
                );
              },
            ),
            if (!_offline && snapshot.data?.live == true)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: TextField(
                  decoration: const InputDecoration(labelText: 'Search deals'),
                  textInputAction: TextInputAction.search,
                  onSubmitted: (term) {
                    _search = term.trim();
                    _reloadDeals(pipeline, _stage, 1);
                  },
                ),
              ),
            Expanded(child: _dealList(pipeline)),
          ],
        );
      },
    ),
  );

  Widget _dealList(int pipeline) => FutureBuilder<({Json? record, bool live})>(
    future: _deals,
    builder: (context, snapshot) {
      if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
      if (snapshot.connectionState != ConnectionState.done) {
        return const Center(child: CircularProgressIndicator());
      }
      final record = snapshot.data?.record;
      final rows = _items(record);
      final live = snapshot.data?.live == true;
      final total = record?['total'];
      return Column(
        children: [
          if (!live)
            Text(
              record == null ? 'No saved deals for this view.' : 'Saved deals',
            ),
          if (total is int)
            ListTile(
              dense: true,
              title: Text(total == 1 ? '1 deal' : '$total deals'),
            ),
          Expanded(
            child: rows.isEmpty && record != null
                ? const Center(child: Text('No deals in this view.'))
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: rows.length,
                    itemBuilder: (context, index) {
                      final row = rows[index];
                      final id = row['id'];
                      final name = '${row['name'] ?? 'Deal'}';
                      return Card(
                        child: ListTile(
                          title: Text(name),
                          subtitle: Text(
                            [
                                  row['company_name'] ?? row['contact_name'],
                                  row['stage_name'] ?? row['status'],
                                  if (row['amount'] != null)
                                    "${row['amount']} ${row['currency'] ?? ''}"
                                        .trim(),
                                  if (row['probability'] != null)
                                    "${row['probability']}%",
                                  if (row['expected_close_date'] != null)
                                    "Close ${row['expected_close_date']}",
                                  row['owner_name'],
                                ]
                                .whereType<String>()
                                .where((text) => text.isNotEmpty)
                                .join(' · '),
                          ),
                          trailing: live && widget.canMove && id is int
                              ? IconButton(
                                  tooltip: 'Move $name',
                                  icon: const Icon(Icons.swap_horiz),
                                  onPressed: () => _moveDeal(id, pipeline),
                                )
                              : null,
                          onTap: id is int
                              ? () => Navigator.of(context).push<void>(
                                  MaterialPageRoute(
                                    builder: (_) => widget.dealBuilder(
                                      row,
                                      !live,
                                      () =>
                                          _reloadDeals(pipeline, _stage, _page),
                                    ),
                                  ),
                                )
                              : null,
                        ),
                      );
                    },
                  ),
          ),
          if (_page > 1 || (total is int && _page * _pageSize < total))
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                TextButton(
                  onPressed: _page > 1
                      ? () => _reloadDeals(pipeline, _stage, _page - 1)
                      : null,
                  child: const Text('Previous'),
                ),
                Text('Page $_page'),
                TextButton(
                  onPressed: total is int && _page * _pageSize < total
                      ? () => _reloadDeals(pipeline, _stage, _page + 1)
                      : null,
                  child: const Text('Next'),
                ),
              ],
            ),
        ],
      );
    },
  );
}
