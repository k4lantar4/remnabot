# Earn Tab Redesign — Design Spec

**Date:** 2026-07-13  
**Status:** Approved  
**Scope:** Cabinet user surface (`/referral`) — Phase 1 frontend only  
**Route:** unchanged (`/referral`); nav label and page IA change

---

## Problem

The current «نمایندگی» page (`cabinet/src/pages/Referral.tsx`) merges two distinct user journeys into one long scroll:

1. **Invite friends** — regular users share a bot link and earn referral credit usable on purchases.
2. **Partnership (نمایندگی)** — users apply to become resellers with wholesale discount, brand prefix, and campaign tools.

Pain points confirmed with operator:

- «درخواست نمایندگی» CTA is buried below stats, links, terms, and referral lists.
- Too many financial numbers (5–6 withdrawal fields) that do not match the Iran business model (no direct payouts to users).
- Mixed terminology: nav «نمایندگی», badge «شریک», sections «معرفی» / «کمیسیون» / «تخفیف عمده».
- Same layout for all user states; partners and regular users see irrelevant blocks.
- Duplicate commission rates (referral `info.commission_percent` vs partner `partnerStatus.commission_percent`).

---

## Business Model (Iran)

| Actor | Relationship | UI priority |
|-------|--------------|---------------|
| End user of a partner | Never sees our site; partner manages their subscriptions | Out of scope for this page |
| Regular cabinet user | Invites friends via bot link; earns **referral credit** (Toman) usable on own purchases — **not cash withdrawal** | Tab «دعوت» |
| Approved partner (نماینده) | Buys at wholesale discount, resells to own users; needs status confirmation + discount % + simple sales stats | Tab «نمایندگی» (default) |
| User applying for partnership | Needs prominent apply CTA + 3 benefits | Tab «نمایندگی» (default) |

**No user-facing withdrawal flow** in Phase 1. Backend withdrawal APIs remain; UI is hidden.

**Referral credit display:** use `available_balance_rubles` from `GET /cabinet/referral` — referral entitlement usable for purchases (not general wallet balance label).

---

## Decisions (from brainstorming)

| Topic | Decision |
|-------|----------|
| Page structure | Two in-page tabs: «نمایندگی» \| «دعوت» |
| Default tab | Always «نمایندگی» (partner acquisition first) |
| Nav label | «کسب درآمد» (`nav.earn`) |
| Tab labels | «نمایندگی» \| «دعوت» |
| Withdrawal UI | Hidden; replaced by referral credit on invite tab |
| Invite tab content | Bot link + referral credit + one-line explainer + referred users list |
| Partner tab (approved) | Status emoji + wholesale discount % + simple stats + link to invite tab |
| Partner tab (non-partner) | Hero CTA + 3 benefits + apply button at top |
| Partner tab (pending/rejected) | Status cards (existing logic, repositioned) |
| Campaigns | Shown simplified under partner stats when `approved` |
| Cabinet referral link | Removed from invite tab (bot link only) |
| Program terms grid (4 cards) | Removed; one dynamic line on invite tab |
| Commission wording | Partner: «درصد تخفیف نمایندگی»; Invite: «پورسانت معرفی» |
| Badge «شریک» | → «نماینده فعال» |
| Backend Phase 1 | No API changes |
| Bot menu parity | Phase 2 optional (`MENU_REFERRALS`) |

---

## Information Architecture

```
Nav: کسب درآمد  →  /referral

┌─────────────────────────────────────────┐
│  [ نمایندگی ]  [ دعوت ]    ← tabs       │
├─────────────────────────────────────────┤
│  (active tab content)                   │
└─────────────────────────────────────────┘
```

### Tab: نمایندگی (default)

**`partner_status === 'none'`** and `partner_section_visible !== false`:

```
┌ Hero ────────────────────────────────────┐
│  🏪 درخواست نمایندگی                     │
│  • تخفیف خرید عمده                       │
│  • برند اختصاصی در پنل                   │
│  • آمار فروش و مدیریت مشتریان            │
│  [ درخواست نمایندگی ]  ← primary CTA    │
└──────────────────────────────────────────┘
```

**`pending`:** warning card — under review + submitted date.

**`rejected`:** error card — admin comment + reapply.

**`approved`:**

```
┌ Status ──────────────────────────────────┐
│  ✅ نماینده فعال                         │
│  🏷 برند: {panel_brand_prefix} (if set)  │
│  💰 درصد تخفیف نمایندگی: {wholesale}%    │
├ Stats (aggregated from campaigns) ───────┤
│  • {n} دعوت / ثبت‌نام                    │
│  • {amount} تومان درآمد از معرفی         │
├ Quick action ────────────────────────────┤
│  [ دعوت دوستان ← ]  → switches to دعوت   │
└──────────────────────────────────────────┘
│  Campaign cards (simplified, if any)     │
```

Wholesale % = `Math.round(wholesale_discount_bps / 100)`.

Aggregated stats (Phase 1, no new API):

```ts
registrations = sum(campaign.registrations_count)
referrals     = sum(campaign.referrals_count)
earnings      = sum(campaign.earnings_kopeks) → display via useCurrency
```

If partner has no campaigns, show referral-level stats from `info` (total_referrals, total_earnings_rubles).

### Tab: دعوت

```
┌ Credit ──────────────────────────────────┐
│  💵 پورسانت معرفی: {available_balance}   │
│     قابل استفاده در خرید بعدی            │
├ Link ────────────────────────────────────┤
│  🔗 لینک دعوت ربات                       │
│  [ کپی ]  [ اشتراک‌گذاری ]               │
├ Explainer (one line) ────────────────────┤
│  با هر خرید دوستت، {percent}% پورسانت    │
│  به اعتبار معرفی‌ات اضافه می‌شود         │
├ List ────────────────────────────────────┤
│  دعوت‌شده‌ها (max 10, existing API)      │
└──────────────────────────────────────────┘
```

**Optional collapse:** earnings history in `<details>` if user has earnings (reduces clutter; not required Phase 1).

**Removed from invite tab:**

- Stats grid (total referrals, commission rate cards at top)
- Cabinet `/login?ref=` link
- Program terms 4-card grid
- Withdrawal section entirely

---

## Terminology Map

| Key area | Old (fa) | New (fa) |
|----------|----------|----------|
| `nav.referral` | نمایندگی | کسب درآمد |
| Page title | نمایندگی | کسب درآمد |
| Tab 1 | — | نمایندگی |
| Tab 2 | — | دعوت |
| Partner badge | شریک / فعال | نماینده فعال ✅ |
| Wholesale rate label | تخفیف عمده‌فروشی | درصد تخفیف نمایندگی |
| Referral earnings | کل درآمد | پورسانت معرفی |
| Commission (invite context) | نرخ کمیسیون | پورسانت معرفی |
| Become partner | شریک شوید | درخواست نمایندگی |

English (`en.json`) mirrors structure under `earn.*` namespace; keep `referral.*` keys deprecated but untouched in Phase 1 to avoid breaking admin references — new keys preferred for user tab.

---

## Component Structure (Phase 1)

```
cabinet/src/pages/Referral.tsx          — shell: tabs, queries, disabled state
cabinet/src/components/earn/
  EarnTabs.tsx                          — tab bar UI
  PartnerTab.tsx                        — partner journey
  InviteTab.tsx                         — invite journey
```

Shared data fetching stays in `Referral.tsx` (React Query); pass props to tab components.

Tab state: `useState<'partner' | 'invite'>('partner')`.

Pattern: match `AdminPromoOffers.tsx` tab buttons (`bg-dark-700` active chip).

---

## Edge Cases

| Case | Behavior |
|------|----------|
| `terms.is_enabled === false` | Full-page disabled (unchanged) |
| `partner_section_visible === false` | Partner tab shows only message «بخش نمایندگی غیرفعال است»; invite tab works |
| Not approved partner | Partner tab = apply hero; no withdrawal/campaigns |
| Approved partner, no campaigns | Stats from `referral info` fallback |
| No bot link | Hide copy/share; show empty hint |
| `partner_status === 'pending'` on partner tab | Hide apply CTA; show review card |

---

## Out of Scope (Phase 1)

- New backend endpoints for partner purchase volume / wholesale savings
- Bot Telegram menu redesign (`MENU_REFERRALS`)
- Admin partner panels
- Removing withdrawal API routes
- URL query `?tab=invite` (Phase 2 if needed)
- `CampaignCard` chart expansion redesign (only hide from default partner view if too heavy — keep cards, no chart removal unless UX review says so)

---

## Success Criteria

1. «درخواست نمایندگی» visible without scrolling on mobile (partner tab, non-partner).
2. Regular user can copy bot invite link within 2 taps from opening «کسب درآمد» → «دعوت».
3. Approved partner sees «نماینده فعال» + wholesale % without referral clutter on default tab.
4. Zero withdrawal UI visible to any user.
5. No new Cyrillic or ₽ strings; amounts via `useCurrency` / Toman display rules.
6. Cabinet `npm run build` passes; `import main` unaffected (cabinet-only).

---

## Smoke Checklist (staging `@mrj7_bot`)

- [ ] Nav shows «کسب درآمد»
- [ ] Default tab «نمایندگی» with apply CTA at top (non-partner account)
- [ ] Switch to «دعوت» → bot link + پورسانت معرفی amount
- [ ] Approved partner account → status card + discount % + stats
- [ ] Pending application → review state on partner tab
- [ ] No withdrawal section anywhere
