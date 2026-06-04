# Currency Phase B — blocked pending approval

Phase A (display + cabinet FX fix) must pass user smoke before starting B.

## Prerequisite (user must approve explicitly)

Persian label for approval: **تایید صفر کردن موجودی**

1. Full database backup
2. Explicit user confirmation to zero all balances (if that is the chosen migration path)

```sql
-- Example from plan — DO NOT run without approval:
-- UPDATE users SET balance_kopeks = 0;
```

## Phase B scope (not implemented in Phase A)

- `balance_kopeks` stored as integer Toman 1:1 (no ÷100 in `balance_rubles`)
- Bot: `User.balance_rubles`, CRUD, cabinet/webapi/miniapp field semantics
- Cabinet: remove legacy ×100 assumptions in types and forms
- Smoke B: input 100 → DB +100; purchase/payment regression on separate track

## Out of scope for B (phase C)

- `transactions.amount_kopeks` historical revalue
- `price_kopeks` / tariff catalog scale
- Payment provider FX (YooKassa, Stars, etc.)
