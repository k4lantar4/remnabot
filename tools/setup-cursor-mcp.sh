#!/usr/bin/env bash
# Bootstrap Cursor MCP for remnabot (prod + staging Docker MCP sidecars).
# Safe to run repeatedly. Does not print secrets.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MCP_JSON="$ROOT/.cursor/mcp.json"
MCP_EXAMPLE="$ROOT/.cursor/mcp.json.example"

echo "==> Cursor MCP setup"

if [[ ! -f "$MCP_JSON" ]]; then
  cp "$MCP_EXAMPLE" "$MCP_JSON"
  echo "Created .cursor/mcp.json from example"
fi

for f in .env .env.staging; do
  if [[ ! -f "$f" ]]; then
    echo "WARN: missing $f — MCP servers using envFile $f will fail until file exists" >&2
  fi
done

echo "==> Pull MCP images (idempotent)"
docker pull crystaldba/postgres-mcp:latest
docker pull mcp/redis:latest

echo "==> Check Docker networks"
for net in bot-remnawave_bot_network remnawave-staging_staging_network; do
  if docker network inspect "$net" >/dev/null 2>&1; then
    echo "  OK $net"
  else
    echo "  MISSING $net — start prod: docker compose up -d postgres redis; staging: make staging-rebuild" >&2
  fi
done

echo "==> Check DB containers"
for c in remnawave_bot_db remnawave_staging_db; do
  if docker ps --format '{{.Names}}' | grep -qx "$c"; then
    echo "  OK $c running"
  else
    echo "  WARN $c not running" >&2
  fi
done

echo ""
echo "Done. Reload Cursor window (or restart) so MCP servers connect."
echo "Dev MCP: run 'uv sync' if remnawave-dev server fails (needs mcp dev dep)."
echo "Docs: docs/ops/mcp-dev.md | rule: .cursor/rules/mcp-dev.mdc"
