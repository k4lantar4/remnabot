# Cursor MCP — Postgres & Redis (production + staging)

Project config: `.cursor/mcp.json` (copy from `.cursor/mcp.json.example` if missing).

Bootstrap:

```bash
make setup-cursor
# then reload Cursor window
```

## Servers

| MCP name | Stack | Network | envFile | Use for |
|----------|-------|---------|---------|---------|
| `remnawave-postgres` | Production | `bot-remnawave_bot_network` | `.env` | Read-only schema/queries on live prod DB |
| `remnawave-redis` | Production | `bot-remnawave_bot_network` | `.env` | Cart/cache keys on prod Redis |
| `remnawave-staging-postgres` | Staging | `remnawave-staging_staging_network` | `.env.staging` | Staging DB after `make staging-rebuild` |
| `remnawave-staging-redis` | Staging | `remnawave-staging_staging_network` | `.env.staging` | Staging carts/cache |

Postgres MCP runs with `--access-mode=restricted` (read-only).

## When the agent should use MCP

- Verifying balances, subscriptions, migrations, row counts — **use MCP**, do not guess.
- Debugging **staging smoke** — prefer **`remnawave-staging-*`** servers.
- Production incidents / live user data — **`remnawave-postgres`** / **`remnawave-redis`** only when necessary; never write via MCP.

Plugin MCPs (Cursor marketplace): **context7** for library docs; ignore **neon-postgres** (not this Docker DB).

## Prerequisites

1. Docker running on the host.
2. `.env` (prod) and `.env.staging` present (gitignored).
3. Stacks up:
   - Prod DB: `docker compose up -d postgres redis`
   - Staging: `make staging-rebuild`
4. Images: `crystaldba/postgres-mcp`, `mcp/redis` (pulled by `make setup-cursor`).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| MCP server not listed | Reload Cursor; check `.cursor/mcp.json` exists |
| Connection refused | Start DB container; verify network name with `docker network ls` |
| Auth failed | Check `POSTGRES_PASSWORD` in correct env file |
| Staging MCP fails | Run `make staging-ps`; network must be `remnawave-staging_staging_network` |

## Security

- Passwords stay in `.env` / `.env.staging` only (`envFile` in mcp.json).
- Do not commit secrets or paste connection strings in chat.
- MCP does not replace `delivery-cycle.mdc` smoke or user approval for deploy.

## Hooks

`.cursor/hooks.json` runs `session-start.sh` on each agent session — ensures `mcp.json` exists and reminds the agent of `autonomous-dev-workflow.mdc`.
