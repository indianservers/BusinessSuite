import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import 'models.dart';

class SuiteReadCache {
  static Future<Database>? _opening;

  static Future<Database> _open() => _opening ??= _create();

  static Future<Database> _create() async {
    try {
      return await openDatabase(
        '${await getDatabasesPath()}/business_suite_read_cache.db',
        version: 1,
        onCreate: (db, _) => db.execute(
          'CREATE TABLE snapshots (scope TEXT PRIMARY KEY, saved_at INTEGER NOT NULL, rows TEXT NOT NULL)',
        ),
      );
    } catch (_) {
      _opening = null;
      rethrow;
    }
  }

  static Future<List<Json>?> read(String scope) async {
    return (await snapshot(scope))?.rows;
  }

  static Future<({List<Json> rows, DateTime savedAt})?> snapshot(
    String scope,
  ) async {
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
    );
  }

  static Future<void> write(String scope, List<Json> rows) async {
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
}
