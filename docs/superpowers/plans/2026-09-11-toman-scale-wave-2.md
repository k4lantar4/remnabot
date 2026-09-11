# Toman balance scale — wave 2 (lost refunds, remaining 100x sites, cabinet tariff switch)

**Status:** active — wave 1 done (below); wave 2 not started. Task 7 waits on a product decision.
**Repos:** `remnabot` first (Tasks 1, 2, 4, 5), then `frontend` (Tasks 3, 6, 7). Cross-repo work is
bot-first and additive.
**Upstream basis:** remnabot `origin/main` `58e5a405`, `upstream/main` `bf33d125` (2026-09-11);
frontend `origin/main` `d1d1d001`, `upstream/main` `346d1f11`.
**Kind:** bounded payment fixes (fix + PR, TDD) per the user's payment policy. Phase C (renaming
`*_kopeks` / `*_rubles`, collapsing scales) is **out of scope**. Run the `fix-payment` skill; the
`payment-fixer` agent memory (`remnabot/.claude/agent-memory/payment-fixer/known-scale-bugs.md`,
`scale-conversion-map.md`) has the per-site scale map.

## Goal

Every balance check, debit, refund and balance display uses the right scale on every surface, and no
failure path keeps the user's money without delivering. B2C and partner users alike (same paths).

## Wave 1 — done (2026-09-10/11)

The wallet balance is Toman 1:1 ("Phase B") while catalog prices are `price_kopeks` (÷100); these PRs
converted the paths that still mixed the two. Deployed to the dev bot and the live cabinet checkout on
2026-09-11.

| PR | What |
|---|---|
| remnabot #32 (+#33) | Renewal `SubscriptionRenewalService.finalize()` default/clamp in Toman; menu activate button; refund lost after rollback; admin renewal notification balance |
| remnabot #34 | `format_price(<balance>)` → `format_balance` across cabinet/miniapp `balance_label`, six admin notifications and ~30 more sites; AST guard test |
| remnabot #35 | Referral withdrawal amounts (display + typed input ×100), email/notification `*_rubles` per-event scale, `*_toman` placeholders |
| remnabot #36 | Check + debit + refund together: cabinet/miniapp tariff switch, miniapp purchase/server add, classic purchase preview, paid trial, bot countries/traffic, admin buy-for-user, gift, **scheduled autopay** (silently failing for everyone) |
| remnabot #37 | Bot `tariff_purchase.py` (8 gates), auto-purchase after top-up (4 flows + legacy cart), cabinet `update_countries`, simple subscription, `force_check_subscriptions`, admin-buy refund; 13 refund-after-rollback losses |
| frontend #13 | Cabinet stops ÷100 on wallet amounts: top-up success modal, gift, campaign bonus, merge, trial/daily cards, withdrawal flow |
| frontend #14 | fa currency label «تومان» (was «ریال» via Intl `IRR`), referral-earnings screens 1:1 |

Contract kept from #36: fields the cabinet feeds to `InsufficientBalancePrompt` (`missing_amount_kopeks`)
carry `missing_toman_on_catalog_scale` (Toman shortfall × 100); `missing_amount` in 402 bodies is Toman.

Not yet done from wave 1: the **production** DB check (read-only) for users charged 100x on renewal,
switch, trial, gift, autopay or auto-purchase before these PRs — no read-only production access exists
in this workspace; the user runs it before release.

## Design

Same pattern as #36/#37: fix each site's check, debit and refund together with the helpers in
`app/utils/price_display.py` (`user_can_afford`, `calculate_missing_amount`, `catalog_price_in_toman`,
`format_balance`) and the frontend's `src/utils/catalogScale.ts` / `balanceScale.ts`; transaction rows
and `*_kopeks` fields keep their current scale. Refund-on-failure uses the charged/delivered flags from
the #37 admin-buy fix (refund only if the debit committed and delivery didn't) — a blanket
except-refund would also refund when only the final message failed.

## Vs. upstream

- Ours: Toman 1:1 balance and its display; the refund fixes are upstream bugs we fix on upstream code
  (`tariff_purchase.py` is a hot file — minimal edits, helpers only, note for the next merge).
- Reused as-is: `subtract_user_balance` / `add_user_balance`, `SwitchTariffSheet`, the stats components.
- No deferred gateway involved. `wheel_service` (spin cost from the RUB stars rate) belongs with the
  Stars/CryptoBot Toman-rate plan (`2026-09-10-cryptobot-topup-toman-rate.md`), not here.

## Tasks

1. **Lost refunds in live bot tariff flows** (highest priority — money loss).
   Repo `remnabot`: `app/handlers/subscription/tariff_purchase.py` `confirm_tariff_extend`,
   `confirm_tariff_switch`, `confirm_instant_switch`; `app/handlers/simple_subscription.py` outer
   `except` blocks. Test: extend `tests/services/test_tariff_purchase_toman.py` — debit commits, the
   next step raises → balance restored exactly once; final-message failure → no refund. Refresh the
   user before `add_user_balance` after any rollback (see agent memory, refund-loss patterns).
   i18n: none expected.

2. **Instant switch to a daily tariff with a short balance switches for free.**
   Repo `remnabot`: `confirm_instant_switch` (daily branch). Today it skips the first-day charge when
   the balance is short (the preview blocks it, the confirm callback doesn't). Refuse with the same
   insufficient-balance message the preview uses. Test: balance 5,000 vs daily 10,000 → refused, tariff
   unchanged, no debit. i18n: reuse the existing insufficient-balance key.

3. **Cabinet server management affordability (classic mode).**
   Repo `frontend`: `src/components/subscription/sheets/ServerManagementSheet.tsx`
   (`totalCost <= balance_kopeks`, `missingAmount = totalCost - balance`) → `userCanAfford` /
   `missingToman` from `src/utils/catalogScale.ts`. Backend already fixed in #37 (402 `{code, message,
   missing_amount}`). Test: helper-level unit tests exist; add a component-logic test if the branch is
   non-trivial, else verify live (hidden while `SALES_MODE=tariffs`).

4. **Remaining ÷100 balance displays in the bot.**
   Repo `remnabot`: `app/services/daily_subscription_service.py` `_notify_daily_charge` (balance ÷100 and
   hardcoded «₽»); `notify_daily_debit` `formatted_amount`; `app/services/referral_service.py` user
   notifications (invite promise, bonus received, inviter breakdown); `app/handlers/admin/referrals.py`
   settings/diagnostics screens (`REFERRAL_*_KOPEKS` are Toman since #35); `app/webapi/routes/users.py`
   `new_balance_rubles = new_balance_kopeks / 100` (additive `new_balance_toman` if a consumer exists —
   grep `frontend/src` first); poll rewards and promo-offer `bonus_amount_kopeks` — verify their scale
   before touching. Extend the #34 AST guard where cheap. Test: one failing test per module (150,000
   balance → «150,000 تومان»). i18n: hardcoded Russian strings touched here become keys in all five
   baked locales + runtime `locales/`, byte-identical; natural Persian, Latin digits.

5. **Toman fields for mixed-scale stats (bot side, additive).**
   Repo `remnabot`: the endpoints behind cabinet sales stats, admin campaign revenue/deposits, the
   AdminDashboard campaign revenue, the referral network spend/branch/campaign revenue, the admin user's
   total spent, and the partner campaign daily/period series. Each sums rows of mixed scale
   (`_BALANCE_SCALE_TRANSACTION_TYPES`); add `*_toman` fields normalized per row type next to the old
   ones. Test: a fixture with one catalog-scale and one balance-scale row → the `*_toman` total is the
   Toman sum. Produces the field names Task 6 consumes — list them in the PR body.

6. **Cabinet consumes the Task 5 fields.**
   Repo `frontend`: `src/components/stats/DailyChart.tsx`, `PeriodComparison.tsx` (shared by partner
   `CampaignDetailStats.tsx` and admin campaign stats), the sales-stats tabs, and `src/pages/Info.tsx`
   loyalty tab (hardcoded `currency: 'RUB'`, line ~573 — verify its amount scale, then format via
   `formatBalance`/`formatPrice`). Test: mapping in `src/api` if any; otherwise visual — verify live.
   Ships after Task 5 merges.

7. **Cabinet tariff switch in multi-tariff mode — needs the user's decision first.**
   Finding (2026-09-11): with `MULTI_TARIFF_ENABLED=true` (live) the cabinet never offers «تغییر
   تعرفه»: `TariffPickerGrid.tsx` computes `canSwitch = !isMultiTariff && …`, so every other tariff
   shows «خرید» (buy it as an additional subscription). This is upstream's deliberate design
   (bedolaga-cabinet `bcbfa419`, "multi-tariff purchase UX - disable switch, show Buy for new tariffs",
   2026-03-19). The bot still offers switching in the same mode (`app/keyboards/inline.py`
   `instant_switch` / `tariff_switch`), and the bot endpoint `tariff_switch.py` supports it in
   multi-tariff mode (it only refuses a target tariff the user already owns, 409). Surfaces disagree.
   Options: (a) keep upstream — cabinet buys additional subscriptions, bot switches (document it);
   (b) fork change — show «تغییر» per subscription in the cabinet in multi-tariff mode, reusing
   `SwitchTariffSheet` and the existing endpoint (frontend-only, `TariffPickerGrid.tsx` + tests);
   (c) turn `MULTI_TARIFF_ENABLED` off (config; changes the whole purchase model). Execute only the
   chosen option.

## Found, not in this plan

- Admin bot withdrawal detail raises `KeyError` for a request without `risk_analysis` (reported in #35).
- Remaining Russian strings in withdrawal/admin risk texts and renewal success messages — a
  translation task (`fix-translation`), amounts already correct.
- Cabinet top-up form still uses kopek semantics (input ×100); no cabinet top-up method is registered
  today — belongs with the Stars/CryptoBot Toman-rate plan.
- Startup log: `platega_subscriptions does not exist` (dedup cleanup) — plan
  `2026-09-10-missing-upstream-tables.md`.

## Smoke test

`smoke-test-checklist` after implementation — one combined list for the wave (the user asked for a
single list per batch of this bug class).
