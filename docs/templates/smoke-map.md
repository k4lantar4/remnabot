# Smoke map — Phase 4 + 4b + 4c (my_sub onboarding + cabinet UX polish)

> Branch `i18n/fa-onboarding-my-sub` @ `f8e27dda`; staging deployed 2026-06-24.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-onboarding-my-sub` |
| Phase 4 | `2c572ed0` fa.json keys, `6b7b36b7` detail onboarding UI |
| Phase 4b | `bdc1021e` miniapp copy, `cabe43f3` smart WebApp URL, `ec15aca4` single connect button |
| Phase 4c | `a09dd053` bot labels, `f9d05116` cabinet fa copy, `f8e27dda` Subscription.tsx CTA |
| Staging | `make staging-rebuild` + `make staging-health` ✓ |

## What changed

### Bot `app/localization/locales/fa.json`

- Detail onboarding: `MY_SUB_DETAIL_ONBOARDING`, `MY_SUB_DETAIL_FIRST_CONNECT`, `MY_SUB_BTN_CONNECT_LINK`
- Purchase success: `POST_PURCHASE_ONBOARDING` — mini-app flow (no manual paste)
- Connect screen: `SUBSCRIPTION_CONNECT_MINIAPP_MESSAGE` — mini-app explainer
- **Phase 4c:** `MY_SUB_DETAIL_HEADER` → `نام اشتراک:`; `MY_SUB_BTN_TRAFFIC` → `خرید ترافیک اضافه`; `MY_SUB_BTN_AUTOPAY` → `تمدید خودکار از اعتبار`

### Cabinet `cabinet/src/locales/fa.json` + `Subscription.tsx` (Phase 4c)

- `subscription.traffic` → `حجم`; new `subscription.volumeEmptyHint` when used = 0 GB
- Connect card: `dashboard.connectGuideTitle` / `connectGuideSubtitle` — no device count on CTA box

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
| 6 | Subscription detail (`@mrj7_bot`) | `📋 نام اشتراک: u_…`; buttons «خرید ترافیک اضافه» / «تمدید خودکار از اعتبار» |
| 7 | Staging cabinet → active sub page | Section label «حجم»; hint when 0 GB used; connect box «🔗 راهنمای اتصال — برای وصل شدن ضربه بزنید» (no «۰ از ۵») |
| 8 | Tap connect box | `/connection?sub=` → InstallationGuide |

## Sign-off

- [ ] User smoke on staging
- [ ] PR → merge → prod deploy
