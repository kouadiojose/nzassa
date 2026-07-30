import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/api_client.dart';
import '../../../core/theme.dart';
import '../../auth/presentation/auth_providers.dart';
import '../../customers/presentation/customers_screen.dart';

final appointmentsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final data = await api.get<List<dynamic>>(
    '/appointments',
    query: {'per_page': 100, 'sort_dir': 'asc'},
  );
  return data.cast<Map<String, dynamic>>();
});

final servicesProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final data = await api.get<List<dynamic>>('/catalog/services', query: {'per_page': 100});
  return data.cast<Map<String, dynamic>>();
});

final employeesProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final data = await api.get<List<dynamic>>('/employees');
  return data.cast<Map<String, dynamic>>();
});

const _statusInfo = {
  'pending': ('En attente', NzColors.muted, Icons.schedule),
  'confirmed': ('Confirmé', NzColors.info, Icons.event_available),
  'arrived': ('Arrivé', NzColors.gold, Icons.emoji_people),
  'in_progress': ('En cours', NzColors.primary, Icons.content_cut),
  'completed': ('Terminé', NzColors.success, Icons.check_circle_outline),
  'cancelled': ('Annulé', NzColors.danger, Icons.cancel_outlined),
  'no_show': ('Absent', NzColors.danger, Icons.person_off_outlined),
};

/// Prochaine étape logique pour chaque statut (miroir du backend).
const _nextStep = {
  'pending': ('confirmed', 'Confirmer'),
  'confirmed': ('arrived', 'Client arrivé'),
  'arrived': ('in_progress', 'Démarrer'),
  'in_progress': ('completed', 'Terminer'),
};

class AppointmentsScreen extends ConsumerWidget {
  const AppointmentsScreen({super.key});

  Future<void> _updateStatus(
      BuildContext context, WidgetRef ref, String id, String status) async {
    final api = ref.read(apiClientProvider);
    try {
      await api.post<Map<String, dynamic>>(
        '/appointments/$id/status',
        body: {'status': status},
      );
      ref.invalidate(appointmentsProvider);
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  Future<void> _create(BuildContext context, WidgetRef ref) async {
    final customers = await ref.read(customersProvider.future);
    final services = await ref.read(servicesProvider.future);
    final employees = await ref.read(employeesProvider.future);
    if (!context.mounted) return;
    if (services.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Créez d’abord une prestation (web)')),
      );
      return;
    }

    String? customerId = customers.isNotEmpty ? customers.first['id'] as String : null;
    String serviceId = services.first['id'] as String;
    String? employeeId = employees.isNotEmpty ? employees.first['id'] as String : null;
    var date = DateTime.now().add(const Duration(days: 1));
    var time = const TimeOfDay(hour: 10, minute: 0);

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
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Nouveau rendez-vous',
                  style: TextStyle(
                      fontSize: 18, fontWeight: FontWeight.w800, color: NzColors.ink),
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  value: customerId,
                  decoration: const InputDecoration(labelText: 'Client'),
                  items: [
                    for (final c in customers)
                      DropdownMenuItem(
                        value: c['id'] as String,
                        child: Text(
                          '${c['first_name'] ?? ''} ${c['last_name'] ?? ''}'.trim(),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: (value) => setSheetState(() => customerId = value),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: serviceId,
                  decoration: const InputDecoration(labelText: 'Prestation'),
                  items: [
                    for (final s in services)
                      DropdownMenuItem(
                        value: s['id'] as String,
                        child: Text(
                          '${s['name']} (${s['duration_minutes']} min)',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: (value) =>
                      setSheetState(() => serviceId = value ?? serviceId),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: employeeId,
                  decoration: const InputDecoration(labelText: 'Employé'),
                  items: [
                    for (final e in employees)
                      DropdownMenuItem(
                        value: e['id'] as String,
                        child: Text(
                          '${e['first_name']} ${e['last_name']}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: (value) => setSheetState(() => employeeId = value),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.calendar_today, size: 16),
                        label: Text(DateFormat('dd/MM/yyyy').format(date)),
                        onPressed: () async {
                          final picked = await showDatePicker(
                            context: context,
                            initialDate: date,
                            firstDate: DateTime.now(),
                            lastDate: DateTime.now().add(const Duration(days: 365)),
                          );
                          if (picked != null) setSheetState(() => date = picked);
                        },
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.access_time, size: 16),
                        label: Text(time.format(context)),
                        onPressed: () async {
                          final picked = await showTimePicker(
                              context: context, initialTime: time);
                          if (picked != null) setSheetState(() => time = picked);
                        },
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                FilledButton(
                  onPressed: () => Navigator.of(context).pop(true),
                  child: const Text('Créer le rendez-vous'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    if (confirmed != true || !context.mounted) return;

    final startsAt =
        DateTime(date.year, date.month, date.day, time.hour, time.minute);
    final api = ref.read(apiClientProvider);
    try {
      final branches =
          await api.get<List<dynamic>>('/business/branches');
      final branchId =
          (branches.cast<Map<String, dynamic>>()).first['id'] as String;
      await api.post<Map<String, dynamic>>('/appointments', body: {
        'branch_id': branchId,
        'customer_id': customerId,
        'employee_id': employeeId,
        'starts_at': startsAt.toUtc().toIso8601String(),
        'service_ids': [serviceId],
      });
      ref.invalidate(appointmentsProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Rendez-vous créé ✔')),
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
    final appointments = ref.watch(appointmentsProvider);
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
      appBar: AppBar(
        title: const Text('Rendez-vous'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 10),
            child: IconButton.filledTonal(
              icon: const Icon(Icons.add),
              tooltip: 'Nouveau rendez-vous',
              onPressed: () => _create(context, ref),
            ),
          ),
        ],
      ),
      body: appointments.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text('$error', textAlign: TextAlign.center),
          ),
        ),
        data: (items) {
          // À venir d'abord, puis passés
          final upcoming = items
              .where((a) =>
                  a['status'] == 'pending' ||
                  a['status'] == 'confirmed' ||
                  a['status'] == 'arrived' ||
                  a['status'] == 'in_progress')
              .toList();
          final past = items.where((a) => !upcoming.contains(a)).toList();
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(appointmentsProvider),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 40),
              children: [
                if (upcoming.isEmpty && past.isEmpty)
                  const Padding(
                    padding: EdgeInsets.only(top: 80),
                    child: Column(
                      children: [
                        Icon(Icons.event_available,
                            size: 48, color: NzColors.muted),
                        SizedBox(height: 10),
                        Text('Aucun rendez-vous — créez le premier !',
                            style: TextStyle(color: NzColors.muted)),
                      ],
                    ),
                  ),
                for (final appt in upcoming) ...[
                  _AppointmentCard(
                    appointment: appt,
                    customerName: namesById[appt['customer_id']] ?? 'Sans client',
                    onNextStep: (status) =>
                        _updateStatus(context, ref, appt['id'] as String, status),
                  ),
                  const SizedBox(height: 10),
                ],
                if (past.isNotEmpty) ...[
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 8),
                    child: Text(
                      'Historique',
                      style: TextStyle(
                          fontWeight: FontWeight.w800, color: NzColors.muted),
                    ),
                  ),
                  for (final appt in past) ...[
                    _AppointmentCard(
                      appointment: appt,
                      customerName:
                          namesById[appt['customer_id']] ?? 'Sans client',
                      onNextStep: null,
                    ),
                    const SizedBox(height: 10),
                  ],
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

class _AppointmentCard extends StatelessWidget {
  const _AppointmentCard({
    required this.appointment,
    required this.customerName,
    required this.onNextStep,
  });

  final Map<String, dynamic> appointment;
  final String customerName;
  final ValueChanged<String>? onNextStep;

  @override
  Widget build(BuildContext context) {
    final status = appointment['status'] as String;
    final info = _statusInfo[status] ?? (status, NzColors.muted, Icons.help_outline);
    final starts = DateTime.parse(appointment['starts_at'] as String).toLocal();
    final ends = DateTime.parse(appointment['ends_at'] as String).toLocal();
    final next = onNextStep != null ? _nextStep[status] : null;
    final cancellable = onNextStep != null &&
        (status == 'pending' || status == 'confirmed' || status == 'arrived');

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
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
                        customerName,
                        style: const TextStyle(
                            fontWeight: FontWeight.w800, color: NzColors.ink),
                      ),
                      Text(
                        '${DateFormat('EEE dd MMM', 'fr').format(starts)} · '
                        '${DateFormat('HH:mm').format(starts)} — '
                        '${DateFormat('HH:mm').format(ends)}',
                        style: const TextStyle(
                            fontSize: 12.5, color: NzColors.muted),
                      ),
                    ],
                  ),
                ),
                NzStatusChip(label: info.$1, color: info.$2),
              ],
            ),
            if (next != null || cancellable) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  if (cancellable)
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => onNextStep!('cancelled'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: NzColors.danger,
                          side: BorderSide(
                              color: NzColors.danger.withOpacity(0.4)),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12)),
                        ),
                        child: const Text('Annuler'),
                      ),
                    ),
                  if (cancellable && next != null) const SizedBox(width: 10),
                  if (next != null)
                    Expanded(
                      flex: 2,
                      child: FilledButton(
                        onPressed: () => onNextStep!(next.$1),
                        style: FilledButton.styleFrom(
                          minimumSize: const Size.fromHeight(42),
                          textStyle: const TextStyle(
                              fontSize: 13.5, fontWeight: FontWeight.w700),
                        ),
                        child: Text(next.$2),
                      ),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
