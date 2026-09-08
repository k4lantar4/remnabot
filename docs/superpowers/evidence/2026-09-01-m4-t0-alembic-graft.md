# M4-T0 — Graft remnabot Alembic `0088–0104`

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M4-T0 · weight 8  
Commit message (this batch): `feat(M4-T0): graft remnabot alembic 0088-0104; archive upstream 0088-0110`

## Verdict: PASS

| Check | Result |
|---|---|
| `alembic heads` (ScriptDirectory, no DB) | **`0104`** only |
| Head file | `0104_traffic_purchase_expiry_clamp.py` (not `0104_remnawave_numeric_id.py`) |
| `0110_*.py` in `versions/` | **absent** |
| Archive | `docs/superpowers/reference/upstream-alembic-0088-0110/` · **23** upstream files + README |
| Grafted copies vs `/opt/remnabot` | SHA-256 **match** (17 files) |
| Shared `0087` | identical SHA-256 both trees |
| `tests/database/test_migration_chain.py` | **3 passed** |
| `alembic upgrade` / `stamp` on restore | **not run** |
| `rehearsal_bot` app | **absent** |
| `rehearsal_bot_db` `alembic_version` | still **`0103`** |
| Sandbox `remnawave_bot_db` | still **`0110`**; `remnawave_bot` **not** rebuilt/restarted |

## What moved

**Archived** (git mv) remnabot1 upstream `0088–0110` (23 files), including `0104_remnawave_numeric_id.py` and `0110_referral_user_reward_choice.py`.

**Copied** remnabot `0088–0104` (17 files) into `migrations/alembic/versions/`. `0096` remains a merge `down_revision=('0094','0095')`. `0088` is `create_c2c_receipts`. `0103` is `subscription_user_disabled`. `0104` is traffic clamp.

Live chain `0087→0104` (ScriptDirectory walk): 0088 C2C → … → 0096 merge → … → 0103 user_disabled → 0104 clamp.

## Known breakages (expected at M4-T0; do not claim green 4.2 tests)

1. **Models vs grafted schema.** `User.remnawave_id` is `unique=True,index=True`; `Subscription` has partial unique `uq_subscriptions_remnawave_id`. Grafted graph has **no** `remnawave_id` until M4-T3 `0111`. `0001_initial_schema.py` is still `Base.metadata.create_all` of **current** 4.2 models (grace, legal consents, remnawave_id; **no** `c2c_receipts` model on remnabot1). Empty/CI DBs stay inconsistent until M4-T4/T7.
2. **4.2 tests that import unused payments/schema.** `tests/services/test_grace_access_*.py`, `test_legal_consent.py`, coupon/platega paths assume 4.2 tables. They are **not** the M4-T0 gate. Do not run a full pytest green claim.
3. **Sandbox bot DB `0110`.** Live `remnawave_bot` / `remnabot1_postgres_data` is still upstream `0110`. Grafted files no longer contain that revision. **Do not** rebuild or restart `remnawave_bot` against this tree without `SKIP_MIGRATION=true`. Do not `alembic upgrade` that volume. Rehearsal restore (`rehearsal_bot_pg15` at `0103`) is the graft target for later M4-T1 — not this sandbox.
4. **Startup auto-upgrade.** `main.py` still calls `run_alembic_upgrade()` before `setup_bot()`. That is why `rehearsal_bot` stays down until an explicit M4-T1 batch.

## Not done (next batch)

M4-T1 schema/boot diff against remnabot `0104`. Do not start `rehearsal_bot` until the user confirms **M4-T1**.
