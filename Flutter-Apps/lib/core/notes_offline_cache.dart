import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'models.dart';

class NotesOfflineCache {
  NotesOfflineCache(String scope)
    : _key = 'offline_notes_${Uri.encodeComponent(scope)}';
  static const _storage = FlutterSecureStorage();
  final String _key;

  bool _eligible(Json note) =>
      note['can_edit'] == true &&
      note['project_id'] == null &&
      note['visibility_scope'] == 'private' &&
      note['visibility'] == 'private' &&
      note['deleted_at'] == null &&
      note['archived'] != true;

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

  Future<void> saveDetail(Json note) async {
    final details = (await _read(
      'details',
    )).where((row) => row['id'] != note['id']).toList();
    if (_eligible(note) && (note['content'] as String? ?? '').length <= 65536) {
      details.insert(0, note);
    }
    await _write('details', details.take(12).toList());
  }

  Future<void> clear() async {
    for (final suffix in ['summaries', 'details']) {
      try {
        await _storage.delete(key: '$_key:$suffix');
      } catch (_) {}
    }
  }
}
