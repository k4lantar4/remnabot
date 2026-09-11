# Tariff switch direction parity (F-001)

Status: done — remnabot#47 (tasks 1–2), frontend#19 (tasks 3–4)
Repos: remnabot (first, additive) → frontend
Upstream basis: not upstream-derived. Written against remnabot origin/main 7fb15329 (upstream/main
bf33d125) and frontend origin/main 05cda114 (upstream/main 346d1f11).

## Goal

With `TARIFF_SWITCH_DOWNGRADE_ENABLED=false` (or upgrade disabled), the cabinet no longer offers
«تغییر» on tariffs the bot will refuse. That includes equal-price tariffs, which count as downgrades.
When a refusal does happen, the cabinet names it from a machine-readable code instead of
string-matching Russian. B2C and partner alike.

## Design

The direction of a switch comes from the bot's `pricing_engine.calculate_tariff_switch_cost`
(`is_upgrade` = prorated cost > 0). It depends on remaining days and the user's discounts, so the
cabinet can't derive it. The bot therefore computes a per-tariff `switch_allowed: bool` in the
tariffs-mode purchase options, the same rule its own switch list applies
(`_filter_tariffs_by_switch_direction`). The cabinet hides a tariff whose switch is blocked only by
direction, matching the bot, which hides it too. Before this change the card's «تغییر» always
failed, so hiding it removes nothing that worked. The 403 direction refusals become
`detail = {code, message}`. The cabinet also applies its existing purchase-flow hand-off
(`subscription_expired` etc.) to a failing *preview*, not just a failing switch.

## Vs. upstream

- Ours: the direction rule lives in `app/services/tariff_switch_policy.py` (our shared-policy
  module), so upstream's route files only gain a call. The cabinet change sits in our fork's
  `src/utils/tariffSwitch.ts`.
- Reused as-is: `pricing_engine.calculate_tariff_switch_cost`, the `TARIFF_SWITCH_*_ENABLED`
  settings, the existing `use_purchase_flow` error contract.
- No payment gateway is touched.

## Tasks

1. **Bot: direction policy + coded 403s**
   - Files: `app/services/tariff_switch_policy.py`,
     `app/cabinet/routes/subscription_modules/tariff_switch.py` (preview and switch);
     tests `tests/services/test_tariff_switch_policy.py`.
   - Produces: `is_switch_direction_allowed(is_upgrade: bool) -> bool`;
     `switch_direction_refusal(is_upgrade: bool) -> dict` →
     `{'code': 'tariff_upgrade_disabled' | 'tariff_downgrade_disabled', 'message': <English>}`;
     `tariff_switch_allowed(current_tariff, new_tariff, remaining_days, user) -> bool`. It skips
     pricing when both directions are enabled.
   - Test first: allowed/refused per flag combination; an equal-price target counts as a
     downgrade; the refusal codes.
   - i18n: none (API codes; the cabinet localizes them).
2. **Bot: `switch_allowed` on purchase options**
   - Files: `app/cabinet/routes/subscription_modules/purchase.py` (tariffs-mode loop); test in
     `tests/cabinet/`.
   - Rule: `True` unless the subscription has a current tariff, the target differs from it, and
     `tariff_switch_allowed(...)` with `remaining_days_for_switch(subscription.end_date)` is false.
     Additive field; old cabinets ignore it.
3. **Frontend: switch decision + error codes**
   - Files: `src/types/index.ts` (`Tariff.switch_allowed?: boolean`), `src/utils/tariffSwitch.ts`,
     test `src/utils/tariffSwitch.test.ts`.
   - Produces: `TariffSwitchContext.switchAllowed: boolean` (`tariff.switch_allowed !== false`);
     `canSwitchTariff` is false when not allowed; `isSwitchBlockedByDirection(c)` = every other
     switch condition holds but `switchAllowed` is false; `tariffSwitchErrorKey` maps
     `detail.code` first and still accepts the legacy Russian strings.
   - Test first: all three.
   - i18n: reuses `subscription.switchTariff.errors.{upgradeDisabled,downgradeDisabled}`.
4. **Frontend: grid + sheet**
   - Files: `src/components/subscription/purchase/TariffPickerGrid.tsx` (filter out
     `isSwitchBlockedByDirection`), `src/components/subscription/sheets/SwitchTariffSheet.tsx`
     (preview error + `shouldUsePurchaseFlow` → `onExpiredFallback`).
   - Test: visual, verify live.

## Cross-repo contract

`GET /cabinet/subscription/purchase-options` (tariffs mode): each tariff gains `switch_allowed`.
`POST /cabinet/subscription/tariff/switch[/preview]` 403 direction refusals: `detail` goes from a
string to `{code, message}`. Until the frontend PR lands, the old cabinet shows its generic
«not available» text for these, which is already localized. The bot PR merges first.

## Smoke test

Generate with `smoke-test-checklist` after implementation.
