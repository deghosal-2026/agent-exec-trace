.PHONY: help setup format lint typecheck test stack-up stack-down clean migrate api seed-e2e migrate-db

PYTHON ?= python3
PACKAGES := packages/python-sdk services/api services/analytics

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install all Python packages for local dev.
	@for pkg in $(PACKAGES); do \
		echo "==> pip install -e $$pkg"; \
		$(PYTHON) -m pip install -e "$$pkg"; \
	done

format: ## Auto-format Python (ruff).
	@for pkg in $(PACKAGES); do \
		(cd $$pkg && ruff format . && ruff check . --fix); \
	done

lint: ## Lint Python (ruff).
	@for pkg in $(PACKAGES); do \
		(cd $$pkg && ruff check .); \
	done

typecheck: ## Type-check Python (mypy strict).
	@for pkg in $(PACKAGES); do \
		(cd $$pkg && mypy --strict .); \
	done

test: ## Run all unit tests.
	@for pkg in $(PACKAGES); do \
		echo "==> pytest $$pkg"; \
		(cd $$pkg && pytest --cov --cov-report=term); \
	done

stack-up: ## Boot the local docker compose stack.
	docker compose up -d

stack-down: ## Tear down the local docker compose stack.
	docker compose down

migrate: ## Run Alembic migrations for the analytics service.
	cd services/analytics && alembic upgrade head

api: ## Run the API service locally.
	cd services/api && uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

migrate-db: ## Create read-model tables in the compose Postgres.
	docker compose exec -T analytics python -c "\
import asyncio, asyncpg; \
async def m(): \
    c = await asyncpg.connect('postgresql://analytics:analytics@postgres:5432/analytics'); \
    await c.execute(open('src/analytics/migrations/versions/001_initial_schema.py').read() if False else ''); \
    await c.close(); \
asyncio.run(m())" || true
	@python3 scripts/migrate-db.py

seed-e2e: ## Seed the compose Postgres with mock demo data for e2e testing.
	python3 scripts/seed-e2e-data.py

clean: ## Remove generated artifacts.
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned generated artifacts."