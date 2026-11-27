import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import 'models.dart';

class SuiteReadCache {
  static const reuseWindow = Duration(seconds: 15);
  static Future<Database>? _opening;

  static Future<Database> _open() => _opening ??= _create();

  static Future<Database> _create() async {
    try {
      return await openDatabase(
        '${await getDatabasesPath()}/business_suite_read_cache.db',
        version: 3,
        onCreate: (db, _) async {
          await db.execute(
            'CREATE TABLE snapshots (scope TEXT PRIMARY KEY, saved_at INTEGER NOT NULL, rows TEXT NOT NULL, invalidated INTEGER NOT NULL DEFAULT 0)',
          );
          await db.execute(_createExpiryIndex);
        },
        onUpgrade: (db, oldVersion, _) async {
          if (oldVersion < 2) {
            await db.execute(
              'ALTER TABLE snapshots ADD COLUMN invalidated INTEGER NOT NULL DEFAULT 0',
            );
          }
          if (oldVersion < 3) await db.execute(_createExpiryIndex);
        },
      );
    } catch (_) {
      _opening = null;
      rethrow;
    }
  }

  static const _createExpiryIndex =
      'CREATE INDEX snapshots_saved_at_idx ON snapshots(saved_at)';

  static Future<List<Json>?> read(String scope) async {
    return (await snapshot(scope))?.rows;
  }

  static Future<({List<Json> rows, DateTime savedAt, bool invalidated})?>
  snapshot(String scope) async {
    final entries = await (await _open()).query(
      'snapshots',
      where: 'scope = ? AND saved_at >= ?',
      whereArgs: [
        scope,
        DateTime.now().subtract(const Duration(days: 1)).millisecondsSinceEpoch,
      ],
      limit: 1,
    );
    if (entries.isEmpty) return null;
    final entry = entries.single;
    return (
      rows: (jsonDecode(entry['rows'] as String) as List).cast<Json>(),
      savedAt: DateTime.fromMillisecondsSinceEpoch(entry['saved_at'] as int),
      invalidated: entry['invalidated'] == 1,
    );
  }

  static Future<void> write(
    String scope,
    List<Json> rows, {
    int? retainRecent,
  }) async {
    final db = await _open();
    final now = DateTime.now();
    await db.transaction((tx) async {
      await tx.delete(
        'snapshots',
        where: 'saved_at < ?',
        whereArgs: [
          now.subtract(const Duration(days: 1)).millisecondsSinceEpoch,
        ],
      );
      if (retainRecent != null) {
        final older = await tx.query(
          'snapshots',
          columns: ['rows'],
          where: 'scope = ?',
          whereArgs: [scope],
        );
        final previous = older.isEmpty
            ? const <Json>[]
            : (jsonDecode(older.single['rows'] as String) as List).cast<Json>();
        final unique = <int, Json>{};
        for (final row in [...rows, ...previous]) {
          if (row['id'] case final int id) unique.putIfAbsent(id, () => row);
        }
        rows = unique.values.take(retainRecent).toList();
      }
      await tx.insert('snapshots', {
        'scope': scope,
        'saved_at': now.millisecondsSinceEpoch,
        'rows': jsonEncode(rows),
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    });
  }

  static Future<void> clear(String scope) async => (await _open()).delete(
    'snapshots',
    where: 'scope = ?',
    whereArgs: [scope],
  );

  static Future<void> invalidate(String scope) async => (await _open()).update(
    'snapshots',
    {'invalidated': 1},
    where: 'scope = ?',
    whereArgs: [scope],
  );

  static String _pagePrefix(String scope) => '$scope:page:';
  static const _pageScopeFilter = 'scope = ? OR (scope >= ? AND scope < ?)';

  // A bounded range lets SQLite use the snapshot primary-key index.
  static List<String> _pageScopeArgs(String scope) => [
    scope,
    _pagePrefix(scope),
    '$scope:page;',
  ];

  static Future<List<Json>?> readPages(String scope) async {
    final entries = await (await _open()).query(
      'snapshots',
      columns: ['rows'],
      where: '($_pageScopeFilter) AND saved_at >= ?',
      whereArgs: [
        ..._pageScopeArgs(scope),
        DateTime.now().subtract(const Duration(days: 1)).millisecondsSinceEpoch,
      ],
      orderBy: 'saved_at DESC',
    );
    if (entries.isEmpty) return null;
    final unique = <int, Json>{};
    for (final entry in entries) {
      for (final row
          in (jsonDecode(entry['rows'] as String) as List).cast<Json>()) {
        if (row['id'] case final int id) {
          final existing = unique[id];
          final version = row['version'];
          final existingVersion = existing?['version'];
          if (existing == null ||
              (version is int &&
                  existingVersion is int &&
                  version > existingVersion)) {
            unique[id] = row;
          }
        }
      }
    }
    final ids = unique.keys.toList()..sort((a, b) => b.compareTo(a));
    return [for (final id in ids) unique[id]!];
  }

  static Future<void> writePage(String scope, int page, List<Json> rows) =>
      write(page == 1 ? scope : '${_pagePrefix(scope)}$page', rows);

  static Future<void> clearPages(String scope) async {
    await (await _open()).delete(
      'snapshots',
      where: _pageScopeFilter,
      whereArgs: _pageScopeArgs(scope),
    );
  }
}
