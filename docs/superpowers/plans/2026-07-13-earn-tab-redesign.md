# Earn Tab Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the cabinet `/referral` page into a two-tab «کسب درآمد» experience that prioritizes partnership acquisition and simplifies invite/referral credit for regular users, hiding withdrawal UI.

**Architecture:** Split `Referral.tsx` into a tab shell plus `PartnerTab` and `InviteTab` components under `cabinet/src/components/earn/`. Reuse existing React Query fetches; no backend changes. New `earn.*` i18n keys in `fa.json` / `en.json`; update nav label in AppShell components.

**Tech Stack:** React 18, TanStack Query, react-i18next, Tailwind (`bento-card`, `btn-primary`), existing `useCurrency` hook.

**Spec:** `docs/superpowers/specs/2026-07-13-earn-tab-redesign-design.md`

---

## File Map

| File | Responsibility |
|------|----------------|
| `cabinet/src/pages/Referral.tsx` | Page shell: queries, disabled state, tab state, pass props |
| `cabinet/src/components/earn/EarnTabs.tsx` | Tab bar («نمایندگی» \| «دعوت») |
| `cabinet/src/components/earn/PartnerTab.tsx` | Partner hero / status / stats / campaigns |
| `cabinet/src/components/earn/InviteTab.tsx` | Referral credit, bot link, explainer, list |
| `cabinet/src/utils/earnStats.ts` | Pure `aggregatePartnerStats()` helper |
| `cabinet/src/utils/earnStats.test.ts` | Vitest for aggregator |
| `cabinet/src/locales/fa.json` | New `earn.*` + `nav.earn` keys |
| `cabinet/src/locales/en.json` | English parity |
| `cabinet/src/components/layout/AppShell/AppShell.tsx` | Nav label `nav.earn` |
| `cabinet/src/components/layout/AppShell/AppHeader.tsx` | Same |
| `cabinet/src/components/layout/AppShell/MobileBottomNav.tsx` | Same |
| `cabinet/src/components/dashboard/StatsGrid.tsx` | Dashboard link label if it references referral nav key |

---

### Task 1: Branch + i18n keys

**Files:**
- Modify: `cabinet/src/locales/fa.json`
- Modify: `cabinet/src/locales/en.json`

- [ ] **Step 1: Create branch**

```bash
git checkout main && git pull remnabot main
git checkout -b feat/earn-tab-redesign
```

- [ ] **Step 2: Add `nav.earn` and `earn.*` keys to fa.json**

Add alongside existing `nav` block:

```json
"earn": "کسب درآمد"
```

Add new top-level `earn` object (do not delete `referral` keys yet):

```json
"earn": {
  "title": "کسب درآمد",
  "tabs": {
    "partner": "نمایندگی",
    "invite": "دعوت"
  },
  "invite": {
    "referralCredit": "پورسانت معرفی",
    "referralCreditHint": "قابل استفاده در خرید بعدی",
    "botLink": "لینک دعوت ربات",
    "copyLink": "کپی",
    "copied": "کپی شد!",
    "shareButton": "اشتراک‌گذاری",
    "explainer": "با هر خرید دوستت، {{percent}}٪ پورسانت به اعتبار معرفی‌ات اضافه می‌شود.",
    "shareMessage": "از طریق لینک من به {{botName}} بپیوند!",
    "yourInvitees": "دعوت‌شده‌ها",
    "noInvitees": "هنوز کسی را دعوت نکرده‌اید. لینک را برای دوستان بفرستید!",
    "anonymousUser": "کاربر #{{id}}",
    "status": {
      "paid": "پرداخت شده",
      "pending": "در انتظار"
    }
  },
  "partner": {
    "heroTitle": "درخواست نمایندگی",
    "heroDesc": "با نمایندگی، با تخفیف عمده خرید کنید و برای مشتریان خود مدیریت اشتراک داشته باشید.",
    "benefitDiscount": "تخفیف خرید عمده",
    "benefitBrand": "برند اختصاصی در پنل",
    "benefitStats": "آمار فروش و مدیریت مشتریان",
    "applyButton": "درخواست نمایندگی",
    "activeStatus": "نماینده فعال",
    "discountLabel": "درصد تخفیف نمایندگی",
    "brandLabel": "برند",
    "statsTitle": "آمار شما",
    "statRegistrations": "ثبت‌نام",
    "statReferrals": "دعوت موفق",
    "statEarnings": "درآمد از معرفی",
    "goToInvite": "دعوت دوستان",
    "sectionDisabled": "بخش نمایندگی در حال حاضر غیرفعال است.",
    "underReview": "درخواست در حال بررسی",
    "underReviewDesc": "درخواست نمایندگی شما بررسی می‌شود. پس از تصمیم به شما اطلاع می‌دهیم.",
    "submittedAt": "ارسال شده در {{date}}",
    "rejected": "درخواست رد شد",
    "reapplyButton": "درخواست مجدد",
    "yourCampaigns": "کمپین‌های شما"
  }
}
```

Reuse existing `referral.partner.*` keys for apply form page (`ReferralPartnerApply.tsx`) — no change needed there in Phase 1.

- [ ] **Step 3: Mirror structure in en.json**

```json
"earn": "Earn",
"earn": {
  "title": "Earn",
  "tabs": { "partner": "Partnership", "invite": "Invite" },
  ...
}
```

- [ ] **Step 4: Commit**

```bash
git add cabinet/src/locales/fa.json cabinet/src/locales/en.json
git commit -m "i18n(cabinet): add earn tab keys for referral page redesign"
```

---

### Task 2: Stats aggregator utility + test

**Files:**
- Create: `cabinet/src/utils/earnStats.ts`
- Create: `cabinet/src/utils/earnStats.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// cabinet/src/utils/earnStats.test.ts
import { describe, it, expect } from 'vitest';
import { aggregatePartnerStats } from './earnStats';

describe('aggregatePartnerStats', () => {
  it('sums campaign counters', () => {
    const result = aggregatePartnerStats(
      [
        { registrations_count: 10, referrals_count: 3, earnings_kopeks: 50000 },
        { registrations_count: 5, referrals_count: 2, earnings_kopeks: 25000 },
      ],
      { total_referrals: 99, total_earnings_rubles: 999 },
    );
    expect(result).toEqual({
      registrations: 15,
      referrals: 5,
      earningsKopeks: 75000,
      usedFallback: false,
    });
  });

  it('falls back to referral info when no campaigns', () => {
    const result = aggregatePartnerStats([], {
      total_referrals: 4,
      total_earnings_rubles: 12000,
    });
    expect(result).toEqual({
      registrations: 0,
      referrals: 4,
      earningsKopeks: 1200000,
      usedFallback: true,
    });
  });
});
```

Note: fallback converts `total_earnings_rubles` to kopeks via `* 100` to match storage convention used elsewhere in withdrawal display (`/ 100` in UI).

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd cabinet && npm run test -- src/utils/earnStats.test.ts
```

- [ ] **Step 3: Implement**

```typescript
// cabinet/src/utils/earnStats.ts
export interface CampaignStatsSlice {
  registrations_count: number;
  referrals_count: number;
  earnings_kopeks: number;
}

export interface ReferralInfoFallback {
  total_referrals: number;
  total_earnings_rubles: number;
}

export function aggregatePartnerStats(
  campaigns: CampaignStatsSlice[],
  fallback: ReferralInfoFallback,
) {
  if (campaigns.length === 0) {
    return {
      registrations: 0,
      referrals: fallback.total_referrals,
      earningsKopeks: Math.round(fallback.total_earnings_rubles * 100),
      usedFallback: true,
    };
  }
  return {
    registrations: campaigns.reduce((s, c) => s + (c.registrations_count || 0), 0),
    referrals: campaigns.reduce((s, c) => s + (c.referrals_count || 0), 0),
    earningsKopeks: campaigns.reduce((s, c) => s + (c.earnings_kopeks || 0), 0),
    usedFallback: false,
  };
}
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd cabinet && npm run test -- src/utils/earnStats.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add cabinet/src/utils/earnStats.ts cabinet/src/utils/earnStats.test.ts
git commit -m "feat(cabinet): add partner stats aggregator for earn tab"
```

---

### Task 3: EarnTabs component

**Files:**
- Create: `cabinet/src/components/earn/EarnTabs.tsx`

- [ ] **Step 1: Create tab bar**

```tsx
// cabinet/src/components/earn/EarnTabs.tsx
import { useTranslation } from 'react-i18next';

export type EarnTabId = 'partner' | 'invite';

interface EarnTabsProps {
  active: EarnTabId;
  onChange: (tab: EarnTabId) => void;
}

export function EarnTabs({ active, onChange }: EarnTabsProps) {
  const { t } = useTranslation();
  const tabs: { id: EarnTabId; label: string }[] = [
    { id: 'partner', label: t('earn.tabs.partner') },
    { id: 'invite', label: t('earn.tabs.invite') },
  ];

  return (
    <div className="flex gap-2 rounded-xl bg-dark-800/50 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`flex-1 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
            active === tab.id
              ? 'bg-dark-700 text-dark-100'
              : 'text-dark-400 hover:text-dark-200'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add cabinet/src/components/earn/EarnTabs.tsx
git commit -m "feat(cabinet): add EarnTabs component"
```

---

### Task 4: InviteTab component

**Files:**
- Create: `cabinet/src/components/earn/InviteTab.tsx`

- [ ] **Step 1: Build InviteTab** — extract bot link copy/share from current `Referral.tsx` lines 268–337 and referral list 343–377; use `earn.invite.*` keys; show `available_balance_rubles` with `formatWithCurrency`; explainer uses `terms.commission_percent`.

Props interface:

```typescript
interface InviteTabProps {
  botReferralLink: string;
  referralCreditRubles: number;
  commissionPercent: number;
  brandingName: string;
  referralList: ReferralListResponse | undefined;
  onCopy: (link: string) => void;
  copied: boolean;
}
```

No cabinet link field. No earnings history in Phase 1 default view.

- [ ] **Step 2: Build cabinet**

```bash
cd cabinet && npm run build
```

Expected: PASS (component may be unused until Task 6 — export anyway).

- [ ] **Step 3: Commit**

```bash
git add cabinet/src/components/earn/InviteTab.tsx
git commit -m "feat(cabinet): add InviteTab for earn page"
```

---

### Task 5: PartnerTab component

**Files:**
- Create: `cabinet/src/components/earn/PartnerTab.tsx`

- [ ] **Step 1: Build PartnerTab** with sections per spec:

Props:

```typescript
interface PartnerTabProps {
  partnerSectionVisible: boolean;
  partnerStatus: PartnerStatusResponse | undefined;
  aggregatedStats: ReturnType<typeof aggregatePartnerStats>;
  wholesalePercent: number;
  onApply: () => void;
  onGoToInvite: () => void;
  formatEarnings: (kopeks: number) => string;
}
```

Render logic:
- `!partnerSectionVisible` → disabled message
- `none` → hero + 3 benefits + CTA
- `pending` / `rejected` → existing card patterns from Referral.tsx
- `approved` → status card (✅ emoji in markup) + discount + stats grid + button `onGoToInvite` + `CampaignCard` list when campaigns exist

**Do not import or render withdrawal section.**

- [ ] **Step 2: Commit**

```bash
git add cabinet/src/components/earn/PartnerTab.tsx
git commit -m "feat(cabinet): add PartnerTab for earn page"
```

---

### Task 6: Refactor Referral.tsx shell

**Files:**
- Modify: `cabinet/src/pages/Referral.tsx`

- [ ] **Step 1: Replace monolithic JSX** with:

```tsx
const [activeTab, setActiveTab] = useState<EarnTabId>('partner');
// ... existing queries unchanged except remove withdrawal queries entirely

const aggregatedStats = useMemo(
  () =>
    aggregatePartnerStats(
      partnerStatus?.campaigns ?? [],
      {
        total_referrals: info?.total_referrals ?? 0,
        total_earnings_rubles: info?.total_earnings_rubles ?? 0,
      },
    ),
  [partnerStatus?.campaigns, info],
);

return (
  <div className="space-y-6">
    <h1>{t('earn.title')}</h1>
    <EarnTabs active={activeTab} onChange={setActiveTab} />
    {activeTab === 'partner' ? (
      <PartnerTab ... onGoToInvite={() => setActiveTab('invite')} />
    ) : (
      <InviteTab ... />
    )}
  </div>
);
```

Remove:
- Stats grid at top
- Withdrawal queries (`withdrawalBalance`, `withdrawalHistory`) and mutations
- All withdrawal JSX (lines 548–681)
- Inline program terms, links, lists (moved to tabs)

Keep disabled-state early return using `earn.title`.

- [ ] **Step 2: Build**

```bash
cd cabinet && npm run build
```

- [ ] **Step 3: Agent smoke**

```bash
make smoke
```

- [ ] **Step 4: Commit**

```bash
git add cabinet/src/pages/Referral.tsx
git commit -m "feat(cabinet): redesign referral page as earn tabs"
```

---

### Task 7: Nav label updates

**Files:**
- Modify: `cabinet/src/components/layout/AppShell/AppShell.tsx`
- Modify: `cabinet/src/components/layout/AppShell/AppHeader.tsx`
- Modify: `cabinet/src/components/layout/AppShell/MobileBottomNav.tsx`
- Modify: `cabinet/src/components/dashboard/StatsGrid.tsx` (if uses `nav.referral`)

- [ ] **Step 1: Replace `t('nav.referral')` with `t('nav.earn')`**

Keep route path `/referral` unchanged.

- [ ] **Step 2: Build + commit**

```bash
cd cabinet && npm run build
git add cabinet/src/components/layout/AppShell/*.tsx cabinet/src/components/dashboard/StatsGrid.tsx
git commit -m "i18n(cabinet): rename nav referral label to earn"
```

---

### Task 8: Staging deploy + smoke map

**Files:**
- Modify: `docs/templates/smoke-map.md`

- [ ] **Step 1: Deploy staging**

```bash
make smoke && make deploy-scope && make staging-rebuild
make staging-health
```

- [ ] **Step 2: Fill smoke map** with earn tab checklist from spec.

- [ ] **Step 3: Commit smoke map**

```bash
git add docs/templates/smoke-map.md
git commit -m "docs: add earn tab redesign smoke map"
```

---

## Plan Self-Review

| Spec requirement | Task |
|------------------|------|
| Two tabs, partner default | Task 3, 6 |
| Nav «کسب درآمد» | Task 1, 7 |
| Apply CTA at top | Task 5 |
| Hide withdrawal | Task 6 |
| Referral credit not wallet | Task 4 (`available_balance_rubles`) |
| Bot link only | Task 4 |
| Partner stats + go to invite | Task 5 |
| Terminology | Task 1 |
| No backend changes | — |
| Smoke criteria | Task 8 |

No placeholders remain. Types consistent across tasks.

---

## Execution Handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks
2. **Inline Execution** — implement tasks in this session with checkpoints

Which approach?
