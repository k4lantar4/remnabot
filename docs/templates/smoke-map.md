# Smoke map — Phase 10 Slice A: bot admin locale keys

> Branch `i18n/admin-fa-completion` @ `96133025`; bot `fa.json` only; awaiting user smoke.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/admin-fa-completion` |
| Commit | `96133025` — 7 missing `texts.t` keys (C2C inbox back + disabled payment providers) |
| Files | `app/localization/locales/fa.json` |
| Deploy | `make staging-rebuild` (bot image + locale copy) |
| Bot | `@mrj7_bot` (staging) |
| Locale | `fa` admin (`get_texts(db_user.language)`) |

## What changed

- `C2C_ADMIN_INBOX_BACK` → `📥 صندوق ورودی` (was inline default only)
- `PAYMENT_AURAPAY`, `PAYMENT_KASSA_AI`, `PAYMENT_OVERPAY`, `PAYMENT_PAYPEAR`, `PAYMENT_ROLLYPAY`, `PAYMENT_SEVERPAY` → Latin brand labels with `💳` prefix (disabled providers; admin config test buttons)

## User smoke checklist (staging Telegram, fa admin)

| Step | Path | Expected |
|------|------|----------|
| C2C inbox back | Admin panel → C2C inbox → open receipt → tap back | Button `📥 صندوق ورودی` |
| Regression | Cabinet `/admin` (Slice B) | Still Persian — unchanged |
| Regression | User main menu | Still Persian — unchanged |

Payment provider test buttons: optional (providers disabled in `.env`).

## Sign-off

- [ ] User smoke on `@mrj7_bot` (**تایید** pending)
- [ ] Ship with remaining Phase 10 slices or standalone PR

---

# Smoke map — Phase 10 Slice B: cabinet admin Persian (CLOSED)

> Branch `i18n/admin-fa-completion`; cabinet `fa.json` only; user smoke **تایید** 2026-06-25.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/admin-fa-completion` |
| Commits | `07a7db29` plural/misc (58 keys) · `9902058a` banSystem (148) · `7063e3fe` pinnedMessages + patch tool |
| Files | `cabinet/src/locales/fa.json`, `tools/cabinet_admin_fa_slice_b.py` |
| Deploy | `make staging-cabinet-build` |
| Cabinet URL | staging cabinet (`3021` / `staging-host-cabinet`) |
| Locale | `fa` (admin routes use global i18n; no force-en) |

## What changed

- Cabinet admin `en_only` paths: **206 → 0** (plural `_one`, banSystem, user confirm dialogs, news combobox).
- `banSystem.*` — dashboard, agents, settings, punishments, user detail (Persian).
- `admin.pinnedMessages.*` — was full English leak; now Persian.
- `admin.settings` — already 172/172 Persian (no commit needed).

## User smoke checklist (staging cabinet, fa admin)

| Step | Path | Expected |
|------|------|----------|
| Ban monitoring | `/admin` → نظارت بر مسدودسازی | Tabs/settings Persian |
| Pinned messages | `/admin/pinned-messages` | Create/edit UI Persian |
| User actions | `/admin/users` → delete/disable confirm | Persian dialogs |
| Regression | `/subscription` (user) | Unchanged Persian user UI |

## Sign-off

- [x] User smoke on staging cabinet (**تایید** 2026-06-25)
- [ ] PR → merge → prod deploy (when Phase 10 scope agreed)

---

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

---

# Smoke map — Cabinet partner checkout (یادداشت + نام دلخواه)

> Branch `feat/cabinet-partner-checkout`; staging bot + cabinet rebuild.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `feat/cabinet-partner-checkout` |
| Scope | Partner-only fields on `/subscription/purchase` confirm (cabinet + miniapp WebView) |
| API | `POST /cabinet/subscription/purchase-tariff` + `GET /cabinet/referral/partner/status` (`panel_brand_prefix`) |
| Staging | `make staging-rebuild` + `make staging-health` |
| Cabinet URL | staging cabinet (`3021` / `staging-host-cabinet`) |
| Bot | `@mrj7_bot` (partner account) |

## User smoke checklist (approved partner, fa)

| Step | Path | Expected |
|------|------|----------|
| Open purchase | Cabinet/miniapp → خرید سرویس → انتخاب سرویس → تأیید | بلوک «یادداشت خرید» + «نام دلخواه» visible |
| Non-partner | Same with retail account | No partner block |
| Prefill brand | Partner with saved prefix | نام دلخواه input prefilled |
| Set note + brand | Enter note + `mobile_x` → خرید | Panel username `mobile_x_{serial}`; note in description |
| Renew path | Renew existing sub | Purchase works; username unchanged on panel |

## Sign-off

- [ ] User smoke on staging (`تایید`)
- [ ] PR → merge → prod deploy (after approval)
