# Balance labels show the Toman balance 100x too small

**Status:** done (2026-09-11) — remnabot PR #34 (tasks 1–3, plus the admin-notification and app-wide balance sweep)
**Repos:** `remnabot` (and `frontend` only if it renders `balance_label` — check first)
**Upstream basis:** remnabot `origin/main` `96bf5a12`; `upstream/main` `4e6e9224` (v4.9.0)
**Kind:** bounded display fix (presentation layer only; no charge/credit logic).

## Goal

Every API response that sends a `balance_label` shows the user's real Toman balance. B2C and
partner alike.

## Findings (verified on `main` 2026-09-10)

`settings.format_price(price_kopeks)` divides by 100 (catalog scale); `settings.format_balance(amount_toman)`
shows the stored balance 1:1 (Phase B). These labels pass the **balance** to `format_price`:

- cabinet: `app/cabinet/routes/subscription_modules/daily.py:194`, `purchase.py:393`, `:1181`,
  `tariff_switch.py:179`, `:614`
- miniapp: `app/webapi/routes/miniapp.py:3059, 4120, 5217, 5600, 6622, 6851, 6990, 7282, 7771`

(#26 already fixed the three miniapp renewal responses.) Before editing each site, confirm the
variable really is the balance (e.g. `tariff_switch.py:179` uses a local `balance`), not a price.

## Design

Replace `format_price(<balance>)` with `format_balance(<balance>, language)` at those sites. Don't
touch `balance_kopeks` fields or any charge logic; the field name mismatch is Phase C.

First check whether anything renders `balance_label`: `grep -rn balance_label frontend/src`. The
cabinet may format `balance_kopeks` itself, and the miniapp frontend isn't in this workspace. If
the cabinet formats `balance_kopeks` itself, check that it treats it as Toman.

## Vs. upstream

- Ours: Toman 1:1 balance display. One-word edits in upstream-shaped routes; no new infra.
- No gateway involved.

## Tasks

1. **Failing tests first:** one per module (cabinet daily/purchase/tariff_switch, miniapp). A
   balance of `150_000` gives a label containing `150,000` (not `1,500`).
2. **Fix** the sites above.
3. **Frontend check** as in Design; if the cabinet computes its own label from `balance_kopeks` ÷
   100, that's a separate frontend fix, done after this PR.

## Smoke test

`smoke-test-checklist` after implementation: https://panel.rookari.com daily tariff / purchase /
tariff switch screens show the same balance as the balance page.

## Outcome

Done in remnabot PR #34: every `format_price(<balance>)` in `app/` is now `format_balance`, enforced by the
AST guard in `tests/services/test_balance_display_toman.py`. The cabinet doesn't render `balance_label`.
Its own ÷100 suspects (GiftSubscription, CampaignBonusNotifier, SuccessNotificationModal,
AdminWithdrawalDetail) are listed in the PR for a separate frontend fix.
