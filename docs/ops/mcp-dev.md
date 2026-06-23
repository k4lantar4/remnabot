# Cursor MCP — Postgres, Redis, and remnabot dev tools

Project config: `.cursor/mcp.json` (copy from `.cursor/mcp.json.example` if missing).

Bootstrap:

```bash
make setup-cursor
uv sync   # dev dep `mcp` for remnawave-dev server
# then reload Cursor window
```

## Servers

| MCP name | Stack | Network | envFile | Use for |
|----------|-------|---------|---------|---------|
| `remnawave-postgres` | Production | `bot-remnawave_bot_network` | `.env` | Read-only schema/queries on live prod DB |
| `remnawave-redis` | Production | `bot-remnawave_bot_network` | `.env` | Cart/cache keys on prod Redis |
| `remnawave-staging-postgres` | Staging | `remnawave-staging_staging_network` | `.env.staging` | Staging DB after `make staging-rebuild` |
| `remnawave-staging-redis` | Staging | `remnawave-staging_staging_network` | `.env.staging` | Staging carts/cache |
| `remnawave-dev` | Staging (host) | localhost + Docker CLI | `.env.staging` | Bot health, logs, Telegram API info; optional webhook inject |

Postgres MCP runs with `--access-mode=restricted` (read-only).

### remnawave-dev tools

Read-only (always available when server is running):

| Tool | Purpose |
|------|---------|
| `staging_compose_ps_tool` | `docker compose … ps` for staging stack |
| `staging_bot_health_tool` | `GET /health` + `/health/telegram-webhook` on `127.0.0.1:8081` |
| `tail_staging_bot_logs_tool` | Last N lines of staging bot container logs |
| `read_staging_log_file_tool` | Tail of `logs-staging/current/{bot,error,payments}.log` |
| `telegram_bot_api_info_tool` | Telegram `getMe` + `getWebhookInfo` for staging `BOT_TOKEN` |

Write tools (staging only, opt-in via `REMNAWAVE_DEV_MCP_WRITE=1` in `.env.staging`):

| Tool | Purpose |
|------|---------|
| `inject_staging_webhook_tool` | POST synthetic Update to staging webhook (runs real handlers) |
| `send_test_notification_tool` | Run `tools/send_monitoring_expiring_test.py` in staging container |

Set `DEV_MCP_TELEGRAM_ID` (or `ADMIN_IDS`) for default telegram_id on write tools.

## When the agent should use MCP

- Verifying balances, subscriptions, migrations, row counts — **`remnawave-staging-postgres`** (or prod when necessary), do not guess.
- Bot process health, webhook queue mode, container logs — **`remnawave-dev`**.
- Debugging **staging smoke** — prefer **`remnawave-staging-*`** + **`remnawave-dev`**; never production for UI iteration.
- Production incidents / live user data — **`remnawave-postgres`** / **`remnawave-redis`** only when necessary; never write via MCP.

Plugin MCPs (Cursor marketplace): **context7** for library docs; ignore **neon-postgres** (not this Docker DB).

## Prerequisites

1. Docker running on the host.
2. `.env` (prod) and `.env.staging` present (gitignored).
3. `uv sync` on host (installs `mcp` dev dependency).
4. Stacks up:
   - Prod DB: `docker compose up -d postgres redis`
   - Staging: `make staging-rebuild`
5. Images: `crystaldba/postgres-mcp`, `mcp/redis` (pulled by `make setup-cursor`).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| MCP server not listed | Reload Cursor; check `.cursor/mcp.json` exists |
| `remnawave-dev` fails to start | Run `uv sync`; verify `uv` on PATH |
| Connection refused (health) | `make staging-ps`; staging bot must map `8081:8080` |
| Auth failed (health) | Check `WEB_API_DEFAULT_TOKEN` in `.env.staging` |
| Staging MCP fails | Run `make staging-ps`; network must be `remnawave-staging_staging_network` |
| Write tools missing | Set `REMNAWAVE_DEV_MCP_WRITE=1` in `.env.staging` and reload Cursor |

## Security

- Passwords and tokens stay in `.env` / `.env.staging` only (`envFile` in mcp.json).
- Do not commit secrets or paste connection strings in chat.
- Write tools mutate staging DB / send real Telegram messages — staging only.
- MCP does not replace `delivery-cycle.mdc` smoke or user approval for deploy.

## Hooks

`.cursor/hooks.json` runs `session-start.sh` on each agent session — ensures `mcp.json` exists and reminds the agent of `autonomous-dev-workflow.mdc`.
