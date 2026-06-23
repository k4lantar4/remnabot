# Smoke map — Phase 0 closeout (force-default-language + safe fa fallback)

> Agent: filled for Phase 0 closeout (2026-06-23).
> User: follow paths in Telegram to verify before prod deploy.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `main` (Phase 0 commits `d1df0821`, `881286bf` already merged) |
| Staging bot | `@mrj7_bot` (from `.env.staging` `BOT_USERNAME`) |
| Staging cabinet | `https://staging-host-cabinet.rookari.com` |
| Deploy | `make staging-rebuild` (2026-06-23) |
| Env | `LANGUAGE_SELECTION_ENABLED=false`, `DEFAULT_LANGUAGE=fa` |

## Phase 0 — what changed

1. When language selection is disabled, `/start` and main menu force `DEFAULT_LANGUAGE` (`fa`) and persist correction to DB.
2. Missing `fa.json` keys fall back to `ru` (not crash); `texts.t(key, default)` still uses explicit default.

**Not in this smoke:** duplicate «حجم», `تعداد کاربر`, purchase onboarding — Phases 3–5 of audit plan.

## Changes → where to smoke

| # | What to verify | Expected behavior | Telegram path |
|---|----------------|-------------------|---------------|
| 1 | Stale `language=en` user sees Persian after `/start` | Main menu labels in Persian; DB `language` updated to `fa` | `/start` → main menu |
| 2 | Language picker blocked when selection off | Alert with Persian `LANGUAGE_SELECTION_DISABLED`; no picker | Menu → language button (if visible in layout) |
| 3 | New user skips language picker | Registration / menu in Persian without language step | New Telegram account → `/start` |
| 4 | No bot crash on normal flows | No `KeyError` / `AttributeError` in logs | Buy path, «اشتراک من», balance |
| 5 | DB persistence | After `/start`, `users.language = 'fa'` for corrected accounts | Check staging DB for test user |

## Callback / button checklist

| Callback / button | Handler | Expected after Phase 0 |
|-------------------|---------|------------------------|
| `/start` | `start.py` | Forces `fa` when selection disabled; persists DB |
| `main_menu` / back to menu | `menu.py` `show_main_menu` | Same force + Persian UI |
| `language_menu` / language change | `menu.py` | Disabled alert when selection off |
| Normal menu items | various | Unchanged for existing `fa` users |

## DB check (staging)

```bash
docker compose -f docker-compose.staging.yml --env-file .env.staging -p remnawave-staging \
  exec staging-postgres psql -U remnawave_user -d remnawave_bot_staging \
  -c "SELECT telegram_id, language FROM users WHERE language != 'fa' LIMIT 5;"
```

After test user sends `/start`, re-run for that `telegram_id` — expect `language = fa`.

## User smoke sign-off

- [ ] Staging Telegram: paths 1–4 verified
- [ ] Staging DB: path 5 verified (optional)
- [ ] No Cyrillic leaks in user-visible strings during flows
- [ ] User approves → prod deploy (`CONFIRM_PROD_DEPLOY=1 ./tools/deploy-production.sh`)

## After merge to main (production stack, same server)

```bash
git checkout main && git pull
CONFIRM_PROD_DEPLOY=1 ./tools/deploy-production.sh
```

Production smoke (short): `/start` on live bot — same paths as above, especially stale-`en` user if available.
