import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api_client.dart';
import 'models.dart';
import 'suite_read_cache.dart';

class SalesOrderDrafts {
  SalesOrderDrafts(String scope, {this.invalidate})
    : _key = 'sales_order_drafts_${Uri.encodeComponent(scope)}',
      _company = '${(jsonDecode(scope) as List)[2]}',
      _scope = scope,
      purchase = false;

  SalesOrderDrafts.purchaseOrders(String scope, {this.invalidate})
    : _key = 'purchase_order_drafts_${Uri.encodeComponent(scope)}',
      _company = '${(jsonDecode(scope) as List)[2]}',
      _scope = scope,
      purchase = true;

  static const endpoint = '/srm/sales-orders';
  static const customersEndpoint = '/srm/business/customers';
  static const productsEndpoint = '/srm/inventory/items';
  static const _storage = FlutterSecureStorage();
  static final _running = <String, Future<void>>{};
  static final _changes = StreamController<String>.broadcast();
  final String _key, _company, _scope;
  final bool purchase;
  static const purchaseOrdersEndpoint = '/srm/procurement/purchase-orders';
  final Future<void> Function(String)? invalidate;
  Stream<String> get changes => _changes.stream.where((scope) => scope == _key);
  static String productPickerCacheKey(String scope) =>
      '$scope:$productsEndpoint:order-picker';

  Future<List<Json>> products(
    ApiClient api,
    String search, {
    required bool offline,
  }) async {
    final revision = api.sessionRevision;
    if (!offline) {
      try {
        final data =
            await api.request(
                  'GET',
                  productsEndpoint,
                  query: {
                    'summary_only': true,
                    'page': 1,
                    'per_page': 50,
                    if (search.isNotEmpty) 'search': search,
                  },
                  scopeHeaders: {'X-Suite-Organization': _company},
                )
                as Json;
        if (revision != api.sessionRevision) {
          throw ApiFailure('Your session ended. Sign in again.', 401);
        }
        final rows = (data['items'] as List).whereType<Json>().toList();
        if (rows.isNotEmpty) {
          final savedAt = DateTime.now().millisecondsSinceEpoch;
          try {
            await SuiteReadCache.write(productPickerCacheKey(_scope), [
              for (final row in rows)
                {
                  for (final field in [
                    'id',
                    'item_name',
                    'sku',
                    'barcode',
                    'sales_rate',
                  ])
                    field: row[field],
                  'picker_saved_at': savedAt,
                },
            ], retainRecent: 200);
          } catch (_) {
            // The catalogue is still available while online.
          }
        }
        return rows;
      } on ApiFailure catch (error) {
        if (const {401, 403}.contains(error.status) &&
            revision == api.sessionRevision) {
          try {
            await SuiteReadCache.clear(productPickerCacheKey(_scope));
            await SuiteReadCache.clear('$_scope:$productsEndpoint');
          } catch (_) {}
        }
        if (!error.connectionFailure || revision != api.sessionRevision) {
          rethrow;
        }
      }
    }
    final snapshots = await Future.wait([
      SuiteReadCache.snapshot('$_scope:$productsEndpoint'),
      SuiteReadCache.snapshot(productPickerCacheKey(_scope)),
    ]);
    if (revision != api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    final term = search.toLowerCase();
    final cutoff = DateTime.now()
        .subtract(const Duration(days: 1))
        .millisecondsSinceEpoch;
    final saved = <int, (int, Json)>{};
    for (final snapshot in snapshots.nonNulls) {
      for (final row in snapshot.rows) {
        final timestamp =
            row['picker_saved_at'] as int? ??
            snapshot.savedAt.millisecondsSinceEpoch;
        if (row['id'] case final int id
            when timestamp >= cutoff && timestamp > (saved[id]?.$1 ?? 0)) {
          saved[id] = (timestamp, row);
        }
      }
    }
    return saved.values
        .map((entry) => entry.$2)
        .where(
          (row) => '${row['item_name']} ${row['sku']} ${row['barcode']}'
              .toLowerCase()
              .contains(term),
        )
        .toList();
  }

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

  Future<void> _write(Json drafts) async {
    await _storage.write(key: _key, value: jsonEncode(drafts));
    _changes.add(_key);
  }

  Future<void> save(
    String operation,
    Json payload, {
    String? customerName,
    String? replaceRejected,
    String? branch,
  }) => _modify((drafts) async {
    if (replaceRejected != null) {
      final previous = drafts[replaceRejected] as Json?;
      if (previous?['status'] != 422) {
        throw StateError(
          'This saved order draft has changed. Reopen it first.',
        );
      }
      drafts.remove(replaceRejected);
    }
    drafts[operation] = {
      'payload': payload,
      'customer_name': ?customerName,
      'branch': ?branch,
    };
    await _write(drafts);
  });

  Future<void> discard(String operation) => _modify((drafts) async {
    drafts.remove(operation);
    await _write(drafts);
  });

  Future<void> submit(
    ApiClient api,
    String operation,
    Json payload, {
    String? branch,
  }) async {
    final result = await api.request(
      'POST',
      purchase ? '$purchaseOrdersEndpoint/drafts/offline-create' : endpoint,
      data: payload,
      scopeHeaders: {
        'X-Suite-Organization': _company,
        'X-Suite-Branch': ?branch,
        'X-Offline-Operation': operation,
      },
    );
    if (purchase &&
        (result is! Json ||
            result['id'] is! int ||
            result['status'] != 'draft')) {
      throw ApiFailure('Draft confirmation is unavailable.', 503);
    }
  }

  Future<void> sync(ApiClient api, {void Function()? onUploaded}) {
    final revision = api.sessionRevision;
    return _modify((drafts) async {
      for (final operation in drafts.keys.toList()) {
        if (!api.hasSession || api.sessionRevision != revision) return;
        final draft = drafts[operation] as Json;
        if (draft['error'] != null) continue;
        try {
          await submit(
            api,
            operation,
            draft['payload'] as Json,
            branch: draft['branch'] as String?,
          );
          drafts.remove(operation);
        } on ApiFailure catch (error) {
          if (error.connectionFailure ||
              error.status == 401 ||
              error.status == 429 ||
              (error.status ?? 500) >= 500) {
            return;
          }
          draft['error'] = error.toString();
          draft['status'] = error.status;
        }
        await _write(drafts);
        if (!drafts.containsKey(operation) && api.sessionRevision == revision) {
          try {
            await invalidate?.call(
              '$_scope:${purchase ? purchaseOrdersEndpoint : endpoint}',
            );
          } catch (_) {
            // The server has already accepted the draft.
          }
          onUploaded?.call();
        }
      }
    });
  }
}
