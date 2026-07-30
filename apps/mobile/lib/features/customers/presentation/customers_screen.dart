import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/presentation/auth_providers.dart';
import '../../sales/presentation/sales_providers.dart';

final customersProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final api = ref.watch(apiClientProvider);
  try {
    final data = await api.get<List<dynamic>>('/customers', query: {'per_page': 100});
    return data.cast<Map<String, dynamic>>();
  } catch (_) {
    final db = await ref.watch(localDbProvider.future);
    if (db == null) rethrow;
    final rows = await db.db.query('cached_customers', where: 'is_active = 1');
    return rows
        .map((row) => {
              'id': row['id'],
              'first_name': row['first_name'],
              'last_name': row['last_name'],
              'phone': row['phone'],
            })
        .toList();
  }
});

class CustomersScreen extends ConsumerWidget {
  const CustomersScreen({super.key});

  Future<void> _createCustomer(BuildContext context, WidgetRef ref) async {
    final nameController = TextEditingController();
    final phoneController = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Nouveau client'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              decoration: const InputDecoration(labelText: 'Prénom'),
            ),
            TextField(
              controller: phoneController,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: 'Téléphone (+225…)'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Créer'),
          ),
        ],
      ),
    );
    if (confirmed != true || nameController.text.trim().isEmpty) return;

    final payload = {
      'first_name': nameController.text.trim(),
      'phone': phoneController.text.trim().isEmpty ? null : phoneController.text.trim(),
    };
    final api = ref.read(apiClientProvider);
    try {
      await api.post<Map<String, dynamic>>('/customers', body: payload);
    } catch (_) {
      // Hors ligne : la création rejoint la file de synchronisation (mobile).
      final sync = await ref.read(syncServiceProvider.future);
      if (sync != null) {
        await sync.enqueue('create_customer', payload);
      } else if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Connexion impossible — réessayez en ligne')),
        );
        return;
      }
    }
    ref.invalidate(customersProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final customers = ref.watch(customersProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Clients'),
        actions: [
          IconButton(
            icon: const Icon(Icons.person_add_alt),
            onPressed: () => _createCustomer(context, ref),
          ),
        ],
      ),
      body: customers.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('$error')),
        data: (items) => ListView.separated(
          itemCount: items.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final customer = items[index];
            final name =
                '${customer['first_name'] ?? ''} ${customer['last_name'] ?? ''}'.trim();
            return ListTile(
              leading: CircleAvatar(child: Text(name.isEmpty ? '?' : name[0])),
              title: Text(name),
              subtitle: Text(customer['phone'] as String? ?? ''),
            );
          },
        ),
      ),
    );
  }
}
