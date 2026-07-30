import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
        children: [
          ListTile(
            leading: const CircleAvatar(child: Icon(Icons.person)),
            title: Text(auth.user?.fullName ?? ''),
            subtitle: Text(auth.user?.email ?? ''),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.sync),
            title: const Text('Synchroniser maintenant'),
            subtitle: pending.maybeWhen(
              data: (count) => Text('$count opération(s) en attente'),
              orElse: () => null,
            ),
            onTap: () async {
              final sync = await ref.read(syncServiceProvider.future);
              final applied = await sync.pushPending();
              await sync.pullChanges();
              ref.invalidate(pendingSyncCountProvider);
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('$applied opération(s) synchronisée(s)')),
                );
              }
            },
          ),
          const ListTile(
            leading: Icon(Icons.calendar_month_outlined),
            title: Text('Rendez-vous'),
            subtitle: Text('Disponible sur la plateforme web'),
          ),
          const ListTile(
            leading: Icon(Icons.bar_chart_outlined),
            title: Text('Rapports détaillés'),
            subtitle: Text('Disponible sur la plateforme web'),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.logout, color: Colors.red),
            title: const Text('Déconnexion', style: TextStyle(color: Colors.red)),
            onTap: () => ref.read(authStateProvider.notifier).logout(),
          ),
        ],
      ),
    );
  }
}
