# N'Zassa Business

> **L'assistant intelligent des entrepreneurs africains.**
> *Gérez. Vendez. Grandissez.*

N'Zassa Business est une solution SaaS de gestion destinée aux instituts de beauté, salons de coiffure, boutiques de cosmétiques, petits commerces, prestataires de services et PME africaines — y compris les entreprises multi-points de vente.

## Composants

| Composant | Techno | Répertoire |
|-----------|--------|------------|
| API Backend | Python 3.13 · FastAPI · PostgreSQL · SQLAlchemy 2 · Redis | `apps/backend/` |
| Plateforme Web (Entreprise + Super Admin) | Angular 18 · Signals · PrimeNG · Tailwind | `apps/web/` |
| Application mobile (Android/iOS) | Flutter · Riverpod · GoRouter · Drift | `apps/mobile/` |
| Contrats partagés | OpenAPI / JSON schemas | `packages/shared-contracts/` |
| Infrastructure | Docker · Nginx · Prometheus/Grafana | `infrastructure/` |

## Démarrage rapide

```bash
cp .env.example .env
make up            # démarre PostgreSQL, Redis, backend, web via Docker Compose
make migrate       # applique les migrations Alembic
make seed          # charge les données de démonstration
```

Sans Docker :

```bash
make backend-install && make backend-dev    # API sur http://localhost:8000
make web-install && make web-dev            # Web sur http://localhost:4200
```

- Documentation API interactive : http://localhost:8000/docs
- Health check : http://localhost:8000/api/v1/health

## Documentation

- [Avancement du développement](docs/DEVELOPMENT_PROGRESS.md)
- [Architecture](docs/architecture/README.md)
- [Modèle de données](docs/database/README.md)
- [Stratégie multi-tenant](docs/architecture/multi-tenancy.md)
- [Guide d'installation](docs/deployment/installation.md)
- [Sécurité](docs/architecture/security.md)
- [Dette technique](docs/TECHNICAL_DEBT.md)

## Licence

Propriétaire — © N'Zassa Business.
