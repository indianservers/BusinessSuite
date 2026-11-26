import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/notes_offline_cache.dart';

const _notesPath = '/project-management/notes';
const _richPrefix = '<!--suite-richtext:v1-->';

class NotesPage extends StatefulWidget {
  const NotesPage({
    super.key,
    required this.api,
    this.cache,
    this.offline = false,
  });
  final ApiClient api;
  final NotesOfflineCache? cache;
  final bool offline;

  @override
  State<NotesPage> createState() => _NotesPageState();
}

class _NotesPageState extends State<NotesPage> {
  List<Map<String, dynamic>> _notes = [];
  List<Map<String, dynamic>> _creations = [];
  String _query = '';
  String _view = 'all';
  String? _error;
  bool _loading = true;
  bool _savedView = false;
  late bool _unreachable = widget.offline;
  int _request = 0;
  Timer? _debounce;
  StreamSubscription<String>? _syncSubscription;

  @override
  void initState() {
    super.initState();
    _syncSubscription = widget.cache?.syncChanges.listen((_) {
      if (mounted && !_loading) unawaited(_load(reconnect: true, sync: false));
    });
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _syncSubscription?.cancel();
    super.dispose();
  }

  Future<void> _load({bool reconnect = false, bool sync = true}) async {
    final request = ++_request;
    final query = _query.trim();
    final view = _view;
    final revision = widget.api.sessionRevision;
    bool current() =>
        mounted &&
        request == _request &&
        widget.api.sessionRevision == revision;
    setState(() {
      _loading = true;
      _error = null;
      if (view != 'all' && _savedView) {
        _notes = [];
        _savedView = false;
      }
    });
    final saved = view == 'all' ? await widget.cache?.summaries() : null;
    if (!current()) return;
    if (saved != null && saved.isNotEmpty) {
      final term = query.toLowerCase();
      setState(() {
        _savedView = true;
        _notes = saved
            .where(
              (note) => '${note['title']} ${note['preview']}'
                  .toLowerCase()
                  .contains(term),
            )
            .toList();
      });
    }
    try {
      if (_unreachable && !reconnect) {
        throw ApiFailure('Connect to see the latest notes.');
      }
      try {
        if (sync) await widget.cache?.sync(widget.api);
      } catch (_) {
        // Online reads remain available if the device queue is unavailable.
      }
      if (!current()) return;
      final result =
          await widget.api.request(
                'GET',
                _notesPath,
                query: {'view': view, if (query.isNotEmpty) 'q': query},
              )
              as List;
      if (!current()) return;
      final notes = result.cast<Map<String, dynamic>>();
      setState(() {
        _notes = notes;
        _unreachable = false;
        _savedView = false;
        _loading = false;
      });
      if (view == 'all' && query.isEmpty) {
        await widget.cache?.saveSummaries(notes);
      }
    } catch (error) {
      if (!current()) return;
      final denied =
          error is ApiFailure && const {401, 403, 404}.contains(error.status);
      setState(() {
        _unreachable =
            _unreachable && !reconnect ||
            error is ApiFailure &&
                (error.connectionFailure || (error.status ?? 0) >= 500);
        if (denied || view != 'all') {
          _notes = [];
          _savedView = false;
        }
        _error = error.toString();
        _loading = false;
      });
      if (denied) await widget.cache?.clear();
    } finally {
      if (current()) {
        try {
          final drafts = await widget.cache?.creations();
          if (current()) setState(() => _creations = drafts ?? []);
        } catch (_) {}
      }
    }
  }

  void _open([Map<String, dynamic>? summary]) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => _NoteEditor(
          api: widget.api,
          summary: summary,
          cache: widget.cache,
          offline: _unreachable,
        ),
      ),
    );
    if (mounted && changed == true) await _load();
  }

  Future<void> _viewCreation(Map<String, dynamic> entry) async {
    final values = entry['values'] as Map<String, dynamic>;
    final discard = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          (values['title'] as String).trim().isEmpty
              ? 'Untitled note'
              : values['title'] as String,
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${entry['error'] ?? 'Saved on this device · Awaiting sync'}',
              ),
              const SizedBox(height: 12),
              SelectableText(values['content'] as String),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          if (entry['error'] != null)
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Discard saved note'),
            ),
        ],
      ),
    );
    if (discard == true && mounted) {
      await widget.cache?.discard(entry['key']);
      if (mounted) await _load();
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Notes'),
      actions: [
        PopupMenuButton<String>(
          tooltip: 'Filter notes',
          initialValue: _view,
          onSelected: (view) {
            _view = view;
            _load();
          },
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'all', child: Text('My notes')),
            PopupMenuItem(value: 'shared', child: Text('Shared with me')),
            PopupMenuItem(value: 'archive', child: Text('Archived')),
            PopupMenuItem(value: 'trash', child: Text('Trash')),
          ],
        ),
        IconButton(
          tooltip: 'Refresh notes',
          onPressed: () => _load(reconnect: true),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    floatingActionButton: FloatingActionButton.extended(
      onPressed: _unreachable && widget.cache == null ? null : () => _open(),
      icon: const Icon(Icons.add),
      label: const Text('New note'),
    ),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: TextField(
            maxLength: 200,
            decoration: const InputDecoration(
              labelText: 'Search notes',
              prefixIcon: Icon(Icons.search),
              counterText: '',
            ),
            onChanged: (value) {
              _query = value;
              _request++;
              _debounce?.cancel();
              _debounce = Timer(const Duration(milliseconds: 250), _load);
            },
          ),
        ),
        if (_loading) const LinearProgressIndicator(),
        if (_savedView) const Text('Saved private notes'),
        if (_error != null)
          Padding(padding: const EdgeInsets.all(16), child: Text(_error!)),
        if (!_loading && _error == null && _notes.isEmpty && _creations.isEmpty)
          const Text('No notes found'),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () => _load(reconnect: true),
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.only(bottom: 88),
              itemCount:
                  _notes.length +
                  (_view == 'all' && _query.trim().isEmpty
                      ? _creations.length
                      : 0),
              itemBuilder: (context, index) {
                final drafts = _view == 'all' && _query.trim().isEmpty
                    ? _creations
                    : const [];
                if (index < drafts.length) {
                  final draft = drafts[index] as Map<String, dynamic>;
                  final title = (draft['values']['title'] as String).trim();
                  return ListTile(
                    title: Text(title.isEmpty ? 'Untitled note' : title),
                    subtitle: Text(
                      draft['error'] == null
                          ? 'Saved · Awaiting sync'
                          : 'Saved note needs review',
                    ),
                    onTap: () => _viewCreation(draft),
                  );
                }
                final note = _notes[index - drafts.length];
                return ListTile(
                  title: Text(
                    note['title'] as String? ?? 'Untitled note',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(
                    note['preview'] as String? ?? '',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  onTap: () => _open(note),
                );
              },
            ),
          ),
        ),
      ],
    ),
  );
}

class _NoteEditor extends StatefulWidget {
  const _NoteEditor({
    required this.api,
    this.summary,
    this.cache,
    required this.offline,
  });
  final ApiClient api;
  final Map<String, dynamic>? summary;
  final NotesOfflineCache? cache;
  final bool offline;

  @override
  State<_NoteEditor> createState() => _NoteEditorState();
}

class _NoteEditorState extends State<_NoteEditor> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  Map<String, dynamic>? _note;
  String? _error;
  bool _loading = false;
  bool _saving = false;
  bool _dirty = false;
  bool _savedView = false;
  Map<String, dynamic>? _pending;

  bool get _rich =>
      (_note?['content'] as String? ?? '').startsWith(_richPrefix);
  bool get _editable {
    if (_loading || _pending != null) return false;
    if (_savedView) {
      return !_rich && (_note?['version'] is int) && widget.cache != null;
    }
    if (widget.offline && widget.summary == null) return widget.cache != null;
    return !widget.offline &&
        (widget.summary == null && _note == null ||
            _note?['can_edit'] == true && _note?['deleted_at'] == null);
  }

  @override
  void initState() {
    super.initState();
    final summary = widget.summary;
    if (summary != null) _load();
  }

  Future<void> _load() async {
    final revision = widget.api.sessionRevision;
    setState(() {
      _loading = true;
      _error = null;
    });
    final cached = await widget.cache?.detail(widget.summary!['id']);
    if (!mounted || revision != widget.api.sessionRevision) return;
    if (cached != null) _show(cached, saved: true);
    try {
      if (widget.offline) {
        throw ApiFailure('Connect to refresh this note.');
      }
      final note =
          await widget.api.request(
                'GET',
                '$_notesPath/${widget.summary!['id']}',
              )
              as Map<String, dynamic>;
      if (!mounted || revision != widget.api.sessionRevision) return;
      _show(note, saved: false);
      await widget.cache?.saveDetail(note);
    } catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        final denied =
            error is ApiFailure && const {401, 403, 404}.contains(error.status);
        setState(() {
          _error = '$error';
          if (denied) {
            _note = null;
            _savedView = false;
            _title.clear();
            _body.clear();
          }
        });
        if (denied) await widget.cache?.clear();
      }
    } finally {
      if (mounted && revision == widget.api.sessionRevision) {
        Map<String, dynamic>? pending;
        try {
          if (_note != null) {
            pending = await widget.cache?.pending(_note?['id']);
          }
        } catch (_) {}
        if (mounted && revision == widget.api.sessionRevision) {
          setState(() {
            _pending = pending;
            if (pending?['values'] case final Map<String, dynamic> values) {
              _title.text = values['title'] as String;
              _body.text = values['content'] as String;
            }
            _loading = false;
          });
        }
      }
    }
  }

  void _show(Map<String, dynamic> note, {required bool saved}) {
    setState(() {
      _note = note;
      _savedView = saved;
      _title.text = note['title'] as String? ?? '';
      _body.text = _rich
          ? (note['preview'] as String? ?? '')
          : (note['content'] as String? ?? '');
    });
  }

  Future<void> _save() async {
    if (_saving || !_dirty || !_editable) return;
    final note = _note;
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final values = <String, dynamic>{
        'title': _title.text,
        'content': _rich ? note!['content'] : _body.text,
        if (note != null)
          for (final key in [
            'version',
            'project_id',
            'task_id',
            'folder_id',
            'tags',
            'pinned',
            'favorite',
            'archived',
          ])
            key: note[key],
      };
      if (_savedView || widget.offline) {
        if (note == null) {
          await widget.cache!.enqueueNew(values);
        } else {
          await widget.cache!.enqueue(note, values);
        }
        if (!mounted || revision != widget.api.sessionRevision) return;
        _dirty = false;
        _saving = false;
        Navigator.of(context).pop(true);
        return;
      }
      final updated = await widget.api.request(
        note == null ? 'POST' : 'PUT',
        note == null ? _notesPath : '$_notesPath/${note['id']}',
        data: values,
      );
      if (!mounted || revision != widget.api.sessionRevision) return;
      if (updated is Map<String, dynamic>) {
        await widget.cache?.saveDetail(updated);
      }
      if (!mounted) return;
      setState(() {
        _dirty = false;
        _saving = false;
      });
      Navigator.of(context).pop(true);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = error is ApiFailure && error.status == 409
            ? 'This note changed elsewhere. Your edits are still here. Copy them before reopening the latest version.'
            : error.toString();
      });
    }
  }

  Future<void> _discardPending() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Discard the saved edit?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Keep'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
    if (!mounted || confirmed != true) return;
    try {
      await widget.cache!.discard(_note!['id']);
      if (mounted) await _load();
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    }
  }

  void _changed(String _) {
    if (!_dirty) setState(() => _dirty = true);
  }

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_dirty && !_saving,
    onPopInvokedWithResult: (didPop, _) async {
      if (didPop || _saving || !_dirty) return;
      final discard = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Discard unsaved edits?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Keep editing'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Discard'),
            ),
          ],
        ),
      );
      if (discard == true && context.mounted) Navigator.of(context).pop();
    },
    child: Scaffold(
      appBar: AppBar(
        title: Text(widget.summary == null ? 'New note' : 'Note'),
        actions: [
          TextButton(
            onPressed: _editable && _dirty && !_saving ? _save : null,
            child: Text(_saving ? 'Saving…' : 'Save'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading) const LinearProgressIndicator(),
          if (_savedView)
            Text(
              _editable ? 'Saved note · Edits sync when online' : 'Saved note',
            ),
          if (_pending != null) ...[
            Text(
              _pending!['error'] == null
                  ? 'Edit saved · Awaiting sync'
                  : 'Saved edit needs review. Copy your changes before discarding the draft.',
            ),
            if (_pending!['error'] != null)
              TextButton(
                onPressed: _discardPending,
                child: const Text('Discard saved edit'),
              ),
          ],
          if (_error != null) Text(_error!),
          if (widget.summary != null && _note == null) ...[
            if (_loading) ...[
              Text(
                widget.summary?['title'] as String? ?? 'Untitled note',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              Text(widget.summary?['preview'] as String? ?? ''),
            ] else
              TextButton(onPressed: _load, child: const Text('Retry')),
          ] else ...[
            TextField(
              controller: _title,
              readOnly: !_editable || _saving,
              maxLength: 180,
              onChanged: _changed,
              decoration: const InputDecoration(labelText: 'Title'),
            ),
            if (_rich)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  'Formatted note preview. Edit the full document on the web.',
                ),
              ),
            TextField(
              controller: _body,
              readOnly: !_editable || _saving || _rich,
              minLines: 10,
              maxLines: null,
              onChanged: _changed,
              decoration: InputDecoration(
                labelText: _rich ? 'Preview' : 'Note',
              ),
            ),
          ],
        ],
      ),
    ),
  );
}
