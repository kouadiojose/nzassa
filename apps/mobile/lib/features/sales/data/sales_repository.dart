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

  /// Nulle quand la file offline n'est pas disponible (Flutter Web) :
  /// les erreurs réseau sont alors remontées à l'utilisateur.
  final SyncService? _sync;

  /// Tente la création en ligne ; en cas d'échec réseau, enfile l'opération
  /// dans la file de synchronisation locale (offline-first, mobile uniquement).
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
      final sync = _sync;
      if (error.code == 'NETWORK_ERROR' && sync != null) {
        await sync.enqueue('create_sale', payload);
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
