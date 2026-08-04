.PHONY: help setup lint format test typecheck stack-up stack-down clean

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

clean: ## Remove generated artifacts.
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned generated artifacts."