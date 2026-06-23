#!/usr/bin/env bash
# Session start: ensure MCP config exists; inject workflow reminder for the agent.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MCP_JSON="$ROOT/.cursor/mcp.json"
MCP_EXAMPLE="$ROOT/.cursor/mcp.json.example"

if [[ ! -f "$MCP_JSON" && -f "$MCP_EXAMPLE" ]]; then
  cp "$MCP_EXAMPLE" "$MCP_JSON"
fi

# sessionStart hook output (additional_context when supported)
cat <<'EOF'
{
  "additional_context": "remnabot dev: Follow .cursor/rules/autonomous-dev-workflow.mdc — plan, implement, make staging-rebuild without per-chat briefing; ship/merge/prod only after user تایید. MCP: remnawave-postgres/redis (production read-only), remnawave-staging-postgres/redis (staging). Prefer staging MCP when debugging staging smoke. Setup: make setup-cursor. Never prod docker compose for UI iteration."
}
EOF
