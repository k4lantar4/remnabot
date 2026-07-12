#!/usr/bin/env bash
# Detect deploy scope from git changes vs main (branch + working tree).
# Outputs one of: fa, bot, cabinet, bot+cabinet, none
#
# Usage:
#   ./tools/deploy-scope.sh              # auto-detect
#   ./tools/deploy-scope.sh --bot-only   # force bot
#   ./tools/deploy-scope.sh --cabinet-only
#   ./tools/deploy-scope.sh --both
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FORCE=""

for arg in "$@"; do
  case "$arg" in
    --bot-only) FORCE=bot ;;
    --cabinet-only) FORCE=cabinet ;;
    --both) FORCE="bot+cabinet" ;;
    -h|--help)
      cat <<'EOF'
Usage: deploy-scope.sh [--bot-only|--cabinet-only|--both]

Prints deploy scope: fa | bot | cabinet | bot+cabinet | none
Override flags always win over auto-detection.
EOF
      exit 0
      ;;
    *) echo "Unknown: $arg" >&2; exit 1 ;;
  esac
done

if [[ -n "$FORCE" ]]; then
  echo "$FORCE"
  exit 0
fi

collect_changed_files() {
  {
    git diff --name-only main...HEAD 2>/dev/null || true
    git diff --name-only --cached
    git diff --name-only
  } | sort -u | grep -v '^$' || true
}

bot_code=0
cabinet_code=0
fa_changed=0

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  case "$f" in
    cabinet/src/*)
      cabinet_code=1
      ;;
    app/localization/locales/fa.json)
      fa_changed=1
      ;;
    app/*|migrations/*)
      bot_code=1
      ;;
  esac
done < <(collect_changed_files)

if [[ "$bot_code" -eq 1 && "$cabinet_code" -eq 1 ]]; then
  echo "bot+cabinet"
elif [[ "$bot_code" -eq 1 ]]; then
  echo "bot"
elif [[ "$cabinet_code" -eq 1 ]]; then
  echo "cabinet"
elif [[ "$fa_changed" -eq 1 ]]; then
  echo "fa"
else
  echo "none"
fi
