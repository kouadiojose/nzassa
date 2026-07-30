import 'package:decimal/decimal.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nzassa_mobile/features/products/data/product.dart';
import 'package:nzassa_mobile/features/sales/data/cart.dart';

Product _product(String id, String price, {String name = 'Produit'}) => Product(
      id: id,
      name: name,
      sellingPrice: Decimal.parse(price),
    );

void main() {
  group('Cart', () {
    test('additionne les quantités du même produit', () {
      var cart = const Cart();
      final parfum = _product('p1', '25000');
      cart = cart.add(parfum).add(parfum).add(parfum);
      expect(cart.lines.single.quantity, 3);
      expect(cart.total, Decimal.parse('75000'));
    });

    test('calcule le total multi-produits en Decimal exact', () {
      var cart = const Cart();
      cart = cart.add(_product('p1', '25000'));
      cart = cart.add(_product('p2', '1500'));
      cart = cart.setQuantity('p2', 4);
      expect(cart.total, Decimal.parse('31000'));
    });

    test('quantité à zéro retire la ligne', () {
      var cart = const Cart().add(_product('p1', '1000'));
      cart = cart.setQuantity('p1', 0);
      expect(cart.isEmpty, isTrue);
      expect(cart.total, Decimal.zero);
    });

    test('construit un payload de vente conforme à l\'API', () {
      var cart = const Cart().add(_product('p1', '25000'));
      cart = cart.setQuantity('p1', 2);
      final payload = cart.toSalePayload(
        branchId: 'branch-1',
        customerId: 'cust-1',
        paymentMethod: 'wave',
        amountPaid: Decimal.parse('30000'),
      );
      expect(payload['branch_id'], 'branch-1');
      final items = payload['items'] as List<dynamic>;
      expect(items.single, {
        'item_type': 'product',
        'product_id': 'p1',
        'quantity': '2',
      });
      final payments = payload['payments'] as List<dynamic>;
      expect(payments.single, {'method': 'wave', 'amount': '30000'});
    });

    test('aucun paiement si montant nul (vente à crédit)', () {
      final cart = const Cart().add(_product('p1', '5000'));
      final payload = cart.toSalePayload(
        branchId: 'b',
        paymentMethod: 'cash',
        amountPaid: Decimal.zero,
      );
      expect(payload['payments'], isEmpty);
    });
  });

  group('Product', () {
    test('fromJson parse les montants en Decimal', () {
      final product = Product.fromJson(const {
        'id': 'p1',
        'name': 'Parfum',
        'selling_price': '25000.00',
        'sku': 'SKU1',
        'barcode': null,
        'is_active': true,
      });
      expect(product.sellingPrice, Decimal.parse('25000.00'));
      expect(product.isActive, isTrue);
    });

    test('fromCacheRow reconstruit depuis SQLite', () {
      final product = Product.fromCacheRow(const {
        'id': 'p1',
        'name': 'Savon',
        'selling_price': '1500',
        'sku': null,
        'barcode': '123',
        'is_active': 1,
      });
      expect(product.name, 'Savon');
      expect(product.barcode, '123');
    });
  });
}
