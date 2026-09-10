# Un-defer grace access: create `grace_access_sessions` (remnabot)

**Status:** active — **awaiting design approval** (migration → architectural; no code until approved)
**Repos:** `remnabot` only. The cabinet already ships the admin grace screens; no frontend change.
**Upstream basis:** v4.8.0 (`1fe2b47a`, 2026-09-09); the table comes from upstream migration
`0097_add_grace_access.py` (`67d45b6a`, fixes in `35206d7b` / PR #3075) plus the `remnawave_id`
column and nullable `remnawave_uuid` from upstream `0104_remnawave_numeric_id.py`.

## Goal

Make upstream's *grace access* usable in our fork: when a paid subscription expires or runs out of
traffic, the user keeps short, restricted access until they pay (B2C, and partner customers
through the same subscription path). Today the feature is compiled in but cannot run, because its
table was never created.

## Background — why the table is missing

Our Alembic chain forked from upstream at `0096`. Upstream `0097`–`0104` are *different* migrations
from ours with the same numbers (ours: `0097_add_quick_amounts…` … `0104_traffic_purchase_expiry_clamp`).
When the 4.2 ORM was grafted, `0111_remnawave_id_and_boot_extras.py` added the grace *marker
columns* on `subscriptions` but **deliberately deferred** the `grace_access_sessions` table
(`tests/database/test_0111_remnawave_id.py` lists it in `FORBIDDEN_TABLES`). Only databases created
fresh (`create_all`) have it.

Runtime code ignored that deferral. PR `fix/grace-guard-missing-table` (bounded, ships
independently of this plan) makes the startup delete-guard and `grace_access_runtime.start()`
respect a missing table. That PR is what fixes "every subscription delete fails"; **this plan is
only needed if we want the grace feature itself.**

## Decision needed before execution

1. **Do we want grace access at all for the Iranian market?** If not, close this plan. The bounded
   fix already leaves the fork correct with the table deferred.
2. If yes, enabling it later (`GRACE_ACCESS_MODE=observe|active`) needs **business numbers I won't
   invent**: `GRACE_ACCESS_DURATION_HOURS`, `GRACE_ACCESS_TRAFFIC_GB`, and which of
   `GRACE_ACCESS_TRIAL/DAILY/FREE_ENABLED` apply, plus the restricted squad UUIDs
   (`GRACE_ACCESS_LIMITED_SQUAD_UUID` / `GRACE_ACCESS_EXPIRED_SQUAD_UUID`) from the panel. This
   plan only creates the schema; the mode stays `false`.

## Design

One new Alembic revision **`0113_create_grace_access_sessions`** (`down_revision = '0112'`), a
straight port of upstream `0097`'s *table part* adapted to our current model
(`GraceAccessSessionModel` in `app/database/models.py` is the source of truth):

- Inspector-guarded and idempotent: skip `create_table` if the table already exists (fresh-DB
  installs built by `create_all` have it). Create the missing `ix_grace_access_sessions_remnawave_id`
  index separately under the same guard. The whole revision is a no-op on a fresh DB.
- Columns, check constraints, `uq_grace_access_sessions_incident`, the partial unique index
  `uq_grace_access_sessions_one_open` and `ix_grace_access_sessions_state_until` exactly as the
  model declares. `remnawave_uuid` nullable and `remnawave_id BIGINT NULL` indexed, as upstream's
  `0104` left them.
- **Does not** touch `subscriptions`: the marker columns/indexes already exist from `0111`.
- **Does not** install the delete-guard trigger: `_ensure_runtime_schema_guards()` owns it and,
  after the bounded fix, installs it on the next start once the table exists. One owner, no
  duplicate DDL.
- `downgrade()`: drop the trigger if present (`DROP TRIGGER IF EXISTS … ON subscriptions`), then
  the indexes and the table.

Error cases: a partially created table from a manual attempt → the inspector guard skips
`create_table` but still adds a missing index. Production DB with open data → the table is new and
empty, so there's no backfill; `ACCESS EXCLUSIVE` is only on the new table.

Out of scope: enabling grace mode; any change to grace policy; the date-rule fix for the grace path
in `2026-09-09-upstream-selective-patches.md` Task 2 (it becomes live code once this lands — do it
after this plan).

## Vs. upstream

- **Ours:** only the revision id/numbering. Our `0113` collides in number with upstream's
  `0113_create_tabpay_payments` (same situation as the existing `0097`–`0112`). Revision ids are what
  Alembic keys on, so this is harmless in our lineage but must be called out in any future upstream
  migration triage.
- **Reused as-is:** upstream grace runtime/service/admin routes and cabinet screens; the table DDL.
- **Deferred gateways:** none touched. Do not graft upstream `0098`–`0101` (CisPay / Platega / Lava)
  alongside this.

## Tasks

**1. Revision `0113_create_grace_access_sessions` + test**
- Files: create `migrations/alembic/versions/0113_create_grace_access_sessions.py`;
  test `tests/database/test_0113_grace_access_sessions.py`; update the head assertions in
  `tests/database/test_0111_remnawave_id.py` / `test_0112_referral_earnings_columns.py` that pin
  `get_current_head() == '0112'` to `'0113'`.
- Interfaces: consumes `GraceAccessSessionModel` (names of constraints/indexes above). Produces
  the table that `_ensure_runtime_schema_guards()` (bounded-fix PR) detects via
  `to_regclass('grace_access_sessions')`.
- Test (failing first): chain `0112 → 0113` and head is `0113`; on a SQLite DB at `0112` shape
  (no table) upgrade creates the table with every model column, the partial unique index and the
  check constraints; upgrade on a DB that already has the table is a no-op; downgrade removes it.
- Persian/i18n: none.

**2. Verify on the dev stack**
- No files. Restart the bot (`docker compose up -d bot`); expect the log `Grace access is
  disabled` (not `Grace startup failed`), `trg_guard_open_grace_subscription_delete` present on
  `subscriptions`, and a subscription delete from the cabinet admin succeeding.
- Persian/i18n: none.

## Smoke test

Generate with `smoke-test-checklist` after implementation (admin → delete a subscription; bot
startup log; cabinet admin grace-access page loads).
