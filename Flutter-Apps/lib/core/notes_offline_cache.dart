import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import 'models.dart';
import 'api_client.dart';

class NotesOfflineCache {
  NotesOfflineCache(String scope)
    : _key = 'offline_notes_${Uri.encodeComponent(scope)}',
      _company = '${(jsonDecode(scope) as List)[2]}';
  static const _storage = FlutterSecureStorage();
  final String _key;
  final String _company;
  static final _running = <String, Future<void>>{};
  static final _synced = StreamController<String>.broadcast();

  Stream<String> get syncChanges => _synced.stream.where((key) => key == _key);

  bool _privateNote(Json note) =>
      note['can_edit'] == true &&
      note['project_id'] == null &&
      note['visibility_scope'] == 'private' &&
      note['visibility'] == 'private' &&
      note['deleted_at'] == null;

  bool _eligible(Json note) => _privateNote(note) && note['archived'] != true;

  bool _archived(Json note) => _privateNote(note) && note['archived'] == true;

  Future<List<Json>> _read(String suffix) async {
    try {
      final raw = await _storage.read(key: '$_key:$suffix');
      if (raw == null) return [];
      final data = jsonDecode(raw) as Json;
      final cutoff = DateTime.now()
          .subtract(const Duration(days: 1))
          .millisecondsSinceEpoch;
      if ((data['saved'] as int) < cutoff) return [];
      return (data['rows'] as List).cast<Json>();
    } catch (_) {
      return [];
    }
  }

  Future<void> _write(String suffix, List<Json> rows) async {
    try {
      await _storage.write(
        key: '$_key:$suffix',
        value: jsonEncode({
          'saved': DateTime.now().millisecondsSinceEpoch,
          'rows': rows,
        }),
      );
    } catch (_) {
      // A local cache failure must not interrupt online Notes.
    }
  }

  Future<List<Json>> summaries() => _read('summaries');

  Future<List<Json>> archivedSummaries() => _read('archive');

  Future<void> saveArchivedSummaries(List<Json> notes) async {
    final owned = notes.where(_archived).take(100).toList();
    await _write('archive', owned);
    final allowed = owned.map((note) => note['id']).toSet();
    final details = await _read('archive-details');
    final current = details
        .where((note) => allowed.contains(note['id']))
        .toList();
    if (current.length != details.length) {
      await _write('archive-details', current);
    }
  }

  Future<List<Json>> folders() async {
    final ids = (await summaries()).map((note) => note['folder_id']).toSet();
    return (await _read(
      'folders',
    )).where((folder) => ids.contains(folder['id'])).toList();
  }

  Future<void> saveFolders(List<Json> folders) async {
    final ids = (await summaries()).map((note) => note['folder_id']).toSet();
    await _write('folders', [
      for (final folder in folders)
        if (folder['project_id'] == null && ids.contains(folder['id']))
          {'id': folder['id'], 'name': folder['name']},
    ]);
  }

  Future<void> saveSummaries(List<Json> notes) async {
    final owned = notes.where(_eligible).take(100).toList();
    await _write('summaries', owned);
    final allowed = owned.map((note) => note['id']).toSet();
    final details = await _read('details');
    final current = details
        .where((note) => allowed.contains(note['id']))
        .toList();
    if (current.length != details.length) await _write('details', current);
  }

  Future<Json?> detail(Object? id) async =>
      (await _read('details')).where((note) => note['id'] == id).firstOrNull;

  Future<Json?> archivedDetail(Object? id) async => (await _read(
    'archive-details',
  )).where((note) => note['id'] == id).firstOrNull;

  Future<Map<int, String>> savedBodies() async => {
    for (final note in (await _read('details')).where(_eligible))
      if (note['id'] case final int id)
        if (note['content'] case final String content) id: content,
  };

  Future<Map<int, String>> archivedBodies() async => {
    for (final note in (await _read('archive-details')).where(_archived))
      if (note['id'] case final int id)
        if (note['content'] case final String content) id: content,
  };

  Future<void> forgetNote(Object? id) async {
    await _forget(id, ['summaries', 'details', 'archive', 'archive-details']);
  }

  Future<void> _forget(Object? id, List<String> suffixes) async {
    for (final suffix in suffixes) {
      final notes = await _read(suffix);
      final remaining = notes.where((note) => note['id'] != id).toList();
      if (remaining.length != notes.length) await _write(suffix, remaining);
    }
  }

  Future<void> saveDetail(Json note) async {
    final archived = _archived(note);
    if (archived) {
      await _forget(note['id'], ['summaries', 'details']);
    } else {
      await _forget(note['id'], ['archive', 'archive-details']);
    }
    final suffix = archived ? 'archive-details' : 'details';
    final details = (await _read(
      suffix,
    )).where((row) => row['id'] != note['id']).toList();
    if ((_eligible(note) || archived) &&
        (note['content'] as String? ?? '').length <= 65536) {
      details.insert(0, note);
    }
    await _write(suffix, details.take(12).toList());
  }

  Future<void> saveArchiveChange(Json note) =>
      _serial(() => _saveSyncedNote(note));

  Future<void> _saveSyncedNote(Json note) async {
    if (!_privateNote(note)) {
      await forgetNote(note['id']);
      return;
    }
    final (active, archived) = await (summaries(), archivedSummaries()).wait;
    final isArchived = _archived(note);
    final current = isArchived ? archived : active;
    final existing = [
      ...current,
      ...(isArchived ? active : archived),
    ].where((row) => row['id'] == note['id']).firstOrNull;
    if (existing?['version'] is int &&
        note['version'] is int &&
        (existing!['version'] as int) > (note['version'] as int)) {
      return;
    }
    await saveDetail(note);
    await _write(isArchived ? 'archive' : 'summaries', [
      {
        ...?existing,
        for (final key in [
          'id',
          'title',
          'preview',
          'tags',
          'version',
          'created_at',
          'updated_at',
          'folder_id',
          'project_id',
          'task_id',
          'pinned',
          'favorite',
          'has_attachments',
          'archived',
          'visibility',
          'visibility_scope',
          'can_edit',
          'deleted_at',
        ])
          if (note.containsKey(key)) key: note[key],
      },
      ...current.where((row) => row['id'] != note['id']).take(99),
    ]);
  }

  Future<void> clear() async {
    for (final suffix in [
      'summaries',
      'details',
      'folders',
      'archive',
      'archive-details',
    ]) {
      try {
        await _storage.delete(key: '$_key:$suffix');
      } catch (_) {}
    }
  }

  Future<Json> _edits() async {
    final raw = await _storage.read(key: '$_key:edits');
    return raw == null ? {} : jsonDecode(raw) as Json;
  }

  Future<void> _storeEdits(Json edits) =>
      _storage.write(key: '$_key:edits', value: jsonEncode(edits));

  Future<void> _serial(Future<void> Function() action) async {
    final previous = _running[_key] ?? Future<void>.value();
    final next = previous.then(
      (_) => action(),
      onError: (Object _) => action(),
    );
    _running[_key] = next;
    try {
      await next;
    } finally {
      if (identical(_running[_key], next)) _running.remove(_key);
    }
  }

  Future<Json?> pending(Object? id) async => (await _edits())['$id'] as Json?;

  Future<({Map<int, Json> edits, List<Json> creations})>
  pendingChanges() async {
    final entries = (await _edits()).entries;
    return (
      edits: {
        for (final entry in entries)
          if (int.tryParse(entry.key) case final int id)
            id: entry.value as Json,
      },
      creations: [
        for (final entry in entries)
          if (entry.key.startsWith('create:'))
            {...entry.value as Json, 'key': entry.key},
      ],
    );
  }

  Future<List<Json>> creations() async => (await pendingChanges()).creations;

  Future<void> enqueueNew(Json values, {String? operation}) =>
      _serial(() async {
        final edits = await _edits();
        edits['create:${operation ?? const Uuid().v4()}'] = {'values': values};
        await _storeEdits(edits);
      });

  Future<void> enqueue(Json note, Json values, {String? operation}) =>
      _serial(() async {
        final id = note['id'];
        if (!canQueueEdit(note)) {
          throw StateError('This note is unavailable for offline editing.');
        }
        final edits = await _edits();
        if (edits.containsKey('$id')) {
          throw StateError('This note already has an edit awaiting sync.');
        }
        edits['$id'] = {
          'values': {...values, 'version': note['version']},
          'operation': operation ?? const Uuid().v4(),
        };
        await _storeEdits(edits);
      });

  bool canQueueEdit(Json note) =>
      note['id'] is int && note['version'] is int && _eligible(note);

  Future<void> discard(Object? id) => _serial(() async {
    final edits = await _edits();
    edits.remove('$id');
    await _storeEdits(edits);
  });

  Future<void> sync(ApiClient api) {
    final revision = api.sessionRevision;
    return _serial(() async {
      final edits = await _edits();
      for (final id in edits.keys.toList()) {
        if (!api.hasSession || api.sessionRevision != revision) return;
        final edit = edits[id] as Json;
        if (edit['error'] != null) continue;
        final create = id.startsWith('create:');
        if (!create && edit['operation'] == null) {
          edit['operation'] = const Uuid().v4();
          await _storeEdits(edits);
          if (api.sessionRevision != revision) return;
        }
        try {
          final note =
              await api.request(
                    create ? 'POST' : 'PUT',
                    create
                        ? '/project-management/notes/offline-create'
                        : '/project-management/notes/$id',
                    scopeHeaders: {
                      'X-Suite-Organization': _company,
                      'X-Offline-Operation': create
                          ? id.substring('create:'.length)
                          : edit['operation'] as String,
                    },
                    data: edit['values'],
                  )
                  as Json;
          if (api.sessionRevision != revision) return;
          await _saveSyncedNote(note);
          edits.remove(id);
        } on ApiFailure catch (failure) {
          if (failure.status == null ||
              failure.status == 401 ||
              (create && const {404, 405}.contains(failure.status)) ||
              failure.status == 429 ||
              failure.status! >= 500) {
            return;
          }
          edit['error'] = '$failure';
        }
        await _storeEdits(edits);
        if (!edits.containsKey(id)) _synced.add(_key);
      }
    });
  }
}
