# Smoke map — Phase 7 cabinet device terminology

> Branch `i18n/fa-cabinet-device-terminology`; staging deployed after 2 commits.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-cabinet-device-terminology` |
| Commit 1 | `c794d287` — 96 paths in `cabinet/src/locales/fa.json` |
| Commit 2 | `8a3b3b13` — 20 `CABINET_*` keys in `app/localization/locales/fa.json` |
| Staging | `make staging-rebuild` + `make staging-health` |
| Surfaces | Staging cabinet (`staging-host-cabinet`, port 3021) + cabinet API toasts via bot |

## What changed

Terminology migration: user-facing `دستگاه` → `تعداد کاربر` / `کاربر` (HWID slot limits) or `اتصال` / `اتصال‌های فعال` (connected HWID list, revoke, delete).

**Cabinet React (`cabinet/src/locales/fa.json`):** 96 user paths across `successNotification`, `dashboard`, `subscription` (+ trial, connection, additionalOptions, revoke, cta), `info`, `onboarding`, `merge`, `landing`, `gift`.

**Bot API (`app/localization/locales/fa.json`):** `CABINET_DEVICES_*`, `CABINET_DEVICE_*`, `CABINET_TARIFF_SWITCH_DEVICES_RESET`.

**Guard:** user cabinet paths with `دستگاه` → **0** (admin sections unchanged, 30 hits remain).

## User smoke checklist (staging cabinet)

| # | Path | Expect |
|---|------|--------|
| 1 | Dashboard → active subscription card | `👥 کاربر:` usage line — not `دستگاه‌ها:` |
| 2 | Subscription detail page | Label `تعداد کاربر`; section `اتصال‌های فعال` |
| 3 | Purchase wizard → devices step | Step `تعداد کاربر`; counts `N کاربر` |
| 4 | Connection page (`/connection`) | `سیستم‌عامل خود را انتخاب کنید`; CTA `دریافت لینک اتصال` |
| 5 | Additional options → buy/reduce users | `افزودن کاربر`; API toast uses `کاربر` not `دستگاه` |
| 6 | Revoke link confirm dialog | `اتصال‌ها` disconnected wording |
| 7 | Gift / landing purchase flow | Column label `تعداد کاربر` |
| 8 | Merge accounts compare screen | `تعداد کاربر` label |
| 9 | Onboarding tour (first login) | Connect step: `راهنمای اتصال VPN` — no `دستگاه` |
| 10 | Admin cabinet (tariffs, users) | Still `دستگاه` — expected (Phase 10) |

**Regression:** Toman amounts, Jalali dates, Phase 6 `سرویس` labels, no Cyrillic in user UI.

## Sign-off

- [ ] User smoke on staging cabinet
- [ ] PR → merge → prod deploy
