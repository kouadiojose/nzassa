# Guide d'installation et de déploiement

## Prérequis

- Docker + Docker Compose (recommandé) **ou** Python 3.13, Node 22, Flutter stable
- PostgreSQL 16, Redis 7 (fournis par Docker Compose)

## Démarrage avec Docker

```bash
cp .env.example .env          # adapter SECRET_KEY, mots de passe…
make up                       # postgres, redis, backend, worker, web, nginx
docker compose exec backend alembic upgrade head
docker compose exec backend python -m nzassa.seeds.demo
```

- Web : http://localhost:4200 (ou http://localhost:8080 via Nginx)
- API/Docs : http://localhost:8000/docs
- Health : http://localhost:8000/api/v1/health/ready

## Démarrage sans Docker

```bash
# Backend
make backend-install
make migrate && make seed
make backend-dev              # :8000

# Web
make web-install && make web-dev   # :4200 (proxy /api -> :8000)

# Mobile
cd apps/mobile
flutter create . --platforms=android,ios
flutter run --dart-define=NZASSA_API_URL=http://10.0.2.2:8000
```

## Accès de démonstration (LOCAL uniquement — jamais en production)

| Rôle | Email | Mot de passe |
|------|-------|--------------|
| Super Admin | admin@nzassa.app | Demo#Nzassa2026 |
| Propriétaire | demo@nzassa.app | Demo#Nzassa2026 |
| Gérant | gerant@nzassa.app | Demo#Nzassa2026 |
| Caissier | caisse@nzassa.app | Demo#Nzassa2026 |
| Vendeur | vente@nzassa.app | Demo#Nzassa2026 |

## Production — points d'attention

1. `NZASSA_ENV=production`, `NZASSA_DEBUG=false`, `SECRET_KEY` fort
   (`openssl rand -hex 32`), CORS restreint aux domaines réels.
2. TLS sur Nginx (certbot), en-têtes HSTS.
3. Sauvegardes PostgreSQL (voir ci-dessous), monitoring Sentry/Prometheus.
4. Ne jamais exposer `/docs` publiquement (désactivé automatiquement en prod).

## Sauvegarde / restauration PostgreSQL

```bash
# Sauvegarde quotidienne (cron)
pg_dump -Fc -h localhost -U nzassa nzassa > backup_$(date +%F).dump

# Restauration
createdb -U nzassa nzassa_restore
pg_restore -U nzassa -d nzassa_restore backup_2026-07-30.dump
```

Conserver 7 sauvegardes quotidiennes + 4 hebdomadaires ; tester la
restauration chaque mois.
