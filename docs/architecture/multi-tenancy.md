# Stratégie multi-tenant

## Modèle : base partagée, schéma partagé, colonne `tenant_id`

Chaque table métier porte une colonne `tenant_id UUID NOT NULL` référencant
`tenants.id`, indexée, avec contraintes composites (`UNIQUE(tenant_id, …)`)
pour l'unicité par entreprise (SKU, numéro de vente, téléphone client…).

## Application de l'isolation

1. **Source de vérité** : le `tenant_id` provient exclusivement du JWT vérifié
   (`CurrentContext.tenant_id`), jamais d'un paramètre client.
2. **Couche accès** : `tenant_query(Model, tenant_id)` et
   `get_tenant_entity(...)` (nzassa/core/tenancy.py) filtrent systématiquement.
   Une entité d'un autre tenant renvoie **404 NOT_FOUND** (jamais 403) pour ne
   pas révéler l'existence de données tierces.
3. **Défense en profondeur** : `get_current_context` vérifie la cohérence
   token/tenant de l'utilisateur ; les rôles sont rattachés au tenant.
4. **Super Admin** : comptes plateforme sans tenant (`tenant_id NULL`,
   `is_superadmin = true`), espace `/superadmin` totalement séparé.

## Tests d'isolation

`apps/backend/tests/test_tenancy.py` vérifie que produits, clients et ventes
d'un tenant A sont invisibles (liste + accès direct + modification) depuis un
tenant B, et que les contraintes d'unicité sont bien par tenant.

## Évolution prévue

Ajouter PostgreSQL **Row Level Security** (politiques `USING tenant_id =
current_setting('app.tenant_id')::uuid`) comme deuxième barrière — suivi dans
docs/TECHNICAL_DEBT.md (#1).
