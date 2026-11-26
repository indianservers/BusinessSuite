import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class SuiteNotificationsPage extends StatefulWidget {
  const SuiteNotificationsPage({super.key, required this.api});
  final ApiClient api;

  @override
  State<SuiteNotificationsPage> createState() => _SuiteNotificationsPageState();
}

class _SuiteNotificationsPageState extends State<SuiteNotificationsPage> {
  bool _unread = false;
  bool _saving = false;
  int _page = 1;
  late Future<Json> _result = _load();

  Future<Json> _load() async =>
      await widget.api.request(
            'GET',
            '/notifications/',
            query: {'unread_only': _unread, 'page': _page},
          )
          as Json;

  void _refresh({int? page, bool? unread}) => setState(() {
    _page = page ?? _page;
    _unread = unread ?? _unread;
    _result = _load();
  });

  Future<bool> _mark(String path) async {
    if (_saving) return false;
    setState(() => _saving = true);
    try {
      await widget.api.request('PUT', path);
      if (mounted) _refresh(page: 1);
      return true;
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
      return false;
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _open(Json item) async {
    final id = item['id'];
    if (item['is_read'] == false && id is int) {
      await _mark('/notifications/$id/read');
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${item['title'] ?? 'Notification'}'),
        content: SingleChildScrollView(
          child: SelectableText('${item['message'] ?? ''}'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Notifications'),
      actions: [
        IconButton(
          tooltip: 'Mark all as read',
          icon: const Icon(LucideIcons.checkCheck),
          onPressed: _saving
              ? null
              : () => _mark('/notifications/mark-all-read'),
        ),
        IconButton(
          tooltip: 'Refresh notifications',
          icon: const Icon(LucideIcons.refreshCw),
          onPressed: _saving ? null : _refresh,
        ),
      ],
    ),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: SegmentedButton<bool>(
            segments: const [
              ButtonSegment(value: false, label: Text('All')),
              ButtonSegment(value: true, label: Text('Unread')),
            ],
            selected: {_unread},
            onSelectionChanged: _saving
                ? null
                : (value) => _refresh(page: 1, unread: value.single),
          ),
        ),
        Expanded(
          child: FutureBuilder<Json>(
            future: _result,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text('${snapshot.error}', textAlign: TextAlign.center),
                      TextButton(
                        onPressed: _refresh,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                );
              }
              final data = snapshot.data ?? {};
              final rows = (data['items'] as List? ?? [])
                  .whereType<Json>()
                  .toList();
              final pages = data['pages'] as int? ?? 1;
              return Column(
                children: [
                  Expanded(
                    child: rows.isEmpty
                        ? Center(
                            child: Text(
                              _unread
                                  ? 'No unread notifications'
                                  : 'No notifications',
                            ),
                          )
                        : ListView.builder(
                            itemCount: rows.length,
                            itemBuilder: (context, index) {
                              final item = rows[index];
                              final unread = item['is_read'] == false;
                              return ListTile(
                                leading: Icon(
                                  unread
                                      ? LucideIcons.bellDot
                                      : LucideIcons.bell,
                                ),
                                title: Text(
                                  '${item['title'] ?? 'Notification'}',
                                  style: TextStyle(
                                    fontWeight: unread
                                        ? FontWeight.w700
                                        : FontWeight.normal,
                                  ),
                                ),
                                subtitle: Text(
                                  '${item['message'] ?? ''}',
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                onTap: _saving ? null : () => _open(item),
                              );
                            },
                          ),
                  ),
                  if (pages > 1)
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        IconButton(
                          tooltip: 'Previous page',
                          icon: const Icon(LucideIcons.chevronLeft),
                          onPressed: _saving || _page <= 1
                              ? null
                              : () => _refresh(page: _page - 1),
                        ),
                        Text('$_page of $pages'),
                        IconButton(
                          tooltip: 'Next page',
                          icon: const Icon(LucideIcons.chevronRight),
                          onPressed: _saving || _page >= pages
                              ? null
                              : () => _refresh(page: _page + 1),
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
