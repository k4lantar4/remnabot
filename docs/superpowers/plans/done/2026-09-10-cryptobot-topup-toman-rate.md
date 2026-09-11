# Stars and CryptoBot wallet top-ups in Toman (fixed admin-set rates)

**Status:** done — remnabot PR (branch `fix/stars-cryptobot-toman`), 2026-09-11
**Repos:** `remnabot` only (the cabinet already sends top-up amounts as Toman x100 and reads
`min/max_amount_kopeks` on that scale — no API field changed)
**Upstream basis:** remnabot `origin/main` `6190715e`; `upstream/main` `bf33d125`
**Kind:** payment fix. Written 2026-09-10 as the CryptoBot backlog plan; widened 2026-09-11 to
Telegram Stars when the owner asked to enable both methods. The owner flips the `*_ENABLED` flags
and `payment_method_configs.is_enabled` himself; the rate is a fixed admin/env value, never a live
exchange API (ruling 2026-09-10).

## Goal

A wallet top-up with Telegram Stars or CryptoBot — from the cabinet, the bot or the legacy miniapp —
is priced from one admin-set Toman rate per method and credits the Toman the invoice promised, 1:1
into `users.balance_kopeks`. B2C and partner alike.

## Design

- `app/utils/toman_rates.py` (new): `TELEGRAM_STARS_TOMAN_PER_STAR` (new setting, no default) and
  #26's `CRYPTOBOT_TOMAN_PER_USDT`. Stars: `stars = ceil(toman / rate)`, credit `floor(stars x rate)`
  (never below what was asked). CryptoBot: `usdt = ceil(toman / rate, 0.01)`, credit the requested
  Toman. Limits: Telegram's 1..10,000 stars and the existing 1..1,000 USDT, times the rate. Rate
  unset (or CryptoBot asset not USDT) → method not configured: hidden from every method list and
  refused on create.
- Invoice payload `topup_toman_{user_id}_{toman}[_{nonce}]` names the Toman to credit. The Stars
  `successful_payment` path and the CryptoBot webhook credit that amount (Stars: sanity-checked
  against stars x rate), so a rate change between quote and payment can't move the credit. Legacy
  payloads (`balance_*`, `cabinet_topup_*`) keep upstream's handling unchanged.
- Scales: cabinet/bot/miniapp top-up requests and method limits travel as Toman x100 (existing
  contract, `TopUpAmount.tsx`); conversion to Toman goes through `catalog_price_in_toman` /
  `kopeks_from_display_amount`. The referral base gets the catalog scale (as C2C does).

Out of scope → `/opt/project/FINDINGS.md`: Stars/CryptoBot inside gift/landing guest purchases, wheel
spins, simple subscription, paid trial and the admin Stars test screen (all off in this deployment);
CryptoBot subscription purchase in the classic bot purchase flow; the bot's generic quick-amount
labels.

## Vs. upstream

- Ours: `toman_rates.py`, the new setting, the Toman branches at each conversion point. Upstream's
  ruble code paths stay in place as the legacy branch (`_legacy_stars_amount_kopeks`,
  `_legacy_cryptobot_rub_credit`) so upstream merges stay local to those functions.
- Reused as-is: CryptoBot API client and webhook plumbing (`/cryptobot-webhook` on the unified
  web server, signature = HMAC with SHA256(API token)), Stars invoice/pre-checkout plumbing,
  `payment_method_configs`.
- No deferred gateway re-enabled or depended on.

## Tasks (all in the one PR)

1. Rate module + setting (`app/config.py`, `.env.example`, admin settings category) —
   `tests/utils/test_toman_rates.py`.
2. Method availability/limits (`payment_method_config_service._get_method_defaults`) —
   `tests/services/test_payment_method_config_toman_rates.py`.
3. Cabinet: `/balance/stars-invoice` (now also checks the method list, restriction, limits) and the
   `/balance/topup` CryptoBot branch; range/restriction errors localized in Toman —
   `tests/cabinet/test_balance_stars_cryptobot_toman.py`.
4. Credit: `services/payment/stars.py` (`_resolve_stars_topup_toman`, referral scale),
   `handlers/stars_payments.py` (pre-checkout prefix, success message from the Transaction),
   `services/payment/cryptobot.py` (webhook) — `tests/services/test_stars_topup_toman_credit.py`,
   `tests/handlers/test_stars_payment_handler_toman.py`,
   `tests/services/test_cryptobot_webhook_toman_credit.py`.
5. Parity: bot handlers (`handlers/balance/stars.py`, `cryptobot.py`, typed-Toman entry in
   `main.py`) and miniapp (`webapi/routes/miniapp.py` list + create) —
   `tests/handlers/test_balance_stars_cryptobot_bot_toman.py`, `tests/test_miniapp_payments.py`.
6. Pending-payment amounts for both methods on the top-up scale (`payment_verification_service`) —
   `tests/services/test_pending_payment_amount_toman.py`.
7. Locale keys (en/fa/ru/ua/zh baked + runtime twins): `CABINET_TOPUP_*`, `STARS_TOPUP_*`,
   `STARS_PAY_BUTTON`, `CRYPTOBOT_TOPUP_*`, `CRYPTOBOT_PAY_BUTTON`, `CRYPTOBOT_CHECK_STATUS_BUTTON`,
   `TOPUP_AMOUNT_OUT_OF_RANGE`, `TOPUP_PAYMENT_CREATE_ERROR`; `STARS_PAYMENT_SUCCESS` loses its `₽`.

## Smoke test

`smoke-test-checklist` — cabinet top-up with each method once the owner sets the two rates and
enables the methods.
