import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/theme.dart';
import '../../auth/presentation/auth_providers.dart';
import '../../sales/presentation/sales_providers.dart';

final dashboardProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.get<Map<String, dynamic>>('/reports/dashboard');
});

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  Future<void> _refresh(WidgetRef ref) async {
    ref.invalidate(dashboardProvider);
    final sync = await ref.read(syncServiceProvider.future);
    if (sync != null) {
      await sync.pushPending();
      await sync.pullChanges();
    }
    ref.invalidate(pendingSyncCountProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dashboard = ref.watch(dashboardProvider);
    final pendingSync = ref.watch(pendingSyncCountProvider);
    final auth = ref.watch(authStateProvider);

    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () => _refresh(ref),
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverToBoxAdapter(
              child: _HeroHeader(
                firstName: auth.user?.firstName ?? '',
                pendingCount: pendingSync.maybeWhen(data: (c) => c, orElse: () => 0),
                revenue: dashboard.maybeWhen(
                  data: (d) => formatMoney(Decimal.parse(d['revenue'] as String)),
                  orElse: () => '— —',
                ),
                salesCount: dashboard.maybeWhen(
                  data: (d) => d['sales_count'] as int,
                  orElse: () => 0,
                ),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(16, 18, 16, 100),
              sliver: SliverToBoxAdapter(
                child: dashboard.when(
                  loading: () => const Padding(
                    padding: EdgeInsets.only(top: 60),
                    child: Center(child: CircularProgressIndicator()),
                  ),
                  error: (error, _) => const _OfflineNotice(),
                  data: (data) => Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const _SectionTitle('Aperçu des 30 derniers jours'),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: _KpiTile(
                              icon: Icons.trending_up,
                              color: NzColors.success,
                              label: 'Bénéfice estimé',
                              value: formatMoney(
                                  Decimal.parse(data['estimated_profit'] as String)),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _KpiTile(
                              icon: Icons.receipt_long,
                              color: NzColors.info,
                              label: 'Dépenses',
                              value:
                                  formatMoney(Decimal.parse(data['expenses'] as String)),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: _KpiTile(
                              icon: Icons.hourglass_bottom,
                              color: NzColors.gold,
                              label: 'Créances clients',
                              value: formatMoney(
                                  Decimal.parse(data['open_debts'] as String)),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _KpiTile(
                              icon: Icons.inventory_2_outlined,
                              color: (data['low_stock_count'] as int) > 0
                                  ? NzColors.danger
                                  : NzColors.muted,
                              label: 'Stock faible',
                              value: '${data['low_stock_count']} produit(s)',
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 24),
                      const _SectionTitle('Actions rapides'),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          _QuickAction(
                            icon: Icons.point_of_sale,
                            label: 'Vendre',
                            onTap: () => context.push('/pos'),
                          ),
                          _QuickAction(
                            icon: Icons.person_add_alt,
                            label: 'Client',
                            onTap: () => context.go('/customers'),
                          ),
                          _QuickAction(
                            icon: Icons.inventory_2_outlined,
                            label: 'Stock',
                            onTap: () => context.go('/products'),
                          ),
                          _QuickAction(
                            icon: Icons.receipt_long_outlined,
                            label: 'Ventes',
                            onTap: () => context.go('/sales'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HeroHeader extends StatelessWidget {
  const _HeroHeader({
    required this.firstName,
    required this.pendingCount,
    required this.revenue,
    required this.salesCount,
  });

  final String firstName;
  final int pendingCount;
  final String revenue;
  final int salesCount;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: NzColors.heroGradient,
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(32)),
      ),
      padding: EdgeInsets.fromLTRB(20, MediaQuery.of(context).padding.top + 16, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Bonjour $firstName 👋',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    Text(
                      'Prêt·e à vendre aujourd’hui ?',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.8),
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.16),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      pendingCount > 0 ? Icons.cloud_upload : Icons.cloud_done,
                      color: pendingCount > 0 ? NzColors.gold : Colors.white,
                      size: 16,
                    ),
                    const SizedBox(width: 5),
                    Text(
                      pendingCount > 0 ? '$pendingCount à sync' : 'À jour',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 22),
          Text(
            "CHIFFRE D'AFFAIRES (30 J)",
            style: TextStyle(
              color: Colors.white.withOpacity(0.7),
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.2,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            revenue,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 34,
              fontWeight: FontWeight.w900,
              letterSpacing: -1,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            '$salesCount vente(s) enregistrée(s)',
            style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 13),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 15,
        fontWeight: FontWeight.w800,
        color: NzColors.ink,
      ),
    );
  }
}

class _KpiTile extends StatelessWidget {
  const _KpiTile({
    required this.icon,
    required this.color,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final Color color;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(height: 10),
            FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                value,
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                  color: NzColors.ink,
                ),
              ),
            ),
            Text(
              label,
              style: const TextStyle(fontSize: 12, color: NzColors.muted),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  const _QuickAction({required this.icon, required this.label, required this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: Column(
          children: [
            Container(
              width: 54,
              height: 54,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: NzColors.ink.withOpacity(0.06)),
              ),
              child: Icon(icon, color: NzColors.primaryDark),
            ),
            const SizedBox(height: 6),
            Text(
              label,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: NzColors.ink,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OfflineNotice extends StatelessWidget {
  const _OfflineNotice();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(20),
        child: Column(
          children: [
            Icon(Icons.cloud_off, size: 42, color: NzColors.muted),
            SizedBox(height: 10),
            Text(
              'Hors connexion',
              style: TextStyle(fontWeight: FontWeight.w800, color: NzColors.ink),
            ),
            SizedBox(height: 4),
            Text(
              'Vous pouvez continuer à vendre : tout sera synchronisé au retour du réseau.',
              textAlign: TextAlign.center,
              style: TextStyle(color: NzColors.muted, fontSize: 13),
            ),
          ],
        ),
      ),
    );
  }
}
