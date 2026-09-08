# M2-T1 — Restore bot dump (G1), postgres only

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M2-T1 · weight 8  
Dump (rehearsal input, **not** a cutover artifact): `/opt/remnabot/old_3.60_remnawave_bot.sql`  
SHA-256: `b5fc023a23e99471ab9a4a61f834989ff7ff21c7f6061af4f926e404c093cb85` (P6 match)

## Verdict: G1 PASS

| Check | Result |
|---|---|
| Dump checksum | **PASS** (matches P6) |
| Restore target volume | `rehearsal_bot_pg15` only |
| Restore target container | `rehearsal_bot_db` (`postgres:15-alpine@sha256:3d0f7584…6461f`) |
| `alembic_version` | **`0103`** |
| `0106` present | **no** (count 0) |
| `users` | **7828** |
| `c2c_receipts` | table present, **1186** rows; `approved_amount_kopeks` column present |
| C2C enabled (env) | `.env.rehearsal` `C2C_ENABLED=true`; `C2C_ADMIN_CHAT_ID` absent (empty/not a production chat) |
| `rehearsal_bot` started | **no** |
| `alembic upgrade` / `stamp` | **not run** |
| Live volume `remnabot1_postgres_data` | still mounted only on sandbox `remnawave_bot_db` (healthy) |

## Restore

Volume `rehearsal_bot_pg15` was empty (no PGDATA) before `up`. Started **only** `rehearsal_bot_db` (not redis, not cabinet, not `rehearsal_bot`).

```
docker compose -p rehearsal -f docker-compose.rehearsal.yml up -d rehearsal_bot_db
docker exec -i rehearsal_bot_db psql -U remnawave_user -d remnawave_bot -v ON_ERROR_STOP=1 < dump.sql
```

Exit 0. Log: no `ERROR`/`FATAL`. Dump `\restrict`/`\unrestrict` accepted (container `psql` **15.18**, same as dump).

Bind: `127.0.0.1:6061`. Mount: `rehearsal_bot_pg15 -> /var/lib/postgresql/data`.

## Extra lineage checks (not G1-required, recorded)

| Item | Value |
|---|---|
| `subscriptions` | 3173; column `user_disabled` present (remnabot `0103`) |
| `users.wholesale_discount_bps` | present |
| `users.partner_status` | present |
| `users.remnawave_id` | **absent** (expected until M4-T3 `0111`) |
| Public tables | 107 |
| Server | PostgreSQL 15.18 (the pinned production `15-alpine` digest **is** 15.18) |

## E3 note

The production-pinned digest `sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f` reports **15.18**. Earlier plan text calling 15.18 “aspirational” is stale for this digest; rehearsal used that digest, not a different `:15.18` tag.

## Isolation

| Name | Role after M2-T1 |
|---|---|
| `rehearsal_bot_db` | restored dump; left **running** |
| `rehearsal_bot` | absent |
| `remnawave_bot_db` | sandbox; `remnabot1_postgres_data`; not written |
| `rehearsal_rw_*` | not started this task |

## Next

M2-T2: restore RW 2.8.1 dump into `rehearsal_rw_pg17`. Do not start `rehearsal_bot`. Do not alembic-upgrade this volume until M4-T0.
