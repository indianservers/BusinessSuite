import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api_client.dart';
import 'models.dart';

class CrmOfflineEdits {
  CrmOfflineEdits(String scope)
    : _key = 'crm_edits_${Uri.encodeComponent(scope)}',
      _company = '${(jsonDecode(scope) as List)[2]}';
  final String _key;
  final String _company;
  static const _storage = FlutterSecureStorage();
  static final Map<String, Future<void>> _running = {};

  Future<Json> _read() async {
    final raw = await _storage.read(key: _key);
    return raw == null ? <String, dynamic>{} : jsonDecode(raw) as Json;
  }

  Future<Json?> pending(int id) async => (await _read())['$id'] as Json?;
  Map<String, String> creationHeaders(String operation) => {
    'X-Suite-Organization': _company,
    'X-Offline-Operation': operation,
  };
  Future<List<Json>> creations() async => [
    for (final row in (await _read()).entries)
      if (row.key.startsWith('create:')) {...row.value as Json, 'key': row.key},
  ];

  Future<void> enqueueCreation(
    String operation,
    Json payload, {
    String? replaceRejected,
  }) => _serialized(() async {
    final rows = await _read();
    if (replaceRejected != null) {
      final old = rows[replaceRejected] as Json?;
      if (!replaceRejected.startsWith('create:') || old?['status'] != 422) {
        throw StateError('This saved lead draft has changed. Reopen it first.');
      }
      rows.remove(replaceRejected);
    }
    rows['create:$operation'] = payload;
    await _storage.write(key: _key, value: jsonEncode(rows));
  });
  Future<bool> get hasPending async =>
      (await _read()).values.any((row) => (row as Json)['error'] == null);

  Future<void> _serialized(Future<void> Function() action) async {
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

  Future<void> enqueue(
    int id,
    int version,
    Json values, {
    int? rejectedVersion,
  }) => _serialized(() async {
    final rows = await _read();
    final existing = rows['$id'] as Json?;
    if (rejectedVersion != null) {
      if (existing?['error'] == null ||
          existing?['version'] != rejectedVersion) {
        throw StateError('This saved edit has changed. Refresh the lead.');
      }
    } else if (existing != null) {
      throw StateError(
        'This lead already has a saved edit awaiting review or sync.',
      );
    }
    rows['$id'] = {'version': version, 'values': values};
    await _storage.write(key: _key, value: jsonEncode(rows));
  });

  Future<void> sync(ApiClient api, {int? leadId}) {
    final session = api.sessionRevision;
    return _serialized(() async {
      final rows = await _read();
      final ids = leadId == null ? rows.keys.toList() : ['$leadId'];
      for (final id in ids) {
        if (!api.hasSession || session != api.sessionRevision) return;
        final edit = rows[id] as Json?;
        if (edit == null || edit['error'] != null) continue;
        final creating = id.startsWith('create:');
        try {
          await api.request(
            creating ? 'POST' : 'PATCH',
            creating
                ? '/crm/lead-management/leads'
                : '/crm/lead-management/leads/$id',
            scopeHeaders: creating
                ? creationHeaders(id.substring('create:'.length))
                : {'X-Suite-Organization': _company},
            data: edit,
          );
          rows.remove(id);
        } on ApiFailure catch (failure) {
          if (failure.connectionFailure ||
              failure.status == 401 ||
              failure.status == 429 ||
              (failure.status ?? 500) >= 500) {
            return;
          }
          edit['error'] = failure.toString();
          if (creating) edit['status'] = failure.status;
        }
        await _storage.write(key: _key, value: jsonEncode(rows));
      }
    });
  }

  Future<void> discard(int id) => _serialized(() async {
    final rows = await _read();
    rows.remove('$id');
    await _storage.write(key: _key, value: jsonEncode(rows));
  });

  Future<void> discardCreation(String key) => _serialized(() async {
    if (!key.startsWith('create:')) return;
    final rows = await _read();
    rows.remove(key);
    await _storage.write(key: _key, value: jsonEncode(rows));
  });
}
