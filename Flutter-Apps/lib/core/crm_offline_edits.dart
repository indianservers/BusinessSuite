import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import 'api_client.dart';
import 'crm_detail_snapshot.dart';
import 'models.dart';
import 'suite_read_cache.dart';

class CrmOfflineEdits {
  CrmOfflineEdits(String scope, {this.onTaskSynced})
    : _scope = scope,
      _key = 'crm_edits_${Uri.encodeComponent(scope)}',
      _company = '${(jsonDecode(scope) as List)[2]}';
  final String _key;
  final String _scope;
  final String _company;
  final Future<void> Function(int taskId, String branch, Json record)?
  onTaskSynced;

  factory CrmOfflineEdits.withTaskSnapshots(String scope) => CrmOfflineEdits(
    scope,
    onTaskSynced: (id, branch, record) async {
      final status = record['status'];
      final updatedAt = record['updated_at'];
      if (status is! String || updatedAt is! String) return;
      const path = '/project-management/tasks';
      final detailScope = '$scope:$path/$id:$branch';
      await flushCrmDetailWrite(detailScope);
      await SuiteReadCache.updateTaskStatus(
        listScope: '$scope:$path',
        detailScope: detailScope,
        id: id,
        status: status,
        updatedAt: updatedAt,
      );
    },
  );
  static const _storage = FlutterSecureStorage();
  static final Map<String, Future<void>> _running = {};
  static final _customerUpdates =
      StreamController<(String, String)>.broadcast();

  Stream<void> customerUpdates(int id) => _customerUpdates.stream
      .where((event) => event == (_key, 'customer:$id'))
      .map<void>((_) {});
  static final _taskUpdates =
      StreamController<
        ({String key, int id, ({bool synced, Json? record}) result})
      >.broadcast();

  Stream<({bool synced, Json? record})> taskUpdates(int id) => _taskUpdates
      .stream
      .where((update) => update.key == _key && update.id == id)
      .map((update) => update.result);

  Future<Json> _read() async {
    final raw = await _storage.read(key: _key);
    return raw == null ? <String, dynamic>{} : jsonDecode(raw) as Json;
  }

  Future<Json?> pending(int id) async => (await _read())['$id'] as Json?;
  Future<Json?> pendingCustomer(int id) async =>
      (await _read())['customer:$id'] as Json?;

  Future<void> enqueueCustomer(int id, Json body, String branch) =>
      _serialized(() async {
        final rows = await _read();
        if (rows.containsKey('customer:$id')) {
          throw StateError('This customer already has a saved edit.');
        }
        rows['customer:$id'] = {'body': body, 'branch': branch};
        await _storage.write(key: _key, value: jsonEncode(rows));
      });

  Future<void> discardCustomer(int id) => _serialized(() async {
    final rows = await _read();
    rows.remove('customer:$id');
    await _storage.write(key: _key, value: jsonEncode(rows));
  });
  Future<Json?> pendingTask(int id) async =>
      (await _read())['task:$id'] as Json?;

  Future<void> enqueueTaskStatus(
    int id,
    String status,
    String updatedAt,
    String branch,
  ) => _serialized(() async {
    final rows = await _read();
    if (rows.containsKey('task:$id')) {
      throw StateError('This task already has a saved status change.');
    }
    rows['task:$id'] = {
      'operation': const Uuid().v4(),
      'branch': branch,
      'body': {'status': status, 'expected_updated_at': updatedAt},
    };
    await _storage.write(key: _key, value: jsonEncode(rows));
  });
  Map<String, String> creationHeaders(String operation) => {
    'X-Suite-Organization': _company,
    'X-Offline-Operation': operation,
  };
  Future<List<Json>> creations() async => [
    for (final row in (await _read()).entries)
      if (row.key.startsWith('create:')) {...row.value as Json, 'key': row.key},
  ];

  Future<void> enqueueCreation(
    String operation,
    Json payload, {
    String? replaceRejected,
  }) => _serialized(() async {
    final rows = await _read();
    if (replaceRejected != null) {
      final old = rows[replaceRejected] as Json?;
      if (!replaceRejected.startsWith('create:') || old?['status'] != 422) {
        throw StateError('This saved lead draft has changed. Reopen it first.');
      }
      rows.remove(replaceRejected);
    }
    rows['create:$operation'] = payload;
    await _storage.write(key: _key, value: jsonEncode(rows));
  });
  Future<bool> get hasPending async =>
      (await _read()).values.any((row) => (row as Json)['error'] == null);

  Future<void> _serialized(Future<void> Function() action) async {
    final previous = _running[_key] ?? Future<void>.value();
    final next = previous.then(
      (_) => action(),
      onError: (Object _) => action(),
    );
    _running[_key] = next;
    try {
      await next;
    } finally {
      if (identical(_running[_key], next)) _running.remove(_key);
    }
  }

  Future<void> enqueue(
    int id,
    int version,
    Json values, {
    int? rejectedVersion,
  }) => _serialized(() async {
    final rows = await _read();
    final existing = rows['$id'] as Json?;
    if (rejectedVersion != null) {
      if (existing?['error'] == null ||
          existing?['version'] != rejectedVersion) {
        throw StateError('This saved edit has changed. Refresh the lead.');
      }
    } else if (existing != null) {
      throw StateError(
        'This lead already has a saved edit awaiting review or sync.',
      );
    }
    rows['$id'] = {'version': version, 'values': values};
    await _storage.write(key: _key, value: jsonEncode(rows));
  });

  Future<void> sync(
    ApiClient api, {
    int? leadId,
    int? onlyTask,
    int? onlyCustomer,
    void Function()? onCreated,
  }) {
    final session = api.sessionRevision;
    return _serialized(() async {
      final rows = await _read();
      final ids = onlyTask != null
          ? ['task:$onlyTask']
          : onlyCustomer != null
          ? ['customer:$onlyCustomer']
          : leadId == null
          ? rows.keys.toList()
          : ['$leadId'];
      for (final id in ids) {
        if (!api.hasSession || session != api.sessionRevision) return;
        final edit = rows[id] as Json?;
        if (edit == null || edit['error'] != null) continue;
        final creating = id.startsWith('create:');
        final customer = id.startsWith('customer:');
        final customerPath = '/master-data/companies/${id.split(':').last}';
        final branch = edit['branch'] as String? ?? '';
        final taskId = id.startsWith('task:')
            ? int.tryParse(id.substring(5))
            : null;
        Json? confirmedTask;
        Json? confirmedCustomer;
        try {
          final response = await api.request(
            creating ? 'POST' : 'PATCH',
            taskId != null
                ? '/project-management/tasks/$taskId'
                : creating
                ? '/crm/lead-management/leads'
                : customer
                ? customerPath
                : '/crm/lead-management/leads/$id',
            query: customer ? const {'source': 'crm'} : null,
            scopeHeaders: taskId != null
                ? {
                    ...creationHeaders(edit['operation'] as String),
                    if (edit['branch'] case final String branch
                        when branch.isNotEmpty)
                      'X-Suite-Branch': branch,
                  }
                : creating
                ? creationHeaders(id.substring('create:'.length))
                : {
                    'X-Suite-Organization': _company,
                    if (customer && branch.isNotEmpty) 'X-Suite-Branch': branch,
                  },
            data: taskId == null && !customer ? edit : edit['body'],
          );
          if (taskId != null && response is Json) confirmedTask = response;
          if (customer && response is Json) confirmedCustomer = response;
          rows.remove(id);
        } on ApiFailure catch (failure) {
          if (failure.connectionFailure ||
              failure.status == 401 ||
              failure.status == 429 ||
              (failure.status ?? 500) >= 500) {
            return;
          }
          edit['error'] = failure.toString();
          if (creating) edit['status'] = failure.status;
        }
        if (taskId != null && session == api.sessionRevision) {
          if (confirmedTask != null) {
            try {
              await onTaskSynced?.call(
                taskId,
                edit['branch'] as String,
                confirmedTask,
              );
            } catch (_) {
              // A cache failure cannot roll back a confirmed task change.
            }
          }
        }
        await _storage.write(key: _key, value: jsonEncode(rows));
        if (customer &&
            !rows.containsKey(id) &&
            session == api.sessionRevision) {
          try {
            final key = '$_scope:$customerPath:$branch';
            await flushCrmDetailWrite(key);
            final saved = await SuiteReadCache.read(key);
            final changes = edit['body'] as Json;
            if (saved != null &&
                saved.isNotEmpty &&
                saved.first['version'] == changes['version']) {
              final previous = saved.first;
              await SuiteReadCache.write(key, [
                {
                  for (final entry in previous.entries)
                    entry.key: confirmedCustomer?.containsKey(entry.key) == true
                        ? confirmedCustomer![entry.key]
                        : changes.containsKey(entry.key)
                        ? changes[entry.key]
                        : entry.value,
                  'canEdit':
                      previous['canEdit'] == true &&
                      confirmedCustomer?['version'] is String,
                },
              ]);
            }
            await SuiteReadCache.invalidate(
              '$_scope:/master-data/company-directory/query',
            );
          } catch (_) {
            // The server has already accepted the saved edit.
          }
        }
        if (customer && session == api.sessionRevision) {
          _customerUpdates.add((_key, id));
        }
        if (taskId != null && session == api.sessionRevision) {
          _taskUpdates.add((
            key: _key,
            id: taskId,
            result: (synced: !rows.containsKey(id), record: confirmedTask),
          ));
        }
        if (creating &&
            !rows.containsKey(id) &&
            session == api.sessionRevision) {
          onCreated?.call();
        }
      }
    });
  }

  Future<void> discard(int id) => _serialized(() async {
    final rows = await _read();
    rows.remove('$id');
    await _storage.write(key: _key, value: jsonEncode(rows));
  });

  Future<void> discardTask(int id) => _serialized(() async {
    final rows = await _read();
    if ((rows['task:$id'] as Json?)?['error'] == null) return;
    rows.remove('task:$id');
    await _storage.write(key: _key, value: jsonEncode(rows));
  });

  Future<void> discardCreation(String key) => _serialized(() async {
    if (!key.startsWith('create:')) return;
    final rows = await _read();
    rows.remove(key);
    await _storage.write(key: _key, value: jsonEncode(rows));
  });
}
