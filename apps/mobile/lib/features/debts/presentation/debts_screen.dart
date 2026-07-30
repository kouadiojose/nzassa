import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../core/theme.dart';
import '../../auth/presentation/auth_providers.dart';
import '../../customers/presentation/customers_screen.dart';

/// Créances ouvertes (open + partially_paid), plus récentes d'abord.
final debtsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final data = await api.get<List<dynamic>>('/debts', query: {'per_page': 100});
  return data
      .cast<Map<String, dynamic>>()
      .where((d) => d['status'] == 'open' || d['status'] == 'partially_paid')
      .toList();
});

final debtsSummaryProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.get<Map<String, dynamic>>('/debts/summary');
});

const _collectMethods = {
  'cash': 'Espèces',
  'wave': 'Wave',
  'orange_money': 'Orange Money',
  'mtn_money': 'MTN MoMo',
  'moov_money': 'Moov Money',
};

class DebtsScreen extends ConsumerWidget {
  const DebtsScreen({super.key});

  Future<void> _collect(
    BuildContext context,
    WidgetRef ref,
    Map<String, dynamic> debt,
    String customerName,
  ) async {
    final balance = Decimal.parse(debt['balance'] as String);
    final amountController = TextEditingController(text: balance.toString());
    var method = 'cash';
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
      ),
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.fromLTRB(
              20, 20, 20, MediaQuery.of(context).viewInsets.bottom + 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Encaisser — $customerName',
                style: const TextStyle(
                    fontSize: 18, fontWeight: FontWeight.w800, color: NzColors.ink),
              ),
              const SizedBox(height: 4),
              Text(
                'Solde dû : ${formatMoney(balance)}',
                style: const TextStyle(color: NzColors.muted, fontSize: 13),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: amountController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: 'Montant reçu',
                  prefixIcon: Icon(Icons.payments_outlined, size: 20),
                ),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                children: [
                  for (final entry in _collectMethods.entries)
                    ChoiceChip(
                      label: Text(entry.value),
                      selected: method == entry.key,
                      selectedColor: NzColors.ink,
                      labelStyle: TextStyle(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w700,
                        color: method == entry.key ? Colors.white : NzColors.ink,
                      ),
                      onSelected: (_) => setSheetState(() => method = entry.key),
                    ),
                ],
              ),
              const SizedBox(height: 18),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Confirmer le règlement'),
              ),
            ],
          ),
        ),
      ),
    );
    if (confirmed != true) return;
    final raw = amountController.text.trim().replaceAll(' ', '').replaceAll(',', '.');
    if (raw.isEmpty) return;

    final api = ref.read(apiClientProvider);
    try {
      await api.post<Map<String, dynamic>>(
        '/debts/${debt['id']}/payments',
        body: {'amount': raw, 'method': method},
      );
      ref.invalidate(debtsProvider);
      ref.invalidate(debtsSummaryProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Règlement enregistré ✔')),
        );
      }
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  Future<void> _remind(
      BuildContext context, WidgetRef ref, Map<String, dynamic> debt) async {
    final api = ref.read(apiClientProvider);
    try {
      final data = await api
          .get<Map<String, dynamic>>('/debts/${debt['id']}/reminder-message');
      final whatsappUrl = data['whatsapp_url'] as String?;
      final message = data['message'] as String;
      if (whatsappUrl != null) {
        final launched = await launchUrl(
          Uri.parse(whatsappUrl),
          mode: LaunchMode.externalApplication,
        );
        if (launched) return;
      }
      await Clipboard.setData(ClipboardData(text: message));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Message de relance copié 📋')),
        );
      }
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final debts = ref.watch(debtsProvider);
    final summary = ref.watch(debtsSummaryProvider);
    final customers = ref.watch(customersProvider);
    final namesById = customers.maybeWhen(
      data: (items) => {
        for (final c in items)
          c['id'] as String:
              '${c['first_name'] ?? ''} ${c['last_name'] ?? ''}'.trim(),
      },
      orElse: () => <String, String>{},
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Créances clients')),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(debtsProvider);
          ref.invalidate(debtsSummaryProvider);
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 40),
          children: [
            // Résumé
            summary.maybeWhen(
              data: (s) => Row(
                children: [
                  Expanded(
                    child: _SummaryCard(
                      label: 'Total dû',
                      value: formatMoneyStr(s['total_open'] as String),
                      color: NzColors.gold,
                      icon: Icons.hourglass_bottom,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _SummaryCard(
                      label: 'En retard',
                      value: formatMoneyStr(s['total_overdue'] as String),
                      color: NzColors.danger,
                      icon: Icons.warning_amber_rounded,
                    ),
                  ),
                ],
              ),
              orElse: () => const SizedBox.shrink(),
            ),
            const SizedBox(height: 16),
            debts.when(
              loading: () => const Padding(
                padding: EdgeInsets.only(top: 60),
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (error, _) => Padding(
                padding: const EdgeInsets.all(24),
                child: Text('$error', textAlign: TextAlign.center),
              ),
              data: (items) => items.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.only(top: 60),
                      child: Column(
                        children: [
                          Icon(Icons.celebration_outlined,
                              size: 48, color: NzColors.success),
                          SizedBox(height: 10),
                          Text('Aucune créance ouverte 🎉',
                              style: TextStyle(color: NzColors.muted)),
                        ],
                      ),
                    )
                  : Column(
                      children: [
                        for (final debt in items) ...[
                          _DebtCard(
                            debt: debt,
                            customerName: namesById[debt['customer_id']] ?? 'Client',
                            onCollect: () => _collect(context, ref, debt,
                                namesById[debt['customer_id']] ?? 'Client'),
                            onRemind: () => _remind(context, ref, debt),
                          ),
                          const SizedBox(height: 10),
                        ],
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.label,
    required this.value,
    required this.color,
    required this.icon,
  });

  final String label;
  final String value;
  final Color color;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 8),
            FittedBox(
              child: Text(
                value,
                style: const TextStyle(
                    fontSize: 17, fontWeight: FontWeight.w800, color: NzColors.ink),
              ),
            ),
            Text(label, style: const TextStyle(fontSize: 12, color: NzColors.muted)),
          ],
        ),
      ),
    );
  }
}

class _DebtCard extends StatelessWidget {
  const _DebtCard({
    required this.debt,
    required this.customerName,
    required this.onCollect,
    required this.onRemind,
  });

  final Map<String, dynamic> debt;
  final String customerName;
  final VoidCallback onCollect;
  final VoidCallback onRemind;

  @override
  Widget build(BuildContext context) {
    final balance = Decimal.parse(debt['balance'] as String);
    final original = Decimal.parse(debt['original_amount'] as String);
    final partiallyPaid = debt['status'] == 'partially_paid';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                NzAvatar(label: customerName),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        customerName,
                        style: const TextStyle(
                            fontWeight: FontWeight.w800, color: NzColors.ink),
                      ),
                      Text(
                        'Sur ${formatMoney(original)} au départ',
                        style:
                            const TextStyle(fontSize: 12, color: NzColors.muted),
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      formatMoney(balance),
                      style: const TextStyle(
                          fontWeight: FontWeight.w900,
                          fontSize: 16,
                          color: NzColors.primaryDark),
                    ),
                    NzStatusChip(
                      label: partiallyPaid ? 'Partiel' : 'Ouvert',
                      color: partiallyPaid ? NzColors.info : NzColors.gold,
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onRemind,
                    icon: const Icon(Icons.chat_outlined, size: 18),
                    label: const Text('Relancer'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: NzColors.ink,
                      side: BorderSide(color: NzColors.ink.withOpacity(0.15)),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: onCollect,
                    icon: const Icon(Icons.payments_outlined, size: 18),
                    label: const Text('Encaisser'),
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.fromHeight(42),
                      textStyle: const TextStyle(
                          fontSize: 13.5, fontWeight: FontWeight.w700),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
