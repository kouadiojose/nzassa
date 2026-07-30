# Monitoring

- **Sentry** : renseigner `SENTRY_DSN` dans `.env` (intégration FastAPI à
  activer au déploiement).
- **Prometheus/Grafana** : exposer les métriques via
  `prometheus-fastapi-instrumentator` (à ajouter au déploiement production) ;
  provisionner Grafana avec les dashboards FastAPI + PostgreSQL standard.
- **Health checks** : `/api/v1/health` (liveness) et `/api/v1/health/ready`
  (readiness : PostgreSQL + Redis) — déjà branchés dans Docker Compose.
- **Logs** : JSON structuré en production (structlog), corrélation par
  `correlation_id`, tenant_id attaché automatiquement.
