import 'dart:async';

import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/crm_detail_snapshot.dart';
import 'package:dio/dio.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import 'api_client_test.dart' show FakeAdapter, MemoryStore, response;

void main() {
  testWidgets(
    'Live CRM details can arrive while SQLite is opening',
    (tester) => tester.runAsync(() async {
      const channel = MethodChannel('com.tekartik.sqflite');
      const path = '/crm/contacts/33';
      const scope = 'slow-cache';
      final sqliteReady = Completer<void>();
      var opening = false;
      final messenger =
          TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
      databaseFactory = databaseFactorySqflitePlugin;
      messenger.setMockMethodCallHandler(channel, (call) async {
        expect(call.method, 'getDatabasesPath');
        opening = true;
        await sqliteReady.future;
        throw PlatformException(code: 'cache_unavailable');
      });
      try {
        final api = ApiClient(
          baseUrl: 'https://example.test/api/v1',
          store: MemoryStore(),
          transport: Dio()
            ..httpClientAdapter = FakeAdapter((request) async {
              expect(request.path, path);
              return response({'id': 33, 'full_name': 'Live contact'});
            }),
        );
        final result = await loadCrmDetail(
          api: api,
          path: path,
          scope: scope,
          headers: const {},
          offline: false,
          project: (record) => record,
        ).timeout(const Duration(seconds: 5));
        expect(opening, isTrue);
        expect(result.live, isTrue);
        expect(result.record?['full_name'], 'Live contact');
      } finally {
        sqliteReady.complete();
        await flushCrmDetailWrite('$scope:$path:');
        messenger.setMockMethodCallHandler(channel, null);
        databaseFactory = null;
      }
    }),
  );
}
