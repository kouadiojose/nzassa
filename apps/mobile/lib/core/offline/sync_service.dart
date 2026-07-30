import 'dart:convert';

import 'package:sqflite/sqflite.dart';
import 'package:uuid/uuid.dart';

import '../api_client.dart';
import 'local_db.dart';

/// File de synchronisation offline-first.
///
/// - Chaque opération créée hors ligne reçoit un UUID (`client_operation_id`)
///   qui garantit l'idempotence côté backend ;
/// - `pushPending` rejoue les opérations en attente (avec retries) ;
/// - `pullChanges` met à jour le cache local de façon incrémentale.
class SyncService {
  SyncService(this._db, this._api, {Uuid? uuid}) : _uuid = uuid ?? const Uuid();

  final LocalDb _db;
  final ApiClient _api;
  final Uuid _uuid;

  static const maxRetries = 5;

  /// Enfile une opération créée hors ligne. Retourne son identifiant client.
  Future<String> enqueue(String operationType, Map<String, dynamic> payload) async {
    final id = _uuid.v4();
    await _db.db.insert('pending_operations', {
      'client_operation_id': id,
      'operation_type': operationType,
      'payload_json': jsonEncode(payload),
      'status': 'pending',
      'created_at': DateTime.now().toUtc().toIso8601String(),
    });
    return id;
  }

  Future<List<Map<String, Object?>>> pendingOperations() {
    return _db.db.query(
      'pending_operations',
      where: "status = 'pending' AND retry_count < ?",
      whereArgs: [maxRetries],
      orderBy: 'created_at ASC',
    );
  }

  Future<int> pendingCount() async {
    final rows = await _db.db.rawQuery(
      "SELECT COUNT(*) AS c FROM pending_operations WHERE status = 'pending'",
    );
    return (rows.first['c'] as int?) ?? 0;
  }

  /// Rejoue les opérations en attente vers `POST /sync/push`.
  /// Retourne le nombre d'opérations appliquées.
  Future<int> pushPending() async {
    final pending = await pendingOperations();
    if (pending.isEmpty) return 0;

    final operations = pending
        .map((row) => {
              'client_operation_id': row['client_operation_id'],
              'operation_type': row['operation_type'],
              'payload': jsonDecode(row['payload_json']! as String),
            })
        .toList();

    late final Map<String, dynamic> result;
    try {
      result = await _api.post<Map<String, dynamic>>(
        '/sync/push',
        body: {'operations': operations},
      );
    } on ApiException {
      // Hors ligne ou erreur serveur : on incrémente les retries, on réessaiera.
      final batch = _db.db.batch();
      for (final row in pending) {
        batch.rawUpdate(
          'UPDATE pending_operations SET retry_count = retry_count + 1 '
          'WHERE client_operation_id = ?',
          [row['client_operation_id']],
        );
      }
      await batch.commit(noResult: true);
      return 0;
    }

    var applied = 0;
    final results = (result['results'] as List<dynamic>).cast<Map<String, dynamic>>();
    final batch = _db.db.batch();
    for (final entry in results) {
      final id = entry['client_operation_id'] as String;
      final status = entry['status'] as String;
      if (status == 'applied') {
        applied += 1;
        batch.update(
          'pending_operations',
          {'status': 'applied'},
          where: 'client_operation_id = ?',
          whereArgs: [id],
        );
      } else {
        batch.update(
          'pending_operations',
          {'status': status, 'error_message': entry['error'] as String?},
          where: 'client_operation_id = ?',
          whereArgs: [id],
        );
      }
    }
    await batch.commit(noResult: true);
    return applied;
  }

  /// Synchronisation incrémentale du cache local (produits, clients).
  Future<void> pullChanges() async {
    final stateRows = await _db.db.query(
      'sync_state',
      where: 'key = ?',
      whereArgs: ['last_pull_at'],
    );
    final since = stateRows.isEmpty ? null : stateRows.first['value'] as String;

    final data = await _api.get<Map<String, dynamic>>(
      '/sync/pull',
      query: since != null ? {'since': since} : null,
    );

    final batch = _db.db.batch();
    for (final product in (data['products'] as List<dynamic>).cast<Map<String, dynamic>>()) {
      batch.insert(
        'cached_products',
        {
          'id': product['id'],
          'name': product['name'],
          'sku': product['sku'],
          'barcode': product['barcode'],
          'selling_price': product['selling_price'],
          'is_active': (product['is_active'] as bool) ? 1 : 0,
          'updated_at': product['updated_at'],
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    for (final customer in (data['customers'] as List<dynamic>).cast<Map<String, dynamic>>()) {
      batch.insert(
        'cached_customers',
        {
          'id': customer['id'],
          'first_name': customer['first_name'],
          'last_name': customer['last_name'],
          'phone': customer['phone'],
          'is_active': (customer['is_active'] as bool) ? 1 : 0,
          'updated_at': customer['updated_at'],
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    batch.insert(
      'sync_state',
      {'key': 'last_pull_at', 'value': data['server_time']},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
    await batch.commit(noResult: true);
  }
}
