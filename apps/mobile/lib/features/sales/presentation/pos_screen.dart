import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/theme.dart';
import '../../customers/presentation/customers_screen.dart';
import '../../products/data/product.dart';
import '../data/cart.dart';
import 'barcode_scanner_page.dart';
import 'sales_providers.dart';

const _paymentMethods = {
  'cash': ('Espèces', Icons.payments_outlined),
  'wave': ('Wave', Icons.waves),
  'orange_money': ('Orange Money', Icons.smartphone),
  'mtn_money': ('MTN MoMo', Icons.smartphone),
  'moov_money': ('Moov Money', Icons.smartphone),
  'card': ('Carte', Icons.credit_card),
};

class PosScreen extends ConsumerStatefulWidget {
  const PosScreen({super.key});

  @override
  ConsumerState<PosScreen> createState() => _PosScreenState();
}

class _PosScreenState extends ConsumerState<PosScreen> {
  String _search = '';
  String _paymentMethod = 'cash';
  bool _saving = false;
  String? _customerId;
  String? _customerName;
  final TextEditingController _amountController = TextEditingController();
  bool _amountEdited = false;

  @override
  void dispose() {
    _amountController.dispose();
    super.dispose();
  }

  /// Montant reçu saisi (défaut : total du panier).
  Decimal _amountPaid(Cart cart) {
    if (!_amountEdited || _amountController.text.trim().isEmpty) return cart.total;
    final raw = _amountController.text.trim().replaceAll(' ', '').replaceAll(',', '.');
    return Decimal.tryParse(raw) ?? cart.total;
  }

  Future<void> _pickCustomer() async {
    final customers = await ref.read(customersProvider.future);
    if (!mounted) return;
    final selected = await showModalBottomSheet<Map<String, String?>>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
      ),
      builder: (context) => _CustomerPickerSheet(customers: customers),
    );
    if (selected == null) return;
    setState(() {
      _customerId = selected['id'];
      _customerName = selected['name'];
    });
  }

  Future<void> _scanBarcode() async {
    final code = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (context) => const BarcodeScannerPage()),
    );
    if (code == null || !mounted) return;
    final products = await ref.read(productsProvider.future);
    Product? match;
    for (final product in products) {
      if (product.barcode == code || product.sku == code) {
        match = product;
        break;
      }
    }
    if (!mounted) return;
    if (match != null) {
      ref.read(cartProvider.notifier).add(match);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${match.name} ajouté au panier')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Aucun produit avec le code $code')),
      );
    }
  }

  Future<void> _checkout(Cart cart) async {
    setState(() => _saving = true);
    try {
      final branches = await ref.read(branchesProvider.future);
      if (branches.isEmpty || !mounted) return;
      final amountPaid = _amountPaid(cart);
      if (amountPaid > cart.total) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Le montant reçu dépasse le total')),
        );
        return;
      }
      if (amountPaid < cart.total && _customerId == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content:
                Text('Paiement partiel : sélectionnez un client pour le crédit'),
          ),
        );
        return;
      }
      final repository = await ref.read(salesRepositoryProvider.future);
      final result = await repository.createSale(
        cart: cart,
        branchId: branches.first['id'] as String,
        customerId: _customerId,
        paymentMethod: _paymentMethod,
        amountPaid: amountPaid,
      );
      if (!mounted) return;
      ref.read(cartProvider.notifier).clear();
      _amountController.clear();
      _amountEdited = false;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.check_circle, color: NzColors.gold, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  result.queuedOffline
                      ? 'Hors ligne : vente enregistrée, synchronisation à venir'
                      : 'Vente ${result.number} encaissée ✔',
                  style: const TextStyle(color: Colors.white),
                ),
              ),
            ],
          ),
        ),
      );
      context.pop();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) setState(() => _saving = false);
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
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Rechercher ou scanner un produit…',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.qr_code_scanner, color: NzColors.primaryDark),
                  tooltip: 'Scanner un code-barres',
                  onPressed: _scanBarcode,
                ),
              ),
              onChanged: (value) => setState(() => _search = value.toLowerCase()),
            ),
          ),
          Expanded(
            child: productsAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text('Erreur : $error', textAlign: TextAlign.center),
                ),
              ),
              data: (products) {
                final filtered = products
                    .where((p) =>
                        p.isActive &&
                        (_search.isEmpty ||
                            p.name.toLowerCase().contains(_search) ||
                            (p.barcode ?? '').contains(_search)))
                    .toList();
                if (filtered.isEmpty) {
                  return const Center(
                    child: Text('Aucun produit trouvé',
                        style: TextStyle(color: NzColors.muted)),
                  );
                }
                return GridView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                  gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                    maxCrossAxisExtent: 220,
                    childAspectRatio: 1.9,
                    crossAxisSpacing: 10,
                    mainAxisSpacing: 10,
                  ),
                  itemCount: filtered.length,
                  itemBuilder: (context, index) {
                    final product = filtered[index];
                    final inCart = cart.lines
                        .where((l) => l.product.id == product.id)
                        .fold<int>(0, (sum, l) => sum + l.quantity);
                    return _ProductCard(
                      name: product.name,
                      price: formatMoney(product.sellingPrice),
                      inCartQty: inCart,
                      onTap: () => ref.read(cartProvider.notifier).add(product),
                    );
                  },
                );
              },
            ),
          ),
          _CartPanel(
            cart: cart,
            paymentMethod: _paymentMethod,
            saving: _saving,
            customerName: _customerName,
            amountController: _amountController,
            onAmountEdited: () => _amountEdited = true,
            onPickCustomer: _pickCustomer,
            onClearCustomer: () =>
                setState(() => _customerId = _customerName = null),
            onMethodChanged: (method) => setState(() => _paymentMethod = method),
            onCheckout: () => _checkout(cart),
          ),
        ],
      ),
    );
  }
}

class _ProductCard extends StatelessWidget {
  const _ProductCard({
    required this.name,
    required this.price,
    required this.inCartQty,
    required this.onTap,
  });

  final String name;
  final String price;
  final int inCartQty;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final selected = inCartQty > 0;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: selected ? NzColors.primary.withOpacity(0.08) : Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: selected ? NzColors.primary : NzColors.ink.withOpacity(0.07),
            width: selected ? 1.6 : 1,
          ),
        ),
        child: Row(
          children: [
            NzAvatar(label: name, size: 40),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 13, fontWeight: FontWeight.w600, color: NzColors.ink),
                  ),
                  Text(
                    price,
                    style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        color: NzColors.primaryDark),
                  ),
                ],
              ),
            ),
            if (selected)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: NzColors.primary,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '×$inCartQty',
                  style: const TextStyle(
                      color: Colors.white, fontSize: 12, fontWeight: FontWeight.w800),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _CartPanel extends ConsumerWidget {
  const _CartPanel({
    required this.cart,
    required this.paymentMethod,
    required this.saving,
    required this.customerName,
    required this.amountController,
    required this.onAmountEdited,
    required this.onPickCustomer,
    required this.onClearCustomer,
    required this.onMethodChanged,
    required this.onCheckout,
  });

  final Cart cart;
  final String paymentMethod;
  final bool saving;
  final String? customerName;
  final TextEditingController amountController;
  final VoidCallback onAmountEdited;
  final VoidCallback onPickCustomer;
  final VoidCallback onClearCustomer;
  final ValueChanged<String> onMethodChanged;
  final VoidCallback onCheckout;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return SafeArea(
      top: false,
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(26)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.08),
              blurRadius: 20,
              offset: const Offset(0, -6),
            ),
          ],
        ),
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: NzColors.ink.withOpacity(0.12),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 10),
            if (cart.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 10),
                child: Text(
                  'Touchez un produit pour l’ajouter au panier',
                  style: TextStyle(color: NzColors.muted, fontSize: 13),
                ),
              )
            else ...[
              // Lignes du panier — hauteur bornée, défilement interne
              ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 150),
                child: ListView(
                  shrinkWrap: true,
                  children: [
                    for (final line in cart.lines)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                line.product.name,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                    fontSize: 13.5, fontWeight: FontWeight.w600),
                              ),
                            ),
                            _QtyButton(
                              icon: Icons.remove,
                              onTap: () => ref
                                  .read(cartProvider.notifier)
                                  .setQuantity(line.product.id, line.quantity - 1),
                            ),
                            SizedBox(
                              width: 30,
                              child: Text(
                                '${line.quantity}',
                                textAlign: TextAlign.center,
                                style: const TextStyle(fontWeight: FontWeight.w800),
                              ),
                            ),
                            _QtyButton(
                              icon: Icons.add,
                              onTap: () => ref
                                  .read(cartProvider.notifier)
                                  .setQuantity(line.product.id, line.quantity + 1),
                            ),
                            SizedBox(
                              width: 86,
                              child: Text(
                                formatMoney(line.lineTotal),
                                textAlign: TextAlign.end,
                                style: const TextStyle(
                                    fontWeight: FontWeight.w700, fontSize: 13.5),
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              // Client + montant reçu (paiement partiel = vente à crédit)
              Row(
                children: [
                  Expanded(
                    child: InkWell(
                      onTap: onPickCustomer,
                      borderRadius: BorderRadius.circular(12),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 9),
                        decoration: BoxDecoration(
                          color: NzColors.sand,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.person_outline,
                                size: 18, color: NzColors.muted),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                customerName ?? 'Client (facultatif)',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: customerName != null
                                      ? NzColors.ink
                                      : NzColors.muted,
                                ),
                              ),
                            ),
                            if (customerName != null)
                              GestureDetector(
                                onTap: onClearCustomer,
                                child: const Icon(Icons.close,
                                    size: 16, color: NzColors.muted),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  SizedBox(
                    width: 130,
                    child: TextField(
                      controller: amountController,
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      textAlign: TextAlign.end,
                      onChanged: (_) => onAmountEdited(),
                      decoration: InputDecoration(
                        labelText: 'Reçu',
                        hintText: formatAmount(cart.total),
                        isDense: true,
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 10),
                      ),
                      style: const TextStyle(
                          fontSize: 14, fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              // Moyens de paiement
              SizedBox(
                height: 40,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
                    for (final entry in _paymentMethods.entries)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          avatar: Icon(
                            entry.value.$2,
                            size: 16,
                            color: paymentMethod == entry.key
                                ? Colors.white
                                : NzColors.muted,
                          ),
                          label: Text(entry.value.$1),
                          selected: paymentMethod == entry.key,
                          selectedColor: NzColors.ink,
                          labelStyle: TextStyle(
                            fontSize: 12.5,
                            fontWeight: FontWeight.w700,
                            color: paymentMethod == entry.key
                                ? Colors.white
                                : NzColors.ink,
                          ),
                          onSelected: (_) => onMethodChanged(entry.key),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 10),
              // Bouton encaisser avec total intégré
              InkWell(
                onTap: saving || cart.total == Decimal.zero ? null : onCheckout,
                borderRadius: BorderRadius.circular(18),
                child: Ink(
                  decoration: BoxDecoration(
                    gradient: NzColors.ctaGradient,
                    borderRadius: BorderRadius.circular(18),
                  ),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                  child: Row(
                    children: [
                      Text(
                        saving ? 'Enregistrement…' : 'ENCAISSER',
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w900,
                          fontSize: 15,
                          letterSpacing: 0.6,
                        ),
                      ),
                      const Spacer(),
                      Text(
                        formatMoney(cart.total),
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w900,
                          fontSize: 18,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _QtyButton extends StatelessWidget {
  const _QtyButton({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        width: 28,
        height: 28,
        decoration: BoxDecoration(
          color: NzColors.sand,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(icon, size: 16, color: NzColors.ink),
      ),
    );
  }
}


class _CustomerPickerSheet extends StatefulWidget {
  const _CustomerPickerSheet({required this.customers});

  final List<Map<String, dynamic>> customers;

  @override
  State<_CustomerPickerSheet> createState() => _CustomerPickerSheetState();
}

class _CustomerPickerSheetState extends State<_CustomerPickerSheet> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final filtered = widget.customers.where((c) {
      final name = '${c['first_name'] ?? ''} ${c['last_name'] ?? ''}'.toLowerCase();
      final phone = (c['phone'] as String?) ?? '';
      return _query.isEmpty || name.contains(_query) || phone.contains(_query);
    }).toList();
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.65,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 8),
              child: TextField(
                autofocus: true,
                decoration: const InputDecoration(
                  hintText: 'Rechercher un client (nom, téléphone)…',
                  prefixIcon: Icon(Icons.search),
                ),
                onChanged: (value) => setState(() => _query = value.toLowerCase()),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.person_off_outlined, color: NzColors.muted),
              title: const Text('Aucun client'),
              onTap: () => Navigator.of(context).pop({'id': null, 'name': null}),
            ),
            const Divider(height: 1),
            Expanded(
              child: ListView.builder(
                itemCount: filtered.length,
                itemBuilder: (context, index) {
                  final customer = filtered[index];
                  final name =
                      '${customer['first_name'] ?? ''} ${customer['last_name'] ?? ''}'
                          .trim();
                  return ListTile(
                    leading: NzAvatar(label: name, size: 38),
                    title: Text(name,
                        style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text((customer['phone'] as String?) ?? '',
                        style: const TextStyle(fontSize: 12)),
                    onTap: () => Navigator.of(context)
                        .pop({'id': customer['id'] as String, 'name': name}),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
