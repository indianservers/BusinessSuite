import 'dart:async';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../core/api_client.dart';
import '../core/models.dart';
import 'pms_catalog.dart';

typedef OpenPmsAction =
    Future<void> Function(
      PmsOperation operation,
      Map<String, dynamic> scope,
      Json initial,
    );

class PmsTimerPage extends StatefulWidget {
  const PmsTimerPage({
    super.key,
    required this.controller,
    this.projectId,
    this.taskId,
  });
  final AppController controller;
  final int? projectId, taskId;
  @override
  State<PmsTimerPage> createState() => _PmsTimerPageState();
}

class _PmsTimerPageState extends State<PmsTimerPage>
    with WidgetsBindingObserver {
  Json? _timer;
  bool _loading = false;
  String? _error;
  int? _projectId, _taskId;
  final _description = TextEditingController();
  Timer? _tick;
  AppController get c => widget.controller;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _projectId = widget.projectId;
    _taskId = widget.taskId;
    _load();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted && _timer?['active'] == true) setState(() {});
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _tick?.cancel();
    _description.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final result = await c.api.request('GET', '/project-management/timer');
      if (mounted) {
        setState(
          () => _timer = result == null
              ? null
              : Map<String, dynamic>.from(result),
        );
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _action(String action) async {
    if (_loading) return;
    if (action == 'start' && _projectId == null) {
      setState(() => _error = 'Choose a project.');
      return;
    }
    if (action != 'start') {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialog) => AlertDialog(
          title: Text(
            action == 'stop' ? 'Stop and save time?' : 'Discard this timer?',
          ),
          content: Text(
            action == 'stop'
                ? 'Elapsed time will be saved to your project time log.'
                : 'This running timer will end without creating a time log.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialog, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialog, true),
              child: const Text('Confirm'),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
    }
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final payload = action == 'start'
          ? {
              'project_id': _projectId,
              'task_id': _taskId,
              'session_key': const Uuid().v4(),
              'description': _description.text,
              'timezone': 'Asia/Kolkata',
            }
          : {'session_key': _timer!['session_key']};
      await c.api.request(
        'POST',
        '/project-management/timer/$action',
        data: payload,
      );
      await _load();
      if (mounted && action == 'stop') {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Time log saved.')));
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final active = _timer?['active'] == true;
    final started = DateTime.tryParse('${_timer?['started_at']}');
    final elapsed = started == null
        ? Duration.zero
        : DateTime.now().toUtc().difference(started.toUtc());
    final clock =
        '${elapsed.inHours.toString().padLeft(2, '0')}:${(elapsed.inMinutes % 60).toString().padLeft(2, '0')}:${(elapsed.inSeconds % 60).toString().padLeft(2, '0')}';
    return Scaffold(
      appBar: AppBar(
        title: const Text('Project timer'),
        actions: [
          IconButton(
            tooltip: 'Refresh timer',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          if (_loading) const LinearProgressIndicator(),
          if (_error != null)
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          Text(
            active ? clock : 'Ready to track time',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 24),
          if (active) ...[
            Text('${_timer!['description'] ?? ''}'),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _loading || c.selected?.canEdit != true
                  ? null
                  : () => _action('stop'),
              icon: const Icon(Icons.stop),
              label: const Text('Stop and save time'),
            ),
            TextButton(
              onPressed: _loading || c.selected?.canEdit != true
                  ? null
                  : () => _action('discard'),
              child: const Text('Discard timer'),
            ),
          ] else ...[
            DropdownButtonFormField<int>(
              initialValue: _projectId,
              decoration: const InputDecoration(labelText: 'Project'),
              isExpanded: true,
              items: (c.overview?.projects ?? [])
                  .map(
                    (p) => DropdownMenuItem(value: p.id, child: Text(p.name)),
                  )
                  .toList(),
              onChanged: (id) => setState(() {
                _projectId = id;
                _taskId = null;
              }),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<int>(
              key: ValueKey('timer-$_projectId'),
              initialValue: _taskId,
              decoration: const InputDecoration(labelText: 'Task (optional)'),
              isExpanded: true,
              items: [
                const DropdownMenuItem<int>(
                  value: null,
                  child: Text('No task'),
                ),
                ...(c.overview?.tasks ?? [])
                    .where((t) => t.projectId == _projectId)
                    .map(
                      (t) =>
                          DropdownMenuItem(value: t.id, child: Text(t.title)),
                    ),
              ],
              onChanged: (id) => setState(() => _taskId = id),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _description,
              decoration: const InputDecoration(labelText: 'Work description'),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _loading || c.selected?.canEdit != true
                  ? null
                  : () => _action('start'),
              icon: const Icon(Icons.play_arrow),
              label: const Text('Start timer'),
            ),
          ],
        ],
      ),
    );
  }
}

class PmsMessagesPage extends StatefulWidget {
  const PmsMessagesPage({
    super.key,
    required this.controller,
    required this.workspaceId,
    required this.catalog,
    required this.openAction,
  });
  final AppController controller;
  final int workspaceId;
  final PmsCatalog catalog;
  final OpenPmsAction openAction;
  @override
  State<PmsMessagesPage> createState() => _PmsMessagesPageState();
}

class _PmsMessagesPageState extends State<PmsMessagesPage> {
  List<Json> _rooms = [];
  String? _error;
  bool _loading = true;
  String get base =>
      '/project-management/workspaces/${widget.workspaceId}/chat';
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final response = await widget.controller.api.request(
        'GET',
        '$base/conversations',
      );
      if (mounted) setState(() => _rooms = records(response));
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Messages'),
      actions: [
        IconButton(
          tooltip: 'Refresh conversations',
          onPressed: _loading ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    floatingActionButton: widget.controller.selected?.canEdit == true
        ? FloatingActionButton.extended(
            onPressed: () async {
              final op = widget.catalog.find(
                'POST',
                '/project-management/workspaces/{wid}/chat/conversations',
              )!;
              await widget.openAction(op, {
                'wid': widget.workspaceId,
                'workspace_id': widget.workspaceId,
              }, {});
              if (mounted) _load();
            },
            icon: const Icon(Icons.add_comment_outlined),
            label: const Text('Conversation'),
          )
        : null,
    body: Column(
      children: [
        if (_loading) const LinearProgressIndicator(),
        if (_error != null)
          Padding(padding: const EdgeInsets.all(20), child: Text(_error!)),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _load,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                if (!_loading && _rooms.isEmpty)
                  const Text('No conversations yet.'),
                ..._rooms.map(
                  (room) => Card(
                    child: ListTile(
                      title: Text('${room['name'] ?? 'Conversation'}'),
                      subtitle: Text(
                        '${room['kind']} · ${room['unread'] ?? 0} unread',
                      ),
                      trailing: room['muted'] == true
                          ? const Icon(Icons.notifications_off_outlined)
                          : const Icon(Icons.chevron_right),
                      onTap: () async {
                        await Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => PmsChatRoom(
                              controller: widget.controller,
                              workspaceId: widget.workspaceId,
                              room: room,
                              catalog: widget.catalog,
                              openAction: widget.openAction,
                            ),
                          ),
                        );
                        if (mounted) _load();
                      },
                    ),
                  ),
                ),
                const SizedBox(height: 90),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}

class PmsChatRoom extends StatefulWidget {
  const PmsChatRoom({
    super.key,
    required this.controller,
    required this.workspaceId,
    required this.room,
    required this.catalog,
    required this.openAction,
    this.parentId,
  });
  final AppController controller;
  final int workspaceId;
  final Json room;
  final PmsCatalog catalog;
  final OpenPmsAction openAction;
  final int? parentId;
  @override
  State<PmsChatRoom> createState() => _PmsChatRoomState();
}

class _PmsChatRoomState extends State<PmsChatRoom> with WidgetsBindingObserver {
  List<Json> _messages = [];
  final _text = TextEditingController();
  final _scroll = ScrollController();
  final List<Json> _attachments = [];
  bool _loading = false, _sending = false;
  String? _error;
  int? _before;
  Timer? _poll;
  String? _pendingRequest;
  AppController get c => widget.controller;
  String get base =>
      '/project-management/workspaces/${widget.workspaceId}/chat/conversations/${widget.room['id']}';
  Map<String, dynamic> get scope => {
    'wid': widget.workspaceId,
    'workspace_id': widget.workspaceId,
    'rid': widget.room['id'],
  };
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
    _poll = Timer.periodic(const Duration(seconds: 8), (_) {
      if (WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed &&
          mounted &&
          ModalRoute.of(context)?.isCurrent == true &&
          !_sending &&
          !_loading) {
        _load(quiet: true);
      }
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _poll?.cancel();
    _text.dispose();
    _scroll.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _load();
  }

  Future<void> _load({bool older = false, bool quiet = false}) async {
    if (!quiet) setState(() => _loading = true);
    try {
      final response = await c.api.request(
        'GET',
        '$base/messages',
        query: {
          'limit': 50,
          if (older && _before != null) 'before': _before,
          if (widget.parentId != null) 'parent_id': widget.parentId,
        },
      );
      final items = records(response);
      if (mounted) {
        setState(() {
          _messages = older ? [...items, ..._messages] : items;
          _before = response['before'] as int?;
          _error = null;
        });
      }
      if (items.isNotEmpty) {
        await c.api.request(
          'PUT',
          '$base/read',
          data: {'message_id': items.last['id']},
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '$e';
          if (e is ApiFailure && const {403, 404}.contains(e.status)) {
            _messages = [];
            _attachments.clear();
            _before = null;
          }
        });
      }
    } finally {
      if (mounted && !quiet) setState(() => _loading = false);
    }
  }

  Future<void> _send() async {
    if (_sending || (_text.text.trim().isEmpty && _attachments.isEmpty)) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    _pendingRequest ??= const Uuid().v4();
    try {
      await c.api.request(
        'POST',
        '$base/messages',
        data: {
          'body': _text.text.trim(),
          'client_id': _pendingRequest,
          if (widget.parentId != null) 'parent_id': widget.parentId,
          'attachment_ids': _attachments.map((a) => a['id']).toList(),
        },
      );
      _pendingRequest = null;
      _text.clear();
      _attachments.clear();
      await _load();
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _attach() async {
    try {
      final file = await FilePicker.pickFile();
      if (file == null) return;
      final size = await file.length();
      if (size != null && size > 3 * 1024 * 1024) {
        throw StateError('Choose a file up to 3 MB.');
      }
      final bytes = await file.readAsBytes();
      if (bytes.length > 3 * 1024 * 1024) {
        throw StateError('Choose a file up to 3 MB.');
      }
      setState(() => _sending = true);
      final response = await c.api.request(
        'POST',
        '$base/attachments',
        data: FormData.fromMap({
          'file': MultipartFile.fromBytes(bytes, filename: file.name),
        }),
      );
      if (mounted) {
        setState(() => _attachments.add(Map<String, dynamic>.from(response)));
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _actions(Json message) async {
    final action = await showModalBottomSheet<String>(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              title: const Text('Replies'),
              onTap: () => Navigator.pop(context, 'thread'),
            ),
            if (message['author_id'] == c.user?.id &&
                message['deleted_at'] == null) ...[
              ListTile(
                title: const Text('Edit message'),
                onTap: () => Navigator.pop(context, 'edit'),
              ),
              ListTile(
                title: const Text('Delete message'),
                onTap: () => Navigator.pop(context, 'delete'),
              ),
            ],
          ],
        ),
      ),
    );
    if (!mounted || action == null) return;
    if (action == 'thread') {
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => PmsChatRoom(
            controller: c,
            workspaceId: widget.workspaceId,
            room: widget.room,
            catalog: widget.catalog,
            openAction: widget.openAction,
            parentId: message['id'] as int,
          ),
        ),
      );
    } else {
      final op = widget.catalog.find(
        action == 'edit' ? 'PATCH' : 'DELETE',
        '/project-management/workspaces/{wid}/chat/conversations/{rid}/messages/{mid}',
      )!;
      await widget.openAction(op, {...scope, 'mid': message['id']}, message);
    }
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.parentId == null ? '${widget.room['name']}' : 'Replies',
      ),
      actions: [
        IconButton(
          tooltip: 'Conversation settings',
          onPressed: () async {
            final options = widget.catalog.operations
                .where(
                  (o) =>
                      o.available &&
                      o.path.startsWith(
                        '/project-management/workspaces/{wid}/chat/conversations/{rid}',
                      ) &&
                      !o.path.contains('/messages') &&
                      o.allowed(c),
                )
                .toList();
            final action = await showModalBottomSheet<PmsOperation>(
              context: context,
              builder: (context) => SafeArea(
                child: ListView(
                  shrinkWrap: true,
                  children: options
                      .map(
                        (o) => ListTile(
                          title: Text(o.title),
                          onTap: () => Navigator.pop(context, o),
                        ),
                      )
                      .toList(),
                ),
              ),
            );
            if (action != null) {
              await widget.openAction(action, scope, widget.room);
            }
            if (mounted) _load();
          },
          icon: const Icon(Icons.more_vert),
        ),
      ],
    ),
    body: SafeArea(
      child: Column(
        children: [
          if (_loading || _sending) const LinearProgressIndicator(),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          Expanded(
            child: ListView(
              controller: _scroll,
              padding: const EdgeInsets.all(16),
              children: [
                if (_before != null)
                  TextButton(
                    onPressed: _loading ? null : () => _load(older: true),
                    child: const Text('Older messages'),
                  ),
                for (final message in _messages)
                  Align(
                    alignment: message['author_id'] == c.user?.id
                        ? Alignment.centerRight
                        : Alignment.centerLeft,
                    child: Card(
                      child: InkWell(
                        onLongPress: () => _actions(message),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Align(
                                alignment: Alignment.centerRight,
                                child: IconButton(
                                  tooltip: 'Message actions',
                                  onPressed: () => _actions(message),
                                  icon: const Icon(Icons.more_horiz),
                                ),
                              ),
                              Text(
                                message['deleted_at'] == null
                                    ? '${message['body']}'
                                    : 'Message deleted',
                              ),
                              Text(
                                '${message['created_at'] ?? ''}',
                                style: Theme.of(context).textTheme.labelSmall,
                              ),
                              if ((message['reply_count'] as num? ?? 0) > 0)
                                TextButton(
                                  onPressed: () => _actions(message),
                                  child: Text(
                                    '${message['reply_count']} replies',
                                  ),
                                ),
                              for (final file
                                  in (message['attachments'] as List? ?? []))
                                TextButton.icon(
                                  onPressed: () async {
                                    final op = widget.catalog.find(
                                      'GET',
                                      '/project-management/workspaces/{wid}/chat/conversations/{rid}/attachments/{aid}',
                                    )!;
                                    await widget.openAction(op, {
                                      ...scope,
                                      'aid': file['id'],
                                    }, {});
                                  },
                                  icon: const Icon(Icons.attach_file),
                                  label: Text('${file['name']}'),
                                ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          if (_attachments.isNotEmpty)
            Wrap(
              children: _attachments
                  .map(
                    (a) => InputChip(
                      label: Text('${a['name']}'),
                      onDeleted: () async {
                        try {
                          await c.api.request(
                            'DELETE',
                            '$base/attachments/${a['id']}',
                          );
                          if (mounted) setState(() => _attachments.remove(a));
                        } catch (e) {
                          if (mounted) setState(() => _error = '$e');
                        }
                      },
                    ),
                  )
                  .toList(),
            ),
          if (c.selected?.canEdit == true)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  IconButton(
                    tooltip: 'Attach file',
                    onPressed: _sending ? null : _attach,
                    icon: const Icon(Icons.attach_file),
                  ),
                  Expanded(
                    child: TextField(
                      controller: _text,
                      minLines: 1,
                      maxLines: 5,
                      decoration: const InputDecoration(labelText: 'Message'),
                      onChanged: (_) {
                        if (!_sending) _pendingRequest = null;
                      },
                    ),
                  ),
                  IconButton(
                    tooltip: 'Send message',
                    onPressed: _sending ? null : _send,
                    icon: const Icon(Icons.send),
                  ),
                ],
              ),
            ),
        ],
      ),
    ),
  );
}
