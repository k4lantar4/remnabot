# remnabot — production + staging (same host). Secrets: .env / .env.staging (gitignored).
SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE_PROD    := docker compose
COMPOSE_STAGING := docker compose -f docker-compose.staging.yml --env-file .env.staging -p remnawave-staging
STAGING_DEPLOY  := ./tools/deploy-staging.sh
PROD_DEPLOY     := ./tools/deploy-production.sh
SHIP            := ./tools/ship-after-smoke.sh

.PHONY: help smoke sync-fa sync-fa-staging check-admin-texts setup-cursor \
	prod-ps prod-logs prod-build prod-up prod-deploy \
	staging-ps staging-logs staging-down staging-deploy staging-rebuild \
	staging-migrate staging-health staging-cabinet-build \
	ship up up-follow down reload reload-follow \
	test lint format fix migrate migration migrate-stamp migrate-history

help: ## Show all targets
	@echo ""
	@echo "Development & deploy (production + staging on same host)"
	@echo ""
	@awk -F':.*## ' '/^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Typical i18n sprint:"
	@echo "  make smoke && make staging-rebuild && make staging-health"
	@echo "  (user smoke) CONFIRM_SHIP=1 make ship BRANCH=i18n/foo"
	@echo "  CONFIRM_PROD_DEPLOY=1 make prod-deploy"
	@echo ""

# --- Agent smoke (every commit) ---

smoke: ## import main (production image, no deps)
	$(COMPOSE_PROD) run --rm --no-deps bot python -c "import main"

check-admin-texts: ## Must be 0 — no get_admin_texts in app/
	@! grep -r get_admin_texts app/ || (echo "FAIL: get_admin_texts found" >&2; exit 1)
	@echo "OK: no get_admin_texts"

setup-cursor: ## Bootstrap .cursor/mcp.json + pull MCP Docker images
	@chmod +x tools/setup-cursor-mcp.sh .cursor/hooks/session-start.sh 2>/dev/null || true
	./tools/setup-cursor-mcp.sh

sync-fa: ## Copy fa.json → ./locales/ (production mount)
	@test -f app/localization/locales/fa.json
	cp app/localization/locales/fa.json ./locales/fa.json
	@echo "Synced fa.json → ./locales/"

sync-fa-staging: ## Copy all locale JSON → ./locales-staging/
	@test -f app/localization/locales/fa.json
	@mkdir -p locales-staging
	@cp app/localization/locales/*.json locales-staging/
	@echo "Synced locales → ./locales-staging/"

# --- Production ---

prod-ps: ## Production container status
	$(COMPOSE_PROD) ps

prod-logs: ## Tail production bot logs
	$(COMPOSE_PROD) logs -f --tail=100 bot

prod-build: ## Build production bot + cabinet images
	$(COMPOSE_PROD) build bot cabinet-frontend

prod-up: sync-fa ## Build + up production bot + cabinet (sync fa.json first)
	$(COMPOSE_PROD) build bot cabinet-frontend
	$(COMPOSE_PROD) up -d bot cabinet-frontend
	$(COMPOSE_PROD) ps

prod-deploy: ## Production deploy (requires CONFIRM_PROD_DEPLOY=1)
	$(PROD_DEPLOY)

# --- Staging (parallel stack, ports 8081 / 3021) ---

staging-ps: ## Staging container status
	$(COMPOSE_STAGING) ps

staging-logs: ## Tail staging bot logs
	$(COMPOSE_STAGING) logs -f --tail=100 bot

staging-down: ## Stop staging stack (keeps volumes)
	$(COMPOSE_STAGING) down --remove-orphans

staging-deploy: smoke ## Full staging deploy: smoke + build + up + sync locales
	$(STAGING_DEPLOY)

staging-rebuild: staging-deploy ## Alias: rebuild staging bot + cabinet after code/locale changes

staging-migrate: smoke ## Staging deploy + alembic upgrade (fresh DB / new revision)
	$(STAGING_DEPLOY) --migrate

staging-cabinet-build: ## Rebuild only staging cabinet (after VITE_* / cabinet src change)
	@test -f .env.staging || (echo "Missing .env.staging" >&2; exit 1)
	$(COMPOSE_STAGING) build cabinet-frontend
	$(COMPOSE_STAGING) up -d cabinet-frontend
	@echo "Cabinet: https://staging-host-cabinet.rookari.com (check BOT_USERNAME / BotFather domain)"

staging-health: ## HTTP health check staging bot (localhost:8081 + public hooks)
	@test -f .env.staging || (echo "Missing .env.staging" >&2; exit 1)
	@TOKEN=$$(grep '^WEB_API_DEFAULT_TOKEN=' .env.staging | cut -d= -f2-); \
	echo -n "localhost:8081/health → "; \
	curl -sf "http://127.0.0.1:8081/health" -H "X-API-Key: $$TOKEN" | head -c 120; echo; \
	echo -n "staging-host-hooks/health → "; \
	curl -sf "https://staging-host-hooks.rookari.com/health" -H "X-API-Key: $$TOKEN" | head -c 120; echo; \
	echo -n "staging-host-cabinet → "; \
	curl -sf -o /dev/null -w "HTTP %{http_code}\n" "https://staging-host-cabinet.rookari.com/"

ship: ## Push branch + PR after staging smoke (requires CONFIRM_SHIP=1, optional BRANCH=)
	$(SHIP) $(BRANCH)

# --- Legacy production shortcuts ---

up: prod-up ## Alias: production build + up

up-follow: ## Production build + up (foreground logs)
	$(COMPOSE_PROD) up --build

down: ## Stop production stack
	$(COMPOSE_PROD) down

reload: down up ## Restart production (build + up)

reload-follow: down up-follow ## Restart production with logs

# --- Python / DB (host, not Docker) ---

test: ## Run pytest
	uv run pytest -v

lint: ## ruff check
	uv run ruff check .

format: ## ruff format
	uv run ruff format .

fix: ## ruff fix + format
	uv run ruff check . --fix
	uv run ruff format .

migrate: ## Alembic upgrade (host env — prefer staging-migrate for staging DB)
	uv run alembic upgrade head

migration: ## New migration (make migration m="description")
	uv run alembic revision --autogenerate -m "$(m)"

migrate-stamp: ## Alembic stamp head
	uv run alembic stamp head

migrate-history: ## Alembic history
	uv run alembic history --verbose
