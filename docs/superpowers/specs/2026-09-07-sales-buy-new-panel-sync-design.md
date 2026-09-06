# Sales buy-new isolation + panel sync

**Date:** 2026-09-07  
**Status:** Design locked (operator تایید 2026-09-07). Plan: `docs/superpowers/plans/2026-09-07-sales-buy-new-panel-sync.md`. Implementation not started.  
**Does not execute:** M7-T1, M8, DNS, `MAIN_MENU_MODE=cabinet`, catalog price-model rewrite  
**Trees:** `/opt/remnabot1` (bot API + Telegram handlers) · `/opt/cabinet` (UI already has `?intent=new`; **no React files** in this spec)  
**Donor:** `/opt/remnabot` production behavior (read-only)

**Follows:** `docs/superpowers/specs/2026-09-04-sales-surface-overlay-design.md`. That overlay shipped list/search/identity A and period-confirm isolation. This spec closes the remaining buy-new vs extend leaks and the Remnawave sync failure after extend.

---

## Verdict (binding)

1. **Telegram and cabinet both stay full sales surfaces.** Do not switch `MAIN_MENU_MODE` to `cabinet` as a shortcut. Cabinet UI talks to remnabot1 Python API; skipping bot-tree API work does not skip the bug.
2. **Three products, not two.**  
   - **New purchase** creates a new bot row and a new Remnawave account (partner and retail share the path; only `PricingEngine` price differs).  
   - **Renew from subscription detail** (`se:{id}` / cabinet renew with `subscription_id`) updates that row and that panel account. The renew button **stays** on detail.  
   - **Traffic top-up from detail** (`st:{id}`) adds predefined GB to that row only. No period step.
3. **Catalog matches production traffic UX:** `TRAFFIC_SELECTION_MODE=selectable` with **predefined packages on the tariff**. Wizard order is **traffic, then period**. RC must not stay on `fixed` (that hides the traffic step). Do not invert pricing onto traffic. Do not add a new price formula.
4. **Empty pin means create.** `should_extend_multi_tariff` already exists. Wire the leftover Telegram sites and the cabinet purchase API the same way production does. Forbidden: `get_subscription_by_user_and_tariff` / “next active sub with this tariff_id” when the pin is empty.
5. **Panel sync must run on a clean SQL session.** After extend, 4.2 queries `lava_subscriptions` even though Lava is disabled and the table is absent on the remnabot-lineage DB. The caught `UndefinedTableError` aborts the PostgreSQL transaction; `update_remnawave_user` then fails before any HTTP call to the panel. Do **not** create that table. Skip the query (or inspector-guard) and `rollback` so Remnawave create/update proceeds.
6. **Work order:** (1) buy-new isolation, (2) Lava session poison. Do not start M7 from this spec.

---

## Why this spec exists

Operator smoke (2026-09-05) plus log evidence on `rehearsal_bot`:

| Symptom | Cause (verified) |
|---|---|
| Catalog / cabinet purchase errors; no new Remnawave user | Custom-days, daily confirm, and cabinet API still resolve “existing” by tariff and **extend**. Then Lava query poisons the session; panel API is never called (`rehearsal_rw` has no matching create error). |
| Overlay plan looked done | Task 5 wired **period confirm** only. Production also wires custom confirm, daily confirm, and cabinet `if subscription_id is None: create`. |
| “Insufficient funds” / Russian period copy | Separate Toman/i18n follow-up already shipped; not this spec. |

Previous overlay closeout even documented custom-days and daily as “skip in smoke”. That skip is the leak.

---

## Out of scope

- M7-T1 / cutover / production token  
- `MAIN_MENU_MODE=cabinet`  
- Replacing `tariff_purchase.py` or `Subscription.tsx` wholesale  
- New Alembic for Lava/Platega/guest `campaign_slug` (deferred, not-MVP)  
- Putting period price onto traffic / new SKU model  
- Partner checkout chrome, Earn, `/sales`  
- Changing `PricingEngine`

`guest_purchases.campaign_slug` ASGI noise is **not** this spec unless it sits on the purchase/extend session (it does not on the Telegram path). Mention only: do not “fix” it by copying upstream `0106`.

---

## Components

| Unit | Does | Depends on |
|---|---|---|
| `should_extend_multi_tariff` | Extend only if FSM/`subscription_id` pin exists and the row matches | Pin + loaded sub |
| `handle_custom_confirm` | Same predicate as period confirm; empty pin → `create_paid_subscription` | Helper + CRUD |
| `confirm_daily_tariff_purchase` | Same; stop `next(s for s in active_subs if s.tariff_id == tariff.id)` | Helper + CRUD |
| Cabinet `purchase.py` | If `request.subscription_id is None`, force create (production lines ~993–994). Delete empty-pin `get_subscription_by_user_and_tariff` fallback | Ownership lookup by id only |
| `extend_subscription` Lava shift | If `not settings.is_lava_enabled()`, do not query. If a query still errors, `rollback` then return. Never create the table. | `settings.is_lava_enabled()` |
| Remnawave create/update | Runs after a clean session; retry queue remains for true panel timeouts | SubscriptionService |
| Env | `TRAFFIC_SELECTION_MODE=selectable` on RC rehearsal env (do not commit `.env`) | Tariff `traffic` packages already in DB |

Cabinet React `?intent=new` already unbinds `subscriptionId`. This spec’s cabinet work is the **API**, not new pages.

---

## Data flow

**New purchase** (Telegram `menu_buy` / cabinet `?intent=new`):

1. Clear pin.  
2. Tariff type → predefined traffic packages → period prices.  
3. If balance covers catalog Toman price → charge wallet. Else payment methods (wallet top-up / C2C).  
4. `create_paid_subscription` + `account_sequence` + `create_remnawave_user`.  
5. Title identity A (unchanged).

**Renew** (detail `se:{id}` / cabinet with `subscription_id`):

1. Pin that id.  
2. Traffic packages → period.  
3. Pay as above.  
4. `extend_subscription` + `update_remnawave_user` on that id.

**Traffic top-up** (detail `st:{id}`):

1. Bound id.  
2. Predefined GB packages only.  
3. Pay.  
4. Add traffic on that row; panel HWID/traffic update for that account. No period picker.

---

## Error handling

| Failure | Behavior |
|---|---|
| Buy-new, pin empty or stale | Create; never silent-extend by tariff |
| Renew pin missing | Keyed error; do not create a second service |
| Traffic top-up without bound id | Picker or error; do not open period wizard |
| `lava_subscriptions` missing or Lava disabled | Do not query; `rollback` if the session already aborted; continue panel sync. Do not add a Platega/Lava migration. |
| Remnawave HTTP timeout after bot commit | Enqueue retry; do not refund a delivered bot-side extend/create |
| Insufficient balance | Payment keyboard (C2C + wallet); do not leave a half-created panel user |
| Partner vs retail | Same create/extend path; price only via `PricingEngine` |

---

## Testing

**Automated (bot):**

- Custom confirm and daily confirm: empty pin → create; pinned matching tariff → extend.  
- Cabinet purchase: `subscription_id=None` never calls `get_subscription_by_user_and_tariff`.  
- Extend with missing `lava_subscriptions`: no `InFailedSQLTransactionError` on the following `get_user_by_id` / panel update.  
- Existing period-confirm and identity A tests stay green.

**Operator smoke (STOP, user-visible):**

1. Telegram new buy (traffic → period → wallet) with an already-active sub → **second** bot row and **new** Remnawave user.  
2. Detail renew → same row, same panel username/id, later expiry.  
3. Detail traffic add → same row, more GB, no period step.  
4. Cabinet `?intent=new` → same as (1).  
5. Low balance → C2C/wallet methods visible.

---

## File map (implementation plan will task these)

- `/opt/remnabot1/app/handlers/subscription/tariff_purchase.py` — custom + daily sites  
- `/opt/remnabot1/app/cabinet/routes/subscription_modules/purchase.py` — empty-pin create  
- `/opt/remnabot1/app/database/crud/subscription.py` and/or `/opt/remnabot1/app/services/payment/lava.py` — session-safe Lava skip  
- Tests next to those modules  
- RC env only: `TRAFFIC_SELECTION_MODE=selectable` (`.env` / `.env.rehearsal`; not a git secret)

No cabinet frontend files. If the cabinet purchase form hides traffic because the API still reports `fixed`, that is an env bug (`TRAFFIC_SELECTION_MODE`), not a React task.
