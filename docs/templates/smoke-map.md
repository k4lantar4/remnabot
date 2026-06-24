# Smoke map — Phase 4 (my_subscriptions onboarding)

> Branch `i18n/fa-onboarding-my-sub` @ `6b7b36b7`; staging deployed 2026-06-24.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-onboarding-my-sub` |
| Commits | `2c572ed0` fa.json, `6b7b36b7` my_subscriptions.py |
| Staging | `make staging-rebuild` + `make staging-health` |

## What changed

### Bot `app/localization/locales/fa.json`

- Updated `MY_SUB_BTN_CONNECT_LINK` → `🔗 دریافت لینک و راهنمای اتصال`
- New `MY_SUB_DETAIL_ONBOARDING` — 2-step connect guide on detail screen
- New `MY_SUB_DETAIL_FIRST_CONNECT` — nudge when no HWID connections yet
- New `MY_SUB_BTN_SETUP_GUIDE` → `📖 آموزش اتصال`

### Bot `app/handlers/subscription/my_subscriptions.py`

- `show_subscription_detail()` — onboarding block for active subs; first-connect hint when HWID count is 0 or unknown
- `_fetch_connected_devices_count()` — RemnaWave HWID API (early `callback.answer()` before I/O)
- `_build_subscription_detail_keyboard()` — setup guide row (`sl:{sub_id}` → existing connect flow)

## User smoke checklist (`@mrj7_bot`)

| # | Path | Expect |
|---|------|--------|
| 1 | Buy tariff → success → tap «اشتراک من» | Detail opens (Phase 3 path) |
| 2 | Detail body (active sub) | `راهنمای اتصال` block; `👥 تعداد کاربر` line |
| 3 | New / zero-HWID sub | `هنوز وصل نشده‌اید؟` line present |
| 4 | Detail buttons | `🔗 دریافت لینک و راهنمای اتصال` + `📖 آموزش اتصال` |
| 5 | Tap either connect button | Platform guide / link flow; spinner clears quickly |
| 6 | Expired sub detail | No onboarding block; renew/delete only |

## Sign-off

- [ ] User smoke on staging
- [ ] PR → merge → prod deploy
