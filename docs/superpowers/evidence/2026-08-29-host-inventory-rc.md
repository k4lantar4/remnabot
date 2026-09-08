# Host inventory — RC (bot-v4)

Date: 2026-08-29  
IP: `91.107.144.95`  
Role: Release Candidate / rehearsal host  
Re-verify: 2026-08-31 (appended below).

## Application trees

| Path | Present | Notes |
|---|---|---|
| `/opt/remnabot1` | yes | Maintained bot 4.2.0 |
| `/opt/cabinet` | yes | Maintained cabinet 1.67.0 |
| `/opt/remnabot` | yes | Production reference 3.60.0 READ-ONLY |
| `/opt/bot` | yes | Upstream reference READ-ONLY |
| `/opt/bot-remnawave` | **no** | Live prod path exists only on Bot |
| `/opt/remnawave` | yes | RW runtime |
| `/opt/caddy` | yes | Caddy infra |
| `/opt/remnawave-admin` | yes | Admin tooling (not MVP cutover scope) |

## Docker volumes (sample)

| Volume | Notes |
|---|---|
| `remnawave-db-data` | Legacy — **forbidden** for rehearsal restore |
| `caddy-ssl-data` | Caddy certs |
| `valkey-socket` | RW redis socket |

No `rehearsal_*` or `cutover_*` volumes yet (pre-M1).

## Running containers (2026-08-29)

| Container | Image |
|---|---|
| `remnawave` | `remnawave/backend:3` |
| `remnawave-db` | `postgres:18.4` |
| `remnawave-subscription-page` | `remnawave/subscription-page:latest` |
| `caddy` | `caddy:2.9` |

**Non-promotable** for cutover evidence until replaced by rehearsal-restore track (plan errata E4).

## Rehearsal input dumps

| File | SHA-256 | Notes |
|---|---|---|
| `/opt/remnabot/old_3.60_remnawave_bot.sql` | `b5fc023a23e99471ab9a4a61f834989ff7ff21c7f6061af4f926e404c093cb85` | alembic `0103`; not cutover artifact |
| `/opt/remnawave/old(2.8.1)_remnawave.sql` | `11935de69fc6dc318419753916ff840f950f5b4be7a27be46e2ccf2142347377` | RW 2.8.1 rehearsal input |

## Caddy (local)

Live `/opt/caddy/Caddyfile` includes legacy comment referencing `cabinet1` on `panel.rookari.com` — drift vs maintained topology; single-source under `remnabot1/deploy/caddy/` not yet created.

## Re-verify 2026-08-31

| Item | Value |
|---|---|
| `/opt/bot-remnawave` on RC | still **absent** |
| `/opt/cabinet1` | still **absent** |
| `docker-compose.rehearsal.yml` | still **absent** |
| `deploy/caddy/` | still **absent** |
| `rehearsal_*` / `cutover_*` volumes | still **absent** |
| RC volumes | `remnabot1_postgres_data`, `remnabot1_redis_data`, `remnawave-db-data`, `caddy-ssl-data`, `valkey-socket` — all **forbidden** for restore |
| Running sandbox | `remnabot1-bot` + `postgres:15-alpine`; RW `backend:3` + PG 18.4 + sub `:latest` — **non-promotable** |
| RC Caddy `staging-host-*` | **none** (unlike Bot). Operational RC public hostname is `panel.rookari.com` |
| Bot dump SHA-256 | `b5fc023a23e99471ab9a4a61f834989ff7ff21c7f6061af4f926e404c093cb85` (unchanged) |
| RW dump SHA-256 | `11935de69fc6dc318419753916ff840f950f5b4be7a27be46e2ccf2142347377` (unchanged) |

## Baseline tag (M0-T4, 2026-08-31)

| Item | Value |
|---|---|
| Tag | `baseline/prefork-4.2.0-89fa7dc5` |
| Tagged SHA | `89fa7dc584b9fb7f017c385d604614fb29692d66` (prefork 4.2.0; ancestor of current `prod-cutover` HEAD) |
| Bot dump | **REHEARSAL INPUT — NOT cutover artifact** · SHA-256 `b5fc023a23e99471ab9a4a61f834989ff7ff21c7f6061af4f926e404c093cb85` · alembic `0103` |
| RW dump | **REHEARSAL INPUT — NOT cutover artifact** · SHA-256 `11935de69fc6dc318419753916ff840f950f5b4be7a27be46e2ccf2142347377` |
