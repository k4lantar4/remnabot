---
name: staging-workflow
description: Autonomous staging deploy and ship cycle on same host as prod. Use for every user-visible change — no per-session briefing.
---

# Staging workflow (same server)

Read **`autonomous-dev-workflow.mdc`** first — it is always applied.

## Two stacks, one machine

| Stack | Compose | Env | Ports (host) |
|-------|---------|-----|--------------|
| **Staging** | `docker-compose.staging.yml` | `.env.staging` | **8081**, **3021** |
| **Production** | `docker-compose.yml` | `.env` | 8080, 3020 |

| Staging surface | Value |
|-----------------|-------|
| Telegram bot | **`@mrj7_bot`** |
| Webhook | `https://staging-host-hooks.rookari.com` |
| Cabinet | `https://staging-host-cabinet.rookari.com` |
| Miniapp | `https://staging-host-miniapp.rookari.com` |

Topology: `docs/ops/staging-dev.md`

## Deploy scope (automatic)

```bash
make deploy-scope   # fa | bot | cabinet | bot+cabinet | none
```

| Scope | Staging action |
|-------|----------------|
| `fa` | sync locales + restart bot |
| `bot` | build bot + up bot |
| `cabinet` | `staging-cabinet-sync` (host npm build + dist mount) |
| **`bot+cabinet`** | parallel bot build + cabinet sync (default parity sprint) |
| `none` | skip deploy |

Override: `make staging-rebuild-bot`, `staging-rebuild-cabinet`, `staging-rebuild-both`.

## Agent loop (automatic — do not block chat)

After implementation commits:

```bash
make smoke
make deploy-scope
make staging-rebuild      # background; log in /tmp/remnabot-deploy-staging-*.log
# when log shows success:
make staging-health
```

**Never** await a 10–25 min rebuild inline unless the user asks. Report log path + PID.

Foreground escape hatch: `make staging-deploy STAGING_FLAGS='--both --no-cabinet-sync'`

Alembic: `make staging-migrate` (foreground migrate flag).

## Staging cabinet fast path

`tools/staging-cabinet-sync.sh` — host `npm run build`, nginx serves `./cabinet/dist` mount (staging only).

~30s–2min vs full Docker cabinet build. Prod cabinet stays image-only.

## After user approves (`تایید`)

```bash
CONFIRM_SHIP=1 make ship BRANCH=<branch>
gh pr merge <n> -R k4lantar4/remnabot --merge
git checkout main && git pull remnabot main
CONFIRM_PROD_DEPLOY=1 make prod-deploy   # auto scope, background
# or scoped:
CONFIRM_PROD_DEPLOY=1 make prod-deploy-bot
```

Agent must **not** set `CONFIRM_*` before user staging smoke approval.

## Subdomains

Webhook staging needs its own URL (`staging-host-hooks.*`). Caddy on host routes to `8081` / `3021`. BotFather domain for cabinet login must include `staging-host-cabinet.rookari.com` on **@mrj7_bot**.

Alternative: `BOT_RUN_MODE=polling` on staging — no extra subdomain, less prod-like.
