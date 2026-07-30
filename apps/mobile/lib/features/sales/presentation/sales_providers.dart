import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/offline/local_db.dart';
import '../../../core/offline/sync_service.dart';
import '../../auth/presentation/auth_providers.dart';
import '../../products/data/product.dart';
import '../data/cart.dart';
import '../data/sales_repository.dart';

/// Base locale SQLite — indisponible en Flutter Web (sqflite natif uniquement) :
/// l'app y fonctionne alors en mode en-ligne, sans cache ni file offline.
final localDbProvider = FutureProvider<LocalDb?>((ref) async {
  if (kIsWeb) return null;
  return LocalDb.open();
});

final syncServiceProvider = FutureProvider<SyncService?>((ref) async {
  final db = await ref.watch(localDbProvider.future);
  if (db == null) return null;
  return SyncService(db, ref.watch(apiClientProvider));
});

final salesRepositoryProvider = FutureProvider<SalesRepository>((ref) async {
  final sync = await ref.watch(syncServiceProvider.future);
  return SalesRepository(ref.watch(apiClientProvider), sync);
});

/// Panier de la vente en cours.
class CartNotifier extends Notifier<Cart> {
  @override
  Cart build() => const Cart();

  void add(Product product) => state = state.add(product);
  void setQuantity(String productId, int quantity) =>
      state = state.setQuantity(productId, quantity);
  void remove(String productId) => state = state.remove(productId);
  void clear() => state = const Cart();
}

final cartProvider = NotifierProvider<CartNotifier, Cart>(CartNotifier.new);

/// Produits : API en ligne, cache SQLite hors ligne (mobile uniquement).
final productsProvider = FutureProvider<List<Product>>((ref) async {
  final api = ref.watch(apiClientProvider);
  try {
    final data = await api.get<List<dynamic>>(
      '/catalog/products',
      query: {'per_page': 100},
    );
    return data.cast<Map<String, dynamic>>().map(Product.fromJson).toList();
  } catch (_) {
    final db = await ref.watch(localDbProvider.future);
    if (db == null) rethrow;
    final rows = await db.db.query('cached_products', where: 'is_active = 1');
    return rows.map(Product.fromCacheRow).toList();
  }
});

/// Nombre d'opérations en attente de synchronisation (affiché dans l'UI).
final pendingSyncCountProvider = FutureProvider<int>((ref) async {
  final sync = await ref.watch(syncServiceProvider.future);
  if (sync == null) return 0;
  return sync.pendingCount();
});

final branchesProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final data = await api.get<List<dynamic>>('/business/branches');
  return data.cast<Map<String, dynamic>>();
});
