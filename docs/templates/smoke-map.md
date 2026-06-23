# Smoke map — Phase 3 (purchase success copy)

> Branch `i18n/fa-copy-purchase-success` — awaiting user smoke on `@mrj7_bot` + staging cabinet.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-copy-purchase-success` |
| Commits | `35391a7e` fa.json, `e2751e1d` tariff_purchase.py, `5e3061d4` cabinet fa.json |
| Staging | `make staging-rebuild` + `make staging-health` |

## What changed

### Bot `app/localization/locales/fa.json`

- New `POST_PURCHASE_ONBOARDING` — 3-step connect guide
- Updated success keys: `TARIFF_PURCHASE_SUCCESS`, `TARIFF_DAILY_SUCCESS`, `TARIFF_RENEW_SUCCESS`, `TARIFF_CHANGE_SUCCESS`, `TARIFF_SWITCH_SUCCESS`, `TARIFF_SWITCH_DAILY_SUCCESS`, `TARIFF_INSTANT_SWITCH_*`
- Copy: `سرویس`, `حجم`, `مبلغ پرداخت`, `مدت`, short inline CTA
- `TARIFF_INFO_HEADER`, `CABINET_PURCHASE_TARIFF_SUCCESS`, `SIMPLE_SUB_PAYMENT_*`

### Bot `app/handlers/subscription/tariff_purchase.py`

- `_with_post_purchase_onboarding()` appends numbered block at 8 success `edit_text` sites

### Cabinet `cabinet/src/locales/fa.json`

- `successNotification.tariff` → `سرویس`
- `successNotification.goToSubscription` → `رفتن به اشتراک من`
- `successNotification.subscriptionPurchased.title` → `سرویس خریداری شد!`

## User smoke checklist (`@mrj7_bot`)

| # | Path | Expect |
|---|------|--------|
| 1 | Buy tariff (custom or preset) → success | `سرویس`, `حجم`, `مبلغ پرداخت`; numbered `3 گام تا اتصال`; no `تعرفه` |
| 2 | Tap «اشتراک من» on success keyboard | Opens subscription detail |
| 3 | Renew subscription | Same copy style on `TARIFF_RENEW_SUCCESS` |
| 4 | Switch / instant-switch tariff (if available) | Aligned success copy + onboarding block |
| 5 | Cabinet purchase (staging cabinet URL) | Success modal: `سرویس` label, `رفتن به اشتراک من` button |

## Sign-off

- [x] User smoke تایید 2026-06-24
- [ ] PR merged → prod smoke
