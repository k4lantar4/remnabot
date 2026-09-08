# M3-T1 — Upgrade copy 2.8.1 → candidate 3.4.3 (G3)

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M3-T1 · weight 13 · dependencies: M2-T2, M3-T0  
Authority: `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`  
Official upgrade: `https://docs.rw/install/upgrading/` (compose pull/up; Prisma on start). Did **not** copy official `backend:3` / `postgres:18.4`.

## Verdict: G3 PASS — rehearsal-passed candidate (not production pin)

| Field | Value |
|---|---|
| `CANDIDATE_TAG` | `3.4.3` |
| Pulled / pinned image | `remnawave/backend:3.4.3@sha256:4ea85b2fc16bd3e5d367b61afc07ec219133eaa12dd7b5e898adc33c84515422` |
| Matches M3-T0 Hub index | **yes** |
| Image metadata | `__RW_METADATA_VERSION=3.4.3` · backend git `f8ad8ad3410252215ca7b2e429d157bd275ec564` · frontend `c2c9ba3b476e4914a3b17e8ce677ab9255e1c02f` · build `2026-08-31T20:09:51Z` |
| Prisma | ran on **copy** volume `rehearsal_rw_pg17_candidate`; logs `Remnawave Backend v3.4.3`; Nest started |
| PG | still **17.6** (not 18.4) |
| Production promotion | **not yet** — digest is rehearsal-passed candidate until cutover records it |

## Snapshot (required `pg_dump -Fc`, not PGDATA tar)

Writer `rehearsal_rw` **stopped** first. Dump is a rehearsal artifact, **not** in git, **not** a cutover dump.

| Item | Value |
|---|---|
| Path | `/opt/remnawave/rehearsal-snapshots/rehearsal_rw_pg17_g2_pre_m3t1.dump` |
| SHA-256 | `e87a3aebe002984d8f8a45fa0d63eb1c54eb3ccdf4de5bdec320e0d2a98940d8` |
| Restore | `pg_restore --no-owner --exit-on-error` into new volume `rehearsal_rw_pg17_candidate` |
| G2 volume | `rehearsal_rw_pg17` still present, **unmounted** (2.8.1 freeze) |

## G3 checks

| Check | Before (G2 / 2.8.1) | After (3.4.3 copy) | Result |
|---|---|---|---|
| Numeric identity | `users.t_id` bigint PK; `users.uuid` uuid unique | `users.id` **bigint** PK (`users_id_seq`); **`uuid` column gone** | **PASS** |
| Correlation | `short_uuid` unique 3181; 20-row `t_id`+sha256(short_uuid) | same 20 hashes; `id` equals former `t_id` | **PASS** |
| Counts | users 3181; ism 3180; traffic 3181; hwid 3153 | identical | **PASS** |
| Joins | FKs on `t_id` | FKs on `users.id`; orphan counts **0** | **PASS** |
| Mass revoke | `sub_revoked_at` **205** | **205** (unchanged) | **PASS** |
| Prisma | 112 rows; tail `20260625200530_add_external_squad_index` | **131** finished; tail `20260827222832_add_entity_tags` | **PASS** |
| Login | SPA 200 on `:3100` + proxy headers | HTTP 200 `text/html` title **Remnawave** (120 017 bytes) with `Host` + `X-Forwarded-Proto` + `X-Forwarded-Host` | **PASS** |
| Sub link | (2.8.1 not required for G2) | `GET /api/sub/{shortUuid}` HTTP 200 `text/yaml`; `/api/sub/{shortUuid}/info` `isFound: true` (one ACTIVE non-revoked user; identifier not recorded) | **PASS** |
| `/health` | 200 | 200 `status=ok` database up | **PASS** |

Authenticated admin login **not attempted** (production admin credentials = class D).

`rehearsal_sub` (7.2.6) **not started**. Sub link proven on the panel itself. Official docs use `subscription-page:latest` — **not** pulled.

## Env (fingerprints only)

3.4.3 requires `APP_SECRET` (replaces 2.8.1 `JWT_*` for signing). Generated **class C** in gitignored `.env.rehearsal-rw`. Fingerprint `sha256[:16]=5bfec8c8bf18af41`. Not production JWT. `METRICS_*` still class C from M2-T0.

## Isolation

| Name | After M3-T1 |
|---|---|
| `rehearsal_rw` | 3.4.3 digest above; healthy |
| `rehearsal_rw_db` | `postgres:17.6`; mount **`rehearsal_rw_pg17_candidate` only** |
| `rehearsal_rw_pg17` | G2 freeze; not mounted |
| `rehearsal_bot` | **absent** |
| `rehearsal_bot_db` | still G1 (orphan warning; **not** `--remove-orphans`) |
| sandbox `remnawave` | still `backend:3` @ `sha256:add561a4…c34023` |
| `remnawave-db-data` | still on sandbox `postgres:18.4` |
| live Caddy / `panel.rookari.com` | **unchanged** |

## Next

M3-ID: identity/API proof on **this digest** + official docs (uuid dropped, `shortUuid` retained, mapping to bot `remnawave_short_uuid`). M3-T2: stay on PG 17 (already running). Do not start `rehearsal_bot`. Do not alembic-upgrade bot restore until M4-T0.
