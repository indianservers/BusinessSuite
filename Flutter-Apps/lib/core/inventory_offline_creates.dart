import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import 'api_client.dart';
import 'models.dart';

class InventoryOfflineCreates {
  InventoryOfflineCreates(String scope, {this.invalidate})
    : _scope = scope,
      _key = 'inventory_creates_${Uri.encodeComponent(scope)}',
      _company = '${(jsonDecode(scope) as List)[2]}';
  final String _key, _company;
  String get organizationId => _company;
  final String _scope;
  final Future<void> Function(String)? invalidate;
  static const itemsEndpoint = '/srm/inventory/items';
  static const _storage = FlutterSecureStorage();
  static final Map<String, Future<void>> _running = {};

  Future<List<Json>> entries() async {
    final raw = await _storage.read(key: _key);
    return raw == null ? [] : (jsonDecode(raw) as List).cast<Json>();
  }

  Future<List<Json>> writableBranches(
    ApiClient api, {
    bool offline = false,
  }) async {
    final cacheKey = '${_key}_branches';
    final revision = api.sessionRevision;
    void checkSession() {
      if (api.sessionRevision != revision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
    }

    Future<List<Json>?> savedBranches() async {
      final raw = await _storage.read(key: cacheKey);
      checkSession();
      return raw == null ? null : (jsonDecode(raw) as List).cast<Json>();
    }

    if (offline) {
      return await savedBranches() ??
          (throw ApiFailure('Connect to load writable branches.'));
    }
    try {
      final data =
          await api.request(
                'GET',
                '/branches/context',
                scopeHeaders: {'X-Suite-Organization': _company},
              )
              as Json;
      checkSession();
      final branches = (data['branches'] as List)
          .whereType<Json>()
          .where(
            (branch) =>
                branch['id'] is int &&
                branch['can_write'] == true &&
                branch['is_active'] == true,
          )
          .toList();
      await _storage.write(key: cacheKey, value: jsonEncode(branches));
      checkSession();
      return branches;
    } on ApiFailure catch (error) {
      if (const {401, 403}.contains(error.status) &&
          api.sessionRevision == revision) {
        try {
          await _storage.delete(key: cacheKey);
        } catch (_) {}
      }
      if (error.status != null && error.status! < 500) rethrow;
      final saved = await savedBranches();
      if (saved == null) rethrow;
      return saved;
    }
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

  Future<void> enqueue(
    Json product, {
    required int branchId,
    String? replaceRejected,
  }) => _serialized(() async {
    final pending = await entries();
    final replacementIndex = replaceRejected == null
        ? -1
        : pending.indexWhere(
            (entry) =>
                entry['operation'] == replaceRejected &&
                (entry['error'] != null || entry['branch'] == null),
          );
    if (replaceRejected != null && replacementIndex == -1) {
      throw StateError('This rejected draft is no longer available.');
    }
    if (pending.any(
      (entry) =>
          entry['operation'] != replaceRejected &&
          (entry['product'] as Json)['code'] == product['code'],
    )) {
      throw StateError('An unsynced product already uses this SKU.');
    }
    final legacy =
        replacementIndex >= 0 &&
        pending[replacementIndex]['branch'] == null &&
        pending[replacementIndex]['error'] == null;
    final entry = {
      'operation': legacy ? replaceRejected : const Uuid().v4(),
      'product': product,
      'branch': branchId,
    };
    if (replacementIndex == -1) {
      pending.add(entry);
    } else {
      pending[replacementIndex] = entry;
    }
    await _storage.write(key: _key, value: jsonEncode(pending));
  });

  Future<void> discard(String operation) => _serialized(() async {
    final pending = await entries();
    pending.removeWhere((entry) => entry['operation'] == operation);
    await _storage.write(key: _key, value: jsonEncode(pending));
  });

  Future<void> sync(ApiClient api, {bool reportTemporaryFailure = false}) {
    final revision = api.sessionRevision;
    return _serialized(() async {
      final pending = await entries();
      for (final entry in pending.toList()) {
        if (!api.hasSession || revision != api.sessionRevision) return;
        final branch = entry['branch'];
        if (entry['error'] != null || branch is! int) continue;
        try {
          await api.request(
            'POST',
            '/catalog/items',
            query: {'source': 'srm'},
            scopeHeaders: {
              'X-Suite-Organization': _company,
              'X-Suite-Branch': '$branch',
              'X-Offline-Operation': entry['operation'] as String,
            },
            data: entry['product'],
          );
          try {
            await invalidate?.call('$_scope:$itemsEndpoint');
          } catch (_) {
            // The server accepted the draft even when local reads are unavailable.
          }
          pending.remove(entry);
        } on ApiFailure catch (error) {
          if (error.status == null ||
              error.status == 401 ||
              error.status == 429 ||
              (error.status ?? 500) >= 500) {
            if (reportTemporaryFailure) rethrow;
            return;
          }
          entry['error'] = error.toString();
        }
        await _storage.write(key: _key, value: jsonEncode(pending));
      }
    });
  }
}
