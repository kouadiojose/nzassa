import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nzassa_mobile/features/auth/presentation/login_screen.dart';

void main() {
  testWidgets('LoginScreen affiche le formulaire et valide les champs', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: LoginScreen())),
    );

    expect(find.text("N'Zassa Business"), findsOneWidget);
    expect(find.byType(TextFormField), findsNWidgets(2));

    // Soumission vide -> messages de validation, pas d'appel réseau
    await tester.tap(find.text('Se connecter'));
    await tester.pump();
    expect(find.text('Email invalide'), findsOneWidget);
    expect(find.text('Au moins 8 caractères'), findsOneWidget);
  });
}
