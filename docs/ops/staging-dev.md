# Staging & ship workflow (same host as production)

Agent default: **`autonomous-dev-workflow.mdc`** — plan, implement, `make staging-rebuild`, ship after user `تایید`.

## Topology — one server, two stacks

```
                    ┌─────────────────────────────────────────┐
                    │           Same server (/opt/bot-remnawave) │
                    └─────────────────────────────────────────┘
   Production          │                    Staging
   docker compose     │                    docker-compose.staging.yml
   project: default   │                    project: remnawave-staging
                      │
   remnawave_bot       │   remnawave_staging_bot     host 8081 → container 8080
   cabinet_frontend    │   remnawave_staging_cabinet host 3021 → container 80
   postgres_data       │   staging_postgres_data      (isolated)
   redis_data          │   staging_redis_data
   .env                │   .env.staging
   prod @MOONVPN_BOT   │   @mrj7_bot (separate token)
```

**Never** smoke i18n/UX on the production bot while iterating — use **@mrj7_bot** only.

## Public URLs (staging)

| Host | Role | Caddy → |
|------|------|---------|
| `staging-host-hooks.rookari.com` | webhook staging bot | `localhost:8081` |
| `staging-host-cabinet.rookari.com` | cabinet staging | `localhost:3021` |
| `staging-host-miniapp.rookari.com` | miniapp staging | (as configured) |
| `staging-host-sub.rookari.com` | subscription page | prod sub page (shared) |

Prod domains (`hooks`, `cabinet`, …) unchanged — same IP, different Caddy routes.

## Port / env pitfalls

| Variable | Staging value | Note |
|----------|---------------|------|
| `WEB_API_PORT` | **`8080`** inside container | Host mapping `8081:8080` is in compose |
| `CABINET_PORT` | **`3021`** | Host port for cabinet |
| `POSTGRES_HOST` | **`staging-postgres`** | Do not use `postgres` (resolves to prod on shared network) |
| `BOT_USERNAME` / `VITE_TELEGRAM_BOT_USERNAME` | **`mrj7_bot`** | BotFather + cabinet build |

## First-time setup (same host)

1. `.env.staging` from `.env.staging.example` (never commit)
2. Staging bot in BotFather; domain `staging-host-cabinet.rookari.com` on **@mrj7_bot**
3. Caddy routes for `staging-host-*` → ports 8081 / 3021
4. First boot with migrations: `make staging-migrate`

## Daily sprint loop (Makefile)

```
branch → commits → make smoke
  → make staging-rebuild && make staging-health
  → smoke-map.md → user smokes @mrj7_bot
  → (user تایید) CONFIRM_SHIP=1 make ship BRANCH=…
  → gh pr merge -R k4lantar4/remnabot
  → git pull remnabot main
  → CONFIRM_PROD_DEPLOY=1 make prod-deploy
  → short prod smoke
```

## Scripts

| Command | Stack |
|---------|--------|
| `make staging-rebuild` | Full staging deploy |
| `make staging-health` | localhost + HTTPS health |
| `make staging-cabinet-build` | Cabinet only (VITE / username) |
| `CONFIRM_SHIP=1 make ship BRANCH=…` | Push + PR (after user smoke) |
| `CONFIRM_PROD_DEPLOY=1 make prod-deploy` | Production after merge |

## Resources

Staging stack ≈ **+1–2 GB RAM**. Production keeps running during staging work.

## Security

- `.env.staging` never commit
- staging token ≠ prod token
- C2C on staging: aware test top-ups may hit real admin inbox unless disabled
