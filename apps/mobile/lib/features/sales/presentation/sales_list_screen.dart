import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/format.dart';
import '../../../core/theme.dart';
import 'sales_providers.dart';

final salesListProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final repository = await ref.watch(salesRepositoryProvider.future);
  return repository.listSales();
});

const _statusInfo = {
  'completed': ('Validée', NzColors.success, Icons.check_circle_outline),
  'draft': ('Brouillon', NzColors.muted, Icons.edit_note),
  'cancelled': ('Annulée', NzColors.danger, Icons.cancel_outlined),
  'refunded': ('Remboursée', NzColors.info, Icons.replay_circle_filled),
  'partially_refunded': ('Remb. partiel', NzColors.info, Icons.replay),
};

class SalesListScreen extends ConsumerWidget {
  const SalesListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sales = ref.watch(salesListProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Ventes')),
      body: sales.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text('Hors connexion — $error', textAlign: TextAlign.center),
          ),
        ),
        data: (items) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(salesListProvider),
          child: items.isEmpty
              ? ListView(
                  children: const [
                    SizedBox(height: 120),
                    Icon(Icons.receipt_long_outlined, size: 48, color: NzColors.muted),
                    SizedBox(height: 10),
                    Center(
                      child: Text('Aucune vente pour le moment',
                          style: TextStyle(color: NzColors.muted)),
                    ),
                  ],
                )
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
                  itemCount: items.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    final sale = items[index];
                    final status = sale['status'] as String;
                    final info = _statusInfo[status] ??
                        (status, NzColors.muted, Icons.help_outline);
                    final due = Decimal.parse(sale['amount_due'] as String);
                    return Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: info.$2.withOpacity(0.12),
                                borderRadius: BorderRadius.circular(14),
                              ),
                              child: Icon(info.$3, color: info.$2, size: 22),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    sale['number'] as String,
                                    style: const TextStyle(
                                        fontWeight: FontWeight.w800,
                                        color: NzColors.ink),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    DateFormat('dd/MM/yyyy HH:mm').format(
                                        DateTime.parse(sale['sold_at'] as String)
                                            .toLocal()),
                                    style: const TextStyle(
                                        fontSize: 12, color: NzColors.muted),
                                  ),
                                  const SizedBox(height: 6),
                                  NzStatusChip(label: info.$1, color: info.$2),
                                ],
                              ),
                            ),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(
                                  formatMoneyStr(sale['total'] as String),
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w900,
                                      fontSize: 15,
                                      color: NzColors.ink),
                                ),
                                if (due > Decimal.zero)
                                  Padding(
                                    padding: const EdgeInsets.only(top: 4),
                                    child: NzStatusChip(
                                      label: 'Reste ${formatMoney(due)}',
                                      color: NzColors.gold,
                                    ),
                                  ),
                              ],
                            ),
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
