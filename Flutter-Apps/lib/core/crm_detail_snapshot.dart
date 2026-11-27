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

  Json? cached;
  if (key != null) {
    try {
      cached =
          _pendingDetails[key]?.record ??
          (await SuiteReadCache.read(key))?.firstOrNull;
    } catch (_) {}
    checkSession();
    if (!offline && cached != null) onCached?.call(cached);
  }

  if (!offline) {
    try {
      final record =
          await api.request('GET', path, scopeHeaders: headers) as Json;
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
    }
  }
  checkSession();
  return (record: cached, live: false);
}
