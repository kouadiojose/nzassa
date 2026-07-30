import 'package:decimal/decimal.dart';

/// Formatage monétaire par manipulation de chaîne UNIQUEMENT.
///
/// Ni `double` (précision), ni `BigInt` (la conversion plante en Flutter Web :
/// « type 'int' is not a subtype of type '_BigIntImpl' »). Les montants FCFA
/// s'affichent avec un séparateur de milliers insécable.
String formatAmount(Decimal value) {
  var raw = value.toString();
  final negative = raw.startsWith('-');
  if (negative) raw = raw.substring(1);

  final dot = raw.indexOf('.');
  final intPart = dot >= 0 ? raw.substring(0, dot) : raw;
  var fracPart = dot >= 0 ? raw.substring(dot + 1) : '';
  fracPart = fracPart.replaceFirst(RegExp(r'0+$'), '');

  final buffer = StringBuffer();
  for (var i = 0; i < intPart.length; i++) {
    if (i > 0 && (intPart.length - i) % 3 == 0) buffer.write(' ');
    buffer.write(intPart[i]);
  }
  var result = buffer.toString();
  if (fracPart.isNotEmpty) result = '$result,$fracPart';
  return negative ? '-$result' : result;
}

/// « 75 000 F »
String formatMoney(Decimal value) => '${formatAmount(value)} F';

/// Formate un montant reçu de l'API sous forme de chaîne (ex. "75000.00").
String formatMoneyStr(String raw) => formatMoney(Decimal.parse(raw));
