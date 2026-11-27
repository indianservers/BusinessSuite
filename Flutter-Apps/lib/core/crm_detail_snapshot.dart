import 'dart:async';

import 'api_client.dart';
import 'models.dart';
import 'suite_read_cache.dart';

final _pendingDetails = <String, ({Json record, Future<void> write})>{};

Future<void> flushCrmDetailWrite(String key) async {
  await _pendingDetails[key]?.write;
}

void _saveDetail(String key, Json record) {
  final previous = _pendingDetails[key]?.write ?? Future<void>.value();
  late final Future<void> write;
  write = previous.then((_) async {
    try {
      await SuiteReadCache.write(key, [record]);
    } catch (_) {
      // A failed cache write must not hide live details.
    } finally {
      if (identical(_pendingDetails[key]?.write, write)) {
        _pendingDetails.remove(key);
      }
    }
  });
  _pendingDetails[key] = (record: record, write: write);
  unawaited(write);
}

Future<({Json? record, bool live})> loadCrmDetail({
  required ApiClient api,
  required String path,
  required String? scope,
  required Map<String, String> headers,
  required bool offline,
  required Json Function(Json) project,
  Json query = const {},
  void Function(Json)? onCached,
}) async {
  final revision = api.sessionRevision;
  final branch = headers['X-Suite-Branch'] ?? '';
  final key = scope == null ? null : '$scope:$path:$branch';
  void checkSession() {
    if (revision != api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
  }

  var awaitingLive = !offline;
  Future<Json?> readCached() async {
    if (key == null) return null;
    Json? cached;
    try {
      final pending = await Future<Json?>.value(_pendingDetails[key]?.record);
      cached = pending ?? (await SuiteReadCache.read(key))?.firstOrNull;
    } catch (_) {}
    if (awaitingLive && revision == api.sessionRevision && cached != null) {
      onCached?.call(cached);
    }
    return cached;
  }

  final cached = readCached();
  if (!offline) {
    try {
      final record =
          await api.request('GET', path, scopeHeaders: headers, query: query)
              as Json;
      awaitingLive = false;
      checkSession();
      if (key != null) {
        try {
          _saveDetail(key, project(record));
        } catch (_) {
          // Local storage is optional for the live record.
        }
      }
      checkSession();
      return (record: record, live: true);
    } on ApiFailure catch (error) {
      awaitingLive = false;
      if (key != null && const {401, 403, 404}.contains(error.status)) {
        try {
          await _pendingDetails.remove(key)?.write;
          await SuiteReadCache.clear(key);
        } catch (_) {}
      }
      checkSession();
      if (!error.connectionFailure &&
          error.status != 429 &&
          (error.status ?? 0) < 500) {
        rethrow;
      }
    } finally {
      awaitingLive = false;
    }
  }
  final saved = await cached;
  checkSession();
  return (record: saved, live: false);
}
