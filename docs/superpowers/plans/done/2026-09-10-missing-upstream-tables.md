# Missing upstream tables (`coupons`, `platega_subscriptions`) break admin Activity

Status: done — revision `0117_create_deferred_upstream_tables` (remnabot#74, 2026-09-12).
Option 1 ("create the tables") was chosen by the user on 2026-09-12, after the same two 500s were
hit again while running the S-020 smoke items.
Repos: remnabot only
Upstream basis: remnabot `origin/main` 66fd73da; `upstream/main` 4e6e9224 (2026-09-10)

## Goal

The cabinet admin "Activity" tab (Users → user → Activity) loads again for every user instead of
failing with HTTP 500. Admin-only; no B2C/partner difference.

## Findings (2026-09-10, live dev stack)

- `GET /cabinet/admin/users/{id}/activity` returns 500 for **every** user:
  `UndefinedTableError: relation "coupons" does not exist`. The `coupon` source in
  `_activity_sources()` (`app/cabinet/routes/admin_users.py`, `'coupon': (select(Coupon)…)`) queries
  a table the DB doesn't have. `?types=transaction` (no coupon source) returns 200 — the rest of
  the endpoint works. Predates the ×100 balance fix (PR #24); not caused by it.
- Cause: at 0095 our Alembic chain forked from upstream's under the same numbers (ours
  `0095_partner_panel_fields` … `0112_referral_earnings_reward_columns`; DB head `0112`). Upstream's
  `0095_add_coupons`, `0099_add_platega_subscriptions`, `0100_platega_sub_unique_alive`,
  `0102_coupon_max_per_user` (and the rest of its 0095–0112) were archived, not grafted — but the
  models (`Coupon`, `CouponBatch`, `PlategaSubscription` in `app/database/models.py`) and their code
  came in with upstream syncs.
- Same pattern: `platega_subscriptions` is missing; on the build of 025e015e the startup dedup pass
  still logged `PendingRollbackError … relation "platega_subscriptions" does not exist`
  (`app/services/subscription_dedup_service.py`). `tests/services/test_recurring_cancel_keeps_transaction.py`
  guards the related transaction-poisoning bug — check whether the current `main` still logs it.
- Code touching the missing tables: `app/cabinet/routes/admin_coupons.py`, `app/cabinet/routes/coupon.py`,
  `app/cabinet/routes/admin_users.py` (activity), `app/database/crud/coupon.py`,
  `app/database/crud/platega_subscription.py`, `app/handlers/admin/coupons.py`, `app/handlers/start.py`,
  `app/handlers/subscription/autopay.py`, `app/services/coupon_service.py`.

### Full extent (added 2026-09-10 from the CI-green work — measured, not guessed)

Diffing `Base.metadata` against `information_schema.columns` on the dev DB (alembic head `0112`)
gives this complete list:

- **Missing columns — likely user-facing breakage:** `guest_purchases.campaign_slug` and
  `guest_purchases.idempotency_key` (upstream `0106`/`0107`, archived). Live code uses
  `idempotency_key`: `app/cabinet/routes/gift.py` (~449–463) and `app/handlers/subscription/gift.py`
  (~706, 904, 918). Any ORM `SELECT` of `GuestPurchase` names every mapped column, so **gift/guest
  purchases on a migrated DB likely fail with `UndefinedColumn`**. Reproduce first; if confirmed,
  this is the most urgent part of the plan and belongs in option 1 regardless of the coupon decision.
- **Missing tables:** `coupons`, `coupon_batches` (above), `legal_consents`, `recurrent_payments`,
  `cispay_payments`, `lava_subscriptions`, `platega_subscriptions` (the last four belong to deferred
  gateways: create only to stop errors, never enable), `grace_access_sessions` (own plan:
  `2026-09-10-grace-access-sessions-table.md`), `referral_reward_levels` (deliberately deferred:
  `0112` docstring, `tests/database/test_0111_remnawave_id.py` `FORBIDDEN_TABLES`).
- Fresh installs get all of them via `create_all`; only Alembic-migrated DBs are missing them.
  The test suite can't see this (it builds schemas with `create_all`/SQLite). Add a guard test:
  "after `alembic upgrade head` on an empty Postgres, every mapped column exists", with an explicit
  allowlist for the deliberately deferred tables.
- Re-measure in the picking-up session (the list above is a 2026-09-10 snapshot): compare
  `Base.metadata.sorted_tables` against `information_schema.columns` (read-only).

## Design (decide first in the picking-up session)

Two options — this is a migration, so the choice needs the user's approval before code:
1. **Create the tables** with a new revision on our lineage (after `0112`) porting upstream's
   `coupons`/`coupon_batches` (0095 + 0102) and, only if the code must not error,
   `platega_subscriptions` (0099 + 0100) schemas. Makes coupons usable; Platega stays disabled.
2. **No schema change**: make the activity `coupon` source (and other readers) tolerate the
   missing table, e.g. drop the source when coupons are off. Smaller, but coupons stay dead.

Which one depends on whether coupons are a product we want — ask; don't assume.

## Vs. upstream

- Ours: the diverged Alembic lineage (0095–0112) — never renumber or rewrite it; any new table
  goes in a new revision after our head.
- Reused as-is: upstream's `Coupon`/`CouponBatch` models and coupon service.
- Platega is a deferred gateway (workspace `CLAUDE.md`): don't enable or depend on it; creating
  its table only to stop errors is acceptable, re-enabling it is not.

## Tasks (to be expanded)

1. Reproduce: run a test against Postgres (or the dev DB, read-only) that shows the activity
   500; list every model whose `__tablename__` isn't in the DB (`to_regclass`) to see the full
   extent beyond these two tables.
2. Implement the approved option. Test: `GET …/activity` returns 200 for a user with no coupons
   (`tests/cabinet/`), plus a migration test in `tests/database/` if option 1.
3. Confirm the startup log no longer shows the `platega_subscriptions` dedup error.

## Smoke test

Generate with `smoke-test-checklist` after implementation (cabinet admin → Users → user →
Activity tab loads and shows transactions).

## How it closed (2026-09-12)

Re-measured on the dev database at head `0116` (`Base.metadata` vs. `information_schema.columns`):
eight tables and two columns were missing, exactly the 2026-09-10 snapshot plus
`grace_access_sessions` now created by `0113`.

Revision `0117` creates seven of them — `cispay_payments`, `platega_subscriptions`,
`lava_subscriptions`, `recurrent_payments`, `coupon_batches`, `coupons`, `legal_consents` — and
adds `guest_purchases.campaign_slug` / `idempotency_key` with upstream's unique index on the key.
Every table is inspector-guarded, so the revision is a no-op on a fresh `create_all` database.
Creating a deferred gateway's table is not enabling it: the `*_ENABLED` flags stay off.

`referral_reward_levels` was deliberately left out: it is deferred by product decision M4-T1, and
`tests/database/test_0111_remnawave_id.py::FORBIDDEN_TABLES` still guards it. The cabinet screen
`/admin/partners/referral-levels` therefore still has no table behind it — decide that with the
referral-levels feature, not here.

`tests/database/test_0117_deferred_upstream_tables.py` asserts each created table has exactly the
columns its model declares (`Base.metadata`), so a migrated database ends up with what a fresh
install gets. What is still missing is a guard that would have caught this class of drift in the
first place — it needs a Postgres service in CI, recorded as `F-074`.
