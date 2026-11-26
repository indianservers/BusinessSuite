import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import 'api_client.dart';
import 'models.dart';

class InventoryOfflineCreates {
  InventoryOfflineCreates(String scope)
    : _key = 'inventory_creates_${Uri.encodeComponent(scope)}',
      _company = '${(jsonDecode(scope) as List)[2]}';
  final String _key, _company;
  static const _storage = FlutterSecureStorage();
  static final Map<String, Future<void>> _running = {};

  Future<List<Json>> entries() async {
    final raw = await _storage.read(key: _key);
    return raw == null ? [] : (jsonDecode(raw) as List).cast<Json>();
  }

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
      if (identical(next, _running[_key])) _running.remove(_key);
    }
  }

  Future<void> enqueue(Json product) => _serialized(() async {
    final pending = await entries();
    if (pending.any(
      (entry) => (entry['product'] as Json)['code'] == product['code'],
    )) {
      throw StateError('An unsynced product already uses this SKU.');
    }
    pending.add({'operation': const Uuid().v4(), 'product': product});
    await _storage.write(key: _key, value: jsonEncode(pending));
  });

  Future<void> discard(String operation) => _serialized(() async {
    final pending = await entries();
    pending.removeWhere((entry) => entry['operation'] == operation);
    await _storage.write(key: _key, value: jsonEncode(pending));
  });

  Future<void> sync(ApiClient api) {
    final revision = api.sessionRevision;
    return _serialized(() async {
      final pending = await entries();
      for (final entry in pending.toList()) {
        if (!api.hasSession || revision != api.sessionRevision) return;
        if (entry['error'] != null) continue;
        try {
          await api.request(
            'POST',
            '/catalog/items',
            query: {'source': 'srm'},
            scopeHeaders: {
              'X-Suite-Organization': _company,
              'X-Offline-Operation': entry['operation'] as String,
            },
            data: entry['product'],
          );
          pending.remove(entry);
        } on ApiFailure catch (error) {
          if (error.status == null ||
              error.status == 401 ||
              error.status == 429 ||
              (error.status ?? 500) >= 500) {
            return;
          }
          entry['error'] = error.toString();
        }
        await _storage.write(key: _key, value: jsonEncode(pending));
      }
    });
  }
}
