# fa Jalali Dates — User Surfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show subscription and other user-facing dates in the **Persian (Jalali/Shamsi) calendar** when `language=fa`, while keeping Gregorian dates for `ru`, `en`, and `zh`.

**Architecture:** Add one shared formatter on each surface — Python `format_user_datetime()` (wraps existing `format_local_datetime` + `jdatetime` for `fa`) and cabinet `formatUserDate()` (wraps `Intl.DateTimeFormat` with `calendar: 'persian'`). Call sites pass `language` from `texts.language` / `user.language` / `i18n.language`. No bulk regex migration; migrate P1 user paths file-by-file per `localization-upstream.mdc`. Day counts like `(29 روز)` stay unchanged — they are calendar-agnostic.

**Tech Stack:** Python 3, `jdatetime`, aiogram handlers, FastAPI cabinet + miniapp routes, React cabinet (`Intl`), pytest, Docker smoke (`import main`).

**Related context:** Prior audit (2026-06-09) confirmed no internal Jalali library exists; dates like `📅 تا 09.07.2026 (29 روز)` come from `SUB_STATUS_ACTIVE_LONG` in `fa.json` with `{end_date}` filled via Gregorian `format_local_datetime(..., '%d.%m.%Y')` in `menu.py` / `start.py`.

---

## Scope

### In scope (P1 user surfaces)

| Surface | Examples |
|---------|----------|
| Bot — subscription status | `menu.py`, `start.py` → `📅 تا {end_date} ({days} روز)` |
| Bot — my subscriptions | `my_subscriptions.py` |
| Bot — purchase / simple sub | `purchase.py`, `simple_subscription.py` (user-visible expiry/created lines) |
| Cabinet API | `app/cabinet/routes/subscription_modules/purchase.py` |
| Miniapp API | `app/webapi/routes/miniapp.py` (user-facing date labels) |
| Cabinet UI — user pages | `Subscription.tsx`, `SubscriptionListCard.tsx`, `SubscriptionCardActive.tsx`, `Balance.tsx`, `Profile.tsx`, `Support.tsx`, `Referral.tsx`, `GiftSubscription.tsx`, `MergeAccounts.tsx`, `Wheel.tsx`, `SuccessNotificationModal.tsx` |

### Out of scope (separate plans / tracks)

| Area | Reason |
|------|--------|
| `app/handlers/admin/**` | P2 admin track |
| Cabinet admin pages (`Admin*.tsx`) | P2 |
| `app/services/admin_notification_service.py` | Admin group notifications — dates optional follow-up |
| `app/handlers/balance/**`, payment providers | `localization-upstream.mdc` |
| Email templates | Separate email i18n plan |
| `DateField.tsx` / admin date pickers | Input widgets stay Gregorian unless explicitly requested |
| Persian digit shaping (۱۸ vs 18) | Phase 2 polish; Phase 1 uses numeric Jalali with Western digits (`18.04.1405`) for parity with current `09.07.2026` style |

---

## File map

| File | Responsibility |
|------|----------------|
| `app/utils/jalali_datetime.py` | **Create.** `is_jalali_language()`, `format_user_datetime()` |
| `tests/utils/test_jalali_datetime.py` | **Create.** Unit tests for conversion + language gating |
| `app/utils/timezone.py` | **Unchanged** — `format_local_datetime` remains the Gregorian base |
| `cabinet/src/utils/formatDate.ts` | **Create.** `formatUserDate()`, `formatUserDateTime()` |
| Bot handlers (listed in tasks) | Replace direct `strftime` / `format_local_datetime` with `format_user_datetime(..., language=...)` |
| Cabinet routes + miniapp | Same helper on API-serialized date strings for `fa` users |
| Cabinet user components | Replace raw `toLocaleDateString()` with `formatUserDate()` |

---

## Format contract

| Language | Example input (UTC) | Output shape |
|----------|---------------------|--------------|
| `ru`, `en`, `zh` | `2026-07-09T00:00:00+00:00` | `09.07.2026` (existing `%d.%m.%Y` after local TZ) |
| `fa` | same | `18.04.1405` (Jalali `%d.%m.%Y` after local TZ) |
| `fa` with time | same + `%d.%m.%Y %H:%M` | `18.04.1405 03:30` (time stays clock time in local TZ) |

**Anchor test case:** Gregorian `2026-07-09` (any time) → Jalali `1405/04/18` → formatted `18.04.1405`.

---

## Prerequisites

- [ ] **Step 1:** Create branch from `main`

```bash
git checkout main
git checkout -b i18n/fa-jalali-dates
```

- [ ] **Step 2:** Baseline smoke

```bash
docker compose run --rm --no-deps bot python -c "import main"
cd cabinet && npm run type-check
```

Expected: both succeed before any changes.

### Rules (do not violate)

| Rule | Constraint |
|------|------------|
| `user-surface-parity.mdc` | Subscription/expiry dates: bot + cabinet API + cabinet UI + miniapp in the **same slice** |
| `localization-upstream.mdc` | One handler/route file per commit (helper+tests = separate commit) |
| `delivery-cycle.mdc` | `import main` after every Python commit |
| `currency-display-toman.mdc` | Do not touch FX/pricing in this branch |

---

### Task 1: Python Jalali helper + tests

**Files:**
- Create: `app/utils/jalali_datetime.py`
- Create: `tests/utils/test_jalali_datetime.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Write the failing test**

Create `tests/utils/test_jalali_datetime.py`:

```python
"""Tests for fa Jalali date formatting."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _utc_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'TIMEZONE', 'UTC', raising=False)
    from app.utils.timezone import get_local_timezone

    get_local_timezone.cache_clear()


def test_fa_formats_jalali_date() -> None:
    from app.utils.jalali_datetime import format_user_datetime

    dt = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    assert format_user_datetime(dt, language='fa', fmt='%d.%m.%Y') == '18.04.1405'


def test_ru_keeps_gregorian_date() -> None:
    from app.utils.jalali_datetime import format_user_datetime

    dt = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    assert format_user_datetime(dt, language='ru', fmt='%d.%m.%Y') == '09.07.2026'


def test_none_returns_placeholder() -> None:
    from app.utils.jalali_datetime import format_user_datetime

    assert format_user_datetime(None, language='fa') == 'N/A'
    assert format_user_datetime(None, language='fa', na_placeholder='—') == '—'


def test_is_jalali_language() -> None:
    from app.utils.jalali_datetime import is_jalali_language

    assert is_jalali_language('fa') is True
    assert is_jalali_language('fa-IR') is True
    assert is_jalali_language('ru') is False
    assert is_jalali_language('en') is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/utils/test_jalali_datetime.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.utils.jalali_datetime'` or `jdatetime` not installed.

- [ ] **Step 3: Add dependency**

In `requirements.txt` under `# Утилиты`:

```
jdatetime==5.2.0
```

Install in dev container if needed:

```bash
docker compose run --rm --no-deps bot pip install jdatetime==5.2.0
```

- [ ] **Step 4: Write minimal implementation**

Create `app/utils/jalali_datetime.py`:

```python
"""Language-aware datetime formatting with Jalali calendar for fa users."""

from __future__ import annotations

from datetime import datetime

import jdatetime

from app.utils.timezone import format_local_datetime, to_local_datetime


def is_jalali_language(language: str | None) -> bool:
    code = (language or '').split('-')[0].lower()
    return code == 'fa'


def format_user_datetime(
    dt: datetime | None,
    *,
    language: str = 'ru',
    fmt: str = '%d.%m.%Y',
    na_placeholder: str = 'N/A',
) -> str:
    """Format datetime for end users.

    fa → Jalali calendar (Shamsi), localized to settings.TIMEZONE.
    Other languages → existing Gregorian format_local_datetime().
    """
    if dt is None:
        return na_placeholder

    if not is_jalali_language(language):
        return format_local_datetime(dt, fmt=fmt, na_placeholder=na_placeholder)

    localized = to_local_datetime(dt)
    if localized is None:
        return na_placeholder

    naive_local = localized.replace(tzinfo=None)
    jalali_dt = jdatetime.datetime.fromgregorian(datetime=naive_local)
    return jalali_dt.strftime(fmt)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/utils/test_jalali_datetime.py -v
docker compose run --rm --no-deps bot python -c "import main"
```

Expected: all tests PASS; `import main` OK.

- [ ] **Step 6: Commit**

```bash
git add app/utils/jalali_datetime.py tests/utils/test_jalali_datetime.py requirements.txt
git commit -m "feat(dates): add format_user_datetime helper for fa Jalali calendar"
```

---

### Task 2: Bot subscription status — `menu.py`

**Files:**
- Modify: `app/handlers/menu.py` (~1087, ~1209)

- [ ] **Step 1: Import helper**

```python
from app.utils.jalali_datetime import format_user_datetime
```

- [ ] **Step 2: Replace status date formatting**

In `_get_subscription_status`, change:

```python
end_date_text = format_local_datetime(end_date, '%d.%m.%Y') if end_date else None
```

to:

```python
end_date_text = (
    format_user_datetime(end_date, language=texts.language, fmt='%d.%m.%Y')
    if end_date
    else None
)
```

Find the other `format_local_datetime(sub.end_date, '%d.%m.%Y')` in the same file (~1209) and apply the same pattern with `language=texts.language`.

- [ ] **Step 3: Smoke**

```bash
docker compose run --rm --no-deps bot python -c "import main"
```

Expected: OK.

- [ ] **Step 4: Manual check (user smoke later)**

Telegram bot, fa user, main menu subscription line should show:
`📅 تا 18.04.1405 (N روز)` instead of `📅 تا 09.07.2026 (N روز)`.

- [ ] **Step 5: Commit**

```bash
git add app/handlers/menu.py
git commit -m "feat(dates): show Jalali expiry in menu subscription status for fa"
```

---

### Task 3: Bot subscription status — `start.py`

**Files:**
- Modify: `app/handlers/start.py` (~2406)

- [ ] **Step 1: Import and replace**

Same pattern as Task 2. In the subscription status helper:

```python
from app.utils.jalali_datetime import format_user_datetime

end_date_display = (
    format_user_datetime(end_date, language=texts.language, fmt='%d.%m.%Y')
    if end_date
    else None
)
```

- [ ] **Step 2: Smoke + commit**

```bash
docker compose run --rm --no-deps bot python -c "import main"
git add app/handlers/start.py
git commit -m "feat(dates): show Jalali expiry in start subscription status for fa"
```

---

### Task 4: Bot — `my_subscriptions.py`

**Files:**
- Modify: `app/handlers/subscription/my_subscriptions.py` (~96, ~327)

- [ ] **Step 1: Replace strftime calls**

```python
from app.utils.jalali_datetime import format_user_datetime

end_date = (
    format_user_datetime(sub.end_date, language=texts.language, fmt='%d.%m.%Y')
    if sub.end_date
    else '—'
)
```

And for detail view with time:

```python
end_date = (
    format_user_datetime(subscription.end_date, language=texts.language, fmt='%d.%m.%Y %H:%M')
    if subscription.end_date
    else '—'
)
```

- [ ] **Step 2: Smoke + commit**

```bash
docker compose run --rm --no-deps bot python -c "import main"
git add app/handlers/subscription/my_subscriptions.py
git commit -m "feat(dates): Jalali dates in my_subscriptions for fa users"
```

---

### Task 5: Cabinet frontend helper

**Files:**
- Create: `cabinet/src/utils/formatDate.ts`

- [ ] **Step 1: Create helper**

```typescript
const LOCALE_MAP: Record<string, string> = {
  ru: 'ru-RU',
  en: 'en-US',
  zh: 'zh-CN',
  fa: 'fa-IR',
};

function resolveLocale(lang?: string): string | undefined {
  if (!lang) return undefined;
  const code = lang.split('-')[0].toLowerCase();
  return LOCALE_MAP[code] ?? lang;
}

function isJalaliLanguage(lang?: string): boolean {
  return (lang ?? '').split('-')[0].toLowerCase() === 'fa';
}

export function formatUserDate(
  iso: string | null | undefined,
  lang?: string,
  options: Intl.DateTimeFormatOptions = {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  },
): string {
  if (!iso) return '—';
  try {
    const normalized = iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`;
    const date = new Date(normalized);
    if (Number.isNaN(date.getTime())) return '—';

    const locale = resolveLocale(lang);
    const jalali = isJalaliLanguage(lang);

    return date.toLocaleDateString(locale, jalali ? { ...options, calendar: 'persian' } : options);
  } catch {
    return '—';
  }
}

export function formatUserDateTime(
  iso: string | null | undefined,
  lang?: string,
): string {
  return formatUserDate(iso, lang, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
```

- [ ] **Step 2: Quick Node verification**

```bash
node --input-type=module -e "
const d = new Date('2026-07-09T12:00:00Z');
console.log(d.toLocaleDateString('fa-IR', { calendar: 'persian', day: '2-digit', month: '2-digit', year: 'numeric' }));
"
```

Expected: output contains `1405` and month `4` (not `07`/`2026`).

- [ ] **Step 3: Type-check + commit**

```bash
cd cabinet && npm run type-check
git add cabinet/src/utils/formatDate.ts
git commit -m "feat(dates): add formatUserDate helper with Jalali calendar for fa"
```

---

### Task 6: Cabinet UI — subscription cards (user slice)

**Files:**
- Modify: `cabinet/src/components/subscription/SubscriptionListCard.tsx`
- Modify: `cabinet/src/components/dashboard/SubscriptionCardActive.tsx`
- Modify: `cabinet/src/pages/Subscription.tsx`

- [ ] **Step 1: SubscriptionListCard — replace local formatDate**

Remove the inline `formatDate` function. Import:

```typescript
import { formatUserDate } from '../../utils/formatDate';
```

Use:

```typescript
formatUserDate(iso, i18n.language)
```

- [ ] **Step 2: SubscriptionCardActive**

Replace:

```typescript
const formattedDate = new Date(subscription.end_date).toLocaleDateString();
```

with:

```typescript
import { formatUserDate } from '../../utils/formatDate';
// ...
const formattedDate = formatUserDate(subscription.end_date, i18n.language);
```

(Add `const { i18n } = useTranslation();` if missing.)

- [ ] **Step 3: Subscription.tsx**

Replace all user-visible `new Date(...).toLocaleDateString(...)` for subscription end / purchase expiry with `formatUserDate(..., i18n.language)`. Keep countdown logic on raw ISO — do not change `days_left` math.

- [ ] **Step 4: Build + commit**

```bash
cd cabinet && npm run type-check && npm run build
git add cabinet/src/components/subscription/SubscriptionListCard.tsx \
        cabinet/src/components/dashboard/SubscriptionCardActive.tsx \
        cabinet/src/pages/Subscription.tsx
git commit -m "feat(dates): Jalali subscription dates in cabinet user pages for fa"
```

---

### Task 7: Cabinet API + miniapp parity

**Files:**
- Modify: `app/cabinet/routes/subscription_modules/purchase.py` (~497, ~1117)
- Modify: `app/webapi/routes/miniapp.py` (grep `format_local_datetime` / `strftime('%d.%m.%Y`)

- [ ] **Step 1: Cabinet purchase routes**

Replace:

```python
end_date_str = subscription.end_date.strftime('%d.%m.%Y') if subscription.end_date else ''
```

with:

```python
from app.utils.jalali_datetime import format_user_datetime

end_date_str = (
    format_user_datetime(subscription.end_date, language=user.language, fmt='%d.%m.%Y')
    if subscription.end_date
    else ''
)
```

Ensure `user` (authenticated cabinet user with `.language`) is in scope at both call sites.

- [ ] **Step 2: Miniapp — migrate user-facing date labels**

For each `format_local_datetime(..., '%d.%m.%Y')` that reaches the miniapp client for subscription/purchase UI, pass `language=user.language` (or equivalent from request context):

```python
date_label = format_user_datetime(
    subscription.end_date,
    language=user.language,
    fmt='%d.%m.%Y %H:%M',
) if subscription.end_date else ''
```

- [ ] **Step 3: Smoke + commit**

```bash
docker compose run --rm --no-deps bot python -c "import main"
git add app/cabinet/routes/subscription_modules/purchase.py app/webapi/routes/miniapp.py
git commit -m "feat(dates): Jalali dates in cabinet purchase API and miniapp for fa"
```

---

### Task 8: Bot purchase flows (follow-up commits, one file each)

**Files:**
- Modify: `app/handlers/subscription/purchase.py`
- Modify: `app/handlers/simple_subscription.py`

- [ ] **Step 1: `purchase.py`**

Import `format_user_datetime`. Replace user-visible:

```python
format_local_datetime(subscription.end_date, '%d.%m.%Y %H:%M')
purchase.expires_at.strftime('%d.%m.%Y')
```

with `format_user_datetime(..., language=texts.language, fmt=...)`.

Skip admin-only log lines.

```bash
docker compose run --rm --no-deps bot python -c "import main"
git add app/handlers/subscription/purchase.py
git commit -m "feat(dates): Jalali dates in purchase handler for fa users"
```

- [ ] **Step 2: `simple_subscription.py`**

Replace payment status `created=payment.created_at.strftime('%d.%m.%Y %H:%M')` blocks (5 occurrences) with `format_user_datetime(..., language=texts.language, fmt='%d.%m.%Y %H:%M')`.

```bash
docker compose run --rm --no-deps bot python -c "import main"
git add app/handlers/simple_subscription.py
git commit -m "feat(dates): Jalali dates in simple_subscription for fa users"
```

---

### Task 9: Cabinet UI — remaining user pages (one commit)

**Files:**
- Modify: `cabinet/src/pages/Balance.tsx`
- Modify: `cabinet/src/pages/Profile.tsx`
- Modify: `cabinet/src/pages/Support.tsx`
- Modify: `cabinet/src/pages/Referral.tsx`
- Modify: `cabinet/src/pages/GiftSubscription.tsx`
- Modify: `cabinet/src/pages/MergeAccounts.tsx`
- Modify: `cabinet/src/pages/Wheel.tsx`
- Modify: `cabinet/src/components/SuccessNotificationModal.tsx`

- [ ] **Step 1: Replace raw toLocaleDateString**

In each file, import `formatUserDate` and replace user-visible date displays. Pass `i18n.language`. Do **not** touch `Admin*.tsx` files.

- [ ] **Step 2: Build + commit**

```bash
cd cabinet && npm run type-check && npm run build
git add cabinet/src/pages/Balance.tsx cabinet/src/pages/Profile.tsx \
        cabinet/src/pages/Support.tsx cabinet/src/pages/Referral.tsx \
        cabinet/src/pages/GiftSubscription.tsx cabinet/src/pages/MergeAccounts.tsx \
        cabinet/src/pages/Wheel.tsx cabinet/src/components/SuccessNotificationModal.tsx
git commit -m "feat(dates): Jalali dates across remaining cabinet user pages for fa"
```

---

### Task 10: Update status doc + user smoke checklist

**Files:**
- Modify: `.cursor/rules/fa-i18n-status.mdc`

- [ ] **Step 1: Add Done entry**

Under **Done**, add:

```markdown
- [x] **fa Jalali dates (P1):** `format_user_datetime` + cabinet `formatUserDate`; subscription status menu/start, my_subscriptions, purchase API, miniapp, cabinet subscription UI
```

- [ ] **Step 2: User smoke checklist**

| # | Surface | Action | Expected (fa) |
|---|---------|--------|---------------|
| 1 | Bot main menu | Open menu with active sub | `📅 تا 18.04.1405 (N روز)` not `09.07.2026` |
| 2 | Bot /start status | Same subscription | Jalali date |
| 3 | Bot My Subscriptions | List + detail | Jalali end date |
| 4 | Cabinet Subscription | Active sub card | Jalali end date |
| 5 | Miniapp | Subscription expiry label | Jalali (if rendered from API string) |
| 6 | ru user regression | Switch language ru | Still `09.07.2026` Gregorian |

- [ ] **Step 3: Commit**

```bash
git add .cursor/rules/fa-i18n-status.mdc
git commit -m "docs(i18n): record fa Jalali dates P1 completion"
```

---

## Self-review checklist

| Requirement | Task |
|-------------|------|
| No internal Jalali lib today → add shared helper | Task 1 |
| `📅 تا 09.07.2026 (29 روز)` → Shamsi date | Tasks 2–3 |
| `(29 روز)` unchanged | Architecture note (no task needed) |
| Bot + cabinet + miniapp parity | Tasks 2–7 |
| One file per commit (handlers) | Tasks 2–4, 8 |
| No admin scope creep | Out of scope table |
| Tests with real assertions | Task 1 |
| No TBD / placeholder steps | Verified |

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-09-fa-jalali-dates.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
