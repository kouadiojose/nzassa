# Architecture — N'Zassa Business

## Vue d'ensemble

```mermaid
flowchart LR
    subgraph Clients
        M[Mobile Flutter<br/>Android / iOS] 
        W[Web Angular<br/>Entreprise]
        SA[Web Angular<br/>Super Admin]
    end
    subgraph Backend
        N[Nginx] --> API[FastAPI<br/>/api/v1]
        API --> PG[(PostgreSQL<br/>multi-tenant)]
        API --> R[(Redis)]
        WK[Worker Dramatiq] --> R
        WK --> PG
    end
    M -->|HTTPS + JWT| N
    W -->|HTTPS + JWT| N
    SA -->|HTTPS + JWT| N
    API -.->|emails, push, files| EXT[Services externes<br/>SMTP / FCM / S3]
```

## Backend (apps/backend)

- **FastAPI asynchrone**, SQLAlchemy 2 async, PostgreSQL, Redis, Dramatiq.
- Découpage : `core/` (config, DB, sécurité, tenancy, pagination, audit,
  middleware, RBAC) et `modules/<domaine>/` (router + service + schemas).
- Réponses standardisées `{success, message, data, meta}` et codes d'erreur
  stables (packages/shared-contracts/error-codes.md).
- Toute la logique financière (totaux, taxes, remises, soldes, commissions,
  valorisation) est calculée côté backend en `Decimal`.

## Flux d'une vente

```mermaid
sequenceDiagram
    participant C as Client (mobile/web)
    participant A as API
    participant S as SalesService
    participant St as StockService
    C->>A: POST /sales (items, payments, client_reference?)
    A->>S: create_sale (tenant du token)
    S->>S: prix catalogue + remises + taxes (Decimal)
    S->>S: contrôle session de caisse (paiement espèces)
    S->>St: sale_out par produit (FOR UPDATE, ledger immuable)
    S->>S: dette client si amount_due > 0 (plafond crédit)
    S->>S: commissions + points de fidélité
    S-->>A: vente complète
    A-->>C: {success, data: sale}
```

## Web (apps/web)

Angular 18 standalone + Signals, lazy routes, interceptors (JWT + refresh sur
401), guards (auth, permission, superadmin), PrimeNG + Tailwind.

## Mobile (apps/mobile)

Flutter, Riverpod, GoRouter, Dio. Offline-first : cache SQLite +
file `pending_operations` rejouée sur `/sync/push` (idempotence par UUID).

## Voir aussi

- [Stratégie multi-tenant](multi-tenancy.md)
- [Sécurité](security.md)
- [Modèle de données](../database/README.md)
- [Stratégie hors connexion](offline.md)
