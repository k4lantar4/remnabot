# Cabinet user-first overlay + separate sales desk — design

**Date:** 2026-09-03  
**Status:** Design locked (operator تایید 2026-09-03). Layer A implementation: Part B of `docs/superpowers/plans/2026-09-04-day1-telegram-overlay.md`. Layer C is a later separate plan.  
**Does not execute:** M7-T1, M8, production DNS, cabinet/bot code  
**Trees:** `/opt/cabinet` (1.67.0, base) · `/opt/remnabot/cabinet` (1.57.0 embed, READ-ONLY donor) · `/opt/remnabot1` (bot)

---

## Verdict (binding)

1. **Base = 1.67** at `/opt/cabinet` `prod-cutover`. Do not rebase 1.57 forward.
2. **Before cutover:** only the **normal-user** cabinet surface (Persian, dates, wording, subscription page, RTL numbers/URLs).
3. **Sales model** lives in the **bot price engine** (`PricingEngine` + `wholesale_discount_bps` + `partner_status`). It must keep working on Telegram at cutover even if cabinet has no partner desk yet.
4. **Partner / earn / wholesale admin** are a **separate app** on the same cabinet: new routes under something like `/sales` and `/admin/sales`, not a rewrite of upstream `/referral` or the upstream partner admin pages.
5. Touch upstream files only with **thin hooks** (one menu item, one optional checkout slot). Never replace `Referral.tsx`, `TariffPurchaseForm.tsx`, or whole `fa.json`.

Production today stuffed Earn into `/referral`. That is the merge trap. This design inverts it: upstream referral stays; our sales desk is sibling code.

---

## Three layers (do not mix in one commit)

| Layer | Who sees it | Where it lives | When |
|---|---|---|---|
| **A — Normal user UI** | Every customer | Cabinet 1.67 overlays | Before cutover (named plan, not M7) |
| **B — Sales rules** | Invisible; partner pays less | remnabot1 `PricingEngine` (already ported) | Already in bot; keep intact |
| **C — Sales desk** | Approved partners + admins | New cabinet routes + later bot API/ORM map | After user UI; gradual; not a cutover blocker |

Normal users do not need Earn tabs, inventory, or wholesale percent. Partners still get the **price** on Telegram via layer B on day one.

---

## Why 1.67 is the base

Maintained fork, M5 compose, M6-T5 Toman skipFx, and upstream coupons/legal/grace/referral-ranks all live here. Starting from 1.57 would replay those versions and wipe RC commits. Production `Referral.tsx` is 135 lines; 1.67 is 1127 lines with a different product. Copying the 1.57 file is a delete of upstream work.

---

## Layer A — normal user (pre-cutover)

Donor: `/opt/remnabot/cabinet` (behavior), implemented as overlays on 1.67.

### A1. Default `fa` + first paint RTL

**Why:** 1.67 `fallbackLng` is `ru`, detects `navigator`, `index.html` is `lang="ru"`. First paint can be Russian.

**How:** Patch only `src/i18n.ts` and `index.html`: default `fa`, fallback `fa → ru → en`, detect `localStorage` only (browser language is often `en`). Keep 1.67 `syncHtmlLang`. Do not replace the i18n module.

### A2. Jalali dates

**Why:** Production user dates use Persian calendar. 1.67 is Gregorian.

**How:** Add `src/utils/formatDate.ts` (new file). Patch **user** pages (subscription, profile, balance, gift, support, wheel, merge, success). Do not bulk-rewrite admin-local date helpers in the same slice.

### A3. User wording

**Why:** Production says تعداد کاربر / سرویس. 1.67 still says دستگاه / تعرفه on many user keys.

**How:** Merge values into 1.67 `fa.json` user paths only. Never replace the whole file (would drop coupons/legal/grace). English digits. Separate commit from Earn keys.

### A4. RTL isolate for amounts and subscription URLs

**Why:** 1.67 `src/` has no `dir="ltr"` / `unicode-bidi: isolate`. Production isolates numbers and links so they do not reverse in Persian layout.

**How:** Small class or wrapper reused on price and URL fields. Surgical patches on subscription/purchase display. No new dependency.

### A5. Subscription detail UX (not a file replace)

**Why:** Production detail page has first-connect checklist, empty-volume hint, config-delivery sheet, traffic text, disable sheet, and hides `user_unknown_*` labels. 1.67 has none of those components.

**How:** Add those as **new** components. Wire them from 1.67 `Subscription.tsx` with small imports. Do **not** copy production `Subscription.tsx` over 1.67.

**Out of A:** partner checkout fields, Earn, wholesale admin, `priceUnits` unless a user screen actually needs them.

---

## Layer B — sales rules (bot, already the source of truth)

**Why:** Live production charges approved partners via `PricingEngine.uses_wholesale_pricing` / `wholesale_discount_bps` on Telegram purchase (`tariff_purchase.py`). remnabot1 already has the engine and column (M4-T7 / M6-T3).

**How:** Do not reimplement pricing in cabinet. Cabinet must eventually *display* the same number the engine would charge; it must not compute a second discount.

**Cutover:** Layer B is enough for the sales model if Layer C is not ready. Telegram partner purchase keeps wholesale. Brand prefix / purchase-note on Telegram (`tariff_purchase_partner.py`) is a **later** remnabot1 port (ORM map of `0095` columns + `partner_checkout` service). It is not required to start Layer A.

**Check at execution:** inspector on rehearsal/production-lineage DB for `users.panel_brand_prefix` and `subscriptions.purchase_note` before adding a new Alembic revision. `0095` already adds them; map ORM if present.

---

## Layer C — sales desk (separate app, after Layer A)

**Why:** Partners need a place for inventory, apply, brand, wholesale badge. Admins need to set percent. Upstream `/referral` is reward/withdrawal/ranks — a different product. Production merged Earn *into* referral; we will not repeat that.

**How:**

- New user routes, e.g. `/sales` (name bikeshed in the implementation plan). Own pages under `src/pages/sales/` or `src/pages/custom/sales/`. Port Earn tabs **here**, not into `Referral.tsx`.
- One thin hook in nav: a menu item visible when `partner_status === approved` (or always “همکاری” that explains apply). `App.tsx` gains a route line only.
- New admin routes, e.g. `/admin/sales/partners/:id/wholesale`. New page, not a rewrite of upstream `AdminPartnerDetail`. Optional later link from partner detail (one button).
- Bot API when C starts: extend `PartnerStatusResponse`, `GET .../inventory`, `PATCH .../wholesale`, purchase fields + `partner_checkout`. Port from `/opt/remnabot`; do not invent a second inventory service.
- Checkout: if partners must buy **from cabinet** with brand/note, inject `PartnerCheckoutFields` as an optional slot in 1.67 `TariffPurchaseForm` — do not replace the form (promo/SBP/Lava stay upstream).

**Do not:** copy 1.57 `Referral.tsx`; copy unused `TariffPurchaseWizard`; conflate 1.67 coupon `wholesale_price_kopeks` with partner BPS.

**Miniapp:** follow-up after cabinet `/sales`. Same bot API; not Layer A.

---

## Overlay vs replace (binding)

| Artifact | Action |
|---|---|
| 1.67 `Referral.tsx`, `TariffPurchaseForm.tsx`, coupons/legal/grace | Keep. At most a nav link or optional slot |
| 1.67 `fa.json` | Merge user-path values only |
| New: `formatDate.ts`, RTL helper, subscription sheets, `/sales/*`, `/admin/sales/*` | Add |
| Donor `Referral.tsx`, `TariffPurchaseForm.tsx`, `TariffPurchaseWizard.tsx`, whole `fa.json` | Do not copy as replacements |
| `AdminEmailTemplatePreview`, `useUserThemePreferences` | Out of scope |

---

## Sequence

1. Layer A on `/opt/cabinet` (named implementation plan; still not M7).
2. Cutover remains **M7-T1 named-start** and is independent of Layer C.
3. Layer C when operator asks: bot ORM/API first, then `/sales` + `/admin/sales`.
4. Telegram brand/note port and miniapp after C’s API exists, or skipped until needed.

Do not ship `/sales` against missing APIs.

---

## Out of scope

- M7/M8, production token, DNS.
- Embedding cabinet into remnabot1.
- Mixing Toman FX with wording commits (skipFx already on 1.67).
- Making Layer C a cutover blocker.
- Designing the full admin sales suite up front (one wholesale-percent page is enough for C1).

---

## Evidence (2026-09-03)

- Cabinet `prod-cutover` @ `c5b1ca9a`; 1.67.0 = `35e5aa9e`.
- Production Earn is wired from `Referral.tsx` default tab `partner`; 1.67 `Referral.tsx` is upstream withdrawal/rewards.
- remnabot1: `wholesale_discount_bps` + `PricingEngine` present; `PartnerStatusResponse` lacks wholesale/brand; ORM lacks `panel_brand_prefix` / `purchase_note`; Alembic `0095` adds those columns.
- 1.67 `src/` has no `dir="ltr"` isolate; production subscription/purchase/traffic text does.
- Operator 2026-09-03: normal-user page first; partner as a separate merge-safe desk; admin gradual; sales rules stay in the bot.

---

## Spec self-review

- No TBD placeholders. Route path `/sales` may be renamed in the plan; the rule is “sibling route, not Referral rewrite.”
- Layer A vs C do not contradict: A has no partner API requirement.
- Layer B vs C: price stays in the engine; C only displays and administers.
- Scope is one design; implementation plans should split A vs C into separate plans so cutover is not blocked.
