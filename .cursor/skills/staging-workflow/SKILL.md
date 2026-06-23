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

## Agent loop (automatic)

After implementation commits:

```bash
make smoke
make staging-rebuild      # or make staging-migrate
make staging-health
```

Fill `docs/templates/smoke-map.md`, then ask user to smoke **staging only**.

## After user approves (`تایید`)

```bash
CONFIRM_SHIP=1 make ship BRANCH=<branch>
gh pr merge <n> -R k4lantar4/remnabot --merge
git checkout main && git pull remnabot main
CONFIRM_PROD_DEPLOY=1 make prod-deploy
```

Agent must **not** set `CONFIRM_*` before user staging smoke approval.

## Subdomains

Webhook staging needs its own URL (`staging-host-hooks.*`). Caddy on host routes to `8081` / `3021`. BotFather domain for cabinet login must include `staging-host-cabinet.rookari.com` on **@mrj7_bot**.

Alternative: `BOT_RUN_MODE=polling` on staging — no extra subdomain, less prod-like.
