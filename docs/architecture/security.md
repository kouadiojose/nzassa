# Sécurité

## Authentification

- Mots de passe **Argon2** (argon2-cffi, paramètres par défaut recommandés).
- **Access token JWT** courte durée (15 min) signé HS256 (`SECRET_KEY`).
- **Refresh token opaque** (48 octets aléatoires) : seule l'empreinte SHA-256
  est stockée ; **rotation à chaque usage** ; la réutilisation d'un token
  consommé révoque toute la session (défense contre le vol de token).
- **Verrouillage** : 5 échecs → 15 min de blocage (configurable). Toutes les
  tentatives sont journalisées (`login_attempts`).
- OTP email/téléphone à 6 chiffres, TTL Redis ; OTP téléphone **simulé** en
  développement (loggé), connecteur SMS à brancher.
- Révocation de session par appareil (`device_sessions`).
- Reset mot de passe : token opaque haché, TTL 30 min, révoque toutes les sessions.

## Autorisation

- RBAC : 8 rôles système (Propriétaire, Administrateur, Gérant, Caissier,
  Vendeur, Employé, Comptable, Lecteur) + permissions granulaires
  `module.action` (nzassa/core/rbac.py).
- Guards FastAPI `require_permissions("sales.create")` sur chaque endpoint ;
  guards équivalents côté Angular (routes) et vérifications d'UI.
- Espace Super Admin isolé (`require_superadmin`).

## Protection de la plateforme

- Rate limiting Redis par IP (global + durci sur `/auth/*`) + limite Nginx.
- Headers de sécurité (nosniff, DENY, referrer-policy, no-store) via middleware
  et Nginx ; CORS restrictif par configuration.
- Correlation ID sur chaque requête (header `X-Correlation-ID`, logs, audit).
- Journal d'audit append-only (`audit_logs`) pour toutes les opérations
  sensibles (connexions, annulations, suspensions, write-off, etc.).
- Erreurs normalisées : aucune stack trace exposée, codes stables.
- Uploads : validation MIME et taille max configurée (`MAX_UPLOAD_SIZE_MB`).

## Données financières

- `Decimal`/NUMERIC uniquement, calculs exclusivement côté backend.
- Ventes validées jamais supprimées : annulation avec auteur, date, motif,
  état précédent et mouvements de compensation (stock + caisse).
- Mouvements de stock immuables ; commissions validées jamais recalculées.

## Secrets

Aucun secret en dur : tout passe par variables d'environnement (.env non
commité, `.env.example` documenté). Les identifiants de démo ne sont valables
qu'en local.
