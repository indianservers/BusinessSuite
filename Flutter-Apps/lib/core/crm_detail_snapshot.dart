import 'api_client.dart';
import 'models.dart';
import 'suite_read_cache.dart';

Future<({Json? record, bool live})> loadCrmDetail({
  required ApiClient api,
  required String path,
  required String? scope,
  required Map<String, String> headers,
  required bool offline,
  required Json Function(Json) project,
}) async {
  final revision = api.sessionRevision;
  final branch = headers['X-Suite-Branch'] ?? '';
  final key = scope == null ? null : '$scope:$path:$branch';
  void checkSession() {
    if (revision != api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
  }

  if (!offline) {
    try {
      final record =
          await api.request('GET', path, scopeHeaders: headers) as Json;
      checkSession();
      if (key != null) {
        try {
          await SuiteReadCache.write(key, [project(record)]);
        } catch (_) {
          // Local storage is optional for the live record.
        }
      }
      checkSession();
      return (record: record, live: true);
    } on ApiFailure catch (error) {
      if (key != null && const {401, 403, 404}.contains(error.status)) {
        try {
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
  List<Json>? rows;
  if (key != null) {
    try {
      rows = await SuiteReadCache.read(key);
    } catch (_) {}
  }
  checkSession();
  return (record: rows?.firstOrNull, live: false);
}
