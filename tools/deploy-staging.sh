#!/usr/bin/env bash
# Deploy staging stack (parallel to production on the same host).
# Run from repo root: ./tools/deploy-staging.sh [--no-build] [--migrate]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f "$ROOT/docker-compose.staging.yml" --env-file "$ROOT/.env.staging" -p remnawave-staging)
BUILD=1
MIGRATE=0

for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD=0 ;;
    --migrate) MIGRATE=1 ;;
    -h|--help)
      echo "Usage: $0 [--no-build] [--migrate]"
      exit 0
      ;;
    *) echo "Unknown: $arg" >&2; exit 1 ;;
  esac
done

if [[ ! -f .env.staging ]]; then
  echo "Missing .env.staging — copy from .env.staging.example" >&2
  exit 1
fi

mkdir -p logs-staging data-staging/backups uploads-staging locales-staging

# App container runs as uid 1000
chown -R 1000:1000 logs-staging data-staging uploads-staging locales-staging 2>/dev/null || true

# Bot locales mount (source of truth in repo)
if [[ -f app/localization/locales/fa.json ]]; then
  cp app/localization/locales/fa.json locales-staging/fa.json
  for f in app/localization/locales/*.json; do
    base="$(basename "$f")"
    cp "$f" "locales-staging/$base"
  done
fi

echo "==> Agent smoke (import main)"
docker compose run --rm --no-deps bot python -c "import main"

if [[ "$BUILD" -eq 1 ]]; then
  echo "==> Build staging images"
  "${COMPOSE[@]}" build bot cabinet-frontend
else
  echo "==> Skip build (--no-build)"
fi

echo "==> Up staging stack"
"${COMPOSE[@]}" up -d bot cabinet-frontend

if [[ "$MIGRATE" -eq 1 ]]; then
  echo "==> Alembic migrate (staging DB)"
  "${COMPOSE[@]}" run --rm bot alembic upgrade head
fi

echo "==> Health"
"${COMPOSE[@]}" ps
echo "Staging ready. Check .env.staging for BOT_USERNAME, CABINET_URL, WEBHOOK_URL"
