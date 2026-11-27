import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api_client.dart';
import 'models.dart';
import 'suite_read_cache.dart';

class InventoryStockReceipts {
  InventoryStockReceipts(this.scope);

  final String scope;
  static const storage = FlutterSecureStorage();
  static const endpoint = '/srm/inventory/stock-movements/offline-create';
  static final Map<String, Future<void>> _operations = {};

  String get _prefix => 'stock_receipt_${Uri.encodeComponent('$scope:')}';
  String key(String branch, int product) =>
      '$_prefix${Uri.encodeComponent('$branch:$product')}';

  static Future<void> serialize(
    String key,
    Future<void> Function() action,
  ) async {
    final previous = _operations[key] ?? Future<void>.value();
    final next = previous.then(
      (_) => action(),
      onError: (Object _) => action(),
    );
    _operations[key] = next;
    try {
      await next;
    } finally {
      if (identical(_operations[key], next)) _operations.remove(key);
    }
  }

  Future<void> sync(ApiClient api) async {
    if (!api.hasSession) return;
    final revision = api.sessionRevision;
    final company = (jsonDecode(scope) as List)[2];
    final receipts = await storage.readAll();
    for (final key in receipts.keys.where((key) => key.startsWith(_prefix))) {
      if (!api.hasSession || api.sessionRevision != revision) return;
      var retryLater = false;
      await serialize(key, () async {
        final raw = await storage.read(key: key);
        if (raw == null || api.sessionRevision != revision) return;
        final entry = jsonDecode(raw) as Json;
        final branch = entry['queuedBranch'];
        if (branch is! String || entry['error'] != null) return;
        final payload = entry['payload'] as Json;
        try {
          await api.request(
            'POST',
            endpoint,
            scopeHeaders: {
              'X-Suite-Organization': '$company',
              if (branch.isNotEmpty) 'X-Suite-Branch': branch,
              'X-Offline-Operation': entry['id'] as String,
            },
            data: payload,
          );
          await storage.delete(key: key);
          await invalidate(branch, payload['product_id'] as int);
        } on ApiFailure catch (error) {
          if (error.status == null ||
              const {401, 429}.contains(error.status) ||
              (error.status ?? 0) >= 500) {
            retryLater = true;
            return;
          }
          await storage.write(
            key: key,
            value: jsonEncode({...entry, 'error': error.message}),
          );
        }
      });
      if (retryLater) return;
    }
  }

  Future<void> invalidate(String branch, int product) async {
    for (final key in [
      '$scope:/srm/inventory/items/$product:$branch',
      '$scope:/srm/inventory/items',
      '$scope:/srm/inventory/reports/reorder',
      '$scope:/srm/inventory/reports/stock-summary',
    ]) {
      try {
        await SuiteReadCache.invalidate(key);
      } catch (_) {
        // A local cache failure cannot undo a confirmed movement.
      }
    }
  }
}
