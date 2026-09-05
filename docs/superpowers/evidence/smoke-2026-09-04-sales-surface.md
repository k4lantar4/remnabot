# Sales surface overlay — operator smoke checklist

**Date:** 2026-09-05 (draft — results empty until operator `تایید`)  
**Plan:** `docs/superpowers/plans/2026-09-04-sales-surface-overlay.md` Task 13  
**Spec:** `docs/superpowers/specs/2026-09-04-sales-surface-overlay-design.md`  
**STOP:** do not start M7 / DNS / production token from this smoke.

This file is the Task 13 checklist. Fill the **Result** column after smoke. Do not mark overlay PASS until operator `تایید`.

## Runtime (fill after rebuild)

| Component | Identity | Status |
|---|---|---|
| Bot commits | remnabot1 `97b4aa88` → `882771dc` (`prod-cutover`, local, not pushed) | `rehearsal_bot` rebuilt 2026-09-05; healthy; `/health` 200 `4.2.0` |
| Cabinet commits | cabinet `0173edae` → `d6aed5db` (`prod-cutover`, local, not pushed) | `cabinet_frontend` rebuilt 2026-09-05; healthy; `intent=new` in `index-MwCk3kax.js` |
| Telegram RC | test token, polling (`@mrj7_bot` / rehearsal_bot) | healthy |
| Cabinet RC | `https://panel.rookari.com` | HTTP 200 |
| Mini-app | same panel host, fa `dir=rtl` | hard-refresh after rebuild |

Do not use production bot token or production C2C admin chat.

Cabinet JS is hashed (`index-MwCk3kax.js`). After rebuild, open panel in a **private window** or hard-refresh so the old bundle is not cached.

### Agent gate (already run)

| Gate | Command | Result |
|---|---|---|
| Bot pytest | `uv run pytest tests/database/test_day1_orm_columns.py tests/custom/test_cache_panel_username.py tests/crud/test_account_sequence.py tests/utils/test_subscription_list_display.py tests/utils/test_subscription_purchase_intent.py tests/services/test_menu_layout_service.py tests/test_wholesale_pricing.py tests/cabinet/test_sales_edges_use_pricing_engine.py tests/cabinet/test_multi_tariff_search.py -q` | **43 passed** (2026-09-04) |
| Cabinet vitest | `npx vitest run src/components/subscription/purchase/purchaseRoutes.test.ts src/utils/subscriptionDisplayLabel.test.ts src/components/icons/directional.test.ts` | **5 passed** (2026-09-04) |

---

## A — Telegram RC (`/start`, already-active test user)

Use a test account that **already has an active subscription**. Period picker only (not custom-days, not daily repurchase of the same tariff).

| ID | Path | Expect | Result |
|---|---|---|---|
| A1 | Send `/start` | Rich 4.2 shell stays (not 3.60 grid). **«خرید سرویس» (`menu_buy`) is visible** even with an active sub. | **PASS** (operator تایید 2026-09-05) |
| A2 | Read chrome | Persian labels; prices/balance in تومان; English digits | **PASS** (operator تایید 2026-09-05) |
| A3 | Tap «خرید سرویس» | Tariff **catalog** (not silent renew of the open sub) | **PASS** (operator تایید 2026-09-05) |
| A4 | Pick a **period** tariff (same or different — both OK) → confirm paid/test path | Creates a **second subscription row**. List shows two titles. | **FAIL** — new row probably not created; catalog calc in Russian. Dual-scale + `format_period_description(fa=ru)` follow-up in flight. Re-test after rebuild. |
| A5 | Same period, partner vs retail (if a test partner exists) | Partner price **cheaper** than retail on that period. Skip if no partner test user. | deferred (operator: later) |
| A6 | Open the **new** sub’s detail → Renew / extend | Extends **that** row (same id), does not create a third row | |
| A7 | Traffic addon on that sub (if offered) | Still priced; Toman | |
| A8 | Device addon on that sub (if offered) | Still priced; Toman | |
| A9 | My Subscriptions list titles | Identity A: panel username (not `user_unknown_*`); else `{tariff} #{seq}`. **No** `Moonvpn_67258` brand_serial titles. | |

---

## B — Cabinet (`https://panel.rookari.com`)

Private/incognito if language cache is dirty. After RC cabinet rebuild from `d6aed5db`.

| ID | Path | Expect | Result |
|---|---|---|---|
| B1 | `/subscriptions` | Unique titles (identity A). Not ten cards with the same tariff name. | |
| B2 | Search (visible when ≥2 accounts) | Filter by username / id; clear restores list | |
| B3 | Empty / buy-another / browse CTA | Goes to `/subscription/purchase?intent=new` | |
| B4 | Buy-another from list while a sub is “current” | Catalog purchase does **not** renew the open sub; new row (or unbound picker) | |
| B5 | Dashboard buy-another / browse (if shown) | Same `?intent=new` URL | |
| B6 | `/subscriptions/<id>` title | Identity A; copy-username only if title is a real panel username | |
| B7 | First-connect checklist | Shown only when active, not limited, `usedGb === 0`, connection URL present. `volumeEmptyHint` still shows at 0 GB. | |
| B8 | Config + guide | Two controls: get config (sheet) **and** open guide (`/connection?sub=…`). Disabled at device limit. | |
| B9 | Additional options | Buy-another row → `?intent=new` (multi-tariff). No note/disable sheets required. | |

---

## C — Mini-app / RTL

| ID | Path | Expect | Result |
|---|---|---|---|
| C1 | fa UI, back control | Back/chevron point the **logical** way (mirrored in `dir=rtl`) | |
| C2 | Search / plus / close icons | **Not** mirrored | |

---

## Skip this round (known leftovers — not a FAIL)

| Skip | Why |
|---|---|
| Catalog **custom-days** confirm of a tariff the user already owns | `handle_custom_confirm` still extends by `tariff_id` |
| Catalog **daily** repurchase of an already-owned daily tariff | `confirm_daily_tariff_purchase` still binds by `tariff_id` |
| Completing a live payment charge | Not required if test/balance path can create the second row |
| Production token, prod C2C chat, M7-T1, DNS | Forbidden |

---

## Operator results

| ID | Result | Notes |
|---|---|---|
| A1–A3 | **PASS** | Operator تایید 2026-09-05 |
| A4 | **FAIL** | New sub probably not created; Russian period/insufficient calc. Follow-up: traffic=fixed, dual-scale Toman, fa period labels. |
| A5–A9 | pending | Operator: remaining smoke later |
| B1–B9 | pending | Search focus + Toman renew/purchase in follow-up; B2 re-test after rebuild |
| C1–C2 | pending | |

**Sales surface overlay smoke:** _pending_ (A4 FAIL; not PASS)  
**Do not start M7** from this result.

## Sign-off

Operator:  
Result:  
Date:  
Bot HEAD at sign-off:  
Cabinet HEAD:  
RC rebuild verified (yes/no):  
