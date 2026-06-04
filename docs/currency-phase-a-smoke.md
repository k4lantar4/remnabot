# Phase A smoke checklist (manual)

Run after `docker compose build bot cabinet-frontend` and `docker compose up -d --force-recreate bot cabinet-frontend`.

## Bot

- [ ] `docker compose run --rm --no-deps bot python -c "import main"` exits 0
- [ ] `pytest tests/utils/test_price_display.py` passes

## Cabinet admin (Persian)

1. Open cabinet on port `3020` (or your `CABINET_PORT`), set language **fa**.
2. Open a test user → **Balance** tab.
3. Note current balance display (should match bot Toman units, not inflated FX).
4. Add **100** in the amount field (placeholder: «مبلغ به تومان»).
5. Confirm:
   - [ ] Card shows **+100** (or correct delta), not millions
   - [ ] Toast shows server `message` if returned (e.g. formatted Toman range)
   - [ ] Network: `POST .../balance` body has `amount_display: 100` (not `amount_kopeks: 1000000`)
6. DB (Phase A, before B): `balance_kopeks` increased by **10000**, not 100.

## Regression guards

- [ ] No `UPDATE users SET balance_kopeks` was run
- [ ] Payment top-up flows unchanged (separate smoke if needed)

Phase B blocked until **تایید صفر کردن موجودی** — see `docs/currency-phase-b-pending.md`.
