import 'package:decimal/decimal.dart';

/// Produit — montants en [Decimal], jamais en double.
class Product {
  const Product({
    required this.id,
    required this.name,
    required this.sellingPrice,
    this.sku,
    this.barcode,
    this.isActive = true,
  });

  factory Product.fromJson(Map<String, dynamic> json) => Product(
        id: json['id'] as String,
        name: json['name'] as String,
        sellingPrice: Decimal.parse(json['selling_price'] as String),
        sku: json['sku'] as String?,
        barcode: json['barcode'] as String?,
        isActive: json['is_active'] as bool? ?? true,
      );

  factory Product.fromCacheRow(Map<String, Object?> row) => Product(
        id: row['id']! as String,
        name: row['name']! as String,
        sellingPrice: Decimal.parse(row['selling_price']! as String),
        sku: row['sku'] as String?,
        barcode: row['barcode'] as String?,
        isActive: (row['is_active'] as int? ?? 1) == 1,
      );

  final String id;
  final String name;
  final Decimal sellingPrice;
  final String? sku;
  final String? barcode;
  final bool isActive;
}
