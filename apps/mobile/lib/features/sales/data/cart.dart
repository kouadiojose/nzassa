import 'package:decimal/decimal.dart';

import '../../products/data/product.dart';

/// Ligne de panier — logique de calcul pure et testable.
class CartLine {
  const CartLine({required this.product, required this.quantity});

  final Product product;
  final int quantity;

  Decimal get lineTotal => product.sellingPrice * Decimal.fromInt(quantity);

  CartLine copyWith({int? quantity}) =>
      CartLine(product: product, quantity: quantity ?? this.quantity);
}

class Cart {
  const Cart({this.lines = const []});

  final List<CartLine> lines;

  Decimal get total =>
      lines.fold(Decimal.zero, (sum, line) => sum + line.lineTotal);

  bool get isEmpty => lines.isEmpty;

  Cart add(Product product) {
    final index = lines.indexWhere((line) => line.product.id == product.id);
    if (index >= 0) {
      final updated = [...lines];
      updated[index] = updated[index].copyWith(quantity: updated[index].quantity + 1);
      return Cart(lines: updated);
    }
    return Cart(lines: [...lines, CartLine(product: product, quantity: 1)]);
  }

  Cart setQuantity(String productId, int quantity) {
    if (quantity <= 0) return remove(productId);
    return Cart(
      lines: [
        for (final line in lines)
          if (line.product.id == productId) line.copyWith(quantity: quantity) else line,
      ],
    );
  }

  Cart remove(String productId) =>
      Cart(lines: lines.where((line) => line.product.id != productId).toList());

  /// Construit le payload de vente attendu par l'API / la file de sync.
  Map<String, dynamic> toSalePayload({
    required String branchId,
    String? customerId,
    required String paymentMethod,
    required Decimal amountPaid,
  }) {
    return {
      'branch_id': branchId,
      'customer_id': customerId,
      'items': [
        for (final line in lines)
          {
            'item_type': 'product',
            'product_id': line.product.id,
            'quantity': line.quantity.toString(),
          },
      ],
      'payments': amountPaid > Decimal.zero
          ? [
              {'method': paymentMethod, 'amount': amountPaid.toString()},
            ]
          : <Map<String, dynamic>>[],
    };
  }
}
