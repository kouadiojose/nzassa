import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/theme.dart';
import '../../auth/presentation/auth_providers.dart';

final notificationsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final data = await api.get<List<dynamic>>('/notifications', query: {'per_page': 50});
  return data.cast<Map<String, dynamic>>();
});

const _typeIcons = {
  'low_stock': (Icons.inventory_2_outlined, NzColors.danger),
  'product_expired': (Icons.event_busy, NzColors.danger),
  'appointment_reminder': (Icons.event, NzColors.info),
  'debt_due': (Icons.hourglass_bottom, NzColors.gold),
  'payment_received': (Icons.payments_outlined, NzColors.success),
  'subscription_expiring': (Icons.card_membership, NzColors.gold),
  'invitation': (Icons.person_add_alt, NzColors.info),
};

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifications = ref.watch(notificationsProvider);
    final api = ref.read(apiClientProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          TextButton(
            onPressed: () async {
              await api.post<dynamic>('/notifications/read-all');
              ref.invalidate(notificationsProvider);
            },
            child: const Text('Tout lire'),
          ),
        ],
      ),
      body: notifications.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text('$error', textAlign: TextAlign.center),
          ),
        ),
        data: (items) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(notificationsProvider),
          child: items.isEmpty
              ? ListView(
                  children: const [
                    SizedBox(height: 100),
                    Icon(Icons.notifications_none, size: 48, color: NzColors.muted),
                    SizedBox(height: 10),
                    Center(
                      child: Text('Aucune notification',
                          style: TextStyle(color: NzColors.muted)),
                    ),
                  ],
                )
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 40),
                  itemCount: items.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, index) {
                    final notification = items[index];
                    final unread = notification['read_at'] == null;
                    final typeInfo = _typeIcons[notification['type']] ??
                        (Icons.notifications_none, NzColors.muted);
                    return Card(
                      child: ListTile(
                        onTap: unread
                            ? () async {
                                await api.post<dynamic>(
                                    '/notifications/${notification['id']}/read');
                                ref.invalidate(notificationsProvider);
                              }
                            : null,
                        leading: Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: typeInfo.$2.withOpacity(0.12),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Icon(typeInfo.$1, color: typeInfo.$2, size: 20),
                        ),
                        title: Text(
                          notification['title'] as String,
                          style: TextStyle(
                            fontWeight: unread ? FontWeight.w800 : FontWeight.w600,
                            fontSize: 14,
                            color: NzColors.ink,
                          ),
                        ),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(notification['body'] as String,
                                style: const TextStyle(fontSize: 12.5)),
                            Text(
                              DateFormat('dd/MM HH:mm').format(
                                  DateTime.parse(
                                          notification['created_at'] as String)
                                      .toLocal()),
                              style: const TextStyle(
                                  fontSize: 11, color: NzColors.muted),
                            ),
                          ],
                        ),
                        trailing: unread
                            ? const Icon(Icons.circle,
                                size: 10, color: NzColors.primary)
                            : null,
                      ),
                    );
                  },
                ),
        ),
      ),
    );
  }
}
