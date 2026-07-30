import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'features/auth/presentation/auth_providers.dart';
import 'features/auth/presentation/login_screen.dart';
import 'features/customers/presentation/customers_screen.dart';
import 'features/debts/presentation/debts_screen.dart';
import 'features/home/presentation/home_screen.dart';
import 'features/more/presentation/more_screen.dart';
import 'features/products/presentation/products_screen.dart';
import 'features/sales/presentation/pos_screen.dart';
import 'features/sales/presentation/sales_list_screen.dart';
import 'core/theme.dart';
import 'shell.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final auth = ref.watch(authStateProvider);
  return GoRouter(
    initialLocation: '/home',
    redirect: (context, state) {
      final loggedIn = auth.isAuthenticated;
      final goingToLogin = state.matchedLocation == '/login';
      if (!loggedIn && !goingToLogin) return '/login';
      if (loggedIn && goingToLogin) return '/home';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
      GoRoute(path: '/pos', builder: (context, state) => const PosScreen()),
      GoRoute(path: '/debts', builder: (context, state) => const DebtsScreen()),
      ShellRoute(
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(path: '/home', builder: (context, state) => const HomeScreen()),
          GoRoute(path: '/sales', builder: (context, state) => const SalesListScreen()),
          GoRoute(path: '/products', builder: (context, state) => const ProductsScreen()),
          GoRoute(path: '/customers', builder: (context, state) => const CustomersScreen()),
          GoRoute(path: '/more', builder: (context, state) => const MoreScreen()),
        ],
      ),
    ],
  );
});

class NzassaApp extends ConsumerWidget {
  const NzassaApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: "N'Zassa Business",
      debugShowCheckedModeBanner: false,
      theme: buildNzassaTheme(),
      routerConfig: router,
    );
  }
}
