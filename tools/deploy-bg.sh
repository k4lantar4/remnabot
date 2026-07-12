#!/usr/bin/env bash
# Run staging or production deploy in background; do not block the caller.
#
# Usage:
#   ./tools/deploy-bg.sh staging [-- flags for deploy-staging.sh]
#   CONFIRM_PROD_DEPLOY=1 ./tools/deploy-bg.sh prod [-- flags for deploy-production.sh]
#
# Prints log path and PID; exits immediately.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TARGET="${1:-}"
shift || true

if [[ -z "$TARGET" ]]; then
  echo "Usage: $0 staging|prod [-- deploy flags...]" >&2
  exit 1
fi

case "$TARGET" in
  staging)
    SCRIPT="$ROOT/tools/deploy-staging.sh"
    ;;
  prod|production)
    SCRIPT="$ROOT/tools/deploy-production.sh"
    TARGET=prod
    ;;
  *)
    echo "Unknown target: $TARGET (use staging or prod)" >&2
    exit 1
    ;;
esac

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG="/tmp/remnabot-deploy-${TARGET}-${TIMESTAMP}.log"

# Filter --bg if accidentally passed through
ARGS=()
for arg in "$@"; do
  [[ "$arg" == "--bg" ]] && continue
  ARGS+=("$arg")
done

setsid env DOCKER_BUILDKIT=1 "$SCRIPT" "${ARGS[@]}" >"$LOG" 2>&1 &
PID=$!

echo "Deploy started in background (target=$TARGET)"
echo "PID=$PID"
echo "LOG=$LOG"
echo "Tail: tail -f $LOG"
