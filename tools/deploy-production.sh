#!/usr/bin/env bash
# Deploy production stack after merge to main (same host; staging stack untouched).
#
# Requires explicit approval: CONFIRM_PROD_DEPLOY=1 ./tools/deploy-production.sh
#
# Flags: --scope auto|--bot-only|--cabinet-only|--both|--bg
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DOCKER_BUILDKIT=1

if [[ "${CONFIRM_PROD_DEPLOY:-}" != "1" ]]; then
  echo "Refusing prod deploy without CONFIRM_PROD_DEPLOY=1" >&2
  echo "After user smoke on staging + merge to main, run:" >&2
  echo "  CONFIRM_PROD_DEPLOY=1 ./tools/deploy-production.sh" >&2
  exit 1
fi

SCOPE_MODE=auto
FORCE_SCOPE=""
BG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bg) BG=1 ;;
    --bot-only) FORCE_SCOPE=bot ;;
    --cabinet-only) FORCE_SCOPE=cabinet ;;
    --both) FORCE_SCOPE="bot+cabinet" ;;
    --scope=*) SCOPE_MODE="${1#--scope=}" ;;
    --scope)
      shift
      SCOPE_MODE="${1:?--scope requires a value}"
      ;;
    -h|--help)
      cat <<'EOF'
Usage: CONFIRM_PROD_DEPLOY=1 deploy-production.sh [options]

Scope (default: auto via deploy-scope.sh):
  --scope auto|fa|bot|cabinet|bot+cabinet
  --bot-only / --cabinet-only / --both

  --bg   run in background via deploy-bg.sh
EOF
      exit 0
      ;;
    *)
      echo "Unknown: $1" >&2
      exit 1
      ;;
  esac
  shift
done

if [[ "$BG" -eq 1 ]]; then
  REARGS=()
  if [[ -n "$FORCE_SCOPE" ]]; then
    case "$FORCE_SCOPE" in
      bot) REARGS+=(--bot-only) ;;
      cabinet) REARGS+=(--cabinet-only) ;;
      bot+cabinet) REARGS+=(--both) ;;
    esac
  elif [[ "$SCOPE_MODE" != "auto" ]]; then
    REARGS+=(--scope "$SCOPE_MODE")
  fi
  exec "$ROOT/tools/deploy-bg.sh" prod "${REARGS[@]}"
fi

if [[ ! -f .env ]]; then
  echo "Missing .env" >&2
  exit 1
fi

BRANCH="$(git branch --show-current)"
if [[ "$BRANCH" != "main" ]]; then
  echo "Warning: not on main (current: $BRANCH)" >&2
fi

resolve_scope() {
  if [[ -n "$FORCE_SCOPE" ]]; then
    echo "$FORCE_SCOPE"
  elif [[ "$SCOPE_MODE" != "auto" ]]; then
    echo "$SCOPE_MODE"
  else
    "$ROOT/tools/deploy-scope.sh"
  fi
}

SCOPE="$(resolve_scope)"
echo "==> Deploy scope: $SCOPE"

echo "==> Agent smoke"
docker compose run --rm --no-deps bot python -c "import main"

sync_fa_prod() {
  if [[ -f app/localization/locales/fa.json ]]; then
    echo "==> Sync fa.json to locales mount"
    cp app/localization/locales/fa.json ./locales/fa.json
  fi
}

case "$SCOPE" in
  none)
    echo "==> No bot/cabinet/fa changes detected — nothing to deploy"
    ;;
  fa)
    sync_fa_prod
    docker compose up -d bot
    ;;
  bot)
    sync_fa_prod
    echo "==> Build + up bot"
    docker compose build bot
    docker compose up -d bot
    ;;
  cabinet)
    echo "==> Build + up cabinet-frontend"
    docker compose build cabinet-frontend
    docker compose up -d cabinet-frontend
    ;;
  bot+cabinet)
    sync_fa_prod
    echo "==> Build + up bot + cabinet-frontend"
    docker compose build bot cabinet-frontend
    docker compose up -d bot cabinet-frontend
    ;;
  *)
    echo "Unknown scope: $SCOPE" >&2
    exit 1
    ;;
esac

echo "==> Health"
docker compose ps
echo "Production deploy done. User smoke on live bot + cabinet."
