.PHONY: help up down logs migrate seed backend-install backend-dev backend-test backend-lint web-install web-dev web-test web-build mobile-get mobile-test lint test

help: ## Affiche l'aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------- Docker ----------
up: ## Démarre toute la stack via Docker Compose
	docker compose up -d --build

down: ## Arrête la stack
	docker compose down

logs: ## Suit les logs
	docker compose logs -f

# ---------- Backend ----------
backend-install: ## Installe les dépendances backend
	cd apps/backend && python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]"

backend-dev: ## Démarre l'API en mode développement
	cd apps/backend && .venv/bin/uvicorn nzassa.main:app --reload --host 0.0.0.0 --port 8000

migrate: ## Applique les migrations Alembic
	cd apps/backend && .venv/bin/alembic upgrade head

migration: ## Crée une migration (make migration m="message")
	cd apps/backend && .venv/bin/alembic revision --autogenerate -m "$(m)"

seed: ## Charge les données de démonstration
	cd apps/backend && .venv/bin/python -m nzassa.seeds.demo

backend-test: ## Lance les tests backend
	cd apps/backend && .venv/bin/pytest -q

backend-lint: ## Ruff + Mypy
	cd apps/backend && .venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests && .venv/bin/mypy src

# ---------- Web ----------
web-install: ## Installe les dépendances Angular
	cd apps/web && npm ci

web-dev: ## Démarre le serveur de dev Angular
	cd apps/web && npm start

web-test: ## Tests Angular
	cd apps/web && npm test -- --watch=false --browsers=ChromeHeadlessNoSandbox

web-build: ## Build de production Angular
	cd apps/web && npm run build

# ---------- Mobile ----------
mobile-get: ## Récupère les dépendances Flutter
	cd apps/mobile && flutter pub get

mobile-test: ## Tests Flutter
	cd apps/mobile && flutter test

# ---------- Agrégats ----------
lint: backend-lint ## Tous les linters

test: backend-test ## Tous les tests exécutables localement
