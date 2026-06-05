# Currency Phase B — executed 2026-06-05

User approved: backup + zero balances + Phase B continuation.

## Pre-migration backup (required before SQL)

```bash
# Confirm DB is reachable
docker compose -f /opt/bot-remnawave/docker-compose.yml exec -T postgres \
  pg_isready -U "${POSTGRES_USER:-postgres}"

# Full backup (adjust user/db from .env)
docker compose -f /opt/bot-remnawave/docker-compose.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-remnawave}" \
  > "/var/backups/remnawave-pre-phase-b-$(date +%Y%m%d%H%M).sql"
```

## SQL applied (user-approved zero)

```sql
UPDATE users SET balance_kopeks = 0;
```

## Semantics after B

| Field | Meaning |
|-------|---------|
| `users.balance_kopeks` | Integer **Toman** (1:1 display) |
| `User.balance_rubles` | `float(balance_kopeks)` |
| Admin `amount_display: 100` | DB `+100` |
| `format_balance` | Grouped Toman + suffix (no ÷100) |
| `format_price` / `price_kopeks` | Unchanged (catalog/payment scale) |

## Out of scope (phase C)

- `transactions.amount_kopeks` historical scale
- Payment webhook credit amounts (YooKassa, Stars, …)
- Purchase compare: `balance_kopeks` vs `price_kopeks` (different scales until C)

## Smoke B checklist

- [ ] `docker compose run --rm --no-deps bot python -c "import main"`
- [ ] Cabinet admin: add `amount_display: 100` → DB `balance_kopeks` +100
- [ ] Bot `/start` menu button: `100` → `100` or `1٬000` تومان (fa grouping)
- [ ] `format_price` on tariff lines still correct (÷100)
- [ ] Top-up webhook regression (separate; may still use kopeks credits)
