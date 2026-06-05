# Currency Phase C — executed 2026-06-05

Branch: `fix/cabinet-502-network`

## Cutoff (hide pre-Phase B transactions)

| Setting | Value |
|---------|-------|
| `BALANCE_TOMAN_CUTOFF_UTC` | `2026-06-05T00:00:00Z` (default in `app/config.py`) |
| Phase B reference | `docs/currency-phase-b-executed.md` |

Transactions with `created_at < cutoff` are excluded from:

- Cabinet admin user detail `recent_transactions`
- Cabinet admin paginated user transactions
- Cabinet user `/balance/transactions`
- Bot Telegram balance history (`handlers/balance/main.py` via `get_user_transactions(..., created_after=...)`)

## Semantics after Phase C

| Storage | Meaning | Display |
|---------|---------|---------|
| `users.balance_kopeks` | Toman integer 1:1 | `format_balance` |
| `tariffs.price_kopeks` / cart totals | Catalog kopeks (unchanged) | `format_price` (÷100) |
| Balance tx after cutoff | Toman 1:1 | `display_transaction_amount_from_storage` |
| Subscription tx | Catalog kopeks | `display_transaction_amount_from_storage` (÷100) |

**Purchase boundary:** compare with `user_can_afford(balance, price_kopeks)`; charge with `subtract_user_balance(..., catalog_price_in_toman(price_kopeks))`.

Helpers: `app/utils/price_display.py` — `catalog_price_in_toman`, `user_can_afford`.

## Code changes (summary)

1. **Display fixes:** `websocket.py`, `notification_delivery_service.py` — balance-scale events use `display_balance_from_storage` / `display_amount_from_kopeks` instead of raw `/100`.
2. **History filter:** cutoff on admin + cabinet + bot history queries.
3. **Purchase boundary:** `purchase.py`, `simple_subscription.py`, `daily_subscription_service.py`, cabinet `subscription_modules/{purchase,traffic,servers,devices}.py`.

## Webhook / top-up inventory (`add_user_balance` / direct `balance_kopeks +=`)

**Out of scope for Phase C** (FX layer 3 — separate commits per provider). Inventory for follow-up:

| Path | Credit pattern | Notes |
|------|----------------|-------|
| `app/database/crud/user.py` | `add_user_balance()` | Canonical API; admin manual top-up uses Toman after Phase B |
| `app/services/payment/common.py` | notification `amount_kopeks / 100` | Admin notify only |
| `app/services/payment/yookassa.py` | `user.balance_kopeks += payment.amount_kopeks` | Likely still catalog-scale from gateway |
| `app/services/payment/stars.py` | direct += | Stars FX |
| `app/services/payment/cloudpayments.py` | direct +=; also `/100` in some paths | Review on enable |
| `app/services/payment/*` (mulenpay, pal24, wata, platega, severpay, rollpay, paypear, riopay, lava, overpay, jupiter, donut, heleket, freekassa, etoplatezhi, kassa_ai, cryptobot, aurapay, antilopay) | `user.balance_kopeks += payment.amount_kopeks` | Each needs Toman conversion at credit point |
| `app/handlers/balance/*.py` | various `/100`, FX | Frozen for i18n; do not bulk-change |
| `app/plugins/c2c/service.py` | `add_user_balance` | Custom plugin — verify separately |
| `app/cabinet/routes/admin_users.py` | `add_user_balance` | Admin UI — already Toman via `balance_from_display_amount` |

**No provider webhook fix in this phase** — document-only; enable per-provider after rate/amount audit.

## Agent smoke (automated)

```bash
docker compose run --rm --no-deps bot python -c "import main"
docker compose run --rm --no-deps bot python -c "from app.utils.price_display import display_transaction_amount_from_storage; assert display_transaction_amount_from_storage(1000,'deposit')==1000"
pytest tests/utils/test_price_display.py
docker compose build bot && docker compose up -d --force-recreate bot
```

## Manual smoke checklist (user)

- [ ] Admin cabinet: add balance +1000 → balance and latest history row both show **۱٬۰۰۰ تومان** (not 10)
- [ ] Pre-cutoff transactions **hidden** in admin user history and bot balance history
- [ ] User balance 100000, tariff display 5000 → purchase **succeeds** (catalog e.g. 500000 kopeks)
- [ ] Insufficient balance message: required price vs balance vs missing amounts consistent (تومان)
- [ ] Bot `/start` balance grouping still correct (fa-IR)
- [ ] Cabinet subscription purchase / traffic / servers from balance after top-up
- [ ] Daily subscription debit notification shows correct amount (not ÷100 again)
- [ ] Top-up via enabled payment provider (regression — may still need Phase C+ webhook work)

## Intentionally unchanged

- DB column renames (`*_kopeks`)
- Mass `price_kopeks` migration
- Pre-cutoff transaction display (hidden, not revalued)
- `handlers/balance/**` payment-provider FX bulk changes
- Miniapp / webapi purchase compare paths (follow-up if needed)
