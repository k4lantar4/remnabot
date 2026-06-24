# Smoke map — Phase 6 user تعرفه → سرویس (fa.json)

> Branch `i18n/fa-tariff-to-service-json`; staging deploy after 1 commit.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-tariff-to-service-json` |
| Commit | `03d6743e` — 66 user keys in `app/localization/locales/fa.json` |
| Staging | `cp fa.json` + `make staging-rebuild` + `make staging-health` |
| Scope | Bot + miniapp API keys only; cabinet React deferred (Phase 6b) |

## What changed

Single-file terminology migration: all non-`ADMIN_*` keys containing `تعرفه` now use `سرویس` (and derived forms: `سرویس‌ها`, `سرویسی`, `سرویس روزانه`, `تغییر سرویس`).

**Already سرویس from prior phases (unchanged):** `TARIFF_*_SUCCESS`, `TARIFF_PURCHASE_CONFIRM_BODY`, pre-invoice breakdown keys.

**Sample keys updated:**

| Group | Examples |
|-------|----------|
| Menu | `MAIN_MENU_TARIFF_LINE` → `📦 سرویس:` |
| Callbacks | `CB_TARIFF_NOT_FOUND`, `CB_NO_TARIFFS_AVAILABLE` |
| Confirm (legacy) | `TARIFF_PURCHASE_CONFIRM`, `TARIFF_RENEW_CONFIRM` |
| Switch flows | `TARIFF_SWITCH_LIST_TITLE`, `TARIFF_INSTANT_UPGRADE` |
| Ledger | `TARIFF_PURCHASE_LEDGER_DESC` → `خرید سرویس` |
| Miniapp | `MINIAPP_TARIFF_SWITCH_SUCCESS` |
| Campaign | `CAMPAIGN_BONUS_TARIFF` |

**Guard:** `rg 'تعرفه' app/localization/locales/fa.json | rg -v ADMIN_` → **0** user keys.

## User smoke checklist (`@mrj7_bot`)

| # | Path | Expect |
|---|------|--------|
| 1 | Main menu (active subscription) | `📦 سرویس:` — not `تعرفه` |
| 2 | Buy → pick tariff → confirm | Labels say `سرویس` (pre-invoice + legacy confirm) |
| 3 | Insufficient balance during purchase | Error body: `📦 سرویس:` |
| 4 | Switch tariff flow | Titles/errors: `سرویس` / `تغییر سرویس` |
| 5 | Campaign bonus (if testable) | `سرویس «…»` |
| 6 | Balance history after purchase | Ledger: `خرید سرویس` |
| 7 | Miniapp tariff switch (if used) | `سرویس به «…» تغییر کرد` |

**Regression:** Phases 3–5 success/onboarding/pre-invoice copy unchanged; amounts still `تومان` with Latin digits.

## Sign-off

- [ ] User smoke on staging (`@mrj7_bot`)
- [ ] PR → merge → prod deploy
