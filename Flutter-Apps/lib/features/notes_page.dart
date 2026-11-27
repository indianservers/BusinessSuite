import 'dart:async';

import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

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
  Map<int, Map<String, dynamic>> _pendingEdits = {};
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
    final canReadSaved = const {'all', 'pinned', 'favorites'}.contains(view);
    final revision = widget.api.sessionRevision;
    bool current() =>
        mounted &&
        request == _request &&
        widget.api.sessionRevision == revision;
    setState(() {
      _loading = true;
      _error = null;
    });
    List<Map<String, dynamic>>? saved;
    try {
      if (canReadSaved) saved = await widget.cache?.summaries();
      final pending = await widget.cache?.pendingEdits();
      if (current()) setState(() => _pendingEdits = pending ?? {});
    } catch (_) {
      // Continue to the server when the device store is unavailable.
    }
    if (!current()) return;
    final savedNotes = saved;
    if (savedNotes != null && savedNotes.isNotEmpty) {
      final term = query.toLowerCase();
      setState(() {
        _savedView = true;
        _notes = savedNotes.where((note) {
          final edits = _pendingFor(note)?['values'];
          if (view == 'pinned' &&
              (edits?['pinned'] ?? note['pinned']) != true) {
            return false;
          }
          if (view == 'favorites' &&
              (edits?['favorite'] ?? note['favorite']) != true) {
            return false;
          }
          return '${_titleFor(note)} ${_previewFor(note)} ${note['tags'] ?? ''}'
              .toLowerCase()
              .contains(term);
        }).toList();
      });
    }
    try {
      if (_unreachable && !reconnect) {
        throw ApiFailure('Connect to see the latest notes.');
      }
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
        try {
          await widget.cache?.saveSummaries(notes);
        } catch (_) {
          // Keep the online results if the device store is unavailable.
        }
      }
      if (current() && sync) unawaited(_syncPending());
    } catch (error) {
      if (!current()) return;
      final denied =
          error is ApiFailure && const {401, 403, 404}.contains(error.status);
      setState(() {
        _unreachable =
            _unreachable && !reconnect ||
            error is ApiFailure &&
                (error.connectionFailure || (error.status ?? 0) >= 500);
        if (denied || !canReadSaved) {
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
          final pending = await widget.cache?.pendingEdits();
          if (current()) {
            setState(() {
              _creations = drafts ?? [];
              _pendingEdits = pending ?? {};
            });
          }
        } catch (_) {}
      }
    }
  }

  Future<void> _syncPending() async {
    try {
      await widget.cache?.sync(widget.api);
    } catch (_) {
      // Queued changes can retry on the next successful connection.
    }
  }

  Map<String, dynamic>? _pendingFor(Map<String, dynamic> note) =>
      note['can_edit'] == true &&
          note['visibility_scope'] == 'private' &&
          note['visibility'] == 'private'
      ? _pendingEdits[note['id']]
      : null;

  String _titleFor(Map<String, dynamic> note) =>
      (_pendingFor(note)?['values']['title'] as String?) ??
      (note['title'] as String?) ??
      'Untitled note';

  String _previewFor(Map<String, dynamic> note) =>
      (_pendingFor(note)?['values']['content'] as String?) ??
      (note['preview'] as String?) ??
      '';

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
  Widget build(BuildContext context) {
    final term = _query.trim().toLowerCase();
    final drafts = _view == 'all'
        ? _creations.where((draft) {
            final values = draft['values'];
            return term.isEmpty ||
                '${values['title']} ${values['content']}'
                    .toLowerCase()
                    .contains(term);
          }).toList()
        : const <Map<String, dynamic>>[];
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notes'),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Filter notes',
            initialValue: _view,
            onSelected: (view) {
              if (view == _view) return;
              _view = view;
              _notes = [];
              _savedView = false;
              _load();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'all', child: Text('My notes')),
              PopupMenuItem(value: 'pinned', child: Text('Pinned')),
              PopupMenuItem(value: 'favorites', child: Text('Favorites')),
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
                setState(() => _query = value);
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
          if (!_loading && _error == null && _notes.isEmpty && drafts.isEmpty)
            const Text('No notes found'),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => _load(reconnect: true),
              child: ListView.builder(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.only(bottom: 88),
                itemCount: _notes.length + drafts.length,
                itemBuilder: (context, index) {
                  if (index < drafts.length) {
                    final draft = drafts[index];
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
                  final pending = _pendingFor(note);
                  return ListTile(
                    title: Text(
                      _titleFor(note),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      _previewFor(note),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    trailing: pending == null
                        ? null
                        : Tooltip(
                            message: pending['error'] == null
                                ? 'Awaiting sync'
                                : 'Saved edit needs review',
                            child: Icon(
                              pending['error'] == null
                                  ? Icons.cloud_upload_outlined
                                  : Icons.error_outline,
                            ),
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
  late bool _offline = widget.offline;
  late final String _createOperation = const Uuid().v4();
  final _title = TextEditingController();
  final _body = TextEditingController();
  Map<String, dynamic>? _note;
  String? _error;
  bool _loading = false;
  bool _saving = false;
  bool _dirty = false;
  final _flagEdits = <String, bool>{};
  bool _savedView = false;
  Map<String, dynamic>? _pending;

  bool get _rich =>
      (_note?['content'] as String? ?? '').startsWith(_richPrefix);
  bool get _editable {
    if (_loading || _pending != null) return false;
    if (_savedView) {
      return !_rich && (_note?['version'] is int) && widget.cache != null;
    }
    if (_offline && widget.summary == null) return widget.cache != null;
    return !_offline &&
        (widget.summary == null && _note == null ||
            _note?['can_edit'] == true && _note?['deleted_at'] == null);
  }

  @override
  void initState() {
    super.initState();
    final summary = widget.summary;
    if (summary != null) _load();
  }

  Future<void> _load({bool reconnect = false}) async {
    if (_loading || _saving || _dirty) return;
    final revision = widget.api.sessionRevision;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      if (_note == null) {
        Map<String, dynamic>? cached;
        try {
          cached = await widget.cache?.detail(widget.summary!['id']);
        } catch (_) {
          // The live read can proceed if local storage is unavailable.
        }
        if (!mounted || revision != widget.api.sessionRevision) return;
        if (cached != null) _show(cached, saved: true);
      }
      if (_offline && !reconnect) {
        throw ApiFailure('Connect to refresh this note.');
      }
      final note =
          await widget.api.request(
                'GET',
                '$_notesPath/${widget.summary!['id']}',
              )
              as Map<String, dynamic>;
      if (!mounted || revision != widget.api.sessionRevision) return;
      _offline = false;
      _show(note, saved: false);
      try {
        await widget.cache?.saveDetail(note);
      } catch (_) {
        // The server copy is already visible.
      }
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
            key: _flagEdits[key] ?? note[key],
      };
      if (_savedView || _offline) {
        if (note == null) {
          await widget.cache!.enqueueNew(values, operation: _createOperation);
        } else {
          await widget.cache!.enqueue(note, values);
        }
        if (!mounted || revision != widget.api.sessionRevision) return;
        _dirty = false;
        _saving = false;
        Navigator.of(context).pop(true);
        return;
      }
      Object? updated;
      try {
        updated = await widget.api.request(
          note == null ? 'POST' : 'PUT',
          note == null ? _notesPath : '$_notesPath/${note['id']}',
          data: values,
          scopeHeaders: {
            if (note == null) 'X-Offline-Operation': _createOperation,
          },
        );
      } on ApiFailure catch (failure) {
        final cache = widget.cache;
        if (!failure.connectionFailure ||
            cache == null ||
            (note != null && (_rich || !cache.canQueueEdit(note))) ||
            revision != widget.api.sessionRevision) {
          rethrow;
        }
        if (note == null) {
          await cache.enqueueNew(values, operation: _createOperation);
        } else {
          await cache.enqueue(note, values);
        }
      }
      if (!mounted || revision != widget.api.sessionRevision) return;
      if (updated is Map<String, dynamic>) {
        try {
          if (updated['archived'] == true) {
            await widget.cache?.forgetNote(updated['id']);
          } else {
            await widget.cache?.saveDetail(updated);
          }
        } catch (_) {
          // A local cache failure does not undo a server save.
        }
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

  Future<void> _changeTrash({required bool restore}) async {
    final note = _note;
    if (_saving || _dirty || note == null) return;
    if (!restore) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Move note to Trash?'),
          content: const Text('You can restore this note from Trash.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Move to Trash'),
            ),
          ],
        ),
      );
      if (!mounted || confirmed != true) return;
    }
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        restore ? 'POST' : 'DELETE',
        '$_notesPath/${note['id']}${restore ? '/restore' : ''}',
        data: {'version': note['version']},
      );
      if (!restore && widget.api.sessionRevision == revision) {
        await widget.cache?.forgetNote(note['id']);
      }
      if (!mounted || widget.api.sessionRevision != revision) return;
      setState(() => _saving = false);
      Navigator.of(context).pop(true);
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted && _saving) setState(() => _saving = false);
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
          if (widget.summary != null)
            IconButton(
              tooltip: 'Refresh note',
              onPressed: _loading || _saving || _dirty
                  ? null
                  : () => _load(reconnect: true),
              icon: const Icon(Icons.refresh),
            ),
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
          if (_note?['can_edit'] == true &&
              _note?['version'] is int &&
              !_savedView &&
              _pending == null)
            OutlinedButton(
              onPressed: _loading || _saving || _offline || _dirty
                  ? null
                  : () => _changeTrash(restore: _note?['deleted_at'] != null),
              child: Text(
                _note?['deleted_at'] == null ? 'Move to Trash' : 'Restore note',
              ),
            ),
          if (widget.summary != null && _note == null) ...[
            if (_loading) ...[
              Text(
                widget.summary?['title'] as String? ?? 'Untitled note',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              Text(widget.summary?['preview'] as String? ?? ''),
            ] else
              TextButton(
                onPressed: () => _load(reconnect: true),
                child: const Text('Retry'),
              ),
          ] else ...[
            if (_note != null)
              for (final (key, label, icon) in const [
                ('pinned', 'Pinned', Icons.push_pin_outlined),
                ('favorite', 'Favorite', Icons.star_border),
                ('archived', 'Archived', Icons.archive_outlined),
              ])
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  secondary: Icon(icon),
                  title: Text(label),
                  value:
                      _flagEdits[key] ??
                      (_pending?['values']?[key] ?? _note?[key]) == true,
                  onChanged: _editable && !_saving
                      ? (value) => setState(() {
                          _flagEdits[key] = value;
                          _dirty = true;
                        })
                      : null,
                ),
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
