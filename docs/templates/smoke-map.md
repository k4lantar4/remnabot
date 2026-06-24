# Smoke map — Phase 5 traffic-first purchase funnel UX

> Branch `i18n/fa-traffic-step-ux`; staging deploy after 5 commits.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-traffic-step-ux` |
| Commits | `22ca0bc6` list, `1dfa334b` fa keys, `af010118` traffic intro, `82b51e4a` period hint, `191e5363` confirm |
| Staging | `make staging-rebuild` + `make staging-health` |

## What changed

### Screen 1 — Tariff list (`format_tariffs_list_text`)

- Removed `1 گیگ / 5 📱` from list lines
- Shows `tariff.description` from admin DB for fa users (migration placeholders skipped)

### Screen 2 — Volume step (`format_traffic_step_preview`)

- `TARIFF_TRAFFIC_STEP_INTRO` — no default volume line on first paint
- `TARIFF_CUSTOM_TRAFFIC_STEP_HINT` / `TARIFF_RENEW_TRAFFIC_STEP_HINT` — preset-flow guidance
- **Package buttons unchanged** (`🔥−%` on buttons if configured)

### Screen 3 — Period step (`show_period_step_after_traffic`)

- `TARIFF_PERIOD_STEP_VOLUME_PRICE` + `TARIFF_PERIOD_STEP_CTA` replace confusing formula hint
- **Period inline buttons unchanged**

### Screen 4 — Pre-invoice (`format_tariff_purchase_confirm_text`)

- `پیش‌فاکتور`, `سرویس` / `حجم` / `مدت`, `مبلغ حجم` / `مبلغ مدت`, `قابل پرداخت`

### Keys (`app/localization/locales/fa.json`)

- `TARIFF_TRAFFIC_STEP_INTRO`, `TARIFF_PERIOD_STEP_*`, confirm `TARIFF_PURCHASE_CONFIRM_*`

## User smoke checklist (`@mrj7_bot`)

**Prerequisite:** Persian `description` on traffic-first tariffs in admin.

| # | Path | Expect |
|---|------|--------|
| 1 | Menu → buy → tariff list | Name + `از X تومان` + description; no `گیگ / 📱` |
| 2 | Pick traffic-first tariff | Intro: name + تعداد کاربر + hint; **no** «1 گیگ» in header |
| 3 | Package buttons | Unchanged (`🔥−%` if present before) |
| 4 | Tap 10 GB | Period: حجم انتخابی + `مبلغ حجم` + CTA; no formula line |
| 5 | Period buttons | Unchanged (`🔥−%` if present before) |
| 6 | Pick period | `پیش‌فاکتور` with سرویس/حجم/مدت breakdown |
| 7 | Confirm purchase | Success + onboarding (unchanged) |
| 8 | Renew traffic-first sub | Renew hints on volume + period steps |

## Sign-off

- [ ] User smoke on staging
- [ ] PR → merge → prod deploy
