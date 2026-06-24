# Smoke map — Phase 4 + 4b (my_sub onboarding + smart miniapp connect)

> Branch `i18n/fa-onboarding-my-sub` @ `ec15aca4`; staging deploy pending user smoke.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-onboarding-my-sub` |
| Phase 4 | `2c572ed0` fa.json keys, `6b7b36b7` detail onboarding UI |
| Phase 4b | `bdc1021e` miniapp copy, `cabe43f3` smart WebApp URL, `ec15aca4` single connect button |
| Staging | `make staging-rebuild` + `make staging-health` |

## What changed

### Bot `app/localization/locales/fa.json`

- Detail onboarding: `MY_SUB_DETAIL_ONBOARDING`, `MY_SUB_DETAIL_FIRST_CONNECT`, `MY_SUB_BTN_CONNECT_LINK`
- Purchase success: `POST_PURCHASE_ONBOARDING` — mini-app flow (no manual paste)
- Connect screen: `SUBSCRIPTION_CONNECT_MINIAPP_MESSAGE` — mini-app explainer

### Bot `app/handlers/subscription/my_subscriptions.py`

- Onboarding block on active subscription detail; first-connect hint when HWID count is 0
- **One** connect button (removed duplicate setup guide row)

### Bot `app/utils/subscription_utils.py` + `links.py`

- `resolve_connect_webapp_url()` — cabinet `/connection?sub=ID` when RemnaWave app config exists; else raw subscription link
- `handle_connect_subscription` miniapp mode uses smart URL; early `callback.answer()`

## User smoke checklist (`@mrj7_bot`)

| # | Path | Expect |
|---|------|--------|
| 1 | Buy tariff → success → «اشتراک من» | Onboarding mentions mini-app (not v2rayNG paste) |
| 2 | Subscription detail | One button: `🔗 دریافت لینک و راهنمای اتصال`; onboarding block |
| 3 | Tap connect | WebApp opens; with RemnaWave apps → cabinet `/connection` platform picker |
| 4 | Tap connect (no app config) | WebApp opens subscription link (`sub.*`) |
| 5 | Expired sub detail | No onboarding block |

## Sign-off

- [ ] User smoke on staging
- [ ] PR → merge → prod deploy
