# Wholesale (partner) discount on daily tariffs

**Status:** active — design awaiting the user's approval; no code yet.
**Repos:** `remnabot` only (no frontend change — see Design, point 3).
**Upstream basis:** `remnabot` `upstream/main` `bf33d125` (v4.9.1), `upstream/dev` `8ca59d6d`; fork
`origin/main` `1443fe79`. Nothing here derives from upstream: wholesale is ours.
**Decision it implements:** the user, 2026-09-11, answering open question 2 of
`plans/done/2026-09-09-upstream-selective-patches.md`: "برای روزانه اضافه کن" — an approved
partner's wholesale discount applies to daily tariffs too. Closes finding F-013.

## Goal

An approved partner (نماینده) on a daily tariff pays their wholesale rate every day, not only on
the first day, and the cabinet shows exactly that daily price. Partner only; B2C prices unchanged.

## Design

**Today (evidence on `1443fe79`), partner 433 at 3000 bps, tariff 9 «روزانه» = 1,000,000 kopeks
(10,000 Toman/day):**

| Step | Code path | Charged / shown |
|---|---|---|
| Tariff card, activation screen | `_build_tariff_response` → `daily_group_price` (group only) + the cabinet's `combinePromoDiscount` (active promo offer) | 10,000 − group − offer |
| First day (cabinet purchase) | `calculate_tariff_purchase_price` → `_calculate_tariff_core` wholesale branch | **7,000** |
| Every later day | `daily_subscription_service` → `daily_group_price` | 10,000 − group |
| Switch periodic → daily (first day) | `_calculate_switch_to_daily`: group + offer | 10,000 − group − offer |
| Switch daily → periodic | `_calculate_switch_from_daily`: group + offer | retail min period |

**Rule (the existing one, extended):** for an approved partner with `wholesale_discount_bps > 0`
(`PricingEngine.uses_wholesale_pricing`), wholesale **replaces** the promo-group discount and the
promo offer — exactly as `apply_checkout_discount` and `_calculate_tariff_core` already do. Not
stacked. A partner whose group discount is larger than their wholesale rate still gets only the
wholesale rate (unchanged rule, not a new number).

1. **One daily price function.** `PricingEngine.daily_group_price(daily_price_kopeks, user)`
   (Plan B's single source of the daily price; all ten callers — cabinet `purchase.py`,
   `helpers.py`, `daily.py`; `daily_subscription_service`; `subscription_auto_purchase_service`;
   Mini App ×3; bot `purchase.py` ×2) returns the wholesale price for a wholesale partner:
   `(apply_wholesale_discount(price)[0], round(bps / 100))`, else today's group-only result. The
   name stays (ten call sites, several in hot files); its docstring states the partner branch.
   Every surface follows automatically: card, activation, first day, each recurring charge, the
   resume paths.
2. **Switch into / out of daily** gets the same wholesale branch
   (`_calculate_switch_to_daily`, `_calculate_switch_from_daily`): cost = wholesale price, group and
   offer percent 0.
3. **The cabinet must not subtract a promo offer from a partner's price.** The client applies the
   active offer itself (`frontend/src/hooks/usePromoDiscount.ts`, `combinePromoDiscount`), from
   `GET /cabinet/promo/active-discount`. The server never applies an offer to a wholesale partner
   (every wholesale branch sets offer = 0 and doesn't consume it). So that endpoint reports
   `is_active: false, discount_percent: 0` for a wholesale partner. The stored offer is left
   untouched: if partner status is revoked it shows again. No frontend change, no new field. Side
   effect: the same fix stops the cabinet stacking an offer onto a partner's **period** prices.
4. **Existing partner daily subscriptions** move to the wholesale price at their next daily charge
   (the price is computed per charge). No migration, no data change.

**Currency:** unchanged scale. `daily_price_kopeks` stays catalog scale; the charges already
convert with `catalog_price_in_toman` / `user_can_afford` (#21). Nothing touches
`_BALANCE_SCALE_TRANSACTION_TYPES`. Phase C: out of scope, not widened.

**Out of scope:**
- **F-029:** the cabinet period list (`_build_tariff_response` period loop) and the
  periodic → periodic switch ignore wholesale. Same bug class, period side, own bounded fix.
- Volume tiers, minimum bulk, per-tariff partner rates: not built; would need policy numbers.
- Reseller management of their own customers ("Layer C"): separate.

## Vs. upstream

- **Ours, must survive merges:** `uses_wholesale_pricing` / `apply_wholesale_discount` /
  `wholesale_discount_bps` in `pricing_engine.py` — this plan only adds call sites of them. The
  wholesale branch in `daily_group_price` sits next to upstream's promo-group logic in the same
  function (upstream `968687ce` owns the function): expect a one-hunk conflict there on an
  upstream merge.
- **Reused as-is:** `PricingEngine.daily_group_price` (upstream `968687ce`), the promo offer model
  and `active-discount` route (upstream), `TariffSwitchResult`.
- **Gateways:** none touched. CryptoBot unchanged.

## Tasks

**1. Wholesale branch in `daily_group_price`.**
- Files: `app/services/pricing_engine.py` (`daily_group_price`, ~line 128). Tests:
  `tests/services/test_wholesale_pricing.py` (unit), `tests/services/test_daily_price_parity_surfaces.py`
  (extend: for a wholesale partner the cabinet's `daily_price_kopeks` equals the amount
  `daily_subscription_service` charges), `tests/services/test_daily_charge_fork_sites.py` (the
  recurring charge takes `catalog_price_in_toman(700_000)` = 7,000 Toman for 3000 bps).
- Interfaces: signature unchanged — `daily_group_price(daily_price_kopeks: int, user) -> tuple[int, int]`;
  for a wholesale partner the second item is `round(bps / 100)` (the same display percent
  `calculate_traffic_discount` uses), so the cabinet sends `original_daily_price_kopeks` and shows
  the struck-through retail price.
- Test first (logic): approved 3000 bps → (700_000, 30); approved 175 bps → floor price, pct 2;
  pending partner / bps 0 / no user → today's group-only result; price 0 → (0, 0).
- i18n: none.

**2. Wholesale branch in the daily switch paths.**
- Files: `app/services/pricing_engine.py` (`_calculate_switch_to_daily`, `_calculate_switch_from_daily`).
  Test: `tests/services/test_wholesale_pricing.py` (or the switch cost tests it sits beside).
- Consumes: `apply_wholesale_discount`, `get_wholesale_discount_bps`. Produces: `TariffSwitchResult`
  with `upgrade_cost` = wholesale price, `group_discount_pct = 0`, `offer_discount_pct = 0` for a
  wholesale partner; B2C results unchanged.
- Test first: partner with an active 20% offer switching periodic → tariff 9 costs 700,000 (not
  10,000 − group − 20%); daily → periodic costs the wholesale min-period price; B2C cases unchanged.
- i18n: none.

**3. `active-discount` hides the offer from wholesale partners.**
- Files: `app/cabinet/routes/promo.py` (`get_active_discount`, ~line 145). Mini App parity: the
  Mini App passes `promo_offer_discount_percent` into its tariff models (`miniapp.py:3263`, `:3511`)
  — the same rule there (0 for a wholesale partner). Test: a cabinet route test next to the existing
  promo route tests (create `tests/cabinet/test_promo_active_discount.py` if none exists).
- Produces: unchanged response shape `ActiveDiscountInfo`; values `is_active=False`,
  `discount_percent=0` for `PricingEngine.uses_wholesale_pricing(user)`. The user row is not
  modified.
- Test first: approved 3000 bps partner with a live 20% offer → inactive/0; B2C user with the same
  offer → active/20; pending partner → active/20.
- i18n: none. If the cabinet shows a "your discount" banner fed by this endpoint, it disappears for
  partners — intended.

## Smoke test

After implementation, `smoke-test-checklist` (cabinet only), as partner 433 (3000 bps) and as a
B2C user, on tariff 9: card, activation, first-day debit, next-day charge (or its preview), and a
periodic → daily switch; include a partner with an active promo offer. Note that open smoke S-002.4
expects 10,000 Toman on the switch to «روزانه» — as partner 433 it becomes 7,000.
