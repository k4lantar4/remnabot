# Toman scale batch A — admin amounts 100x off, and the daily-switch refund

- Status: active
- Repos: remnabot (branch `fix/toman-scale-batch-a`), then frontend (branch `fix/referral-level-fixed-toman`)
- Upstream basis: remnabot origin/main `0b5ec3ff` (fork 4.2.0+rookari.1); frontend origin/main `91009e94`
- Findings: F-014, F-015, F-016, F-030, F-031, F-051, F-032 (`/opt/project/FINDINGS.md`)

## Goal

Admins (owner) see and enter money in real Toman everywhere this batch touches: bot income stats,
referral earnings, the web-API transaction list, referral-level fixed rewards (bot + cabinet), the
bot quick top-up buttons; a cabinet balance edit gets the same 10,000,000-Toman cap as the bot. A
daily-tariff switch that was delivered is never refunded. B2C and partner alike.

## Design

Each site formats or stores a **balance-scale** value (wallet Toman 1:1) with the **catalog**
helper (`format_price`, ÷100) or multiplies input by 100. The fix is to use the balance helpers
that already exist — `settings.format_balance` / `texts.format_balance`,
`display_transaction_amount_from_storage`, `storage_sum_to_display_toman`,
`balance_from_display_amount` (all in `app/utils/price_display.py` / `app/config.py`). No new scale
logic, no change to `_BALANCE_SCALE_TRANSACTION_TYPES`; nothing moves toward or away from Phase C.
F-032 copies the charged/delivered pattern the periodic switch already uses
(`tariff_purchase.py` `confirm_tariff_switch`, `refund_undelivered_debit`).

Out of scope (record as new findings if still true at PR time): Russian labels in
`app/handlers/admin/statistics.py`; YooKassa ₽ bound messages in `balance/main.py` (deferred
gateway); `app/webapi/routes/contests.py` if its amounts turn out to mix scales (Task 4).

## Vs. upstream

- Ours: the Toman wallet scale (Phase B) and its display helpers. The edits are one-line swaps at
  upstream call sites (`format_price` → `format_balance`, dropping `* 100`); upstream merges
  touching those lines will conflict visibly, not silently.
- Reused as-is: `get_transactions_statistics` (keys are added, none renamed — the cabinet
  `admin_stats.py` and `webapi/routes/stats.py` keep reading the old ones), `refund_undelivered_debit`,
  `NumberField` in the cabinet.
- No deferred gateway is enabled or depended on; the quick-amount keyboard stays method-agnostic.

## Tasks

### 1. F-014 — cabinet balance edit capped like the bot

- Repo/files: remnabot `app/utils/price_display.py` (new constant `ADMIN_BALANCE_EDIT_MAX_TOMAN = 10_000_000`),
  `app/handlers/admin/users.py:74` (drop the local `_ADMIN_BALANCE_EDIT_MAX_TOMAN`, import the shared one;
  uses at `:2463,:2466`), `app/cabinet/schemas/users.py:342-352` (`UpdateBalanceRequest.amount_kopeks`
  and `.amount_display`: `ge=-ADMIN_BALANCE_EDIT_MAX_TOMAN, le=ADMIN_BALANCE_EDIT_MAX_TOMAN` — both
  fields are Toman 1:1, see the route at `app/cabinet/routes/admin_users.py:1273-1295`).
- Interfaces: produces `ADMIN_BALANCE_EDIT_MAX_TOMAN` (int) for later imports.
- Test: `tests/cabinet/` new test — `UpdateBalanceRequest(amount_display=10_000_001)` raises
  `ValidationError`, `10_000_000` and `-10_000_000` pass; existing `tests/handlers/test_admin_balance_edit_toman.py` stays green.
- i18n: none (422 from pydantic; the cabinet already shows API errors).

### 2. F-015 — bot admin income stats in Toman

- Repo/files: remnabot `app/database/crud/transaction.py` `get_transactions_statistics` — add
  `totals.expenses_toman` (withdrawal is balance scale → the raw sum), `totals.profit_toman`
  (`income_toman - expenses_toman`), and `by_payment_method[m]['amount_toman']` (group the payment-method
  query by `payment_method, type` and sum `storage_sum_to_display_toman` per row; keep `count` and
  `amount` as today). `app/handlers/admin/statistics.py` — `show_revenue_statistics` (`:148-166`),
  `show_summary_statistics` (`:264-290`, ARPU from `income_toman`), `show_revenue_by_period`
  (`:335-350`, sum `amount_toman` from `get_revenue_by_period`) print every money value with
  `settings.format_balance(<*_toman>)`.
- Interfaces: additive keys only; `admin_stats.py` / `webapi/routes/stats.py` untouched.
- Test: extend `tests/cabinet/test_admin_stats_toman_scale.py` — a 50,000-Toman deposit + a
  catalog subscription payment of `price_kopeks=10_000_000` via method `card` →
  `by_payment_method['card']['amount_toman'] == 150_000`, `profit_toman` = income − withdrawals.
  New handler test (`tests/handlers/test_admin_statistics_toman.py`): rendered text contains the
  `format_balance` of 150,000, not of 1,500.
- i18n: none (labels stay as they are — out of scope).

### 3. F-016 — referral earnings in Toman (admin card + menu placeholder)

- Repo/files: remnabot `app/handlers/admin/users.py:2963,2964,2970` → `settings.format_balance`;
  `app/services/menu_layout/service.py:984` → `texts.format_balance(context.referral_earnings_kopeks)`.
  Source is `get_user_referral_stats` (`app/database/crud/referral.py:483`), `ReferralEarning` sums, Toman 1:1.
- Interfaces: none.
- Test: menu layout — `{referral_earnings}` with `referral_earnings_kopeks=20_000` renders
  `format_balance(20_000)`. Admin card: assert on the text builder around `users.py:2955` if it
  can be called without a live bot; otherwise covered by the menu test + review.
- i18n: none.

### 4. F-030 — web API `amount_rubles` per transaction type

- Repo/files: remnabot `app/webapi/routes/transactions.py:25` →
  `amount_rubles=display_transaction_amount_from_storage(transaction.amount_kopeks, transaction.type)`.
  Contests (`app/webapi/routes/contests.py:188,215`): first check which transaction types feed
  `ReferralContestEvent.amount_kopeks` (`app/database/crud/transaction.py:185,259` →
  `referral_contest_service.on_subscription_payment`). One scale → convert with the matching helper
  in this task; mixed → leave the code, new F- entry.
- Interfaces: response field names unchanged.
- Test: new `tests/webapi/test_transactions_serialize.py` — `_serialize` of a `deposit` 50,000 →
  `amount_rubles == 50000.0`; `subscription_payment` 5,000,000 → `50000.0`.
- i18n: none.

### 5. F-031 — referral-level fixed reward entered and stored in Toman (bot)

- Repo/files: remnabot `app/handlers/admin/referral_levels.py` — `:1056` store the typed Toman 1:1
  (parse with `balance_from_display_amount` so fa digits/separators work; money fields become
  integers, no decimals); display `:128,:275,:284,:1072` with `settings.format_balance`; fix the
  comment at `:1055` ("entered in rubles, stored in kopeks"). The engine already credits these 1:1
  (`app/services/referral_reward_service.py:565,608`); the cabinet route
  `app/cabinet/routes/admin_referral_levels.py` passes the field through unscaled (verified), and the
  legacy import copies `REFERRAL_*_BONUS_KOPEKS`, which are Toman (`referral_service.py:697,731`) — both stay.
- Interfaces: `referrer_fixed_kopeks` / `referee_fixed_kopeks` keep their names; meaning is now
  documented as Toman 1:1 (matches Task 6).
- Test: `tests/handlers/test_admin_referral_levels.py` `TestValueInput` — rename
  `test_money_is_entered_in_rubles_stored_in_kopeks`; input `'150,000'` → stored `150000`, input
  `'۱۵۰۰۰۰'` → `150000`.
- i18n: none (no string text changes; the Russian admin texts belong to F-009).

### 6. F-031 — cabinet referral-level inputs (frontend)

- Repo/files: frontend `src/pages/AdminReferralLevels.tsx:458-461,503-506` — `value` without `/ 100`,
  drop `scale={100}` (default 1); `src/pages/adminReferralLevels.test.tsx:215` — expect the typed
  Toman unchanged (e.g. `150000`).
- Interfaces: consumes the unchanged `PATCH` body fields `referrer_fixed_kopeks` / `referee_fixed_kopeks`.
- Test: the updated vitest case fails first against `scale={100}`.
- i18n: check the field label `admin.referralLevels.fixedAmount` in `frontend/src/locales/fa.json`
  and `en.json` states Toman; fix if it names another unit.

### 7. F-051 — bot quick top-up buttons and generic bounds in Toman

- Repo/files: remnabot `app/keyboards/topup_amounts.py:49-52` `format_quick_amount(amount_kopeks, language)`
  → `settings.format_price(amount_kopeks, language=language)` (quick amounts and method limits are
  on the Toman ×100 top-up scale, see F-052); caller `:98` passes `language`.
  `app/handlers/balance/main.py:624-636` — replace the two Russian ₽ literals with
  `texts.t('TOPUP_AMOUNT_TOO_LOW', …)` / `texts.t('TOPUP_AMOUNT_TOO_HIGH', …)` formatted with
  `texts.format_price(100)` / `texts.format_price(5_000_000)` (same bounds as today: 1 and 50,000).
- Interfaces: `format_quick_amount` gains a `language` parameter.
- Test: `tests/test_topup_amounts_keyboard.py` — `test_format_quick_amount` and the `'300 ₽'`
  assertion expect the `format_price` output; no `₽` in any button.
- i18n: `TOPUP_AMOUNT_TOO_LOW`, `TOPUP_AMOUNT_TOO_HIGH` (grep first — reuse if they exist) in
  `locales/en.json`, `locales/fa.json` and the baked twin `app/localization/locales/fa.json`
  (byte-identical), idiomatic Persian, Latin digits.

### 8. F-032 — daily switch: refund only an undelivered debit

- Repo/files: remnabot `app/handlers/subscription/tariff_purchase.py` `confirm_daily_tariff_switch`
  (`:4080-4380`). Add `charged = False` / `delivered = False` before the `try`; `charged = True`
  right after a successful `subtract_user_balance`; `delivered = True` right after the
  `await db.commit()` that saves the switched subscription (~`:4224`). Replace the inline refund in
  the `except` (rollback + `add_user_balance` + `_persist_failed_refund`) with
  `if charged and not delivered: await refund_undelivered_debit(db, db_user, catalog_price_in_toman(final_daily_price), <reason>, promo_snapshot=promo_snapshot)`,
  reason string built before the `try`, as in `confirm_tariff_switch` (`:4065`).
- Interfaces: none.
- Test: new `tests/handlers/test_daily_tariff_switch_refund.py` — (a) final `edit_text` raises after
  the commit → no refund, no `REFUND` row; (b) panel-independent failure before the commit (e.g.
  `get_all_server_squads` raises) → exactly one refund; (c) `subtract_user_balance` raises → no refund.
- i18n: none.

## Cross-repo contract

No endpoint or field changes. Task 6 only changes what the cabinet puts into the existing fields;
the bot route stores them as-is. Merge the remnabot PR (Tasks 1-5, 7, 8) first, then the frontend PR.
Release note for both PR bodies: any existing `referral_reward_levels` rows hold ×100 values and
must be divided by 100 during the production data merge (the table is absent in the dev DB).

## Smoke test

After implementation, run `smoke-test-checklist` (cabinet only): the admin balance edit above the
cap, and the admin referral-levels fixed amounts saving and reloading in Toman.
