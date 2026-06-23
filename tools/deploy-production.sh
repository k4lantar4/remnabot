#!/usr/bin/env bash
# Deploy production stack after merge to main (same host; staging stack untouched).
# Requires explicit approval: CONFIRM_PROD_DEPLOY=1 ./tools/deploy-production.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${CONFIRM_PROD_DEPLOY:-}" != "1" ]]; then
  echo "Refusing prod deploy without CONFIRM_PROD_DEPLOY=1" >&2
  echo "After user smoke on staging + merge to main, run:" >&2
  echo "  CONFIRM_PROD_DEPLOY=1 ./tools/deploy-production.sh" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Missing .env" >&2
  exit 1
fi

BRANCH="$(git branch --show-current)"
if [[ "$BRANCH" != "main" ]]; then
  echo "Warning: not on main (current: $BRANCH)" >&2
fi

echo "==> Agent smoke"
docker compose run --rm --no-deps bot python -c "import main"

if [[ -f app/localization/locales/fa.json ]]; then
  echo "==> Sync fa.json to locales mount"
  cp app/localization/locales/fa.json ./locales/fa.json
fi

echo "==> Build + up production"
docker compose build bot cabinet-frontend
docker compose up -d bot cabinet-frontend

echo "==> Health"
docker compose ps
echo "Production deploy done. User smoke on live bot + cabinet."
