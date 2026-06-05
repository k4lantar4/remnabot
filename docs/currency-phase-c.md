# Currency Phase C — what remains after Phase B

Phase B (2026-06-05) changed **only user balance storage and display**:

| After Phase B | Meaning |
|---------------|---------|
| `users.balance_kopeks` | Integer **Toman**, 1:1 with what the user sees |
| Admin `amount_display: 100000` | DB `+100000` |
| `format_balance` / `balance_rubles` | Grouped Toman + suffix, **no ÷100** |
| `format_price` / `price_kopeks` | **Unchanged** — still catalog kopeks (÷100 for display) |

## What Phase C must align

Everything that still uses the **old kopeks scale** (×100 internally):

1. **Tariff catalog** — `price_kopeks`, period/device/traffic add-on prices
2. **Purchase flow** — compare `user.balance_kopeks` vs `final_price` (different scales today)
3. **Payment webhooks** — YooKassa, Stars, C2C, etc. credit amounts into balance
4. **Transaction history storage** — mixed: admin balance ops are 1:1; old payment/subscription rows may still be kopeks-scale
5. **Referral / promocode balance bonuses** — `amount_kopeks` on earnings and rewards
6. **Withdrawal limits** — `min_amount_kopeks` on methods and partner settings
7. **Stats / revenue APIs** — admin dashboards aggregating `amount_kopeks`

## Why Phase C was deferred

- Phase B is a **display + balance integer** change with a controlled reset (zero balances, backup).
- Phase C touches **purchase hot paths**, every payment provider, and historical rows — high regression risk.
- Safer to ship B (readable balance card) first, then one boundary at a time in C.

## What breaks if Phase C is skipped

Example after Phase B:

- User balance: **100000** Toman (stored 1:1)
- Tariff price: **5000** Toman shown, but stored as `price_kopeks = 500000` (old scale)
- Purchase check: `100000 < 500000` → “insufficient balance” even though UI shows enough money
- Top-up webhook may credit **100×** too much or too little vs displayed Toman
- Subscription charge transactions still stored in kopeks; display layer must know type (fixed in B follow-up for admin history)

## Phase C approach (planned)

1. **Single scale at boundaries** — convert at purchase/top-up entry (or migrate `price_kopeks` to Toman integers).
2. **Migration or conversion layer** — revalue historical `transactions.amount_kopeks` OR tag rows by era.
3. **Provider-by-provider** — one webhook family per commit (`currency-fx-boundaries.mdc`).
4. **Smoke** — balance vs price on real tariff purchase, one live top-up, referral payout.

## Display vs amount (user note)

Thousand separators (e.g. `۱۰۰٬۰۰۰ تومان`) are **formatting only**. The stored integer stays `100000`; grouping must never divide the value.
