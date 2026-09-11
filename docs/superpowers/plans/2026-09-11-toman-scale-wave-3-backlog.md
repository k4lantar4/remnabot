# Toman balance scale — wave 3 backlog (leftovers from waves 1–2)

**Status:** active (backlog — recorded 2026-09-11, not started; expand the chosen tasks into a full plan in
the session that picks this up)
**Repos:** `remnabot` first, then `frontend` where a task says so (bot-first, additive).
**Upstream basis:** remnabot `origin/main` `e51d7ed1`; frontend `origin/main` `05cda114`.
**Kind:** bounded payment/display fixes (fix + PR, TDD) unless a task says a product decision is needed.
Phase C stays out of scope. Background: `plans/done/2026-09-11-toman-scale-wave-2.md` (what waves 1–2
fixed, the helpers and the cabinet contract) and the `payment-fixer` agent memory.

## Goal

Close the remaining places where a Toman balance is shown or credited on the wrong scale, and the small
UX gaps the waves left in the cabinet. B2C and partner alike.

## Before release (not code)

- **Production check, read-only:** users charged 100x before bot #32–#37 (renewal, tariff switch, paid
  trial, gift, autopay, auto-purchase) and poll rewards credited 100x before #41. No read-only
  production access exists in this workspace — the user runs it.

## Tasks (priority order)

1. **Cabinet: same-price tariff switch offered, then refused.** Tariffs with an equal price count as a
   downgrade, blocked by `TARIFF_SWITCH_DOWNGRADE_ENABLED=false`; the bot hides them, the cabinet
   (frontend #15) shows «تغییر» and the preview refuses. Bot: add a per-tariff `switch_allowed` (and a
   machine-readable error `code` on the switch 403/409 responses, instead of the cabinet matching message
   text) to the purchase-options/switch-preview API — additive. Frontend: hide or disable «تغییر» when
   `switch_allowed === false`; map codes to fa messages. Also: a subscription that lapses while the
   preview is open shows the bot's English message instead of handing off to the purchase form.
2. **Credit ×100 in the admin referral test-bonus tool.** The typed amount is credited ×100 (TEST_MODE is
   off). Fix the scale; its cap is a business number — **ask the user**, don't invent one.
3. **`LOW_BALANCE_ALERT`**: shows the balance ÷100 with «₽» in every locale; the threshold's scale is
   unverified. Verify, fix display via `format_balance`, locale keys in all five baked + runtime copies.
4. **Remaining `*_rubles = kopeks / 100` on Toman amounts (bot):** `app/webapi/routes/partners.py`,
   `app/webapi/routes/servers.py` (`balance_rubles`), cabinet `admin/campaigns/{id}/stats`
   `total_revenue_rubles` / `avg_revenue_per_user_rubles` (the cabinet no longer reads them). Additive
   `*_toman` where a consumer exists (grep `frontend/src`), otherwise fix in place.
5. **Admin partner pages (`/admin/partners/{id}`, `/admin/partners/stats`)** have no `*_toman` fields;
   the cabinet shows them 1:1 per frontend #14. Verify each field's scale; add `*_toman` where mixed.
6. **Unverified cabinet admin pages:** `AdminWheel` (`total_revenue_kopeks / 100`), `AdminTrafficUsage`
   (`total_spent_kopeks`), `AdminBulkActions` spent column — verify the bot field's scale, fix the ones
   that are off.
7. **Referral odds and ends (bot):** the levels referral scheme (off) still uses `format_price` on Toman;
   unused `process_referral_purchase` computes commission on the unconverted catalog amount; a refund
   (wave 2 Task 1) does not restore a consumed promo offer.

## Not in this backlog

- `wheel_service` spin cost (RUB stars rate) and the cabinet top-up form's kopek semantics → the
  Stars/CryptoBot Toman-rate plan (`2026-09-10-cryptobot-topup-toman-rate.md`).
- Russian texts left in withdrawal/risk admin screens, campaign screens, renewal success messages and the
  cabinet admin promo default message (with «₽») → `fix-translation`.
- Switching a 30-day subscription to the daily tariff resets its end date to one day — upstream bot
  behaviour on both surfaces; a product question if it matters.
- Admin bot withdrawal detail `KeyError` for a request without `risk_analysis` — bot-only admin screen.
- `ServerManagementSheet` prices lack a thousands separator (classic mode only).

## Smoke test

`smoke-test-checklist` per PR (ledger `/opt/project/SMOKE-TESTS.md`), cabinet screens only.
