---
name: staging-workflow
description: Parallel staging stack on same host as prod; smoke-map; ship after user approval. Use for i18n and user-visible changes.
---

# Staging workflow (same server)

## Two stacks, one machine

| Stack | Compose | Env | Ports (host) |
|-------|---------|-----|--------------|
| **Staging** | `docker-compose.staging.yml` | `.env.staging` | 8081, 3021 |
| **Production** | `docker-compose.yml` | `.env` | 8080, 3020 |

Topology: `docs/ops/staging-dev.md`

## After implementation

1. Fill `docs/templates/smoke-map.md` (keys + Telegram path)
2. `docker compose run --rm --no-deps bot python -c "import main"`
3. `./tools/deploy-staging.sh` (first time: `--migrate`)
4. User smokes **staging bot** + `staging-cabinet` URL — not prod bot

## After user approves staging

```bash
CONFIRM_SHIP=1 ./tools/ship-after-smoke.sh <branch>
# user merges PR, then same host:
CONFIRM_PROD_DEPLOY=1 ./tools/deploy-production.sh
```

Agent must not run `CONFIRM_*` without explicit user approval.

## Subdomains

Webhook staging needs its own URL (e.g. `staging-hooks.*`). Same IP as prod; Caddy routes by hostname to ports 8081/3021.

Alternative: `BOT_RUN_MODE=polling` on staging — no extra subdomain, less prod-like.
