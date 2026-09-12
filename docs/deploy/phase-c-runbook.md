# Toman Phase C — deploy and rollback runbook

Plan: `docs/superpowers/plans/done/2026-09-11-toman-phase-c.md`. Written from what the 2026-09-12
deploy on the dev VPS actually needed; the future production cutover follows the same order.

**Target head revision: `0116`** (`0115` divides the catalog columns, `0116` divides
`tariffs.traffic_topup_packages`, which `0115` could not see). A state that stops at `0115` is not
a Phase C database: the traffic packages would still be x100 under Toman code.

**Scale marker:** the latest row of `amount_scale_state` (`scale = 'toman'`). `0115` writes it, its
downgrade deletes it. Since Task 6 the bot checks it at start (`app/database/amount_scale_guard.py`)
and exits with `Refusing to start: the database declares amount scale …` when it is missing —
also with `SKIP_MIGRATION=true`. A fresh, empty database gets the row from the bootstrap.

## Deploy

1. **Back up first.** There is no other undo for a wrong rate or a wrong image:
   ```bash
   docker exec remnawave_bot_db pg_dump -U remnawave_user -Fc remnawave_bot > phase-c-before-$(date +%F).dump
   ```
   (the `docker-compose.yml` defaults; use `POSTGRES_USER` / `POSTGRES_DB` from `.env` if set.)
2. **Pre-cutoff rows.** `0115` refuses to run while `transactions` or `users` hold rows created
   before `2026-06-05T00:00:00Z` (ruble-era amounts). Converting them needs a ruble→Toman rate that
   the owner has not given — the migration never guesses. Check before deploying:
   ```sql
   SELECT (SELECT count(*) FROM transactions WHERE created_at < '2026-06-05Z') AS tx,
          (SELECT count(*) FROM users        WHERE created_at < '2026-06-05Z') AS users;
   ```
3. **Numeric catalog env keys.** The config defaults moved to Toman, but values set in env override
   them: divide every `PRICE_*` and `TRAFFIC_*_CONFIG` amount by 100 in **both** `.env` and
   `.env.dev` (the dev compose file loads `.env.dev`). Only those numeric keys — never a token,
   secret or `*_ENABLED` flag. `system_settings` may also override them:
   `SELECT key, value FROM system_settings WHERE key LIKE 'PRICE\_%' OR key LIKE 'TRAFFIC\_%';`
4. **Pull and recreate the bot** (the migration runs at start, before anything is served):
   ```bash
   git -C /opt/project/remnabot pull --ff-only origin main
   docker compose -f docker-compose.dev.yml up -d --force-recreate bot
   ```
   Use `up -d --force-recreate`, not `restart`, whenever an env value changed in step 3:
   `restart` keeps the container's old environment.
5. **Verify:**
   ```sql
   SELECT version_num FROM alembic_version;                        -- 0116 or later
   SELECT scale, applied_at FROM amount_scale_state ORDER BY id;   -- one 'toman' row
   SELECT * FROM amount_scale_rounding_log;                        -- pre-images of non-round rows
   SELECT id, period_prices, traffic_topup_packages FROM tariffs;  -- Toman, e.g. {"10": 30000}
   ```
   Bot log: no `Refusing to start`. Cabinet: a tariff price, the top-up limits and the admin tariff
   editor show the same Toman numbers as before the deploy.

## Rollback

**Database first, then the image — never the image alone.** The old image on a Toman database
charges and credits 100x; the new image on a downgraded database refuses to start (the guard), so
the order below is the only one that never serves a mismatched pair.

1. Stop the bot, and take a fresh `pg_dump -Fc` (rows written since the deploy are Toman).
2. Downgrade with the **current** image's migrations (the old image does not know the revisions):
   ```bash
   docker compose -f docker-compose.dev.yml run --rm --no-deps bot alembic downgrade 0114
   ```
   This steps back through every revision above `0114`. On the 2026-09-12 chain that includes
   `0118` (drops the deferred upstream tables) and `0117` (drops `guest_purchases.idempotency_key`
   and `campaign_slug`) — data in them is lost, which is why step 1 dumps first. `0116` multiplies
   the traffic packages back; `0115` multiplies the catalog columns back, restores the non-round rows
   exactly from `amount_scale_rounding_log`, and deletes the `toman` marker.
3. Verify: `SELECT version_num FROM alembic_version` → `0114`, and `amount_scale_state` is empty.
4. Multiply the step-3 env keys back by 100 in `.env` and `.env.dev`.
5. Deploy the pre-Phase-C image / commit (`up -d --force-recreate bot`). Do not start the current
   image on this database: the guard will refuse, by design.

If the dump from deploy step 1 is restored instead of downgrading, the same rule holds: that dump has
no `toman` marker, so only the pre-Phase-C image may run on it.
