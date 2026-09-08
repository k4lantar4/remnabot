# M4-T5 — `persist_identity` seam (panel `.id`)

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M4-T5 · weight 5 · dependencies: M4-T4  
Commit message (this batch): `feat(M4-T5): persist_identity seam for numeric panel id`

## Verdict: PASS

Thin adapter writes Remnawave 3.x `users.id` onto bot `User.remnawave_id` and/or `Subscription.remnawave_id`. No uuid lookup. No `resolve_remnawave_id`.

| Check | Result |
|---|---|
| User write path | `persist_identity(user=…, panel_user=…)` stores `panel_user.id` |
| Subscription write path | `persist_identity(subscription=…, panel_user=…)` stores `panel_user.id` |
| UUID `panel_id` / uuid-only object | `RemnaWaveInvalidUserIdError`; target unchanged |
| Wired in `subscription_service` | create/update, adopt-by-short-uuid, bind-by-short-uuid |
| Client uuid routes | unchanged (M4-T2) |
| Backfill `--apply` | **not run** (M4-T6) |

## Tests (TDD)

File: `tests/custom/test_persist_identity.py`

1. **RED:** `ModuleNotFoundError: app.custom.identity`
2. **GREEN:** `uv run pytest tests/custom/test_persist_identity.py` + M4-T2 / 3.0.0 coerce tests → **129 passed** (with token_guard)

## Isolation

| Name | After M4-T5 |
|---|---|
| G1 `rehearsal_bot_pg15` | still **`0111`** (no further Alembic) |
| `rehearsal_bot` app | **absent** |
| sandbox `remnawave_bot` | still **`0110`**; `Created=2026-09-01T10:26:23Z` |
| live Caddy / `panel.rookari.com` | **unchanged** |

## Not done (next batch)

**M4-T6** backfill (`remnawave_identity_backfill`, dry-run default). Do not poll `rehearsal_bot`. Do not rebuild sandbox `remnawave_bot`.
