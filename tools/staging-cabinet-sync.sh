#!/usr/bin/env bash
# Fast staging cabinet path: host npm build + nginx serves mounted dist.
# Skips docker build cabinet-frontend when dist/ is fresh enough.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f "$ROOT/docker-compose.staging.yml" --env-file "$ROOT/.env.staging" -p remnawave-staging)

if [[ ! -f .env.staging ]]; then
  echo "Missing .env.staging" >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a
source "$ROOT/.env.staging"
set +a

export VITE_API_URL="${VITE_API_URL:-/api}"
export VITE_TELEGRAM_BOT_USERNAME="${VITE_TELEGRAM_BOT_USERNAME:-${BOT_USERNAME:-}}"
export VITE_APP_NAME="${VITE_APP_NAME:-Moon VPN Staging}"
export VITE_APP_LOGO="${VITE_APP_LOGO:-V}"

echo "==> Staging cabinet host build (VITE_APP_NAME=$VITE_APP_NAME)"
cd "$ROOT/cabinet"
if [[ ! -d node_modules ]]; then
  echo "==> npm ci (first run)"
  npm ci
fi
npm run build

echo "==> Restart staging cabinet-frontend (dist mount)"
cd "$ROOT"
"${COMPOSE[@]}" up -d cabinet-frontend
"${COMPOSE[@]}" ps cabinet-frontend
echo "Staging cabinet sync done."
