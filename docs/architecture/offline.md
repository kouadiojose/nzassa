# Stratégie hors connexion (mobile)

## Objectif

Vendre, encaisser, créer des clients et des dépenses **sans réseau**, avec une
synchronisation fiable dès le retour de la connexion.

## Côté mobile (Flutter)

- Cache SQLite : `cached_products`, `cached_customers` (rafraîchis par
  `GET /sync/pull?since=<dernier pull>` — delta par `updated_at`).
- File locale `pending_operations` : chaque opération créée hors ligne reçoit
  un **UUID client** (`client_operation_id`) et un payload JSON.
- `SyncService.pushPending()` envoie les lots vers `POST /sync/push` avec
  retries (max 5) ; l'état (`applied` / `conflict` / `failed`) et le résultat
  serveur sont stockés localement.
- Indicateur d'état de synchronisation dans l'UI + action « Synchroniser
  maintenant » ; pull-to-refresh déclenche push + pull.

## Côté backend

- `POST /api/v1/sync/push` : lot de 1 à 100 opérations
  (`create_sale`, `create_expense`, `create_customer`).
  - **Idempotence** : `(tenant_id, client_operation_id)` unique ; une opération
    déjà appliquée renvoie son résultat stocké (`duplicate: true`).
  - Les ventes utilisent aussi `client_reference` (unique par tenant) : rejouer
    une vente ne déduit jamais le stock deux fois.
  - **Doublons clients** : détection par téléphone → renvoie l'existant.
  - Les ventes offline n'exigent pas de session de caisse ouverte.
- `GET /api/v1/sync/pull` : produits, prestations, clients modifiés depuis
  `since`, plus `server_time` servant de curseur pour l'appel suivant.

## Conflits

- Vente/dépense : idempotence stricte (même id → même résultat), pas de fusion.
- Client : dédoublonnage par téléphone.
- Erreurs métier (ex. stock insuffisant) : l'opération passe en `failed` avec
  le code d'erreur stable ; l'utilisateur est informé et peut corriger.
