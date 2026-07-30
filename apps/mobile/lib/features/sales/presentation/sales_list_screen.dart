import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import 'sales_providers.dart';

final _numberFormat = NumberFormat.decimalPattern('fr');

final salesListProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final repository = await ref.watch(salesRepositoryProvider.future);
  return repository.listSales();
});

class SalesListScreen extends ConsumerWidget {
  const SalesListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sales = ref.watch(salesListProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Ventes')),
      body: sales.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Hors connexion — $error')),
        data: (items) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(salesListProvider),
          child: ListView.separated(
            itemCount: items.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final sale = items[index];
              final due = num.parse(sale['amount_due'] as String);
              return ListTile(
                title: Text(sale['number'] as String),
                subtitle: Text(
                  DateFormat('dd/MM/yyyy HH:mm')
                      .format(DateTime.parse(sale['sold_at'] as String).toLocal()),
                ),
                trailing: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      '${_numberFormat.format(num.parse(sale['total'] as String))} F',
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    if (due > 0)
                      Text(
                        'Reste ${_numberFormat.format(due)} F',
                        style: const TextStyle(color: Colors.orange, fontSize: 12),
                      ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
