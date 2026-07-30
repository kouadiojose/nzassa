# Suivi de l'avancement — N'Zassa Business

Dernière mise à jour : 2026-07-30

## Modules terminés

| Module | Backend | Tests | Web | Mobile |
|--------|---------|-------|-----|--------|
| Monorepo, Docker Compose, Nginx, CI | ✅ | — | — | — |
| Socle backend (config, DB, Redis, erreurs, logs, correlation ID, pagination, réponses standard, rate limiting) | ✅ | ✅ | — | — |
| Modèle de données multi-tenant (73 tables) + migration Alembic | ✅ | ✅ | — | — |
| Authentification (register tenant, login, refresh rotatif + détection de réutilisation, verrouillage, OTP simulé, sessions/appareils, reset mot de passe) | ✅ | ✅ | ✅ | ✅ |
| RBAC (8 rôles système, permissions granulaires, guards) | ✅ | ✅ | ✅ (guards) | — |
| Entreprise, points de vente, paramètres | ✅ | ✅ | partiel | — |
| Membres/invitations, employés | ✅ | ✅ | — | — |
| Catalogue (produits, prestations, catégories, marques, unités, taxes, import/export CSV, code-barres) | ✅ | ✅ | ✅ (produits) | ✅ (lecture) |
| Stock (grand livre immuable, entrées/sorties/ajustements/transferts, verrous ligne, alertes stock faible) | ✅ | ✅ | ✅ (niveaux) | — |
| Clients (+historique, stats, fidélité) | ✅ | ✅ | ✅ | ✅ |
| Ventes (calculs serveur Decimal, numérotation verrouillée, paiements mixtes/partiels, crédit + plafond, annulation compensée, remboursements partiels, reçu PDF, idempotence offline) | ✅ | ✅ | ✅ | ✅ |
| Caisse (sessions, fond, mouvements, écart de fermeture) | ✅ | ✅ | — | — |
| Dépenses (catégories, seuil d'approbation, intégration caisse) | ✅ | ✅ | ✅ | ✅ (offline) |
| Créances clients (règlements, promesses, passage en perte, message WhatsApp) | ✅ | ✅ | — | — |
| Rendez-vous (machine à états, conflits d'horaires, report, conversion en vente) | ✅ | ✅ | — | — |
| Commissions (règles %/fixe, accumulation auto, validation/paiement/contestation) | ✅ | ✅ | — | — |
| Fournisseurs & achats (commandes, réceptions partielles → stock, paiements, dettes) | ✅ | ✅ | — | — |
| Abonnements SaaS (3 plans seedés, essai, limites appliquées, factures, abstraction paiement sans faux succès) | ✅ | ✅ | — | — |
| Notifications (canaux interne/push/email, préférences, interfaces SMS/WhatsApp) | ✅ | ✅ | — | — |
| Rapports (dashboard KPI, CA/jour, top produits, par employé, moyens de paiement, export CSV) | ✅ | ✅ | ✅ | ✅ |
| Synchronisation offline (push idempotent, pull incrémental) | ✅ | ✅ | — | ✅ |
| Assistant IA (abstraction fournisseur, parsing FR → proposition, confirmation obligatoire, Q&A) | ✅ | ✅ | — | — |
| Super Admin (dashboard global, tenants, suspension, plans, factures d'abonnement, audit, feature flags) | ✅ | ✅ | ✅ | — |
| Facturation (factures depuis ventes, avoirs, connecteur fiscal simulé en dev) | ✅ | ✅ | — | — |
| Seeders de démonstration | ✅ | ✅ | — | — |
| Plateforme web Angular 18 (auth, guards, interceptors, dashboard, POS, produits, clients, stock, dépenses, super admin) | — | ✅ 3 tests | ✅ | — |
| Application mobile Flutter (login, accueil KPI, POS offline-first, produits, clients, sync) | — | ✅ tests écrits | — | ✅ |

## Modules en cours / restants

- Web : écrans rendez-vous, commissions, fournisseurs, rapports avancés, paramètres, abonnement (l'API est prête).
- Mobile : scan de code-barres (caméra), rappels push FCM réels, écrans dettes/rendez-vous.
- Variantes produit et lots/péremption : modèle en base, endpoints à exposer.
- Inventaires complets (modèle prêt, endpoints d'inventaire à finaliser).
- E2E navigateur (Playwright) — les parcours principaux sont couverts en tests d'intégration API.

## Décisions techniques

1. **Multi-tenant** : base + schéma partagés, colonne `tenant_id` non nullable sur
   toutes les tables métier, filtrage systématique via `tenant_query`/`get_tenant_entity`
   (retour 404 — jamais 403 — pour ne rien révéler). RLS PostgreSQL prévu en défense
   supplémentaire (voir TECHNICAL_DEBT).
2. **Montants** : `Decimal`/`NUMERIC(14,2)` partout ; côté Flutter `package:decimal`,
   côté Angular les montants restent des chaînes converties à l'affichage.
3. **Numérotation** (ventes, BC, factures, avoirs) : séquence par tenant protégée par
   `pg_advisory_xact_lock` — pas de doublon sous concurrence.
4. **Stock** : chaque changement passe par `apply_movement` (SELECT FOR UPDATE +
   écriture immuable dans `stock_movements`). Corrections = mouvements de compensation.
5. **Refresh tokens** : opaques, hachés SHA-256 en base, rotation à chaque usage,
   réutilisation → révocation de toute la session (protection contre le vol).
6. **Offline mobile** : UUID client (`client_operation_id` / `client_reference`),
   file SQLite locale, push idempotent, pull incrémental par `updated_at`.
7. **Paiements SaaS** : `ManualPaymentProvider` par défaut — jamais de faux succès ;
   activation par le Super Admin après règlement vérifié.
8. **Connecteur fiscal (FNE CI)** : abstraction + connecteur SIMULÉ en dev/test
   uniquement ; en production, connecteur nul tant qu'aucune intégration agréée n'existe.
9. **Assistant IA** : `StubProvider` déterministe par règles (sans dépendance externe),
   contrat identique pour brancher Anthropic ; toute action financière exige une
   confirmation explicite (`AiActionProposal`).
10. **Dramatiq + Redis** pour les tâches asynchrones ; StubBroker en tests.
11. **Flutter sans codegen** (pas de Freezed/Drift générés) : modèles manuels et
    sqflite pour garantir un dépôt qui compile sans étape build_runner.

## Migrations appliquées

- `20260730_f86b8c9a60d2_initial_schema` — schéma initial complet (73 tables).

## Tests disponibles

- Backend : `apps/backend/tests` — 44 tests d'intégration sur PostgreSQL réel
  (auth, isolation multi-tenant, permissions par rôle, cycle de vente complet,
  caisse, stock, créances, P1, assistant, super admin, facturation, seed).
- Web : `apps/web/src/**/*.spec.ts` — 3 tests (AuthService, permissions).
- Mobile : `apps/mobile/test` — tests unitaires panier/produits + widget login.

## Commandes utiles

```bash
make backend-install && make migrate && make seed && make backend-dev
make backend-test && make backend-lint
make web-install && make web-dev        # http://localhost:4200
make web-test && make web-build
cd apps/mobile && flutter create . --platforms=android,ios && flutter test
make up                                  # stack Docker complète
```

## Limitations actuelles

- SMTP/FCM/SMS/WhatsApp : interfaces prêtes, identifiants externes requis.
- Paiements Mobile Money réels (CinetPay, Wave…) : abstraction prête, intégration à brancher.
- Export Excel : CSV livré, XLSX à ajouter (openpyxl déjà en dépendance).
- Reverse-proxy TLS/production hardening à configurer au déploiement.
