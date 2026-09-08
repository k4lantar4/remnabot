# Day-1 remaining overlay — Telegram 4.2 + cabinet 1.67

**Date:** 2026-09-04  
**Status:** Design locked (operator تایید 2026-09-04, sections 1–4). Implementation plan is a later `writing-plans` step after spec review.  
**Does not execute:** M7-T1, M8, production DNS, Layer C sales desk, application code in this document  
**Trees:** `/opt/remnabot1` (bot 4.2.0, `prod-cutover`) · `/opt/cabinet` (1.67.0) · `/opt/remnabot` (3.60 donor, READ-ONLY)

**Related:** cabinet Layer A is specified in `docs/superpowers/specs/2026-09-03-cabinet-b2-overlay-design.md` and implemented as Part B of `docs/superpowers/plans/2026-09-04-day1-telegram-overlay.md`. This spec names the joint cutover-readiness bar.

---

## Verdict (binding)

1. **Scope = remaining production custom only.** MVP ports stay Done: C2C plugin, FA fallback, Toman dual-scale, wholesale `PricingEngine`, numeric panel identity, token guard, cabinet `skipFx`, cabinet JWT isolation. Do not unwind them into plugins.
2. **Success bar = day-1 Telegram + cabinet user surface before DNS cutover.** A normal customer and an approved partner must recognize the Iran product on `/start`, My Subscriptions, purchase, and cabinet. Layer C (Earn / wholesale admin web) is after cutover and is not a blocker.
3. **Keep the 4.2 rich `/start` shell.** Overlay Persian, Jalali, and Toman on Connect / Subscription / Balance / Promo / Referrals / Support / Info. Do not restore the 3.60 inline grid (mini-app row, «نمایندگی و دعوت», caption overflow «و N مورد دیگر»).
4. **Restore production My Subscriptions list behavior on 4.2.** Search, page/total, brand+serial identity (e.g. `Moonvpn_67258`), «تعداد کاربر», Jalali dates. Do not copy `/opt/remnabot/app/handlers/subscription/my_subscriptions.py` over the 4.2 file.
5. **Isolation = surgical overlay.** New helpers + thin hooks in hot files. No 3.60 file replace. No new plugin framework. Cabinet Layer A stays overlay-on-1.67.
6. **This track does not start M7.** Named-start for cutover stays on the MVP plan. Day-1 overlay can run in parallel with that gate; it does not flip DNS.

---

## Why this spec exists

Operator screenshots (2026-09-03) showed the gap that M6-T5 did not cover:

| Surface | Production 3.60 | RC 4.2 today |
|---|---|---|
| `/start` | Custom Persian grid + Jalali preview + Toman caption | 4.2 rich menu (`Show more`, Connect, Subscription, Balance) |
| My Subscriptions | Persian title, page/total, search, brand+serial, «تعداد کاربر», Jalali | Hardcoded Russian chrome (`Мои подписки`, Трафик, Устройства), Gregorian, tariff name, gift, no search |
| Balance | Toman | Toman (already ported) |

M6-T5 only verified that My Subscriptions **opens**. Cabinet Layer A covers the SPA, not Telegram chrome. Without this spec, cutover can be green on C2C/Toman and still ship a Russian 4.2 shell.

Pagination count 24 vs 117 is different accounts, not a missing feature.

---

## Architecture

Two application trees, two overlay programs, one day-1 bar. Donor behavior is `/opt/remnabot` (read-only).

```
4.2 rich /start  +  3.60 list behavior  +  cabinet Layer A
        \              |                      /
         \             |                     /
          \            v                    /
           ---- day-1 smoke (Telegram + panel.rookari.com) ----
                         |
                    M7 named-start (not this spec)
```

**Bot (`/opt/remnabot1`):** keep upstream rich-menu renderer. Overlay strings and dates. Replace the list line formatter and add search/identity via `app/utils/subscription_list_display.py` (name may shift in the implementation plan; responsibility stays: one helper owns list chrome). Partner checkout and `user_disabled` are thin modules with fail-open if ORM is not mapped.

**Cabinet (`/opt/cabinet`):** execute the existing Layer A plan. Do not replace `Referral.tsx`, `TariffPurchaseForm.tsx`, or whole `fa.json`.

**Pollution boundary:** helpers own logic; hot files get callsites only. Do not turn `my_subscriptions.py` into a 3.60 clone. Existing MVP edits in `PricingEngine`, `config.py`, and `models.py` stay; this spec does not extract them.

---

## Components

### Already Done (out of this work, must not regress)

C2C (`app/plugins/c2c/`), FA fallback, Toman `format_price` / `format_balance`, wholesale `PricingEngine`, `persist_identity`, token guard, cabinet `skipFx`, Alembic graft through `0112`.

### Cabinet Layer A (existing plan, `/opt/cabinet`)

A1 default `fa` + first-paint RTL · A2 Jalali · A3 user wording · A4 LTR isolate · A5 subscription sheets. Implementation: Part B of `docs/superpowers/plans/2026-09-04-day1-telegram-overlay.md`.

### Telegram rich `/start` (4.2 shell stays)

- `fa.json` keys for `MAIN_MENU_RICH_*` (and any visible English chrome such as Show more / Connect / Subscription).
- Jalali in the rich-menu subscription preview via existing `app/utils/jalali_datetime.py`.
- Keyboard structure unchanged. Regression test: `/start` still exposes Connect/Subscription, not the 3.60 grid.

### My Subscriptions list (production behavior)

- Helper path: `app/utils/subscription_list_display.py`. Owns one list line (traffic, user-count label, Jalali), display identity (brand+serial when present, else 4.2 tariff name), and search filter over serial/brand/label.
- `my_subscriptions.py` drops hardcoded Cyrillic in `_format_subscription_line` / keyboard labels and calls the helper. Adds search button + title `page/total`. 4.2 gift row **stays**.
- Donor search FSM is the behavior reference; port into helper + thin handler hooks, not a file replace.

### Serial / brand ORM

Columns already exist via remnabot-lineage `0095` (`users.panel_brand_prefix`, `subscriptions.purchase_note`). Map them on SQLAlchemy models. Display helper reads them. Inspect rehearsal/production-lineage DB before adding any new Alembic revision. Do not autogenerate.

### Partner checkout (Telegram day-1)

Thin module: purchase note + brand toggle for `partner_status == approved`, hooked at 4.2 confirm. Price still comes from `PricingEngine` (Layer B). No cabinet `PartnerCheckoutFields`. If ORM fields are missing, skip the extra UI and continue the 4.2 purchase.

### Pause (`user_disabled`)

Column exists via `0103`. Map on the bot ORM. Telegram subscription detail can pause/resume. Cabinet `DisableSubscriptionSheet` is **not** in this spec (needs API/type later). If the column is unmapped, omit the button.

### Jalali wiring

One util (`jalali_datetime.py`). Call sites: rich menu preview, list lines, purchase-success dates. Missing `jdatetime` → Gregorian. Not a new package.

---

## Data flow

1. **`/start`** — 4.2 rich renderer. Language already forced `fa`. Balance already Toman. Overlay supplies `fa.json` copy and `format_user_datetime` for preview dates. Keyboard JSON shape unchanged.
2. **My Subscriptions** — existing 4.2 query (multi-sub per user already in schema). Each row: helper identity → helper line format → handler pagination/buttons. Search FSM: user text → filter serial/brand/label → same renderer. Empty query or expired FSM → keyed message, full list.
3. **Partner purchase** — 4.2 confirm funnel. If approved partner, inject note/brand fields; persist `purchase_note` / `panel_brand_prefix`. Wholesale amount is Layer B, already ported.
4. **Pause** — detail action writes `user_disabled`; list status label updates. Cabinet is not a consumer in this slice.
5. **Cabinet Layer A** — independent browser path: 1.67 + overlays → bot `/api`. Does not share the Telegram list helper.

---

## Error handling

| Failure | Behavior |
|---|---|
| `jdatetime` missing | Gregorian dates; no crash |
| No brand/serial | 4.2 tariff name |
| Search empty / FSM lost | Locale message; show full list |
| Partner columns unmapped | Hide extra fields; 4.2 purchase continues |
| `user_disabled` unmapped | Hide pause button |
| Missing `fa` key | Existing `fa → en → ru` |
| Rich-menu date format throws | Fall back to Gregorian; `/start` must still render |

---

## Testing

**Automated (bot):**

- List formatter: Jalali for `fa`, Gregorian otherwise; serial vs tariff; «کاربر» not Cyrillic device wording.
- Search filter over serial/brand.
- Static guard: list-render path in `my_subscriptions.py` has no hardcoded Cyrillic.
- Keyboard: search present; gift present; `/start` still 4.2 Connect/Subscription.

**Automated (cabinet):** vitest/biome from Layer A plan.

**Not in CI:** Telegram E2E, DNS, production token.

**Operator smoke (day-1 bar):**

1. `/start` on RC test bot: rich 4.2 shell, Persian chrome, Jalali preview, Toman balance.
2. My Subscriptions: Persian chrome, Jalali, search, page/total, brand+serial when the account has prefix/serial.
3. Cabinet `https://panel.rookari.com`: first paint `fa`/RTL, Jalali, wording, subscription sheets (Layer A checklist).
4. Optional: one approved-partner Telegram purchase with note/brand if a test partner exists.

---

## Day-1 workstreams (for the implementation plan)

Parallelizable: **Cabinet A** ∥ **rich menu** ∥ **ORM map** ∥ **list formatter**. The Jalali helper already exists (`jalali_datetime.py`); list formatter does not wait on the rich-menu slice. Search/identity, partner checkout, and pause wait on the ORM map.

| ID | Workstream | Tree | Depends on |
|---|---|---|---|
| A | Cabinet Layer A (A1–A5 + cabinet smoke) | `/opt/cabinet` | — |
| T | Rich `/start` fa + Jalali | `/opt/remnabot1` | — |
| O | ORM map `0095` + `0103` columns | `/opt/remnabot1` | inspect DB; no autogenerate |
| L | List formatter (Jalali, تعداد کاربر, drop Cyrillic) | `/opt/remnabot1` | existing `jalali_datetime.py` |
| S | List identity + search + page/total | `/opt/remnabot1` | L, O |
| P | Partner checkout Telegram | `/opt/remnabot1` | O |
| U | Pause on Telegram detail | `/opt/remnabot1` | O |
| G | Joint day-1 smoke | both | A, T, S, P, U |

Granular tasks belong in the implementation plan (one concern per commit). This spec only locks the workstreams and dependencies.

---

## Out of scope

- Restoring the 3.60 `/start` keyboard grid
- Cabinet Layer C (`/sales`, Earn tabs, `AdminPartnerWholesale`, `PartnerCheckoutFields`)
- Cabinet disable sheet (`user_disabled` API/types)
- Miniapp sales desk follow-up
- New 4.2 natives: referral ranks productization, coupons, grace, legal consents, YooKassa/Platega/Lava/CisPay
- M7-T1 / M8 / DNS / production token
- Extracting Toman/FA/wholesale out of core into plugins
- Full `alembic revision --autogenerate`
- Copying donor `my_subscriptions.py`, `Referral.tsx`, or whole `fa.json`

---

## Sequence vs cutover

Day-1 overlay **before** DNS is the product bar. M7 remains named-start on the MVP plan and is not auto-started from this spec. Layer B pricing already holds for partners on Telegram even without Layer C.
