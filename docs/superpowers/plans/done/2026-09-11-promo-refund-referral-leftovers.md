# Promo offer survives a refunded purchase; referral level-scheme leftovers (F-007)

**Status:** active
**Repos:** `remnabot` only. The cabinet reads none of the touched fields (grep `frontend/src/api`
for `promo_offer_discount`: display only, no contract change).
**Upstream basis:** remnabot `origin/main` `df7bd874`; `upstream/main` `bf33d125` (v4.9.1)
**Kind:** payment (run `fix-payment` for tasks 1-3 and 5), notif for task 4 (`fix-notif`).
**Origin:** finding F-007 in `/opt/project/FINDINGS.md` (from remnabot#41); the PR quotes it and
deletes the entry after merge.

## Goal

A user whose balance debit consumed a one-time promo offer (e.g. «20٪ تخفیف») and whose purchase then
failed gets both the money **and the offer** back, on every path that refunds. Referral rewards under
`REFERRAL_REWARD_SCHEME=levels` show Toman amounts at the right scale and in the user's language.
B2C and partner alike.

## Design

`subtract_user_balance(..., consume_promo_offer=True)` zeroes `promo_offer_discount_percent`,
`_source` and `_expires_at` in the same commit as the debit. Seven code paths already snapshot those
three fields before the debit and put them back when they refund (`tariff_purchase.py`
`handle_custom_confirm` / `confirm_tariff_purchase`, `subscription_auto_purchase_service.py` ×3,
`subscription_renewal_service.py`); the others refund money only, including the cabinet's own
`purchase_tariff` (`app/cabinet/routes/subscription_modules/purchase.py`, `_refund_charge`), which is
the path users actually hit because the bot runs in cabinet mode. We
lift the existing pattern into two small helpers next to `refund_undelivered_debit` and apply them
at every refunding path that lacks it. The restore is written **before** `add_user_balance` in
the refund, because `add_user_balance` commits. A missing snapshot (offer wasn't consumed) means
nothing to restore. No product decision: the existing restore sites show the intended behaviour.

Referral: `ReferralEarning` rows and level-scheme money (`referrer_fixed_kopeks`,
`referee_fixed_kopeks`, `outcome.money_credited`) are balance-scale Toman (credited 1:1 via
`add_user_balance`), so display goes through `settings.format_balance`, not `format_price` (÷100).
`process_referral_purchase` has no callers; its commission base is a catalog price and must be
converted with `catalog_price_in_toman` before crediting, so a future caller can't credit 100×.

Out of scope: paths with `consume_promo_offer` that do not refund at all (cabinet `switch_tariff`,
miniapp `purchase_tariff_endpoint` / `switch_tariff_endpoint`, `gift_purchase_service`,
`subscription_purchase_service.submit_purchase`, `menu.handle_activate_button`,
`purchase.confirm_extend_subscription`). They get no restore because they have no refund. If one
turns out to debit and then fail without refunding, that's a new `F-` entry, not this plan.

## Vs. upstream

- Ours: nothing market-specific. This is a correctness fix to upstream code (upstream has the same
  gap). The helpers live in our `app/services/balance_refund.py` (added by us in wave 2); the
  handler edits are 2-4 lines per site so hot-file conflicts stay small (`tariff_purchase.py`,
  `purchase.py` are hot files, see `remnabot/CLAUDE.md`).
- Reused as-is: `subtract_user_balance` consume logic, `add_user_balance`, `refund_undelivered_debit`,
  `_persist_failed_refund`, the referral reward engine.
- No deferred gateway touched or depended on.

## Tasks

### 1. Promo snapshot/restore helpers
- **Files:** `app/services/balance_refund.py`; test `tests/services/test_balance_refund_promo.py` (new).
- **Produces:**
  - `PromoOfferSnapshot` (frozen dataclass: `percent: int`, `source: str | None`,
    `expires_at: datetime | None`)
  - `snapshot_promo_offer(user, consume: bool) -> PromoOfferSnapshot | None`: `None` when
    `consume` is false or the percent is 0
  - `restore_promo_offer(user, snapshot: PromoOfferSnapshot | None) -> None`: sets the three
    fields, no commit
  - `refund_undelivered_debit(db, user, amount_toman, reason, *, promo_snapshot=None)`: calls
    `restore_promo_offer` after `db.refresh(user)` and before `add_user_balance` (which commits)
- **Test first:** refund with a snapshot restores all three fields and the balance; without a
  snapshot the fields stay zeroed; a failing `add_user_balance` still records the failed refund
  (existing behaviour kept). Use `tests/fixtures/sqlite_memory.py`.

### 2. Bot handlers: pass the snapshot on refund
- **Files:** `app/handlers/subscription/tariff_purchase.py` (`confirm_daily_tariff_purchase`,
  `confirm_tariff_extend`, `confirm_tariff_switch`, `confirm_daily_tariff_switch`,
  `confirm_instant_switch`, including its daily branch with `consume_promo_for_daily`),
  `app/handlers/simple_subscription.py` (`handle_simple_subscription_pay_with_balance`,
  `confirm_simple_subscription_purchase`), `app/handlers/subscription/purchase.py`
  (`_extend_existing_subscription`).
- **Consumes:** task 1 helpers. Take the snapshot right before `subtract_user_balance`; sites that
  call `refund_undelivered_debit` pass `promo_snapshot=`; sites with an inline
  `add_user_balance` refund call `restore_promo_offer` before it.
- **Test first:** one handler-level test per distinct refund shape (helper-based vs inline), for
  example `confirm_tariff_extend` and `confirm_daily_tariff_purchase`, with `extend_subscription`
  / subscription creation forced to raise: the offer percent is back after the refund. Put them in
  `tests/handlers/test_promo_offer_refund_restore.py`.

### 3. Cabinet purchase and background services
- **Files:** `app/cabinet/routes/subscription_modules/purchase.py` (`purchase_tariff` →
  `_refund_charge`: it re-loads the user by id after `db.rollback()`, so snapshot plain values
  before the debit and call `restore_promo_offer(refund_user, snapshot)` before its
  `add_user_balance`), `app/services/monitoring_service.py` (`_process_autopayments`),
  `app/services/subscription_auto_purchase_service.py` (`_auto_purchase_daily_tariff`); test
  `tests/services/test_promo_offer_refund_restore_services.py` (the cabinet case may go under
  `tests/cabinet/` if a purchase-route test harness already exists there).
- **Consumes:** task 1 helpers; same rule as task 2.
- **Test first:** the failure-after-debit branch of each restores the offer; for the cabinet
  route, a purchase whose subscription creation raises returns the error, the balance and the offer.

### 4. Level-scheme reward amounts and notification text
- **Files:** `app/services/referral_reward_service.py` (the `format_price(config.referrer_fixed_kopeks)`
  / `referee_fixed_kopeks` lines in the reward description helpers, ~1316/1417/1437/1608),
  `app/services/referral_service.py` (`_format_reward_line`, `_level_event_phrase`,
  `_notify_level_outcome`); test `tests/services/test_referral_level_notifications.py` (new, or extend
  the existing referral reward tests if one already covers these helpers).
- **Change:** `format_price` → `settings.format_balance` for these amounts; the hard-coded Russian in
  the three notification helpers moves to locale keys, rendered with the recipient's language
  (`get_texts(recipient.language)`).
- **Test first:** a 50,000 Toman fixed reward renders as `settings.format_balance(50000)` (not
  «500»); the fa notification contains no Cyrillic and no `₽`.
- **i18n:** new keys (prefix `REFERRAL_LEVEL_NOTIFY_…`: title for referrer, title for referee,
  "credited" line, days line with and without tariff suffix, the three event phrases, and the
  "member of your network (level N)" / "your referral {name}" sources) in all five baked locales
  (`app/localization/locales/{ru,en,ua,fa,zh}.json`, ru keeps today's Russian, ua/zh may carry
  English) **and** the runtime copies in `locales/`; `cmp` each pair. Persian must read naturally,
  e.g. «🎁 پاداش معرفی!», «واریز شد: …», Latin digits.

### 5. `process_referral_purchase` commission base in Toman
- **Files:** `app/services/referral_service.py` (`process_referral_purchase`); test in
  `tests/services/test_referral_level_notifications.py` or a new `test_referral_purchase_scale.py`.
- **Change:** `commission_amount = int(catalog_price_in_toman(purchase_amount_kopeks) * pct / 100)`;
  fix its log line's `/ 100`. Keep the function (upstream keeps it; deleting it only costs merges).
- **Test first:** 10% of a `1_000_000` catalog-kopek purchase credits 1,000 Toman and writes a
  1,000 `ReferralEarning`.

## Smoke test

After implementation: `smoke-test-checklist`. Cabinet surface: task 3's cabinet purchase
refund, which only shows up when a purchase fails after the debit. The checklist names how to
provoke that on dev (e.g. panel unreachable) or states that it can't be triggered by hand. Tasks
2, 4 and 5 have no cabinet surface (bot handlers; the level scheme is off).
