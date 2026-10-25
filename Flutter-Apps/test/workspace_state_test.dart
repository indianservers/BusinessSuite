import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:business_suite_mobile/app_controller.dart';
import 'package:business_suite_mobile/core/api_client.dart';
import 'package:business_suite_mobile/core/models.dart';
import 'api_client_test.dart' show MemoryStore, FakeAdapter, response;

void main() {
  late Dio dio;
  late AppController controller;
  setUp(() {
    dio = Dio();
    controller = AppController(
      ApiClient(
        baseUrl: 'https://example.test/api/v1',
        store: MemoryStore(),
        transport: dio,
      ),
    );
  });
  test(
    'late workspace response cannot replace a more recent selection',
    () async {
      final pending = Completer<ResponseBody>();
      dio.httpClientAdapter = FakeAdapter((r) async {
        if (r.path.contains('/1/')) return pending.future;
        return response({'role': 'Guest', 'projects': [], 'tasks': []});
      });
      final first = controller.selectWorkspace(
        const Workspace(1, 'First', 'Member'),
      );
      await Future<void>.delayed(Duration.zero);
      await controller.selectWorkspace(const Workspace(2, 'Second', 'Guest'));
      pending.complete(
        response({'role': 'Owner', 'projects': [], 'tasks': []}),
      );
      await first;
      expect(controller.selected!.id, 2);
      expect(controller.selected!.role, 'Guest');
      expect(controller.overview!.role, 'Guest');
    },
  );
  test('revoked workspace access clears its previous data', () async {
    controller.overview = Overview.fromJson({
      'role': 'Owner',
      'projects': [],
      'tasks': [],
    });
    dio.httpClientAdapter = FakeAdapter(
      (r) async => response({'detail': 'Workspace not found'}, 404),
    );
    await controller.selectWorkspace(const Workspace(1, 'Team', 'Owner'));
    expect(controller.overview, isNull);
    expect(controller.error, 'Workspace not found');
    expect(controller.loading, false);
  });
  test('refresh updates membership role before exposing editing', () async {
    dio.httpClientAdapter = FakeAdapter(
      (r) async => response({'role': 'Guest', 'projects': [], 'tasks': []}),
    );
    await controller.selectWorkspace(const Workspace(1, 'Team', 'Owner'));
    expect(controller.selected!.canEdit, false);
  });
}
