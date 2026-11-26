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
        try {
          await api.request(
            'PATCH',
            '/crm/lead-management/leads/$id',
            scopeHeaders: {'X-Suite-Organization': _company},
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
}
