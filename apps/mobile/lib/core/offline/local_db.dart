import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart' as p;

/// Base SQLite locale : cache du catalogue/clients + file d'opérations offline.
class LocalDb {
  LocalDb._(this.db);

  final Database db;

  static Future<LocalDb> open({String? path}) async {
    final dbPath = path ?? p.join(await getDatabasesPath(), 'nzassa.db');
    final db = await openDatabase(dbPath, version: 1, onCreate: _createSchema);
    return LocalDb._(db);
  }

  static Future<void> _createSchema(Database db, int version) async {
    await db.execute('''
      CREATE TABLE cached_products (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        sku TEXT,
        barcode TEXT,
        selling_price TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
      )
    ''');
    await db.execute('''
      CREATE TABLE cached_customers (
        id TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT,
        phone TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
      )
    ''');
    await db.execute('''
      CREATE TABLE pending_operations (
        client_operation_id TEXT PRIMARY KEY,
        operation_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        error_message TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
      )
    ''');
    await db.execute('''
      CREATE TABLE sync_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
    ''');
  }

  Future<void> close() => db.close();
}
