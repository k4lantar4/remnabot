#!/usr/bin/env bash
# Deploy staging stack (parallel to production on the same host).
#
# Run from repo root:
#   ./tools/deploy-staging.sh [--scope auto] [--bot-only|--cabinet-only|--both]
#   ./tools/deploy-staging.sh [--cabinet-sync|--no-cabinet-sync] [--bg] [--no-build] [--migrate]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DOCKER_BUILDKIT=1

COMPOSE=(docker compose -f "$ROOT/docker-compose.staging.yml" --env-file "$ROOT/.env.staging" -p remnawave-staging)
BUILD=1
MIGRATE=0
SCOPE_MODE=auto
FORCE_SCOPE=""
CABINET_SYNC=1
BG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build) BUILD=0 ;;
    --migrate) MIGRATE=1 ;;
    --cabinet-sync) CABINET_SYNC=1 ;;
    --no-cabinet-sync) CABINET_SYNC=0 ;;
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
Usage: deploy-staging.sh [options]

Scope (default: auto via deploy-scope.sh):
  --scope auto|fa|bot|cabinet|bot+cabinet
  --bot-only / --cabinet-only / --both   explicit override

Cabinet:
  --cabinet-sync      host npm build + dist mount (default for cabinet scope)
  --no-cabinet-sync   docker build cabinet-frontend

Other:
  --no-build          skip image builds (still runs cabinet-sync if scoped)
  --migrate           alembic upgrade after up
  --bg                run in background via deploy-bg.sh
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
  # Re-invoke self without --bg in background wrapper
  REARGS=()
  [[ "$BUILD" -eq 0 ]] && REARGS+=(--no-build)
  [[ "$MIGRATE" -eq 1 ]] && REARGS+=(--migrate)
  [[ "$CABINET_SYNC" -eq 0 ]] && REARGS+=(--no-cabinet-sync) || REARGS+=(--cabinet-sync)
  [[ -n "$FORCE_SCOPE" ]] && REARGS+=("--$FORCE_SCOPE" 2>/dev/null || true)
  if [[ -n "$FORCE_SCOPE" ]]; then
    case "$FORCE_SCOPE" in
      bot) REARGS+=(--bot-only) ;;
      cabinet) REARGS+=(--cabinet-only) ;;
      bot+cabinet) REARGS+=(--both) ;;
    esac
  elif [[ "$SCOPE_MODE" != "auto" ]]; then
    REARGS+=(--scope "$SCOPE_MODE")
  fi
  exec "$ROOT/tools/deploy-bg.sh" staging "${REARGS[@]}"
fi

if [[ ! -f .env.staging ]]; then
  echo "Missing .env.staging — copy from .env.staging.example" >&2
  exit 1
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

mkdir -p logs-staging data-staging/backups uploads-staging locales-staging
chown -R 1000:1000 logs-staging data-staging uploads-staging locales-staging 2>/dev/null || true

sync_locales_staging() {
  if [[ -f app/localization/locales/fa.json ]]; then
    cp app/localization/locales/fa.json locales-staging/fa.json
    for f in app/localization/locales/*.json; do
      base="$(basename "$f")"
      cp "$f" "locales-staging/$base"
    done
  fi
}

echo "==> Agent smoke (import main)"
docker compose run --rm --no-deps bot python -c "import main"

sync_locales_staging

build_bot() {
  if [[ "$BUILD" -eq 1 ]]; then
    echo "==> Build staging bot"
    "${COMPOSE[@]}" build bot
  else
    echo "==> Skip bot build (--no-build)"
  fi
}

build_cabinet_docker() {
  if [[ "$BUILD" -eq 1 ]]; then
    echo "==> Build staging cabinet-frontend (docker)"
    "${COMPOSE[@]}" build cabinet-frontend
  else
    echo "==> Skip cabinet docker build (--no-build)"
  fi
}

deploy_cabinet() {
  if [[ "$CABINET_SYNC" -eq 1 ]]; then
    "$ROOT/tools/staging-cabinet-sync.sh"
  else
    build_cabinet_docker
    "${COMPOSE[@]}" up -d cabinet-frontend
  fi
}

case "$SCOPE" in
  none)
    echo "==> No bot/cabinet/fa changes detected — nothing to deploy"
    ;;
  fa)
    echo "==> fa.json sync only — restart bot"
    "${COMPOSE[@]}" up -d bot
    ;;
  bot)
    build_bot
    "${COMPOSE[@]}" up -d bot
    ;;
  cabinet)
    deploy_cabinet
    ;;
  bot+cabinet)
    if [[ "$CABINET_SYNC" -eq 1 && "$BUILD" -eq 1 ]]; then
      echo "==> Parallel: bot docker build + staging cabinet sync"
      build_bot &
      PID_BOT=$!
      "$ROOT/tools/staging-cabinet-sync.sh" &
      PID_CAB=$!
      wait "$PID_BOT"
      wait "$PID_CAB"
      "${COMPOSE[@]}" up -d bot
    elif [[ "$CABINET_SYNC" -eq 1 ]]; then
      deploy_cabinet
      "${COMPOSE[@]}" up -d bot
    else
      if [[ "$BUILD" -eq 1 ]]; then
        echo "==> Build bot + cabinet-frontend"
        "${COMPOSE[@]}" build bot cabinet-frontend
      fi
      "${COMPOSE[@]}" up -d bot cabinet-frontend
    fi
    ;;
  *)
    echo "Unknown scope: $SCOPE" >&2
    exit 1
    ;;
esac

if [[ "$MIGRATE" -eq 1 ]]; then
  echo "==> Alembic migrate (staging DB)"
  "${COMPOSE[@]}" run --rm bot alembic upgrade head
fi

echo "==> Health"
"${COMPOSE[@]}" ps
echo "Staging ready. Check .env.staging for BOT_USERNAME, CABINET_URL, WEBHOOK_URL"
