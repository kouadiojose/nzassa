import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../../auth/presentation/auth_providers.dart';
import '../../sales/presentation/sales_providers.dart';

class MoreScreen extends ConsumerWidget {
  const MoreScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authStateProvider);
    final pending = ref.watch(pendingSyncCountProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Plus')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
        children: [
          // Carte profil
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: NzColors.heroGradient,
              borderRadius: BorderRadius.circular(22),
            ),
            child: Row(
              children: [
                NzAvatar(label: auth.user?.firstName ?? '?', size: 52),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        auth.user?.fullName ?? '',
                        style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w800,
                            fontSize: 16),
                      ),
                      Text(
                        auth.user?.email ?? '',
                        style: TextStyle(
                            color: Colors.white.withOpacity(0.85), fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _MenuCard(
            children: [
              _MenuTile(
                icon: Icons.sync,
                color: NzColors.info,
                title: 'Synchroniser maintenant',
                subtitle: pending.maybeWhen(
                  data: (count) => count > 0
                      ? '$count opération(s) en attente'
                      : 'Tout est à jour',
                  orElse: () => null,
                ),
                onTap: () async {
                  final sync = await ref.read(syncServiceProvider.future);
                  if (sync == null) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Mode hors ligne indisponible sur le web'),
                        ),
                      );
                    }
                    return;
                  }
                  final applied = await sync.pushPending();
                  await sync.pullChanges();
                  ref.invalidate(pendingSyncCountProvider);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                          content: Text('$applied opération(s) synchronisée(s)')),
                    );
                  }
                },
              ),
            ],
          ),
          const SizedBox(height: 16),
          _MenuCard(
            children: [
              _MenuTile(
                icon: Icons.hourglass_bottom,
                color: NzColors.gold,
                title: 'Créances clients',
                subtitle: 'Suivre, encaisser et relancer',
                onTap: () => context.push('/debts'),
              ),
              const _MenuTile(
                icon: Icons.calendar_month_outlined,
                color: NzColors.primary,
                title: 'Rendez-vous',
                subtitle: 'Disponible sur la plateforme web',
              ),
              const _MenuTile(
                icon: Icons.bar_chart_outlined,
                color: NzColors.success,
                title: 'Rapports détaillés',
                subtitle: 'Disponible sur la plateforme web',
              ),
            ],
          ),
          const SizedBox(height: 16),
          _MenuCard(
            children: [
              _MenuTile(
                icon: Icons.logout,
                color: NzColors.danger,
                title: 'Déconnexion',
                onTap: () => ref.read(authStateProvider.notifier).logout(),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MenuCard extends StatelessWidget {
  const _MenuCard({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Column(
        children: [
          for (var i = 0; i < children.length; i++) ...[
            children[i],
            if (i < children.length - 1)
              Divider(height: 1, color: NzColors.ink.withOpacity(0.05), indent: 60),
          ],
        ],
      ),
    );
  }
}

class _MenuTile extends StatelessWidget {
  const _MenuTile({
    required this.icon,
    required this.color,
    required this.title,
    this.subtitle,
    this.onTap,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String? subtitle;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      leading: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(icon, color: color, size: 20),
      ),
      title: Text(
        title,
        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5),
      ),
      subtitle: subtitle != null
          ? Text(subtitle!,
              style: const TextStyle(fontSize: 12.5, color: NzColors.muted))
          : null,
      trailing: onTap != null
          ? const Icon(Icons.chevron_right, color: NzColors.muted, size: 20)
          : null,
    );
  }
}
