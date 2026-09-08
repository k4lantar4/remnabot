# M4-T7 — Port C2C, FA fallback, Toman, wholesale from `/opt/remnabot`

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M4-T7 · weight 13 · batch M4.6 · dependencies: M4-T0, M4-T1  
Commit message (this batch): `feat(M4-T7): port C2C, FA fallback, Toman, wholesale`

## Verdict: PASS (code port + agent tests)

Protected production behavior is in remnabot1 4.2:

- C2C plugin + `PaymentMethod.C2C='c2c'` + `C2cReceipt` → existing grafted `c2c_receipts` (no new Alembic)
- FA default language + missing-key chain `fa → en → ru`
- Toman dual-scale (`format_price` / `format_balance`, `User.balance_rubles` 1:1)
- Wholesale/partner via remnabot `app/utils/price_display.py` + `PricingEngine` wholesale-first (not a new `app/custom/pricing` seam)

**G8 (isolated C2C chat) is not this batch.** P1 still UNKNOWN. Do not claim MVP PASS.

## Port source

READ-ONLY `/opt/remnabot` (3.60 custom). Did **not** merge cabinet. Did **not** port unused Russian payment providers.

## Code delta (summary)

| Area | Where |
|---|---|
| C2C plugin | `app/plugins/c2c/` + `app/plugins/__init__.py` |
| C2C compile helpers | `cart_checkout_keyboard.py`, `topup_suggestion.py`, `topup_prompt.py`; Jalali stub `jalali_datetime.py` (no `jdatetime` dep) |
| Models | `PaymentMethod.C2C`; `C2cReceipt` / `C2cReceiptStatus`; `User.wholesale_discount_bps` already on G1 via graft `0093` |
| Config | `C2C_*`, `is_c2c_enabled()`, `PRICE_DISPLAY_SUFFIX`, Toman `format_price`/`format_balance` |
| Wires | `app/bot.py`, balance `main.py`, `payment_utils.py`, `inline.py`, `user_cart_service.py`, `AdminStates.c2c_custom_amount` |
| FA | `user_language.py`; `start.py` / `menu.py`; `loader.py` + `texts.py` fa→en→ru |
| Toman / wholesale | remnabot `price_display.py`; `PricingEngine` wholesale-first; 4.2 stacked promo kept for retail |
| fa.json | 49 `C2C_*` / `PAYMENT_C2C` keys (isolated strings) |

No new migration. No `grace_access_sessions`. No autogenerate revision.

## Tests

Command:

```text
MULTI_TARIFF_ENABLED=false uv run pytest \
  tests/plugins/c2c tests/utils/test_price_display.py tests/test_wholesale_pricing.py \
  tests/localization tests/custom/test_persist_identity.py \
  tests/services/test_remnawave_identity_backfill.py
```

**152 passed, 3 skipped.** Skips (not C2C product skips):

1. `test_wallet_topup_amount_fsm` — module skip: 4.2 has no `AwaitingCustomTrafficFilter`
2. `test_auto_purchase_uses_persian_tariff_ledger_description` — 4.2 auto-purchase ledger still Russian; FA purchase strings are M6
3. `test_fa_en_ru_chain` sample skip — no shared en+ru keys missing from fa

C2C approve Persian ledger test **passed**.  
`tests/utils/test_rich_menu.py::test_builder_single_subscription_structure` updated for comma-grouped Toman (`1,250 تومان`) — **passed**.  
`uv run python -c "import main"` — **OK**. `grep -r get_admin_texts app/` — **0**.

## Env (fingerprints only — no secrets, no card numbers)

Live `/opt/remnabot1/.env` was **not rewritten**.

| Key | Live `.env` | `.env.rehearsal` |
|---|---|---|
| `C2C_ENABLED` | `true` | `true` |
| `C2C_ADMIN_CHAT_ID` | EMPTY | ABSENT |
| `C2C_CARDS` | PRESENT count=2 fp=`0bc52870ca6942f9` | ABSENT |
| `C2C_DISPLAY_NAME` | set | set |
| `DEFAULT_LANGUAGE` | `fa` | `fa` |
| `LANGUAGE_SELECTION_ENABLED` | `true` | `false` |
| `PRICE_DISPLAY_SUFFIX` | ABSENT (code default) | ABSENT |
| `BOT_TOKEN` | PRESENT fp=`458863639bbe6d6b` (test token) | same fp |

`is_c2c_enabled()` is True when cards are present. Empty `C2C_ADMIN_CHAT_ID` **falls back** to admin notifications chat (fp=`44aad73189295471`). That is a **G8 risk** if polling starts before P1: receipts would go to the notifications chat, not an isolated C2C admin chat. This batch did **not** start polling.

## Isolation

| Name | After M4-T7 |
|---|---|
| `rehearsal_bot` app | **absent** (not polled) |
| `rehearsal_bot_db` | Up (G1 volume); not used this batch |
| sandbox `remnawave_bot` | `Created=2026-09-01T10:26:23Z`; **not rebuilt** |
| sandbox Alembic | **`0110`** |
| G1 `rehearsal_bot_pg15` | still **`0111`** + G6 (untouched this batch) |
| live Caddy / `panel.rookari.com` | **unchanged** |

## Not done (later batches)

- M5-T1: RC cabinet from `/opt/cabinet`
- M6-T1..T3: FA / Toman / wholesale regression gates (deeper tests)
- M6-T4 / G8: isolated C2C chat (requires P1). Set a dedicated `C2C_ADMIN_CHAT_ID` before any polling bot with `C2C_ENABLED=true`
- Do not start polling `rehearsal_bot` until a named batch
- Do not rebuild sandbox `remnawave_bot` (DB still `0110`)
