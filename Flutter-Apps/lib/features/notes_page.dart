import 'dart:async';

import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import '../core/notes_offline_cache.dart';

const _notesPath = '/project-management/notes';
const _richPrefix = '<!--suite-richtext:v1-->';

enum _NoteChange { saved, removed }

class _NoteHistory extends StatefulWidget {
  const _NoteHistory({
    required this.api,
    required this.noteId,
    required this.canRestore,
  });

  final ApiClient api;
  final int noteId;
  final bool canRestore;

  @override
  State<_NoteHistory> createState() => _NoteHistoryState();
}

class _NoteHistoryState extends State<_NoteHistory> {
  String get _path => '$_notesPath/${widget.noteId}/revisions';
  late final _versions = widget.api.request('GET', _path);
  Future<dynamic>? _preview;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Version history')),
    body: FutureBuilder(
      future: _preview ?? _versions,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('${snapshot.error}'));
        }
        final data = snapshot.data;
        if (data is List) {
          return ListView(
            children: [
              if (data.isEmpty)
                const ListTile(title: Text('No saved versions')),
              for (final revision in data.whereType<Map<String, dynamic>>())
                ListTile(
                  title: Text(
                    'Version ${revision['version']} · ${revision['title']}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => setState(() {
                    _preview = widget.api.request(
                      'GET',
                      '$_path/${revision['version']}',
                    );
                  }),
                ),
            ],
          );
        }
        if (data is! Map<String, dynamic>) {
          return const Center(child: Text('Version unavailable'));
        }
        final content = data['content'] as String? ?? '';
        return ListView(
          padding: const EdgeInsets.all(20),
          children: [
            TextButton(
              onPressed: () => setState(() => _preview = null),
              child: const Text('All versions'),
            ),
            Text(
              '${data['title']}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            SelectableText(
              content.startsWith(_richPrefix)
                  ? 'Formatted content can be restored from this version.'
                  : content,
            ),
            if (widget.canRestore)
              OutlinedButton(
                onPressed: () => Navigator.pop(context, data),
                child: const Text('Use this version'),
              ),
          ],
        );
      },
    ),
  );
}

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
  Json? _folder;
  String _sort = 'modified';
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
    final folderId = _folder?['id'];
    final sort = _sort;
    final canReadSaved = const {
      'all',
      'pinned',
      'favorites',
      'quick',
      'personal',
      'recent',
      'folder',
    }.contains(view);
    final revision = widget.api.sessionRevision;
    bool current() =>
        mounted &&
        request == _request &&
        widget.api.sessionRevision == revision;
    setState(() {
      _loading = true;
      _error = null;
    });
    var showSavedResults = true;
    Future<void> loadSaved() async {
      final cache = widget.cache;
      if (cache == null) return;
      final pending = cache.pendingChanges().then(
        (value) => value,
        onError: (Object _) => (edits: <int, Json>{}, creations: <Json>[]),
      );
      final (summaries, bodies, changes) = await (
        canReadSaved ? cache.summaries() : Future.value(<Json>[]),
        canReadSaved && query.isNotEmpty
            ? cache.savedBodies()
            : Future.value(<int, String>{}),
        pending,
      ).wait;
      if (!current()) return;
      setState(() {
        _creations = changes.creations;
        _pendingEdits = changes.edits;
      });
      if (!showSavedResults || summaries.isEmpty) return;
      final term = query.toLowerCase();
      setState(() {
        _savedView = true;
        _notes = summaries.where((note) {
          if (folderId != null && note['folder_id'] != folderId) return false;
          final edits = _pendingFor(note)?['values'];
          if (view == 'quick' &&
              (note['project_id'] != null || note['folder_id'] != null)) {
            return false;
          }
          if (view == 'pinned' &&
              (edits?['pinned'] ?? note['pinned']) != true) {
            return false;
          }
          if (view == 'favorites' &&
              (edits?['favorite'] ?? note['favorite']) != true) {
            return false;
          }
          final body = edits?['content'] ?? bodies[note['id']] ?? '';
          return '${_titleFor(note)} ${_previewFor(note)} $body ${edits?['tags'] ?? note['tags'] ?? ''}'
              .toLowerCase()
              .contains(term);
        }).toList()..sort((a, b) => _compareSavedNotes(a, b, sort));
      });
    }

    final local = loadSaved();
    try {
      if (_unreachable && !reconnect) {
        throw ApiFailure('Connect to see the latest notes.');
      }
      final result =
          await widget.api.request(
                'GET',
                _notesPath,
                query: {
                  'view': const {'personal', 'folder'}.contains(view)
                      ? 'all'
                      : view,
                  if (view == 'personal') 'personal': true,
                  'folder_id': ?folderId,
                  if (sort != 'modified') 'sort': sort,
                  if (query.isNotEmpty) 'q': query,
                },
              )
              as List;
      if (!current()) return;
      final notes = result.cast<Map<String, dynamic>>();
      showSavedResults = false;
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
      if (denied) showSavedResults = false;
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
      await local;
      if (current()) {
        try {
          final changes = await widget.cache?.pendingChanges();
          if (current()) {
            setState(() {
              _creations = changes?.creations ?? [];
              _pendingEdits = changes?.edits ?? {};
            });
          }
        } catch (_) {}
      }
    }
  }

  Future<List<Json>> _folders() async {
    final revision = widget.api.sessionRevision;
    if (_unreachable) return await widget.cache?.folders() ?? [];
    try {
      final rows =
          await widget.api.request('GET', '/project-management/note-folders')
              as List;
      if (revision != widget.api.sessionRevision) return [];
      final folders = rows.whereType<Json>().toList();
      await widget.cache?.saveFolders(folders);
      return folders;
    } on ApiFailure catch (error) {
      if (error.connectionFailure || (error.status ?? 0) >= 500) {
        return await widget.cache?.folders() ?? [];
      }
      rethrow;
    }
  }

  Future<void> _chooseFolder() async {
    final revision = widget.api.sessionRevision;
    final folders = _folders();
    final folder = await showDialog<Json>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('Note folders'),
        children: [
          FutureBuilder(
            future: folders,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const LinearProgressIndicator();
              }
              final rows = snapshot.data ?? const <Json>[];
              if (rows.isEmpty) {
                return Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    snapshot.error?.toString() ?? 'No folders available',
                  ),
                );
              }
              final byId = {for (final row in rows) row['id']: row};
              return Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (final row in rows)
                    SimpleDialogOption(
                      onPressed: () => Navigator.pop(context, row),
                      child: Text(
                        [
                          if (byId[row['parent_id']]?['name']
                              case final String name)
                            name,
                          row['name'] ?? 'Folder',
                        ].join(' / '),
                      ),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
    if (folder == null || !mounted || revision != widget.api.sessionRevision) {
      return;
    }
    await _selectFolder(folder);
  }

  Future<void> _editFolder({bool rename = false}) async {
    final api = widget.api;
    final revision = api.sessionRevision;
    final folder = await showDialog<Json>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _NotesFolderForm(
        api: api,
        parent: rename ? null : _folder,
        folder: rename ? _folder : null,
      ),
    );
    if (folder == null || !mounted || revision != api.sessionRevision) return;
    await _selectFolder(folder);
    if (widget.cache case final cache?) {
      final saved = await cache.folders();
      if (mounted && revision == api.sessionRevision) {
        await cache.saveFolders([
          ...saved.where((row) => row['id'] != folder['id']),
          folder,
        ]);
      }
    }
  }

  Future<void> _selectFolder(Json folder) async {
    _folder = folder;
    _view = 'folder';
    _notes = [];
    _savedView = false;
    await _load();
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

  int _compareSavedNotes(
    Map<String, dynamic> a,
    Map<String, dynamic> b,
    String sort,
  ) {
    bool pinned(Map<String, dynamic> note) =>
        (_pendingFor(note)?['values']['pinned'] ?? note['pinned']) == true;
    if (pinned(a) != pinned(b)) return pinned(a) ? -1 : 1;
    final dateKey = sort == 'created' ? 'created_at' : 'updated_at';
    final compared = sort == 'title'
        ? _titleFor(a).compareTo(_titleFor(b))
        : '${b[dateKey] ?? ''}'.compareTo('${a[dateKey] ?? ''}');
    return compared == 0
        ? (b['id'] as int? ?? 0).compareTo(a['id'] as int? ?? 0)
        : compared;
  }

  String _previewFor(Map<String, dynamic> note) {
    final pending = _pendingFor(note)?['values']['content'] as String?;
    if (pending != null && !pending.startsWith(_richPrefix)) return pending;
    return note['preview'] as String? ?? '';
  }

  void _open([Map<String, dynamic>? summary]) async {
    final changed = await Navigator.of(context).push<_NoteChange>(
      MaterialPageRoute<_NoteChange>(
        builder: (_) => _NoteEditor(
          api: widget.api,
          summary: summary,
          folder: summary == null ? _folder : null,
          cache: widget.cache,
          offline: _unreachable,
        ),
      ),
    );
    if (!mounted || changed == null) return;
    if (changed == _NoteChange.removed) {
      final id = summary?['id'];
      setState(
        () => _notes = _notes.where((note) => note['id'] != id).toList(),
      );
    }
    await _load();
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
    final drafts = const {'all', 'quick', 'personal', 'folder'}.contains(_view)
        ? _creations.where((draft) {
            final values = draft['values'];
            if (_view == 'folder' && values['folder_id'] != _folder?['id']) {
              return false;
            }
            if (_view == 'quick' &&
                (values['folder_id'] != null || values['project_id'] != null)) {
              return false;
            }
            if (_view == 'personal' && values['project_id'] != null) {
              return false;
            }
            return term.isEmpty ||
                '${values['title']} ${values['content']} ${values['tags'] ?? ''}'
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
              if (view == 'new-folder' || view == 'rename-folder') {
                unawaited(_editFolder(rename: view == 'rename-folder'));
                return;
              }
              if (view == 'folder') {
                unawaited(_chooseFolder());
                return;
              }
              if (view == _view) return;
              _folder = null;
              _view = view;
              _notes = [];
              _savedView = false;
              _load();
            },
            itemBuilder: (_) => [
              ...const [
                PopupMenuItem(value: 'all', child: Text('My notes')),
                PopupMenuItem(value: 'personal', child: Text('Personal notes')),
                PopupMenuItem(value: 'quick', child: Text('Quick notes')),
                PopupMenuItem(value: 'recent', child: Text('Recent')),
                PopupMenuItem(value: 'folder', child: Text('Note folders')),
                PopupMenuItem(value: 'pinned', child: Text('Pinned')),
                PopupMenuItem(value: 'favorites', child: Text('Favorites')),
                PopupMenuItem(value: 'shared', child: Text('Shared with me')),
                PopupMenuItem(value: 'archive', child: Text('Archived')),
                PopupMenuItem(value: 'trash', child: Text('Trash')),
              ],
              if (!_unreachable)
                PopupMenuItem(
                  value: 'new-folder',
                  child: Text(_folder == null ? 'New folder' : 'New subfolder'),
                ),
              if (!_unreachable && _folder?['version'] is int)
                const PopupMenuItem(
                  value: 'rename-folder',
                  child: Text('Rename folder'),
                ),
            ],
          ),
          IconButton(
            tooltip: 'Refresh notes',
            onPressed: () => _load(reconnect: true),
            icon: const Icon(Icons.refresh),
          ),
          PopupMenuButton<String>(
            tooltip: 'Sort notes',
            icon: const Icon(Icons.sort),
            initialValue: _sort,
            onSelected: (sort) {
              if (sort == _sort) return;
              _sort = sort;
              _load();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'modified', child: Text('Last modified')),
              PopupMenuItem(value: 'created', child: Text('Date created')),
              PopupMenuItem(value: 'title', child: Text('Title')),
            ],
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
          if (_folder?['name'] case final String name)
            Text(name, style: Theme.of(context).textTheme.titleMedium),
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

class _NotesFolderForm extends StatefulWidget {
  const _NotesFolderForm({required this.api, this.parent, this.folder});

  final ApiClient api;
  final Json? parent;
  final Json? folder;

  @override
  State<_NotesFolderForm> createState() => _NotesFolderFormState();
}

class _NotesFolderFormState extends State<_NotesFolderForm> {
  late String _name = widget.folder?['name'] as String? ?? '';
  String? _error;
  bool _saving = false;

  Future<void> _save() async {
    if (_saving || _name.isEmpty) return;
    final api = widget.api;
    final revision = api.sessionRevision;
    final parent = widget.parent;
    final current = widget.folder;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final folder =
          await api.request(
                current == null ? 'POST' : 'PUT',
                current == null
                    ? '/project-management/note-folders'
                    : "/project-management/note-folders/${current['id']}",
                data: {
                  'name': _name,
                  if (current == null) ...{
                    'parent_id': ?parent?['id'],
                    'project_id': ?parent?['project_id'],
                    'task_id': ?parent?['task_id'],
                  } else
                    for (final key in [
                      'parent_id',
                      'project_id',
                      'task_id',
                      'color',
                      'icon',
                      'position',
                      'version',
                    ])
                      key: ?current[key],
                },
              )
              as Json;
      if (mounted && revision == api.sessionRevision) {
        Navigator.of(context).pop(folder);
      }
    } on ApiFailure catch (error) {
      if (mounted && revision == api.sessionRevision) {
        setState(() => _error = error.message);
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.folder != null
          ? 'Rename folder'
          : widget.parent == null
          ? 'New folder'
          : 'New subfolder',
    ),
    content: TextFormField(
      initialValue: _name,
      autofocus: true,
      maxLength: 120,
      enabled: !_saving,
      decoration: InputDecoration(labelText: 'Folder name', errorText: _error),
      onChanged: (value) => setState(() => _name = value.trim()),
    ),
    actions: [
      TextButton(
        onPressed: _saving ? null : () => Navigator.of(context).pop(),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: _saving || _name.isEmpty || _name == widget.folder?['name']
            ? null
            : _save,
        child: Text(widget.folder == null ? 'Create folder' : 'Save name'),
      ),
    ],
  );
}

class _NoteEditor extends StatefulWidget {
  const _NoteEditor({
    required this.api,
    this.summary,
    this.folder,
    this.cache,
    required this.offline,
  });
  final ApiClient api;
  final Map<String, dynamic>? summary;
  final Json? folder;
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
  final _tags = TextEditingController();
  bool _tagsChanged = false;
  Map<String, dynamic>? _note;
  String? _error;
  bool _loading = false;
  bool _saving = false;
  bool _dirty = false;
  final _flagEdits = <String, bool>{};
  String? _restoredContent;
  bool _savedView = false;
  Map<String, dynamic>? _pending;

  bool get _rich => (_restoredContent ?? _note?['content'] as String? ?? '')
      .startsWith(_richPrefix);

  Future<void> _openHistory() async {
    final noteId = _note?['id'];
    if (noteId is! int) return;
    final session = widget.api.sessionRevision;
    final revision = await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(
        builder: (_) => _NoteHistory(
          api: widget.api,
          noteId: noteId,
          canRestore: _editable && !_dirty,
        ),
      ),
    );
    if (!mounted ||
        widget.api.sessionRevision != session ||
        revision == null ||
        !_editable ||
        _dirty) {
      return;
    }
    setState(() {
      _restoredContent = revision['content'] as String? ?? '';
      _title.text = revision['title'] as String? ?? '';
      _body.text = _rich ? '' : _restoredContent!;
      _dirty = true;
    });
  }

  bool get _editable {
    if (_loading || _pending != null) return false;
    if (_savedView) {
      final note = _note;
      return note != null && widget.cache?.canQueueEdit(note) == true;
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
              _tags.text = (values['tags'] as List?)?.join('\n') ?? '';
              if (!_rich) _body.text = values['content'] as String;
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
      _tags.text = (note['tags'] as List?)?.join('\n') ?? '';
      _body.text = _rich
          ? (note['preview'] as String? ?? '')
          : (note['content'] as String? ?? '');
    });
  }

  Future<void> _save() async {
    if (_saving || !_dirty || !_editable) return;
    final note = _note;
    final tags = _tagsChanged
        ? _tags.text
              .split('\n')
              .map((tag) => tag.trim().toLowerCase())
              .where((tag) => tag.isNotEmpty)
              .toSet()
              .toList()
        : note?['tags'];
    if (_tagsChanged &&
        tags is List<String> &&
        (tags.length > 20 || tags.any((tag) => tag.runes.length > 40))) {
      setState(() => _error = 'Use up to 20 tags of 40 characters each.');
      return;
    }
    final revision = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final values = <String, dynamic>{
        'title': _title.text,
        'content': _rich ? _restoredContent ?? note!['content'] : _body.text,
        'tags': ?tags,
        if (widget.folder case final Json folder when note == null)
          for (final key in ['project_id', 'task_id', 'folder_id'])
            key: folder[key == 'folder_id' ? 'id' : key],
        if (note != null)
          for (final key in [
            'version',
            'project_id',
            'task_id',
            'folder_id',
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
        Navigator.of(context).pop(_NoteChange.saved);
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
            (note != null && !cache.canQueueEdit(note)) ||
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
      final archiveChanged =
          updated is Map<String, dynamic> &&
          note != null &&
          (updated['archived'] == true) != (note['archived'] == true);
      Navigator.of(
        context,
      ).pop(archiveChanged ? _NoteChange.removed : _NoteChange.saved);
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
      Navigator.of(context).pop(_NoteChange.removed);
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted && _saving) setState(() => _saving = false);
    }
  }

  Future<void> _duplicate() async {
    final id = _note?['id'];
    if (id is! int || _saving || _dirty) return;
    final session = widget.api.sessionRevision;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request('POST', '$_notesPath/$id/duplicate');
      if (!mounted || widget.api.sessionRevision != session) return;
      setState(() => _saving = false);
      Navigator.of(context).pop(_NoteChange.saved);
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
    _tags.dispose();
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
          if (_note?['can_edit'] == true && !_offline && !_savedView)
            IconButton(
              tooltip: 'Version history',
              onPressed: _loading || _saving ? null : _openHistory,
              icon: const Icon(Icons.history),
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
              _note?['deleted_at'] == null &&
              !_offline &&
              !_savedView)
            OutlinedButton.icon(
              onPressed: _loading || _saving || _dirty || _pending != null
                  ? null
                  : _duplicate,
              icon: const Icon(Icons.copy_outlined),
              label: const Text('Duplicate note'),
            ),
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
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  _restoredContent == null
                      ? 'Formatted note preview. Edit the full document on the web.'
                      : 'Formatted version ready to save.',
                ),
              ),
            TextField(
              controller: _tags,
              readOnly: !_editable || _saving,
              maxLines: 3,
              onChanged: (value) {
                _tagsChanged = true;
                _changed(value);
              },
              decoration: const InputDecoration(
                labelText: 'Tags',
                helperText: 'One tag per line',
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
