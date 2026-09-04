# Sales surface overlay — buy-new isolation + identity A

**Date:** 2026-09-04  
**Status:** Design locked (operator تایید 2026-09-04: identity A, architecture, components, error/test/out-of-scope). Implementation plan is a later `writing-plans` step after spec review.  
**Does not execute:** M7-T1, M8, production DNS, application code in this document  
**Trees:** `/opt/remnabot1` (bot 4.2.0, `prod-cutover`) · `/opt/cabinet` (1.67 overlay) · `/opt/remnabot` and `ssh bot:/opt/bot-remnawave/cabinet` (1.57 donor, READ-ONLY)

**Supersedes (user-facing titles only):** Day-1 spec identity `brand_serial` / tariff-name-only (`docs/superpowers/specs/2026-09-04-day1-remaining-overlay-design.md` § My Subscriptions list). Day-1 rich shell, Jalali, Toman, C2C, and `PricingEngine` stay.

**Related:** cabinet Layer A `docs/superpowers/specs/2026-09-03-cabinet-b2-overlay-design.md` (wording/RTL/Jalali). Layer C partner desk remains after cutover.

---

## Verdict (binding)

1. **Commercial brain is `PricingEngine`.** Approved partners pay `wholesale_discount_bps`. Everyone else pays list price. Do not add a second price formula. Every sales edge (new purchase, renew, traffic, devices, tariff switch) must call the same engine on Telegram and on cabinet `/api`.
2. **Buy-new is isolated from renew.** `menu_buy` and cabinet `?intent=new` create a **new** subscription row. Renew/extend/traffic/devices bind an existing `subscription_id`. Falling back to `get_subscription_by_user_and_tariff` when the pin is empty is forbidden for buy-new.
3. **Identity A is the only user-facing subscription title** in bot list, rich-menu table, cabinet list, and cabinet detail: panel username (skip `user_unknown_*`); else `{tariff_name} #{account_sequence}`. Day-1 `brand_serial` titles are obsolete.
4. **Keep 4.2 rich `/start`.** Add/keep a visible «خرید سرویس» (`menu_buy`) on the main menu even when the user already has an active subscription (multi-tariff). Do not restore the 3.60 keyboard grid.
5. **Cabinet is overlay-on-1.67**, not a 1.57 file replace. Copy only small missing modules (`purchaseRoutes.ts`, label/search helpers). Wire production **sales** behaviors into `Subscription.tsx` / `Subscriptions.tsx`. Do not copy whole `Subscription.tsx` or `tariff_purchase.py`.
6. **Partner custom UI is out of this overlay.** Do not add `PartnerCheckoutFields`, brand/note checkout chrome, Earn, or `/sales`. Do not revert Day-1 Telegram partner confirm extras if they already shipped; do not expand them here. Wholesale **price** on Telegram and cabinet API stays (Layer B, already ported).
7. **This track does not start M7.** Named-start remains the MVP plan. Do not merge upstream bot 4.4.0 or cabinet 1.69.0 to close these gaps.

---

## Why this spec exists

Operator report (2026-09-04) vs live production (`ssh bot`, cabinet SHA-identical to `/opt/remnabot/cabinet`, v1.57):

| Gap | Production | RC today | Risk |
|---|---|---|---|
| Main-menu buy | Needed for multi-tariff catalog | `show_buy` hides `menu_buy` when a sub is active | No new-service entry on `/start` |
| Buy-new vs renew | `target_subscription_id=None` + `should_extend_multi_tariff` | Confirm falls back to `(user_id, tariff_id)` lookup | Catalog purchase extends the wrong row |
| Cabinet buy-another | `NEW_PURCHASE_PATH` = `?intent=new` | `/subscription/purchase` with no intent | Same bind-to-existing failure |
| Titles | `panel_username` / `tariff #seq` | API omits those fields; UI uses `tariff_name` | Ten subs share one title |
| List search | `search=` + UI | Neither API nor UI | Unusable at volume |
| Detail `/subscriptions/:id` | Gated first-connect, config **and** guide, buy-another row, copy username | Ungated checklist, single connect sheet, no buy-another, tariff title | Connect/sales funnel fails |
| RTL back icons | (fa `dir=rtl` now on RC) | `PiArrowLeft` / `ChevronRight` not mirrored | Wrong-direction chrome |

Upstream fetch 2026-09-04 (bot **4.4.0**, cabinet **1.69.0**) is email/theme/iOS/TabPay — not these gaps. Merging it is out of this spec.

---

## Architecture

```
Identity A helper (bot)     Identity A helper (cabinet)
        |                            |
menu_buy / show_buy           intent=new + list search
        |                            |
should_extend? ---- PricingEngine ---- renewal / traffic / devices / switch
        |
4.2 rich /start (shell stays)
        |
cabinet 1.67 + small donor modules
        |
day-2 smoke (Telegram + panel.rookari.com)
        |
M7-T1 named-start (not this spec)
```

**Pollution boundary:** new helpers own identity, extend-vs-create, and purchase intent. Hot files (`menu_layout/service.py`, `purchase.py` start, `tariff_purchase.py` confirm, `Subscription.tsx`, `Subscriptions.tsx`, `multi_tariff.py`) get thin callsites only.

**Donor:** production behavior, not file overwrite. `/opt/remnabot` and live `/opt/bot-remnawave/cabinet` are read-only.

**Price:** `app/services/pricing_engine.py` is the single source. Cabinet purchase/renewal/traffic/devices/switch modules already call it; this spec forbids new ad-hoc math on those edges.

---

## Identity A (titles)

**Rule:** one function in each tree; same contract.

1. `panel_username` trimmed; if it starts with `user_unknown_`, treat as empty.
2. If non-empty → that string is the title.
3. Else → `{tariff_name or default} #{account_sequence}` (`account_sequence` default 1).

**ORM (bot):** columns already exist via grafted `0091` (`account_sequence`) and `0092` (`panel_username`). Map them on `Subscription`. No new Alembic revision. Do not `alembic revision --autogenerate`. Do not restore DB index `uq_subscriptions_user_tariff_active` (dropped in `0091`). Remove that unique index from SQLAlchemy `__table_args__` so the model matches the DB.

**Cache write:** `persist_identity` stays numeric-id-only (M3-ID). Add a **separate** one-liner helper next to its callsites: if panel payload has `username`, write `subscription.panel_username = username.strip()[:64]`. Restored production rows already have the column populated.

**Create path:** when creating a new paid subscription, set `account_sequence` via existing next-sequence logic (port from production CRUD if remnabot1 create does not set it).

**Cleanup (obsolete labels):** delete or stop calling Day-1 `subscription_list_identity` brand_serial titles. Rich-menu table must not print raw `tariff.name` as the identity cell. Cabinet must not title from `tariff_name` alone when identity A can run. Keep stripping `user_unknown_*`; that is identity A, not a second label system.

**Not identity A:** partner brand prefix UI, public serial as the primary title, `Moonvpn_67258` list chrome.

---

## Components

### Bot — main menu buy

`app/services/menu_layout/service.py`: when `show_buy` is true **and** multi-tariff is enabled, do **not** hide the button because `has_active_subscription`. Single-tariff keeps today’s hide-when-active behavior.

Keyboard still uses builtin `buy_subscription` → `callback_data='menu_buy'`. fa copy already exists (`MENU_BUY_SUBSCRIPTION` / «خرید سرویس»). Rich shell unchanged; this is a visibility condition, not a new grid.

### Bot — buy-new isolation

Port the production predicate (name may be `should_extend_multi_tariff`) into a small module, e.g. `app/utils/subscription_purchase_intent.py`:

- Extend **only** if FSM `target_subscription_id` is set **and** that row exists and matches the chosen tariff (renew from detail).
- Otherwise **create**.
- `start_subscription_purchase` (`menu_buy`) must `update_data(target_subscription_id=None)` **before** redirecting to `show_tariffs_list` (production does this today; remnabot1 does not).

Do not replace `tariff_purchase.py`. Confirm, cart resume, daily, and classic paths that currently fall back to `get_subscription_by_user_and_tariff` when the pin is empty must use the predicate instead for multi-tariff.

Renew/extend callbacks continue to pin `target_subscription_id=sub_id`.

### Bot — list / rich table

`subscription_list_display.py` (or successor) implements identity A for list lines **and** search haystack (username, sequence, tariff, id). Rich-menu `_build_subscriptions_table` uses the same helper.

### Cabinet API (`/opt/remnabot1` `multi_tariff.py`)

Port production list DTO fields needed for A and search: `panel_username`, `account_sequence`, `total`; query `offset`, `limit`, `search`. Search matches username, tariff name, and numeric id. If `purchase_note` is already on the ORM, include it in the search haystack only — no note edit UI.

Do not add partner checkout body fields in this spec.

Cabinet purchase/renewal/traffic/devices/switch keep using `PricingEngine`. Buy-new catalog calls must not send a bound `subscription_id`.

### Cabinet UI (`/opt/cabinet`)

**Copy from donor (small files):**

- `src/components/subscription/purchase/purchaseRoutes.ts` (`NEW_PURCHASE_PATH`, `isNewPurchaseIntent`)
- Expand `subscriptionDisplayLabel.ts` to identity A + search helpers already in production (or equivalent). Tests stay in vitest.

**Wire, do not replace:**

| Surface | Change |
|---|---|
| `Subscriptions.tsx` | Debounced search; buy CTA → `NEW_PURCHASE_PATH`; cards use identity A with `isMultiTariff` |
| `SubscriptionPurchase.tsx` + tariff picker | `intent=new` unbinds `subscriptionId` / options pin (production `effectiveSubscriptionId`) |
| `Dashboard.tsx` buy-another links | Same `NEW_PURCHASE_PATH` |
| `Subscription.tsx` detail | Identity A as `<h1>` + copy username; **gate** first-connect (active, not limited, `usedGb===0`, link visible); connect = config sheet **and** guide `/connection?sub=`; `volumeEmptyHint`; additional-options row «خرید سرویس جدید» → `NEW_PURCHASE_PATH`; keep 1.67 device/traffic/server sheets |
| RTL | `rtl:scale-x-[-1]` (or equivalent) **only** on directional Back/Chevron, not on all icons |

**Do not copy** production `Subscription.tsx` over 1.67 (would drop SBP/Lava and Day-1 work).

**API client:** `getSubscriptions` must pass `search` / `offset` / `limit`; types include identity A fields.

### RTL mini-app icons

Cause: Day-1 `document.dir=rtl` + physical `PiArrowLeft` / `PiCaretRight`. Fix directional icons only. Telegram native BackButton stays native.

---

## Data flow

1. **`/start`** — 4.2 rich HTML + existing menu-layout keyboard. Multi-tariff users always see `menu_buy`. Identity A in the subscription table cells.
2. **`menu_buy`** — clear pin → tariff catalog → confirm uses predicate → **create** → `PricingEngine` price → persist identity numeric id **and** username cache → `account_sequence` assigned.
3. **Renew from detail** — pin id → same catalog/period UI → predicate **extend** → same engine.
4. **Traffic / devices / switch** — always bound to one `subscription_id`; engine addon/switch helpers; never the buy-new pin-clear path.
5. **Cabinet list** — GET `/cabinet/subscriptions?search=` → cards titled with A → buy-another `?intent=new`.
6. **Cabinet detail** — GET by id → title A → gated guide/config → extra options include buy-new and bound renew/traffic/devices.
7. **Cabinet purchase** — if `intent=new`, no `subscription_id` on options/purchase; engine still applies partner vs retail from the authenticated user.

---

## Error handling

| Failure | Behavior |
|---|---|
| Buy-new pin missing or stale | Create new row; never silent-extend |
| Renew pin missing | Show keyed error; do not create a duplicate service |
| `panel_username` empty / `user_unknown_*` | Title `{tariff} #{seq}`; no crash |
| Search empty / no hits | Keyed empty state; clear restores full list |
| `jdatetime` missing | Gregorian; menu still renders |
| Price on an edge ≠ `PricingEngine` | Matrix test FAIL; fix the edge, do not fork math |
| Cabinet CTA without `intent=new` | Must not bind the current subscription |
| Unmapped identity columns | Fail tests; do not ship tariff-only titles |

---

## Testing

**Automated (bot):**

- Identity A: real username; `user_unknown_*`; missing username → `#seq`.
- Predicate: pin+matching tariff → extend; no pin → create; pin/tariff mismatch → create not extend.
- `show_buy`: multi-tariff + active sub → `menu_buy` present; single-tariff + active sub → hidden (today).
- Static guard: no `brand_serial` / partner-prefix title in user list/rich-table formatters.
- **Price matrix (blocking):** retail user vs `partner_status=approved` with `wholesale_discount_bps` on: new tariff purchase, extend, traffic top-up, device top-up, tariff switch. Assert each path calls `PricingEngine` (or the existing engine instance) and that partner < retail when bps > 0. Include cabinet route tests for the same five edges.

**Automated (cabinet):**

- `isNewPurchaseIntent` unbinds id.
- `getSubscriptionDisplayLabel` identity A.
- List search helper matches username / id / tariff.
- RTL: directional icon class present on Back/Chevron (unit or static).

**Not in CI:** Telegram E2E, DNS, production token, merge of 4.4/1.69.

**Operator smoke (this overlay):**

1. RC bot `/start`: «خرید سرویس» visible with an already-active sub; catalog purchase creates a **second** row; prices Toman; partner test account (if present) cheaper than retail on the same tariff/period.
2. Same user: renew from subscription detail extends **that** row, not a new one; traffic/device addons priced from the engine.
3. `https://panel.rookari.com/subscriptions`: unique titles (not ten identical tariff names); search; buy-another does not renew the open sub.
4. Detail `/subscriptions/<id>`: title A, gated first-connect, config + guide, buy-another row.
5. Mini-app fa: back/chevron icons point to the logical back/forward, not mirrored twice.

---

## Workstreams (for the implementation plan)

| ID | Workstream | Tree | Notes |
|---|---|---|---|
| I | ORM map `panel_username` + `account_sequence`; drop unique from `__table_args__`; username cache helper | `/opt/remnabot1` | No autogenerate |
| B | `show_buy` multi-tariff; `menu_buy` clears pin; extend predicate | `/opt/remnabot1` | Thin hooks |
| L | Identity A on list + rich table; remove brand_serial titles | `/opt/remnabot1` | |
| P | Price-matrix tests on five edges | `/opt/remnabot1` | Blocking |
| A | Cabinet API DTO + search | `/opt/remnabot1` | |
| C | Cabinet routes/label/search/detail/RTL | `/opt/cabinet` | Small file copy + wire |
| S | Joint smoke | both | After I,B,L,P,A,C |

One concern per commit. Bot and cabinet stay separate commits.

---

## Out of scope (backlog)

Record only; do not implement in this overlay:

- Cabinet `PartnerCheckoutFields`, brand prefix / purchase-note **UI**, Earn, `/sales`, Layer C
- Cabinet `DisableSubscriptionSheet` / note edit sheets
- Merge BEDOLAGA bot 4.4.0 / cabinet 1.69.0
- Restoring 3.60 `/start` grid
- M7-T1 / M8 / DNS / production token
- Full `Subscription.tsx` or `tariff_purchase.py` replace
- New Alembic heads / autogenerate
- Using `brand_serial` as the customer-facing title

---

## Sequence vs cutover

This overlay is the **sales bar** before DNS. M7-T1 stays named-start on the MVP plan and is not started from this spec. Layer B wholesale pricing must keep working on every sales edge even without partner UI.
