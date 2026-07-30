# Documentation API

- **OpenAPI/Swagger interactif** : `GET /docs` (développement).
- **Schéma brut** : `GET /openapi.json` — à versionner dans
  `packages/shared-contracts/openapi/` à chaque évolution majeure.
- **Codes d'erreur stables** : `packages/shared-contracts/error-codes.md`.

## Conventions

- Préfixe `/api/v1`, authentification `Authorization: Bearer <access_token>`.
- Succès : `{"success": true, "message": "…", "data": …, "meta": {…}}`
- Erreur : `{"success": false, "message": "…", "error": {"code": "…", "details": {…}}}`
- Pagination : `?page=1&per_page=20&sort_by=…&sort_dir=asc|desc&search=…` ;
  `meta` contient `page`, `per_page`, `total`, `total_pages`.
- Idempotence offline : `client_reference` (ventes/dépenses) et
  `client_operation_id` (sync) — UUID générés côté client.
- Corrélation : header `X-Correlation-ID` (généré si absent, renvoyé en réponse).

## Familles d'endpoints

| Préfixe | Domaine |
|---------|---------|
| `/auth` | inscription, connexion, refresh, sessions, OTP, mots de passe |
| `/business` | entreprise, points de vente, paramètres |
| `/members`, `/employees` | équipe, invitations, rôles |
| `/catalog` | produits, prestations, catégories, marques, unités, taxes |
| `/stock` | niveaux, mouvements, entrées/sorties, ajustements, transferts |
| `/customers` | clients + historique |
| `/sales`, `/cash` | ventes, paiements, remboursements, reçus PDF, caisse |
| `/debts` | créances clients |
| `/expenses` | dépenses |
| `/appointments` | rendez-vous |
| `/commissions` | règles et commissions |
| `/suppliers` | fournisseurs et achats |
| `/subscription` | plans et abonnement du tenant |
| `/notifications` | notifications et préférences |
| `/reports` | tableaux de bord et exports |
| `/sync` | synchronisation offline |
| `/assistant` | assistant intelligent (propositions à confirmer) |
| `/invoices` | factures et avoirs |
| `/superadmin` | administration plateforme (isolée) |
