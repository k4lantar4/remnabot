# Smoke map — Cabinet subscription sheets currency (تومان)

> Branch `fix/cabinet-subscription-sheets-currency`; staging cabinet rebuild only.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `fix/cabinet-subscription-sheets-currency` |
| Commit | `8a65e958` — `useCurrency` in traffic/device/server sheets |
| Files | `TrafficTopupSheet.tsx`, `DeviceTopupSheet.tsx`, `ServerManagementSheet.tsx` |
| Staging | `make staging-cabinet-build` (cabinet only — no bot rebuild) |
| Cabinet URL | `https://staging-host-cabinet.rookari.com` (port `3021`) |
| Bot | `@mrj7_bot` (login via Telegram if needed) |

## What changed

- Subscription page «گزینه‌های اضافی» sheets no longer hardcode `₽`.
- Prices use `useCurrency`: `30,000 تومان` for `fa` (comma-grouped Latin digits).
- Fixes double `₽ ₽` on discounted traffic cards in RTL/mobile.

## User smoke checklist (staging cabinet, fa locale)

| Step | Path | Expected |
|------|------|----------|
| Traffic topup | `/subscriptions/:id` → **خرید ترافیک بیشتر** | Package prices show `N تومان`, not `₽` |
| Discount card | Same, package with `-50%` badge | Strikethrough + final price both `تومان`; no double ruble |
| Device topup | **افزودن کاربر بیشتر** (if enabled) | Per-device / total prices in `تومان` |
| Server management | **مدیریت سرورها** (classic mode, if shown) | Country add-on prices in `تومان` |
| Balance prompt | Select package above balance | Insufficient-balance line consistent `تومان` |

**Regression:** `ru` locale still shows ruble amounts; tariff purchase wizard unchanged.

## Sign-off

- [ ] User smoke on staging cabinet (`تایید`)
- [ ] PR → merge → prod deploy (after approval)
