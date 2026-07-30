# Dette technique — N'Zassa Business

TODO non bloquants, documentés et assumés.

| # | Sujet | Détail | Priorité |
|---|-------|--------|----------|
| 1 | PostgreSQL Row Level Security | L'isolation est appliquée en couche service (`tenant_query`). Ajouter des politiques RLS par table comme défense en profondeur. | Haute |
| 2 | SMTP réel | `send_email_task` logge en console ; brancher un SMTP (identifiants externes requis). | Haute |
| 3 | FCM réel | `send_push_notification_task` est un no-op sans credentials Firebase. | Haute |
| 4 | Paiements Mobile Money | `SubscriptionPaymentProvider` n'a que l'implémentation manuelle. Ajouter CinetPay/Wave/Flutterwave/Paystack (comptes marchands requis). | Haute |
| 5 | Connecteur fiscal FNE CI | Simulé en dev uniquement. Intégration réelle soumise à l'API officielle DGI + agrément. | Moyenne |
| 6 | Fournisseur IA Anthropic | `get_ai_provider` retombe sur le stub ; implémenter l'appel API (clé requise) en réutilisant le contrat `AiProvider`. | Moyenne |
| 7 | Export Excel (XLSX) | CSV livré partout ; générer aussi du XLSX via openpyxl. | Basse |
| 8 | Variantes produit / lots / péremption | Modèles en base ; exposer les endpoints et l'UI. | Moyenne |
| 9 | Inventaires guidés | `StockInventory(Item)` modélisés ; écrans + endpoints de comptage à finaliser. | Moyenne |
| 10 | Scan code-barres mobile | Ajouter `mobile_scanner` et brancher la recherche produit. | Moyenne |
| 11 | Flutter codegen | Décision : pas de Freezed/Drift pour garder un dépôt compilable sans build_runner ; réévaluer si les modèles grossissent. | Basse |
| 12 | E2E navigateur | Parcours couverts via tests API ; ajouter Playwright sur le front. | Basse |
| 13 | Sauvegarde automatisée PostgreSQL | Script cron + rétention à ajouter dans infrastructure/scripts (procédure documentée dans docs/deployment). | Haute |
| 14 | Idempotency-Key HTTP générique | L'idempotence est gérée par `client_reference`/`client_operation_id` sur les opérations sensibles ; généraliser via en-tête si besoin. | Basse |
