# Smoke map — Phase 1 (fa → en → ru fallback chain)

> Agent: filled for Phase 1 commit on `i18n/fa-en-ru-fallback` (2026-06-23).
> User: verify on staging before ship approval.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-en-ru-fallback` |
| Staging bot | `@mrj7_bot` |
| Staging cabinet | `https://staging-host-cabinet.rookari.com` |
| Deploy | `make staging-rebuild` |
| Env | `LANGUAGE_SELECTION_ENABLED=false`, `DEFAULT_LANGUAGE=fa` |

## Phase 1 — what changed

1. Missing `fa.json` keys now resolve **`en` before `ru`** (not `fa → ru` directly).
2. `en` users fall back to `ru` only; `ru` users get no locale merge.
3. Rules/privacy defaults use the same `fa → en → ru` chain.

**Not in this smoke:** device terminology, purchase onboarding, cabinet parity — Phases 2–9.

## Changes → where to smoke

| # | What to verify | Expected behavior | Telegram path |
|---|----------------|-------------------|---------------|
| 1 | Normal Persian UI unchanged | All existing flows still Persian | `/start` → main menu |
| 2 | No regressions in purchase | Confirm/success screens Persian | Buy tariff flow |
| 3 | No bot crash | No `KeyError` in logs | «اشتراک من», balance, tickets |
| 4 | Fallback chain (indirect) | If a key were missing from fa, user would see English not Russian | Hard to spot manually — covered by `tests/localization/test_texts_fallback.py` |

## Agent verification (done)

```bash
uv run pytest tests/localization/test_texts_fallback.py tests/localization/test_fa_en_ru_chain.py -q
docker compose run --rm --no-deps bot python -c "import main"
```

## User smoke sign-off

- [ ] Staging Telegram: paths 1–3 verified on `@mrj7_bot`
- [ ] No new Cyrillic leaks in user-visible strings
- [ ] User approves → `CONFIRM_SHIP=1 make ship BRANCH=i18n/fa-en-ru-fallback`

## After merge to main

```bash
git checkout main && git pull remnabot main
CONFIRM_PROD_DEPLOY=1 make prod-deploy
```
