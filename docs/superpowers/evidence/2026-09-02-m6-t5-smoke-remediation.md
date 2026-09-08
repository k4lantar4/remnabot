# M6-T5 smoke remediations (agent gates) — 2026-09-02

Code remediations for three user-visible RC smoke failures. **MVP-VERIFIED not recorded.** User re-smoke required.

## Policy

Main-menu buy stays official-nested (policy A). No production `SIMPLE_SUBSCRIPTION` remap. Extra buy is `➕` inside My Subscriptions.

## Agent verification

- `uv run pytest` Toman + pagination + gift/detail handlers: **51 passed**
- Cabinet `vitest run src/utils/format.test.ts`: **3 passed**
- `rehearsal_bot` rebuilt, polling, `/api/health` 200 `bot_version=4.2.0`
- In-container: `paginate_items(116) → 24 pages of 5`; `display_balance_from_storage(126800)=126800.0`
- Built cabinet asset contains `shouldSkipFxConversion` (`index-vzVOuZo2.js`)
- `https://panel.rookari.com/` 200

## User smoke (max 3)

1. `@mrj7_bot` `/start` → «اشتراک‌های من» opens (page 1 of N) with `➕` buy
2. Cabinet `https://panel.rookari.com` balance equals bot **126,800 تومان** (not ~20M)
3. Buy/renew a tariff — period prices must not be ~159M تومان
