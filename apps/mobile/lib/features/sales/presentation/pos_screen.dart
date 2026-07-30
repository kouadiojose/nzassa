import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../data/cart.dart';
import 'sales_providers.dart';

final _numberFormat = NumberFormat.decimalPattern('fr');

const _paymentMethods = {
  'cash': 'Espèces',
  'wave': 'Wave',
  'orange_money': 'Orange Money',
  'mtn_money': 'MTN Money',
  'moov_money': 'Moov Money',
  'card': 'Carte',
};

class PosScreen extends ConsumerStatefulWidget {
  const PosScreen({super.key});

  @override
  ConsumerState<PosScreen> createState() => _PosScreenState();
}

class _PosScreenState extends ConsumerState<PosScreen> {
  String _search = '';
  String _paymentMethod = 'cash';

  Future<void> _checkout(Cart cart) async {
    final branches = await ref.read(branchesProvider.future);
    if (branches.isEmpty || !mounted) return;
    final repository = await ref.read(salesRepositoryProvider.future);
    try {
      final result = await repository.createSale(
        cart: cart,
        branchId: branches.first['id'] as String,
        paymentMethod: _paymentMethod,
        amountPaid: cart.total,
      );
      if (!mounted) return;
      ref.read(cartProvider.notifier).clear();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            result.queuedOffline
                ? 'Hors ligne : vente enregistrée, elle sera synchronisée'
                : 'Vente ${result.number} enregistrée',
          ),
        ),
      );
      context.pop();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.toString())));
    }
  }

  @override
  Widget build(BuildContext context) {
    final cart = ref.watch(cartProvider);
    final productsAsync = ref.watch(productsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Nouvelle vente')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              decoration: const InputDecoration(
                hintText: 'Rechercher ou scanner un produit…',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
              ),
              onChanged: (value) => setState(() => _search = value.toLowerCase()),
            ),
          ),
          Expanded(
            child: productsAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Center(child: Text('Erreur : $error')),
              data: (products) {
                final filtered = products
                    .where((p) =>
                        p.isActive &&
                        (_search.isEmpty ||
                            p.name.toLowerCase().contains(_search) ||
                            (p.barcode ?? '').contains(_search)))
                    .toList();
                return GridView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    childAspectRatio: 2.2,
                    crossAxisSpacing: 8,
                    mainAxisSpacing: 8,
                  ),
                  itemCount: filtered.length,
                  itemBuilder: (context, index) {
                    final product = filtered[index];
                    return OutlinedButton(
                      onPressed: () => ref.read(cartProvider.notifier).add(product),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            product.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 13),
                          ),
                          Text(
                            '${_numberFormat.format(product.sellingPrice.toBigInt())} F',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    );
                  },
                );
              },
            ),
          ),
          _CartSummary(
            cart: cart,
            paymentMethod: _paymentMethod,
            onMethodChanged: (method) => setState(() => _paymentMethod = method),
            onCheckout: () => _checkout(cart),
          ),
        ],
      ),
    );
  }
}

class _CartSummary extends ConsumerWidget {
  const _CartSummary({
    required this.cart,
    required this.paymentMethod,
    required this.onMethodChanged,
    required this.onCheckout,
  });

  final Cart cart;
  final String paymentMethod;
  final ValueChanged<String> onMethodChanged;
  final VoidCallback onCheckout;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return SafeArea(
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final line in cart.lines)
              Row(
                children: [
                  Expanded(
                    child: Text(line.product.name, maxLines: 1, overflow: TextOverflow.ellipsis),
                  ),
                  IconButton(
                    icon: const Icon(Icons.remove_circle_outline),
                    onPressed: () => ref
                        .read(cartProvider.notifier)
                        .setQuantity(line.product.id, line.quantity - 1),
                  ),
                  Text('${line.quantity}'),
                  IconButton(
                    icon: const Icon(Icons.add_circle_outline),
                    onPressed: () => ref
                        .read(cartProvider.notifier)
                        .setQuantity(line.product.id, line.quantity + 1),
                  ),
                  Text('${_numberFormat.format(line.lineTotal.toBigInt())} F'),
                ],
              ),
            const Divider(),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    value: paymentMethod,
                    decoration: const InputDecoration(labelText: 'Paiement'),
                    items: [
                      for (final entry in _paymentMethods.entries)
                        DropdownMenuItem(value: entry.key, child: Text(entry.value)),
                    ],
                    onChanged: (value) {
                      if (value != null) onMethodChanged(value);
                    },
                  ),
                ),
                const SizedBox(width: 16),
                Text(
                  'Total : ${_numberFormat.format(cart.total.toBigInt())} F',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: cart.isEmpty || cart.total == Decimal.zero ? null : onCheckout,
                style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16)),
                child: const Text('ENCAISSER'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
