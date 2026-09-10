# Missing upstream tables (`coupons`, `platega_subscriptions`) break admin Activity

Status: active (backlog — recorded 2026-09-10, not started; expand the tasks in the session that
picks it up)
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
