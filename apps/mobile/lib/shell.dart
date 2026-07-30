import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// Navigation principale : Accueil, Ventes, Stock/Produits, Clients, Plus.
/// Le bouton « nouvelle vente » reste accessible en permanence.
class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.child});

  final Widget child;

  static const _tabs = ['/home', '/sales', '/products', '/customers', '/more'];

  int _currentIndex(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    final index = _tabs.indexWhere(location.startsWith);
    return index < 0 ? 0 : index;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push('/pos'),
        tooltip: 'Nouvelle vente',
        child: const Icon(Icons.point_of_sale),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex(context),
        onDestinationSelected: (index) => context.go(_tabs[index]),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Accueil'),
          NavigationDestination(icon: Icon(Icons.receipt_long_outlined), label: 'Ventes'),
          NavigationDestination(icon: Icon(Icons.inventory_2_outlined), label: 'Stock'),
          NavigationDestination(icon: Icon(Icons.people_outline), label: 'Clients'),
          NavigationDestination(icon: Icon(Icons.menu), label: 'Plus'),
        ],
      ),
    );
  }
}
