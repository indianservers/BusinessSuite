import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/models.dart';

class FinanceChartPage extends StatefulWidget {
  const FinanceChartPage({
    super.key,
    required this.api,
    this.cacheScope,
    this.scopeHeaders = const {},
    this.offline = false,
  });

  final ApiClient api;
  final String? cacheScope;
  final Map<String, String> scopeHeaders;
  final bool offline;

  @override
  State<FinanceChartPage> createState() => _FinanceChartPageState();
}

class _FinanceChartPageState extends State<FinanceChartPage> {
  late var _chart = _load(offline: widget.offline);
  int? _group;
  String _search = '';

  List<Json> _rows(Json data, String key) =>
      (data[key] as List? ?? const []).whereType<Json>().toList();

  Future<({Json? record, bool live})> _load({required bool offline}) =>
      loadCrmDetail(
        api: widget.api,
        path: '/fam/chart-of-accounts',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: offline,
        project: (data) => {
          'groups': [
            for (final row in _rows(data, 'groups'))
              {
                for (final key in [
                  'id',
                  'group_name',
                  'nature',
                  'system_group',
                ])
                  key: row[key],
              },
          ],
          'ledgers': [
            for (final row in _rows(data, 'ledgers'))
              {
                for (final key in [
                  'ledger_code',
                  'ledger_name',
                  'ledger_group_id',
                  'nature',
                  'ledger_type',
                  'active',
                ])
                  key: row[key],
              },
          ],
        },
      );

  void _refresh() => setState(() {
    _chart = _load(offline: false);
  });

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Chart of Accounts'),
      actions: [
        IconButton(
          tooltip: 'Refresh chart of accounts',
          icon: const Icon(LucideIcons.refreshCw),
          onPressed: _refresh,
        ),
      ],
    ),
    body: FutureBuilder(
      future: _chart,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final result = snapshot.requireData;
        final data = result.record;
        if (data == null) {
          return const Center(
            child: Text(
              'Open Chart of Accounts online to save it on this device.',
            ),
          );
        }
        final groups = _rows(data, 'groups');
        final ledgers = _rows(data, 'ledgers');
        final groupIds = {for (final group in groups) group['id']};
        final selected = groupIds.contains(_group) ? _group : null;
        final counts = <Object?, int>{};
        for (final ledger in ledgers) {
          counts.update(
            ledger['ledger_group_id'],
            (count) => count + 1,
            ifAbsent: () => 1,
          );
        }
        final visible = ledgers.where((ledger) {
          if (selected != null && ledger['ledger_group_id'] != selected) {
            return false;
          }
          return [
            ledger['ledger_code'],
            ledger['ledger_name'],
            ledger['nature'],
            ledger['ledger_type'],
          ].whereType<String>().any(
            (value) => value.toLowerCase().contains(_search),
          );
        }).toList();
        return CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (!result.live)
                    const ListTile(title: Text('Saved chart of accounts')),
                  ExpansionTile(
                    title: Text('Ledger groups (${groups.length})'),
                    children: [
                      ListTile(
                        title: const Text('All groups'),
                        onTap: () => setState(() => _group = null),
                        selected: selected == null,
                      ),
                      for (final group in groups)
                        ListTile(
                          title: Text('${group['group_name']}'),
                          subtitle: Text(
                            '${group['nature']} · ${counts[group['id']] ?? 0} ledgers'
                            '${group['system_group'] == true ? ' · System group' : ''}',
                          ),
                          selected: selected == group['id'],
                          onTap: () =>
                              setState(() => _group = group['id'] as int?),
                        ),
                    ],
                  ),
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: TextField(
                      onChanged: (value) =>
                          setState(() => _search = value.trim().toLowerCase()),
                      decoration: const InputDecoration(
                        labelText: 'Search ledgers',
                        prefixIcon: Icon(LucideIcons.search),
                      ),
                    ),
                  ),
                  if (visible.isEmpty)
                    const ListTile(title: Text('No matching ledgers')),
                ],
              ),
            ),
            SliverList.builder(
              itemCount: visible.length,
              itemBuilder: (context, index) {
                final ledger = visible[index];
                return ListTile(
                  title: Text('${ledger['ledger_name']}'),
                  subtitle: Text(
                    [
                      ledger['ledger_code'],
                      ledger['nature'],
                      ledger['ledger_type'],
                    ].whereType<String>().join(' · '),
                  ),
                  trailing: Text(
                    ledger['active'] == false ? 'Inactive' : 'Active',
                  ),
                );
              },
            ),
          ],
        );
      },
    ),
  );
}
