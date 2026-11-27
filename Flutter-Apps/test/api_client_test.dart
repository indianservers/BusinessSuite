import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/inventory_offline_creates.dart';
import 'package:business_suite_mobile/app_controller.dart';

class MemoryStore implements SessionStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String value) async {
    this.value = value;
  }

  @override
  Future<void> clear() async {
    value = null;
  }
}

class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.handler);
  final Future<ResponseBody> Function(RequestOptions) handler;
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) => handler(options);
  @override
  void close({bool force = false}) {}
}

ResponseBody response(Object data, [int status = 200]) =>
    ResponseBody.fromString(
      jsonEncode(data),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Dio dio;
  late MemoryStore store;
  late ApiClient api;
  setUp(() {
    dio = Dio();
    store = MemoryStore();
    api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      store: store,
      transport: dio,
    );
  });
  test(
    'inventory retries keep the operation ID until the draft is corrected',
    () async {
      FlutterSecureStorage.setMockInitialValues({});
      await api.acceptTokens({
        'access_token': 'access',
        'refresh_token': 'refresh',
      });
      final drafts = InventoryOfflineCreates('["server",1,8]');
      final product = {'kind': 'product', 'name': 'Phone QA', 'code': 'QA'};
      await drafts.enqueue(product, branchId: 3);
      final initial = (await drafts.entries()).single['operation'];
      var status = 503;
      final sent = <Object?>[];
      dio.httpClientAdapter = FakeAdapter((request) async {
        expect(request.headers['X-Suite-Branch'], '3');
        expect(request.headers['X-Suite-Organization'], '8');
        sent.add(request.headers['X-Offline-Operation']);
        return response({'detail': 'Test response'}, status);
      });
      await expectLater(
        drafts.sync(api, reportTemporaryFailure: true),
        throwsA(isA<ApiFailure>()),
      );
      expect((await drafts.entries()).single['error'], isNull);
      await expectLater(
        drafts.enqueue(
          product,
          branchId: 3,
          replaceRejected: initial as String,
        ),
        throwsStateError,
      );
      status = 422;
      await drafts.sync(api);
      expect((await drafts.entries()).single['error'], isNotNull);
      await drafts.enqueue(
        {...product, 'name': 'Corrected'},
        branchId: 3,
        replaceRejected: initial,
      );
      final corrected = (await drafts.entries()).single['operation'];
      expect(corrected, isNot(initial));
      status = 201;
      await drafts.sync(api);
      expect(sent, [initial, initial, corrected]);
      expect(await drafts.entries(), isEmpty);
    },
  );
  test('inventory retains a stale offline product edit for review', () async {
    FlutterSecureStorage.setMockInitialValues({});
    await api.acceptTokens({
      'access_token': 'access',
      'refresh_token': 'refresh',
    });
    final drafts = InventoryOfflineCreates('["server",1,8]');
    const changes = {
      'description': 'Saved offline',
      'expected_updated_at': '2026-11-28T02:00:00Z',
    };
    await drafts.enqueueEdit(
      productId: 314,
      name: 'QA product',
      sku: 'QA',
      branchId: 3,
      changes: changes,
    );
    final operation = (await drafts.entries()).single['operation'];
    var status = 503;
    dio.httpClientAdapter = FakeAdapter((request) async {
      expect(request.method, 'PUT');
      expect(request.path, '/srm/inventory/items/314');
      expect(request.headers['X-Suite-Branch'], '3');
      expect(request.headers['X-Suite-Organization'], '8');
      expect(request.headers['X-Offline-Operation'], operation);
      expect(request.data, changes);
      return response({'detail': 'Product changed'}, status);
    });
    await drafts.sync(api);
    expect((await drafts.entries()).single['error'], isNull);
    status = 409;
    await drafts.sync(api);
    final saved = (await drafts.entries()).single;
    expect(saved['changes'], changes);
    expect(saved['error'], contains('Product changed'));
  });
  test(
    'restores the saved suite only for a disconnected signed-in session',
    () async {
      await api.acceptTokens({
        'access_token': 'access',
        'refresh_token': 'refresh',
      });
      await api.rememberSuite(
        {'id': 4, 'email': 'member@example.test'},
        {'companyId': 2},
      );
      final restored = ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: store,
        transport: dio,
      );
      dio.httpClientAdapter = FakeAdapter(
        (request) async => throw DioException(
          requestOptions: request,
          type: DioExceptionType.connectionError,
        ),
      );
      final controller = AppController(restored, suiteLogin: true);
      await controller.start();
      expect(controller.offline, isTrue);
      expect(controller.user?.id, 4);
      expect(restored.offlineSuite?['access']['companyId'], 2);
      dio.httpClientAdapter = FakeAdapter(
        (request) async => response({'detail': 'Forbidden'}, 403),
      );
      await controller.loadAccount(restoreOffline: true);
      expect(controller.user, isNull);
      expect(controller.offline, isFalse);
      await api.acceptTokens({
        'access_token': 'other',
        'refresh_token': 'other',
      });
      expect(api.offlineSuite, isNull);
    },
  );
  test(
    'PMS login sends module and does not attach a previous bearer',
    () async {
      dio.httpClientAdapter = FakeAdapter((request) async {
        expect(request.path, '/auth/login');
        expect(request.data['module'], 'project_management');
        expect(request.headers['Authorization'], isNull);
        return response({'mfa_required': true, 'mfa_token': 'challenge'});
      });
      expect(
        (await api.login('member@example.test', 'password'))['mfa_required'],
        true,
      );
    },
  );
  test(
    'parallel expired requests share one refresh and retry with rotated token',
    () async {
      var refreshes = 0;
      await api.acceptTokens({
        'access_token': 'expired',
        'refresh_token': 'refresh',
      });
      dio.httpClientAdapter = FakeAdapter((request) async {
        if (request.path == '/auth/refresh') {
          refreshes++;
          await Future<void>.delayed(const Duration(milliseconds: 20));
          return response({'access_token': 'new', 'refresh_token': 'rotated'});
        }
        if (request.headers['Authorization'] == 'Bearer expired') {
          return response({}, 401);
        }
        expect(request.headers['Authorization'], 'Bearer new');
        return response({'ok': true});
      });
      final results = await Future.wait([
        api.request('GET', '/one'),
        api.request('GET', '/two'),
      ]);
      expect(results.every((r) => r['ok'] == true), true);
      expect(refreshes, 1);
      expect(jsonDecode(store.value!)['refresh_token'], 'rotated');
    },
  );
  test(
    'rejected refresh clears stored credentials and expires session',
    () async {
      await api.acceptTokens({
        'access_token': 'expired',
        'refresh_token': 'revoked',
      });
      var expired = false;
      api.onExpired = () => expired = true;
      dio.httpClientAdapter = FakeAdapter(
        (request) async => response({'detail': 'Session revoked'}, 401),
      );
      await expectLater(
        api.request('GET', '/private'),
        throwsA(isA<ApiFailure>()),
      );
      expect(store.value, isNull);
      expect(api.hasSession, false);
      expect(expired, true);
    },
  );
  test('offline refresh preserves session for a later retry', () async {
    await api.acceptTokens({
      'access_token': 'expired',
      'refresh_token': 'valid',
    });
    dio.httpClientAdapter = FakeAdapter((request) async {
      if (request.path == '/auth/refresh') {
        throw DioException(
          requestOptions: request,
          type: DioExceptionType.connectionError,
        );
      }
      return response({}, 401);
    });
    await expectLater(
      api.request('GET', '/private'),
      throwsA(isA<ApiFailure>()),
    );
    expect(api.hasSession, true);
  });
  test('forbidden mutation is not retried or refreshed', () async {
    var requests = 0;
    dio.httpClientAdapter = FakeAdapter((request) async {
      requests++;
      return response({'detail': 'Project access denied'}, 403);
    });
    await expectLater(
      api.request(
        'PATCH',
        '/project-management/tasks/7',
        data: {'status': 'Done'},
      ),
      throwsA(isA<ApiFailure>().having((e) => e.status, 'status', 403)),
    );
    expect(requests, 1);
  });
  test('invalid persisted session is removed', () async {
    store.value = 'invalid';
    await api.restore();
    expect(store.value, isNull);
    expect(api.hasSession, false);
  });
  test(
    'request IDs are unique and structured server errors retain diagnostics',
    () async {
      final ids = <String>{};
      dio.httpClientAdapter = FakeAdapter((request) async {
        ids.add(request.headers['X-Request-ID'] as String);
        return response({
          'detail': {'message': 'Validation rejected'},
          'request_id': 'support-123',
        }, 422);
      });
      for (var i = 0; i < 2; i++) {
        await expectLater(
          api.request('GET', '/private'),
          throwsA(
            isA<ApiFailure>().having(
              (e) => e.message,
              'message',
              'Validation rejected (Reference: support-123)',
            ),
          ),
        );
      }
      expect(ids.length, 2);
    },
  );
}
