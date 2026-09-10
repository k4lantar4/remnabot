# CryptoBot top-up and purchase still convert through the ruble rate

**Status:** active (backlog — recorded 2026-09-10, not started)
**Repos:** `remnabot` first; `frontend` only if an API field the cabinet reads changes (grep
`frontend/src/api` for `cryptobot` / `rate` / `min_amount` before deciding)
**Upstream basis:** remnabot `origin/main` `96bf5a12`; `upstream/main` `4e6e9224` (v4.9.0)
**Kind:** payment fix, CryptoBot is a *planned* method (user ruling 2026-09-10). Fix its Toman
path; **never flip `CRYPTOBOT_ENABLED`** or its `payment_method_configs` rows; the rate is a fixed
admin/env value, never a live exchange API. Run the `fix-payment` skill.

## Goal

Every CryptoBot flow (wallet top-up in bot, cabinet and miniapp, subscription purchase via
CryptoBot, and the webhook that credits the balance) converts Toman ⇄ USDT with one admin-set rate,
so the invoice amount and the credited balance are correct in Toman. B2C and partner alike.

## Findings (verified on `main` 2026-09-10)

- #26 added `CRYPTOBOT_TOMAN_PER_USDT` (`app/config.py`, no default) and
  `settings.get_cryptobot_toman_per_usdt() -> Decimal | None`, and moved **only miniapp renewal**
  onto it (`_compute_cryptobot_limits_toman` in `app/webapi/routes/miniapp.py`).
- Still on the ruble path (`currency_converter`, cbr-xml-daily, 95 fallback):
  - `app/webapi/routes/miniapp.py` — `_get_usd_to_rub_rate` (~361) used by the methods list and
    top-up `create_payment` (~834, ~1261), with RUB-kopek limits.
  - `app/cabinet/routes/balance.py:404` — cabinet top-up.
  - `app/handlers/balance/cryptobot.py:49, :132` — bot top-up.
  - `app/services/payment_service.py:930` — `rub_to_usd` when creating the invoice.
  - `app/services/payment/cryptobot.py:252` — webhook credit: `usd_to_rub(amount_usd)` then ×100
    into the **Toman** balance.
  - `app/handlers/simple_subscription.py:1125`, `app/handlers/subscription/purchase.py:3821` —
    subscription purchase via CryptoBot.
  - `app/handlers/admin/bot_configuration.py:2227` — admin screen shows the live USD→RUB rate.
- Invoice descriptions are hard-coded Russian: `cryptobot.py:63` («Пополнение баланса»),
  `cryptobot.py:541` and `miniapp.py:5398` («Продление подписки на N дней»).
- There are no `cryptobot_payments` rows in the dev DB (2026-09-10); check production before
  release. Already-issued invoices/payloads must keep working either way.

## Design

One helper module (e.g. `app/services/payment/cryptobot_rate.py`): `toman_to_usdt(toman) -> Decimal`
(rounded up to 0.01) and `usdt_to_toman(usdt) -> int`, both from `get_cryptobot_toman_per_usdt()`,
plus Toman limits (reuse #26's `_compute_cryptobot_limits_toman` logic: the existing 1–1000 USD
limits × rate). Rate unset, or `CRYPTOBOT_DEFAULT_ASSET` not USDT → CryptoBot is unavailable: hidden
from method lists and refused on create, never guessed. **Credit on the webhook from the Toman amount
recorded at invoice creation** (the payment row/payload), not by re-converting the paid USDT, so a
rate change between invoice and payment can't move the credited amount. Invoices without a recorded
Toman amount (legacy) keep the old path.

Out of scope: Telegram Stars (its own Toman-per-star rate, same ruling, separate plan); removing
`currency_converter` (other upstream code still uses it).

## Vs. upstream

- Ours: the Toman rate and helper. Upstream's CryptoBot flows are ruble-based; keep edits at the
  conversion points so upstream merges stay local.
- Reused as-is: CryptoBot API client, invoice/webhook plumbing, `payment_method_configs`.
- No deferred gateway re-enabled.

## Tasks

1. **Helper + tests** (`tests/services/test_cryptobot_rate.py`): conversions, rounding, limits,
   unset rate → unavailable, non-USDT asset → unavailable.
2. **Top-up invoice creation** in bot (`handlers/balance/cryptobot.py`), cabinet
   (`cabinet/routes/balance.py`), miniapp (`miniapp.py` methods list + `create_payment`) and
   `payment_service.py`: use the helper, record the Toman amount on the payment. Tests per surface
   (surface parity rule, `remnabot/CLAUDE.md`).
3. **Webhook credit** (`services/payment/cryptobot.py`): credit the recorded Toman amount; the
   legacy fallback is covered by a test.
4. **Subscription purchase via CryptoBot** (`simple_subscription.py`, `purchase.py`): same helper.
5. **Admin screen** (`bot_configuration.py`): show the configured Toman-per-USDT value instead of
   the live RUB rate.
6. **Invoice descriptions → locale keys** (en + fa, all five baked locales, both locale copies).

## Cross-repo contract

Only if the cabinet reads a changed field: bot ships backward-compatible (additive) first, then the
frontend PR.

## Smoke test

`smoke-test-checklist` after implementation. CryptoBot is disabled, so live payment isn't testable.
Check the admin setting renders and CryptoBot stays hidden while the rate is unset.
