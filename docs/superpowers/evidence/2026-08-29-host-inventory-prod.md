# Host inventory — Production (Bot)

Date: 2026-08-29  
IP: `91.107.249.43`  
SSH: `ssh bot` (read-only inspection during RC)  
Re-verify: 2026-08-31 (appended below).

## Live application

| Item | Value |
|---|---|
| Application root | `/opt/bot-remnawave` |
| Compose | `/opt/bot-remnawave/docker-compose.yml` |
| Env | `/opt/bot-remnawave/.env` (13152 bytes; secrets not recorded here) |

## Running stack (2026-08-29)

| Container | Image | Status |
|---|---|---|
| `remnawave_bot` | `bot-remnawave-bot` (local build) | healthy |
| `remnawave_bot_db` | `postgres:15-alpine` | healthy |
| `remnawave_bot_redis` | `redis:7-alpine` | healthy |
| `cabinet_frontend` | `bot-remnawave-cabinet-frontend` | healthy |
| `remnawave` | `remnawave/backend:2.8.1` | healthy |
| `remnawave-db` | `postgres:17.6` | healthy |
| `remnawave-subscription-page` | `remnawave/subscription-page:7.2.6` | healthy |
| `remnawave-redis` | `valkey/valkey:9-alpine` | healthy |
| `caddy-remnawave` | `caddy-remnawave-caddy` | up |
| `pgadmin` | `dpage/pgadmin4:latest` | up |

## Database

| DB | alembic / version | Verified |
|---|---|---|
| Bot | `0103` | `docker exec remnawave_bot_db psql … alembic_version` |
| RW | Prisma tail per plan G2 | restore rehearsal from `/opt/remnawave/old(2.8.1)_remnawave.sql` on RC |

## Env keys (names only — production behavior reference)

| Key | Present | Notes |
|---|---|---|
| `C2C_ENABLED` | yes | `true` |
| `DEFAULT_LANGUAGE` | yes | `fa` |
| `BOT_RUN_MODE` | yes | `webhook` |
| `C2C_ADMIN_CHAT_ID` | yes | class D — fingerprint only in matrices |
| `BOT_TOKEN` | yes | class D |
| `WEBHOOK_URL` | yes | production hooks hostname |

## Caddy hostnames (sample)

Production: `hooks.rookari.com`, `cabinet.rookari.com`, `miniapp.rookari.com`, `{$PANEL_DOMAIN}` → `master.rookari.com`, `{$SUB_DOMAIN}` → `sub.rookari.com`

Staging (on prod host): `staging-host-{hooks,cabinet,miniapp,sub}.rookari.com`

## Docker volumes (forbidden for RC restore — sample)

Includes: `bot-remnawave_postgres_data`, `bot-remnawave_redis_data`, `remnawave-db-data`, `remnawave-admin_postgres_data`, `remnawave-staging_staging_postgres_data`, and multiple feature-branch `*_postgres_data` fossils.

## `/opt` layout (sample)

`bot-remnawave`, `remnawave`, `caddy-remnawave`, `remnawave-admin`, `bedolaga-cabinet`, backups — live prod layout differs from RC `/opt` mirror.

## Re-verify 2026-08-31 (`ssh bot`, read-only)

| Item | Value |
|---|---|
| `/opt/bot-remnawave` | **exists** |
| Bot container | `remnawave_bot` / `bot-remnawave-bot` |
| Bot PG | `postgres:15-alpine` digest `sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f` |
| Live alembic | `0103` |
| RW | `backend:2.8.1`, PG `17.6`, sub `7.2.6` |
| Caddy staging-host | `staging-host-{hooks,cabinet,miniapp,sub}` present on **Bot Caddy** (no `staging-host-master`). **Not** the operational RC. RC public hostname is `panel.rookari.com` |
| Forbidden volumes (sample) | `bot-remnawave_postgres_data`, `bot-remnawave_*`, `remnawave-db-data`, `remnawave-admin_postgres_data`, `remnawave-staging_staging_postgres_data` |
