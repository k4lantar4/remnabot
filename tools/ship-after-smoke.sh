#!/usr/bin/env bash
# Ship feature branch after user staging smoke approval.
# Does NOT merge without CONFIRM_SHIP=1 and prints smoke-map reminder.
#
# Usage (after staging smoke on same host):
#   CONFIRM_SHIP=1 ./tools/ship-after-smoke.sh [branch-name]
#
# Steps: push branch → gh pr create (if needed) → wait for user to merge via gh OR print instructions
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${CONFIRM_SHIP:-}" != "1" ]]; then
  echo "Refusing ship without CONFIRM_SHIP=1 (user must approve staging smoke first)" >&2
  exit 1
fi

BRANCH="${1:-$(git branch --show-current)}"
if [[ "$BRANCH" == "main" || "$BRANCH" == "dev-local" ]]; then
  echo "Refusing to ship from $BRANCH — use a feature branch" >&2
  exit 1
fi

REMOTE="${GIT_REMOTE:-remnabot}"
GITHUB_REPO="${GITHUB_REPO:-k4lantar4/remnabot}"
GH=(gh -R "$GITHUB_REPO")

echo "==> Push $BRANCH to $REMOTE"
git push -u "$REMOTE" "$BRANCH"

if command -v gh >/dev/null 2>&1; then
  if "${GH[@]}" pr view "$BRANCH" --json url -q .url 2>/dev/null; then
    PR_URL="$("${GH[@]}" pr view "$BRANCH" --json url -q .url)"
    echo "PR exists: $PR_URL"
  else
    SMOKE_MAP="docs/templates/smoke-map.md"
    BODY_FILE="$(mktemp)"
    if [[ -f "$SMOKE_MAP" ]]; then
      {
        echo "## Summary"
        echo "Staging smoke approved. See smoke map below."
        echo ""
        cat "$SMOKE_MAP"
        echo ""
        echo "## Test plan"
        echo "- [x] Staging Telegram smoke (user)"
        echo "- [ ] Production smoke after merge"
      } > "$BODY_FILE"
    else
      echo "Staging smoke approved." > "$BODY_FILE"
    fi
    "${GH[@]}" pr create --base main --head "$BRANCH" --title "$BRANCH" --body-file "$BODY_FILE"
    rm -f "$BODY_FILE"
  fi
  echo ""
  echo "Next (after user تایید): ${GH[*]} pr merge <number> --merge"
  echo "Then: git checkout main && git pull $REMOTE main && CONFIRM_PROD_DEPLOY=1 ./tools/deploy-production.sh"
else
  echo "gh not installed — open PR manually on GitHub"
fi
