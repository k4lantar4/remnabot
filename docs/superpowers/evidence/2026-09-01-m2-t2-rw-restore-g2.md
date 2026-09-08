# M2-T2 — Restore Remnawave 2.8.1 dump (G2)

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M2-T2 · weight 8  
Dump (rehearsal input, **not** a cutover artifact): `/opt/remnawave/old(2.8.1)_remnawave.sql`  
SHA-256: `11935de69fc6dc318419753916ff840f950f5b4be7a27be46e2ccf2142347377` (P6 match)

## Verdict: G2 PASS

| Check | Result |
|---|---|
| Dump checksum | **PASS** |
| Restore volume | `rehearsal_rw_pg17` only (not `remnawave-db-data`) |
| `users` | **3181**; `uuid` uuid NOT NULL on all rows; `short_uuid` present; numeric `users.id` **absent** (2.8.1) |
| Prisma tail | **`20260625200530_add_external_squad_index`** (`finished_at` max; 112 rows) |
| Boot image | `remnawave/backend:2.8.1@sha256:361f9bb0…ce956b`; log `Remnawave Backend v2.8.1` |
| `/health` (`127.0.0.1:3101`) | HTTP 200 `status=ok` database up |
| Login surface | HTTP 200 `text/html` title **Remnawave** (119 863 bytes) on `127.0.0.1:3100` with `Host: rw.rookari.com` + `X-Forwarded-Proto: https` |
| Authenticated login | **not attempted** (would need production admin credentials = class D) |
| Public Caddy | **unchanged** (`panel.rookari.com` still cabinet/bot; 2.8.1 not published on a production name) |
| `rehearsal_bot` | absent |
| Sandbox | `backend:3` healthy; `remnawave-db-data` still on `remnawave-db` |

## Restore

Volume was empty after M2-T0 wipe. Started **only** `rehearsal_rw_db`. Dump `OWNER TO postgres`; official image superuser is `rehearsal_rw`, so a local **`postgres` SUPERUSER role** was created (name only, not a production password). Then:

```
docker exec -i rehearsal_rw_db psql -U rehearsal_rw -d postgres -v ON_ERROR_STOP=1 < dump.sql
```

Exit 0. No `ERROR`/`FATAL`. Server: PostgreSQL 17.6 Debian (matches dump header).

Compose warned `Found orphan containers (rehearsal_bot_db)`. **Did not** pass `--remove-orphans` (that would destroy G1). `rehearsal_bot_db` left running on `rehearsal_bot_pg15`.

## Boot

```
docker compose -p rehearsal -f deploy/remnawave/docker-compose.rehearsal.yml up -d rehearsal_rw
```

(`rehearsal_sub` not started.) Prisma `migrate:deploy` + `migrate:seed` ran; tail **unchanged**. Node usage errors to production node IPs in logs are expected on an isolated copy (nodes unreachable) and are not a G2 failure.

Direct HTTP to `:3000` without proxy headers: `ProxyCheckMiddleware: Reverse proxy and HTTPS are required` (empty reply). Login SPA requires `X-Forwarded-Proto: https`. Metrics `/health` on `:3001` does not.

## Isolation

| Name | After M2-T2 |
|---|---|
| `rehearsal_rw` / `_db` / `_redis` | running; left up |
| `rehearsal_rw_pg17` | restored dump |
| `rehearsal_bot_db` | still G1; not orphan-removed |
| `remnawave` sandbox | `backend:3` |
| `remnawave-db-data` | sandbox only |

## Next

M3-T0: choose 3.x **candidate** from official panel releases (then M3-T1 upgrade copy). M4-T0 graft remains independently unblocked. Do not start `rehearsal_bot`. Do not alembic-upgrade the bot restore until M4-T0.
