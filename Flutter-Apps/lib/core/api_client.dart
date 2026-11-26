import 'dart:convert';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kReleaseMode;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'models.dart';

abstract class SessionStore {
  Future<String?> read();
  Future<void> write(String value);
  Future<void> clear();
}

class SecureSessionStore implements SessionStore {
  SecureSessionStore({required String server})
    : _key = 'pms_session_${Uri.encodeComponent(server)}';
  final String _key;
  final _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(storageNamespace: 'businesssuite_session_v1'),
  );
  @override
  Future<String?> read() =>
      _storage.read(key: _key).timeout(const Duration(seconds: 10));
  @override
  Future<void> write(String value) => _storage
      .write(key: _key, value: value)
      .timeout(const Duration(seconds: 10));
  @override
  Future<void> clear() =>
      _storage.delete(key: _key).timeout(const Duration(seconds: 5));
}

class ApiFailure implements Exception {
  ApiFailure(this.message, [this.status, this.connectionFailure = false]);
  final String message;
  final int? status;
  final bool connectionFailure;
  @override
  String toString() => message;
}

class ApiClient {
  static final _random = Random.secure();
  static String _requestId() {
    final bytes = List.generate(16, (_) => _random.nextInt(256));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  ApiClient({required String baseUrl, required this.store, Dio? transport})
    : dio = transport ?? Dio() {
    final uri = Uri.tryParse(baseUrl);
    if (uri == null ||
        !uri.hasAuthority ||
        !{'https', 'http'}.contains(uri.scheme) ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment) {
      throw ArgumentError(
        'API_BASE_URL must be an HTTP(S) URL without credentials, query, or fragment.',
      );
    }
    const allowHttp = bool.fromEnvironment('ALLOW_INSECURE_HTTP');
    if (uri.scheme != 'https' && (kReleaseMode || !allowHttp)) {
      throw ArgumentError(
        'Use HTTPS, or explicitly enable ALLOW_INSECURE_HTTP for local development.',
      );
    }
    dio.options = BaseOptions(
      baseUrl: baseUrl.replaceFirst(RegExp(r'/+$'), ''),
      connectTimeout: const Duration(seconds: 20),
      receiveTimeout: const Duration(seconds: 60),
      headers: {'Accept': 'application/json'},
    );
  }
  final Dio dio;
  final SessionStore store;
  String? _access, _refresh;
  Json? _offlineSuite;
  int _generation = 0;
  Future<void>? _refreshing;
  Future<void> _storageTail = Future.value();
  Future<void> _persist(Future<void> Function() action) {
    final next = _storageTail.then((_) => action());
    _storageTail = next.then<void>((_) {}, onError: (Object _) {});
    return next;
  }

  void Function()? onExpired;
  void Function(String method, String path, int status)? onResponse;
  bool get hasSession => _refresh != null;
  Json? get offlineSuite {
    final snapshot = _offlineSuite;
    final saved = snapshot?['saved_at'];
    final now = DateTime.now().millisecondsSinceEpoch;
    return hasSession &&
            saved is int &&
            saved <= now &&
            now - saved < const Duration(days: 1).inMilliseconds
        ? snapshot
        : null;
  }

  Future<void> restore() async {
    try {
      final raw = await store.read();
      if (raw == null) return;
      final json = jsonDecode(raw) as Json;
      _access = json['access_token'] as String;
      _refresh = json['refresh_token'] as String;
      _offlineSuite = json['offline_suite'] as Json?;
    } catch (_) {
      _access = null;
      _refresh = null;
      _offlineSuite = null;
      try {
        await store.clear();
      } catch (_) {
        /* A new sign-in can recreate invalid device keys. */
      }
    }
  }

  Future<void> acceptTokens(Json json, {bool rotating = false}) async {
    final access = json['access_token'] as String;
    final refresh = json['refresh_token'] as String;
    final generation = _generation;
    await _persist(
      () => store.write(
        jsonEncode({
          'access_token': access,
          'refresh_token': refresh,
          if (rotating && _offlineSuite != null) 'offline_suite': _offlineSuite,
        }),
      ),
    );
    if (generation != _generation) throw ApiFailure('Session ended.', 401);
    _access = access;
    _refresh = refresh;
    if (!rotating) _offlineSuite = null;
  }

  Future<void> rememberSuite(Json identity, Json access) async {
    final token = _access;
    final refresh = _refresh;
    if (token == null || refresh == null) return;
    final snapshot = <String, dynamic>{
      'saved_at': DateTime.now().millisecondsSinceEpoch,
      'identity': identity,
      'access': access,
    };
    await _persist(() async {
      if (_refresh != refresh) return;
      await store.write(
        jsonEncode({
          'access_token': token,
          'refresh_token': refresh,
          'offline_suite': snapshot,
        }),
      );
      if (_refresh == refresh) _offlineSuite = snapshot;
    });
  }

  Future<void> clear() async {
    _generation++;
    _access = null;
    _refresh = null;
    _offlineSuite = null;
    await _persist(store.clear);
  }

  Future<Json> login(
    String email,
    String password, {
    bool suite = false,
  }) async =>
      (await request(
            'POST',
            '/auth/login',
            auth: false,
            data: {
              'email': email,
              'password': password,
              if (!suite) 'module': 'project_management',
            },
          ))
          as Json;

  Future<void> logout() async {
    try {
      await request('POST', '/auth/logout');
    } finally {
      await clear();
    }
  }

  Future<dynamic> request(
    String method,
    String path, {
    Object? data,
    bool auth = true,
    Map<String, dynamic>? query,
    Map<String, String> scopeHeaders = const {},
    ResponseType? responseType,
    bool returnResponse = false,
  }) async {
    final generation = _generation;
    final sentToken = _access;
    final requestId = _requestId();
    try {
      final response = await dio.request<dynamic>(
        path,
        data: data,
        queryParameters: query,
        options: Options(
          method: method,
          responseType: responseType,
          followRedirects: responseType != ResponseType.bytes,
          validateStatus: (status) =>
              status != null &&
              status >= 200 &&
              status < (responseType == ResponseType.bytes ? 400 : 300),
          headers: {
            ...scopeHeaders,
            'X-Request-ID': requestId,
            if (auth && _access != null) 'Authorization': 'Bearer $_access',
          },
        ),
      );
      onResponse?.call(method, path, response.statusCode ?? 0);
      return returnResponse ? response : response.data;
    } on DioException catch (error) {
      onResponse?.call(method, path, error.response?.statusCode ?? 0);
      if (auth && error.response?.statusCode == 401 && _refresh != null) {
        try {
          if (sentToken == _access) {
            await (_refreshing ??= _rotate().whenComplete(
              () => _refreshing = null,
            ));
          }
        } on ApiFailure catch (failure) {
          if (failure.status == 401 || failure.status == 403) {
            await clear();
            onExpired?.call();
          }
          rethrow;
        }
        if (generation != _generation || _access == null) {
          throw ApiFailure('Your session ended. Sign in again.', 401);
        }
        try {
          final response = await dio.request<dynamic>(
            path,
            data: data,
            queryParameters: query,
            options: Options(
              method: method,
              responseType: responseType,
              followRedirects: responseType != ResponseType.bytes,
              validateStatus: (status) =>
                  status != null &&
                  status >= 200 &&
                  status < (responseType == ResponseType.bytes ? 400 : 300),
              headers: {
                ...scopeHeaders,
                'Authorization': 'Bearer $_access',
                'X-Request-ID': requestId,
              },
            ),
          );
          onResponse?.call(method, path, response.statusCode ?? 0);
          return returnResponse ? response : response.data;
        } on DioException catch (retryError) {
          if (retryError.response?.statusCode == 401) {
            await clear();
            onExpired?.call();
          }
          throw _failure(retryError);
        }
      }
      if (auth && error.response?.statusCode == 401) {
        await clear();
        onExpired?.call();
      }
      throw _failure(error);
    }
  }

  Future<void> _rotate() async {
    final generation = _generation;
    final result =
        await request(
              'POST',
              '/auth/refresh',
              auth: false,
              data: {'refresh_token': _refresh},
            )
            as Json;
    if (generation != _generation) throw ApiFailure('Session ended.', 401);
    await acceptTokens(result, rotating: true);
  }

  ApiFailure _failure(DioException error) {
    dynamic body = error.response?.data;
    if (body is List<int>) {
      try {
        body = jsonDecode(utf8.decode(body));
      } catch (_) {
        /* Non-JSON binary error response. */
      }
    }
    final detail = body is Map ? body['detail'] : null;
    final objectMessage = detail is Map
        ? detail['message'] ?? detail['msg']
        : null;
    final message = detail is String
        ? detail
        : objectMessage is String
        ? objectMessage
        : detail is List
        ? detail.map((e) => e is Map ? e['msg'] : e).join('. ')
        : error.type == DioExceptionType.connectionTimeout ||
              error.type == DioExceptionType.receiveTimeout
        ? 'Confirmation timed out. Refresh and check whether your change was saved before trying again.'
        : error.response?.statusCode == 403
        ? 'Your account does not have permission for this action.'
        : 'Unable to reach the server. Check your connection and try again.';
    final responseId = body is Map ? body['request_id'] : null;
    final reference = responseId is String
        ? responseId
        : error.response?.headers.value('x-request-id');
    return ApiFailure(
      reference == null ? message : '$message (Reference: $reference)',
      error.response?.statusCode,
      const {
        DioExceptionType.connectionError,
        DioExceptionType.connectionTimeout,
        DioExceptionType.receiveTimeout,
        DioExceptionType.sendTimeout,
      }.contains(error.type),
    );
  }
}
