# Renewal from balance charges the catalog-kopek price as Toman (100x)

**Status:** done (2026-09-10) — remnabot PR #32 (tasks 1–4, plus the compensating-refund fix found on the way)
**Repos:** `remnabot` only
**Upstream basis:** remnabot `origin/main` `96bf5a12`; `upstream/main` `4e6e9224` (v4.9.0)
**Kind:** bounded payment fix (fix + PR, TDD). Run the `fix-payment` skill. Phase C is **not** in
scope: don't collapse scales, and don't touch the transaction-row scale.

## Goal

Renewing a subscription from the wallet balance charges its Toman price, on every surface. Today
only the cabinet does. B2C and partner users alike (same renewal path).

## Findings (verified on `main` 2026-09-10)

`SubscriptionRenewalService.finalize()` (`app/services/subscription_renewal_service.py`, ~line 365):

```
charge_from_balance = charge_balance_amount
if charge_from_balance is None:
    charge_from_balance = final_total          # pricing.final_total = catalog price_kopeks
charge_from_balance = max(0, min(charge_from_balance, final_total))
… subtract_user_balance(db, user, charge_from_balance, …)   # balance is Toman 1:1 (Phase B)
```

| Caller | Passes `charge_balance_amount`? | Result |
|---|---|---|
| `app/cabinet/routes/subscription_modules/renewal.py:254` | `catalog_price_in_toman(price_kopeks)` | correct |
| `app/services/payment/cryptobot.py:544` (webhook) | `required_balance` (Toman, since #26) | correct |
| `app/handlers/menu.py:1663` (renew from the main menu) | no | **100x** |
| `app/handlers/subscription/purchase.py:1990` (bot renewal) | no | **100x** |
| `app/webapi/routes/miniapp.py:5404` (miniapp, balance covers price) | no | **100x** |

Effect: those renewals try to debit e.g. 20,000,000 for a 200,000-Toman renewal. Usually
`subtract_user_balance` refuses (insufficient funds; the bot shows «⚠ Ошибка списания средств»), so
balance renewals fail. A user whose balance is at least 100x the price gets charged 100x. The dev DB
has no renewal transactions from these paths (2026-09-10: its 19 renewal rows are all tariff-renewal /
auto-purchase rows of test user 433), so no dev data was affected; production must be
checked before release (read-only query for `subscription_payment` rows whose description says
renewal, «Продление» / «تمدید»).

Also check on each 100x path: the affordability pre-check before `finalize()` (it must use
`user_can_afford(balance_toman, price_kopeks)` from `app/utils/price_display.py`, not
`balance < final_total`), and the success/notification text amounts.

## Design

Fix the trap at its single source. When `charge_balance_amount is None`, default to
`catalog_price_in_toman(final_total)`, and clamp against `catalog_price_in_toman(final_total)` instead
of `final_total`. Explicit callers (cabinet, CryptoBot webhook) already pass Toman, so they're
unchanged. Rejected alternative: patching the three callers one by one leaves the default wrong for
the next caller.

Don't change what `finalize()` writes to the transaction row or `total_amount_kopeks` (the catalog
scale per `_BALANCE_SCALE_TRANSACTION_TYPES` in `app/utils/price_display.py`). That's Phase C, and
flipping it silently would misrender history.

## Vs. upstream

- Ours: the Toman 1:1 balance. Upstream's `finalize()` has no scale concept, so this is a
  one-function edit on upstream infra; note it for the next upstream merge.
- Reused as-is: `SubscriptionRenewalService`, `subtract_user_balance`, `catalog_price_in_toman`.
- No deferred gateway involved; `CRYPTOBOT_ENABLED` stays as it is.

## Tasks

1. **Failing test first:** new `tests/services/test_renewal_finalize_toman_charge.py`. `finalize()`
   with `final_total=20_000_000` and no `charge_balance_amount` debits `200_000`; an explicit
   `charge_balance_amount` is respected; the clamp caps at the Toman total. Patch
   `subtract_user_balance` and assert its amount.
2. **Fix** `finalize()` as in Design.
3. **Caller regression tests** (one per path): miniapp balance path (`tests/test_miniapp_payments.py`
   has fixtures), bot renewal (`purchase.py`), menu renewal (`menu.py`). Each asserts the debited
   amount is Toman and the affordability pre-check uses `user_can_afford`. Fix any pre-check that
   compares Toman to kopeks.
4. **Messages:** the renewal success/admin-notification text on these paths shows the price via
   `format_price(final_total)` (catalog, correct) and any balance via `format_balance`. Fix
   mismatches; any new or changed string gets en + fa keys in both locale copies (all five baked
   locales: `tests/test_locale_integrity.py`).

## Smoke test

Generate with `smoke-test-checklist` after implementation: top up a test user, renew from the bot
menu, from «اشتراک‌های من» → تمدید, and from the cabinet; each debits exactly the Toman price shown.

## Outcome

Done in remnabot PR #32. The production check is still open: this workspace has no read-only
production DB access. Run the release query there: `subscription_payment` rows described «Продление
подписки…» / «Автоматическое продление…», compared with the matching balance delta.
