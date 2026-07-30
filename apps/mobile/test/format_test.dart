import 'package:decimal/decimal.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nzassa_mobile/core/format.dart';

void main() {
  group('formatAmount', () {
    test('groupe les milliers avec des espaces insécables', () {
      expect(formatAmount(Decimal.parse('75000')), '75 000');
      expect(formatAmount(Decimal.parse('1234567')), '1 234 567');
      expect(formatAmount(Decimal.parse('999')), '999');
      expect(formatAmount(Decimal.parse('0')), '0');
    });

    test('normalise les décimales de l’API (75000.00 -> 75 000)', () {
      expect(formatAmount(Decimal.parse('75000.00')), '75 000');
      expect(formatAmount(Decimal.parse('1500.50')), '1 500,5');
    });

    test('gère les montants négatifs', () {
      expect(formatAmount(Decimal.parse('-25000')), '-25 000');
    });

    test('formatMoney ajoute le symbole', () {
      expect(formatMoney(Decimal.parse('25000')), '25 000 F');
      expect(formatMoneyStr('50000.00'), '50 000 F');
    });

    test('ne dépend ni de double ni de BigInt (régression Flutter Web)', () {
      // Un montant au-delà de la précision d'un double JS reste exact.
      expect(
        formatAmount(Decimal.parse('9007199254740993')),
        '9 007 199 254 740 993',
      );
    });
  });
}
