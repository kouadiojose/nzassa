import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../auth/presentation/auth_providers.dart';
import '../../sales/presentation/sales_providers.dart';

final _numberFormat = NumberFormat.decimalPattern('fr');

final dashboardProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.get<Map<String, dynamic>>('/reports/dashboard');
});

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dashboard = ref.watch(dashboardProvider);
    final pendingSync = ref.watch(pendingSyncCountProvider);
    final auth = ref.watch(authStateProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text('Bonjour ${auth.user?.firstName ?? ''} 👋'),
        actions: [
          pendingSync.maybeWhen(
            data: (count) => count > 0
                ? Padding(
                    padding: const EdgeInsets.only(right: 12),
                    child: Chip(
                      avatar: const Icon(Icons.sync_problem, size: 16),
                      label: Text('$count en attente'),
                    ),
                  )
                : const Padding(
                    padding: EdgeInsets.only(right: 12),
                    child: Icon(Icons.cloud_done_outlined),
                  ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(dashboardProvider);
          final sync = await ref.read(syncServiceProvider.future);
          if (sync != null) {
            await sync.pushPending();
            await sync.pullChanges();
          }
          ref.invalidate(pendingSyncCountProvider);
        },
        child: dashboard.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => ListView(
            children: [
              const SizedBox(height: 80),
              const Icon(Icons.cloud_off, size: 48, color: Colors.grey),
              const SizedBox(height: 8),
              Center(child: Text('Hors connexion — $error')),
              const Center(
                child: Text('Vous pouvez continuer à vendre, tout sera synchronisé.'),
              ),
            ],
          ),
          data: (data) => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _KpiCard(
                title: "Chiffre d'affaires (30 j)",
                value: '${_numberFormat.format(num.parse(data['revenue'] as String))} F',
                subtitle: '${data['sales_count']} ventes',
                color: const Color(0xFFD1621C),
              ),
              _KpiCard(
                title: 'Bénéfice estimé',
                value:
                    '${_numberFormat.format(num.parse(data['estimated_profit'] as String))} F',
                color: Colors.green.shade700,
              ),
              _KpiCard(
                title: 'Créances clients',
                value: '${_numberFormat.format(num.parse(data['open_debts'] as String))} F',
                color: Colors.amber.shade800,
              ),
              _KpiCard(
                title: 'Stock faible',
                value: '${data['low_stock_count']} produit(s)',
                color: (data['low_stock_count'] as int) > 0 ? Colors.red : Colors.grey,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _KpiCard extends StatelessWidget {
  const _KpiCard({required this.title, required this.value, this.subtitle, required this.color});

  final String title;
  final String value;
  final String? subtitle;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 4),
            Text(
              value,
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: color),
            ),
            if (subtitle != null) Text(subtitle!, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}
