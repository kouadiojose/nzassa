# Codes d'erreur stables — API N'Zassa Business

Le champ `error.code` de la réponse d'erreur contient l'un des codes suivants.

| Code | HTTP | Description |
|------|------|-------------|
| `VALIDATION_ERROR` | 422 | Données de requête invalides |
| `AUTH_INVALID_CREDENTIALS` | 401 | Identifiants incorrects |
| `AUTH_TOKEN_EXPIRED` | 401 | Token expiré |
| `AUTH_TOKEN_INVALID` | 401 | Token invalide ou révoqué |
| `AUTH_ACCOUNT_LOCKED` | 423 | Compte temporairement verrouillé |
| `AUTH_ACCOUNT_DISABLED` | 403 | Compte désactivé |
| `PERMISSION_DENIED` | 403 | Permission insuffisante |
| `TENANT_MISMATCH` | 404 | Ressource hors du tenant courant |
| `NOT_FOUND` | 404 | Ressource introuvable |
| `CONFLICT` | 409 | Conflit (doublon, version obsolète) |
| `IDEMPOTENCY_CONFLICT` | 409 | Clé d'idempotence réutilisée avec un corps différent |
| `BUSINESS_RULE_VIOLATION` | 422 | Règle métier violée |
| `INSUFFICIENT_STOCK` | 422 | Stock insuffisant |
| `CASH_SESSION_REQUIRED` | 422 | Aucune session de caisse ouverte |
| `SUBSCRIPTION_LIMIT_REACHED` | 402 | Limite du plan d'abonnement atteinte |
| `SUBSCRIPTION_EXPIRED` | 402 | Abonnement expiré |
| `RATE_LIMITED` | 429 | Trop de requêtes |
| `INTERNAL_ERROR` | 500 | Erreur interne |
