# Smoke map — Phase 8 cabinet Latin digits + RTL copy

> Branch `i18n/fa-cabinet-latin-digits`; staging deployed after 3 commits (Commit 3 LtrIsolate skipped).

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-cabinet-latin-digits` |
| Commit 1 | `0ef8cc37` — Latin digits in 22 user paths (`cabinet/src/locales/fa.json`) |
| Commit 2 | `dcca3852` — RTL/bidi copy fixes (QR order, steps, گیگ, Stars Persian) |
| Commit 3 | skipped — JSON fixes sufficient; no `LtrIsolate.tsx` |
| Commit 4 | `c76b900d` — `test_cabinet_user_fa_has_latin_digits` + QR order guard |
| Staging | `make staging-rebuild` + `make staging-health` |
| Surfaces | Staging cabinet (`staging-host-cabinet`, port 3021) |

## What changed

**Commit 1 — Western digits (0–9):** 22 user paths across `auth.passwordTooShort`, `dashboard.usageLast14Days`, `subscription.trafficReset.MONTH_ROLLING`, `subscription.connection` steps, `subscription.tvQuickConnect`, `referral.partner`, `landing.periodLabels` d1–d456.

**Commit 2 — RTL-safe copy:** `showQR` / `scanBtn` QR word order; connection steps `مرحله 1:` … `مرحله 3:`; traffic labels `گیگ` instead of `GB`; Persian wrappers for OAuth session, Stars payment strings.

**Guard:** user cabinet paths with Persian digits → **0** (admin unchanged).

## User smoke checklist (staging cabinet)

| # | Path | Expect |
|---|------|--------|
| 1 | Register — password too short | `8 کاراکتر`; digits not flipped |
| 2 | Dashboard chart label | `14 روز` reads left-to-right within RTL page |
| 3 | Subscription → connection guide (`/connection`) | Steps show `مرحله 1:` … `مرحله 3:`; title `راهنمای اتصال VPN` |
| 4 | Purchase wizard → confirm step | `حجم: N گیگ` — no `GB` bidi jump |
| 5 | Traffic top-up sheet | Limit line `…گیگ`; package buttons readable |
| 6 | TV quick connect | `5 رقمی`; `اسکن کد QR` not `QR کد` |
| 7 | Balance → Stars error (outside miniapp) | `پرداخت با ستاره فقط در مینی‌اپ تلگرام` |
| 8 | Landing period picker | `1 روز`, `1 هفته`, Latin digits |
| 9 | Wheel → Stars payment label | `ستاره‌های تلگرام` |
| 10 | Admin cabinet | unchanged (admin track) |

**Regression:** Phase 7 device terminology (`کاربر`/`اتصال`), Toman amounts, Jalali dates, Phase 6 `سرویس` labels.

## Sign-off

- [ ] User smoke on staging cabinet
- [ ] PR → merge → prod deploy
