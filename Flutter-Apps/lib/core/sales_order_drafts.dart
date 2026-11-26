import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api_client.dart';
import 'models.dart';

class SalesOrderDrafts {
  SalesOrderDrafts(String scope)
    : _key = 'sales_order_drafts_${Uri.encodeComponent(scope)}',
      _company = '${(jsonDecode(scope) as List)[2]}';

  static const endpoint = '/srm/sales-orders';
  static const customersEndpoint = '/srm/business/customers';
  static const _storage = FlutterSecureStorage();
  static final _running = <String, Future<void>>{};
  final String _key, _company;

  Future<Json> _read() async {
    final raw = await _storage.read(key: _key);
    return raw == null ? {} : jsonDecode(raw) as Json;
  }

  Future<List<Json>> entries() async => [
    for (final entry in (await _read()).entries)
      {...entry.value as Json, 'operation': entry.key},
  ];

  Future<List<Json>> customers(
    ApiClient api,
    String search, {
    required bool offline,
  }) async {
    final cacheKey = '$_key:customers';
    final revision = api.sessionRevision;
    if (!offline) {
      try {
        final data =
            await api.request(
                  'GET',
                  customersEndpoint,
                  query: {if (search.isNotEmpty) 'q': search},
                  scopeHeaders: {'X-Suite-Organization': _company},
                )
                as Json;
        if (revision != api.sessionRevision) {
          throw ApiFailure('Your session ended. Sign in again.', 401);
        }
        final rows = (data['items'] as List).whereType<Json>().toList();
        if (search.isEmpty) {
          try {
            await _storage.write(
              key: cacheKey,
              value: jsonEncode([
                for (final row in rows) {'id': row['id'], 'name': row['name']},
              ]),
            );
          } catch (_) {}
        }
        return rows;
      } on ApiFailure catch (error) {
        if (const {401, 403}.contains(error.status) &&
            revision == api.sessionRevision) {
          try {
            await _storage.delete(key: cacheKey);
          } catch (_) {}
        }
        if (!error.connectionFailure || revision != api.sessionRevision) {
          rethrow;
        }
      }
    }
    final raw = await _storage.read(key: cacheKey);
    if (revision != api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    if (raw == null) return [];
    final term = search.toLowerCase();
    return (jsonDecode(raw) as List)
        .whereType<Json>()
        .where((row) => '${row['name']}'.toLowerCase().contains(term))
        .toList();
  }

  Future<void> _modify(Future<void> Function(Json drafts) action) async {
    final previous = _running[_key] ?? Future<void>.value();
    Future<void> update() async => action(await _read());
    final next = previous.then((_) => update(), onError: (_) => update());
    _running[_key] = next;
    try {
      await next;
    } finally {
      if (identical(_running[_key], next)) _running.remove(_key);
    }
  }

  Future<void> _write(Json drafts) =>
      _storage.write(key: _key, value: jsonEncode(drafts));

  Future<void> save(String operation, Json payload) => _modify((drafts) async {
    drafts[operation] = {'payload': payload};
    await _write(drafts);
  });

  Future<void> submit(ApiClient api, String operation, Json payload) async {
    await api.request(
      'POST',
      endpoint,
      data: payload,
      scopeHeaders: {
        'X-Suite-Organization': _company,
        'X-Offline-Operation': operation,
      },
    );
  }

  Future<void> sync(ApiClient api, {void Function()? onUploaded}) {
    final revision = api.sessionRevision;
    return _modify((drafts) async {
      for (final operation in drafts.keys.toList()) {
        if (!api.hasSession || api.sessionRevision != revision) return;
        final draft = drafts[operation] as Json;
        if (draft['error'] != null) continue;
        try {
          await submit(api, operation, draft['payload'] as Json);
          drafts.remove(operation);
        } on ApiFailure catch (error) {
          if (error.connectionFailure ||
              error.status == 401 ||
              error.status == 429 ||
              (error.status ?? 500) >= 500) {
            return;
          }
          draft['error'] = error.toString();
        }
        await _write(drafts);
        if (!drafts.containsKey(operation) && api.sessionRevision == revision) {
          onUploaded?.call();
        }
      }
    });
  }
}
