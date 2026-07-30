import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
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
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
      ),
      builder: (context) => Padding(
        padding: EdgeInsets.fromLTRB(
            20, 20, 20, MediaQuery.of(context).viewInsets.bottom + 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Nouveau client',
              style: TextStyle(
                  fontSize: 18, fontWeight: FontWeight.w800, color: NzColors.ink),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: nameController,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Prénom',
                prefixIcon: Icon(Icons.person_outline, size: 20),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: phoneController,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(
                labelText: 'Téléphone (+225…)',
                prefixIcon: Icon(Icons.phone_outlined, size: 20),
              ),
            ),
            const SizedBox(height: 18),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Créer le client'),
            ),
          ],
        ),
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
          Padding(
            padding: const EdgeInsets.only(right: 10),
            child: IconButton.filledTonal(
              icon: const Icon(Icons.person_add_alt),
              onPressed: () => _createCustomer(context, ref),
            ),
          ),
        ],
      ),
      body: customers.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text('$error', textAlign: TextAlign.center),
          ),
        ),
        data: (items) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(customersProvider),
          child: ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
            itemCount: items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (context, index) {
              final customer = items[index];
              final name =
                  '${customer['first_name'] ?? ''} ${customer['last_name'] ?? ''}'.trim();
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      NzAvatar(label: name),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              name,
                              style: const TextStyle(
                                  fontWeight: FontWeight.w700, color: NzColors.ink),
                            ),
                            if ((customer['phone'] as String?) != null)
                              Text(
                                customer['phone'] as String,
                                style: const TextStyle(
                                    fontSize: 12.5, color: NzColors.muted),
                              ),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right, color: NzColors.muted),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
