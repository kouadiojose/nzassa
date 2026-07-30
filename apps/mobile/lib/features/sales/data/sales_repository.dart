import 'package:decimal/decimal.dart';

import '../../../core/api_client.dart';
import '../../../core/offline/sync_service.dart';
import 'cart.dart';

/// Résultat d'une création de vente : en ligne (numéro serveur) ou
/// enfilée hors ligne (en attente de synchronisation).
class SaleResult {
  const SaleResult.online(this.number) : queuedOffline = false;
  const SaleResult.offline() : number = null, queuedOffline = true;

  final String? number;
  final bool queuedOffline;
}

class SalesRepository {
  SalesRepository(this._api, this._sync);

  final ApiClient _api;
  final SyncService _sync;

  /// Tente la création en ligne ; en cas d'échec réseau, enfile l'opération
  /// dans la file de synchronisation locale (offline-first).
  Future<SaleResult> createSale({
    required Cart cart,
    required String branchId,
    String? customerId,
    required String paymentMethod,
    required Decimal amountPaid,
  }) async {
    final payload = cart.toSalePayload(
      branchId: branchId,
      customerId: customerId,
      paymentMethod: paymentMethod,
      amountPaid: amountPaid,
    );
    try {
      final data = await _api.post<Map<String, dynamic>>('/sales', body: payload);
      return SaleResult.online(data['number'] as String);
    } on ApiException catch (error) {
      if (error.code == 'NETWORK_ERROR') {
        await _sync.enqueue('create_sale', payload);
        return const SaleResult.offline();
      }
      rethrow;
    }
  }

  Future<List<Map<String, dynamic>>> listSales() async {
    final data = await _api.get<List<dynamic>>('/sales', query: {'per_page': 50});
    return data.cast<Map<String, dynamic>>();
  }
}
