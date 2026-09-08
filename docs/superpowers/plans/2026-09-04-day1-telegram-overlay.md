# Day-1 overlay Implementation Plan

> **STATUS (2026-09-04):** **COMPLETE / PASS** — Part A Tasks 1–10 and Part B Tasks 1–6 done. Operator smoke `تایید` recorded in `docs/superpowers/evidence/smoke-2026-09-04-day1-overlay.md`. Bot HEAD `e716cb83` (+ docs `2a5e867d`); cabinet `0173edae`. **Out of this plan:** M7-T1 / DNS / Layer C — see cutover MVP named-start.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. This plan is **closed** (all steps `[x]`); do not re-open Tasks 1–10 / Part B 1–6 unless a regression is named.

**Goal:** Day-1 Iran product before DNS: overlay production chrome on remnabot1 4.2 Telegram (Part A) and on cabinet 1.67 (Part B), without restoring the 3.60 start grid, copying donor handlers, or rewriting upstream Referral.

**Architecture:** One plan, two trees. Part A is a surgical overlay on `/opt/remnabot1` `prod-cutover` (list helper, partner confirm, pause). Part B is the cabinet Layer A overlay on `/opt/cabinet` (fa first paint, Jalali, wording, RTL isolate, subscription sheets). Tracks are parallel. Task 10 (Part A smoke) waits for Part B Task 6.

**Tech Stack:** Part A — Python 3.13, aiogram 3, SQLAlchemy, Alembic (map only — no autogenerate), pytest via `uv run pytest`, `jdatetime`. Part B — Vite, React, TypeScript, i18next, vitest, Biome.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-04-day1-remaining-overlay-design.md` (operator تایید 2026-09-04).
- Part A (Tasks 1–10): `/opt/remnabot1` only. Part B (Tasks 1–6 under Part B heading): `/opt/cabinet` only. Do not edit `/opt/remnabot`.
- Keep the 4.2 rich `/start` shell (Connect / Subscription / Balance). Do not restore the 3.60 keyboard grid.
- Do not copy `/opt/remnabot/app/handlers/subscription/my_subscriptions.py` over the 4.2 file.
- 4.2 gift row on My Subscriptions **stays**.
- Do not start M7-T1, touch DNS, production token, or Layer C (`/sales`, Earn, `PartnerCheckoutFields`).
- Do not `alembic revision --autogenerate`. Columns already exist via grafted `0095` and `0103`.
- Do not unwind C2C / Toman / FA / `PricingEngine` into plugins.
- English digits in new fa strings (0-9). Missing fa keys keep `fa → en → ru`.
- One concern per commit on `prod-cutover`. Do not force-push.
- After each code task: `uv run pytest` on the task's test file(s). `import main` smoke is not required unless the task touches `main.py`.
- Fail-open: unmapped ORM fields hide extra UI; missing `jdatetime` falls back to Gregorian.

**Parallel:** Part A Tasks 1–9 and Part B Tasks 1–5 can run on different trees at the same time. Do not mix trees in one commit.

---

## File map

| File | Responsibility |
|---|---|
| `/opt/remnabot1/pyproject.toml` + `uv.lock` | Add `jdatetime>=5.2.0` so fa Jalali actually converts |
| `/opt/remnabot1/app/database/models.py` | Map `users.panel_brand_prefix`, `subscriptions.purchase_note`, `subscriptions.user_disabled` |
| `/opt/remnabot1/app/localization/locales/fa.json` | List / search / pause / partner keys; rich-menu سرویس / تعداد کاربر |
| `/opt/remnabot1/app/utils/subscription_list_display.py` | Identity, list line, search filter (new) |
| `/opt/remnabot1/app/handlers/subscription/my_subscriptions.py` | Call helper; search FSM; pause buttons; drop hardcoded Cyrillic |
| `/opt/remnabot1/app/utils/rich_menu.py` | Jalali fallback text in subscription table |
| `/opt/remnabot1/app/handlers/subscription/purchase.py` | Register search / pause / partner callbacks |
| `/opt/remnabot1/app/states.py` | `searching_my_subscriptions`, `waiting_for_purchase_note` |
| `/opt/remnabot1/app/utils/remnawave_panel_identity.py` | Brand prefix validate + note sanitize (new) |
| `/opt/remnabot1/app/utils/partner_checkout_telegram.py` | Partner confirm extras, fail-open (new) |
| `/opt/remnabot1/app/handlers/subscription/tariff_purchase.py` | Thin hook: extra confirm buttons + persist note/prefix |
| `/opt/remnabot1/app/services/subscription_user_toggle_service.py` | Pause/resume using `remnawave_id` (new) |
| `/opt/remnabot1/tests/utils/test_subscription_list_display.py` | Formatter / identity / search |
| `/opt/remnabot1/tests/handlers/test_my_subscriptions_pagination.py` | Update callsites; search button; no Cyrillic |
| `/opt/remnabot1/tests/database/test_day1_orm_columns.py` | ORM attributes exist |
| `/opt/remnabot1/tests/utils/test_partner_checkout_telegram.py` | Fail-open + persist helpers |
| `/opt/remnabot1/tests/services/test_subscription_user_toggle.py` | Pause rules without panel |
| `/opt/remnabot1/tests/utils/test_rich_menu.py` | Jalali fallback string in table |

---

### Task 1: Install jdatetime

**Files:**
- Modify: `/opt/remnabot1/pyproject.toml`
- Modify: `/opt/remnabot1/uv.lock` (via `uv add`)
- Test: `/opt/remnabot1/tests/utils/test_jalali_datetime.py` (create)

**Interfaces:**
- Consumes: existing `app/utils/jalali_datetime.py::format_user_datetime`
- Produces: runtime `jdatetime` so `language='fa'` converts instead of Gregorian fallback

- [x] **Step 1: Write the failing test**

Create `/opt/remnabot1/tests/utils/test_jalali_datetime.py`:

```python
from datetime import UTC, datetime

from app.utils.jalali_datetime import format_user_datetime, is_jalali_language


def test_fa_is_jalali_language() -> None:
    assert is_jalali_language('fa') is True
    assert is_jalali_language('ru') is False


def test_fa_converts_known_gregorian_anchor() -> None:
    # 2026-07-09 → 18.04.1405 (same anchor as production jalali tests)
    dt = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    assert format_user_datetime(dt, language='fa', fmt='%d.%m.%Y') == '18.04.1405'


def test_ru_stays_gregorian() -> None:
    dt = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    out = format_user_datetime(dt, language='ru', fmt='%d.%m.%Y')
    assert '1405' not in out
    assert '09.07.2026' in out or '07' in out
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_jalali_datetime.py::test_fa_converts_known_gregorian_anchor -v`

Expected: FAIL (`ModuleNotFoundError: jdatetime` inside the helper, which then returns Gregorian — assertion `18.04.1405` fails) **or** FAIL if the helper swallows ImportError and returns a Gregorian string.

- [x] **Step 3: Add the dependency**

```bash
cd /opt/remnabot1 && uv add 'jdatetime>=5.2.0'
```

Do not change `format_user_datetime` unless the test still fails after the package is installed.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_jalali_datetime.py -v`

Expected: PASS (3 tests)

- [x] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests/utils/test_jalali_datetime.py
git commit -m "feat(day1): add jdatetime so fa dates convert to Jalali"
```

---

### Task 2: Map 0095 and 0103 columns on ORM

**Files:**
- Modify: `/opt/remnabot1/app/database/models.py` (User ~2251 after `wholesale_discount_bps`; Subscription after `remnawave_short_id` ~2425)
- Test: `/opt/remnabot1/tests/database/test_day1_orm_columns.py` (create)

**Interfaces:**
- Consumes: grafted tables `users.panel_brand_prefix`, `subscriptions.purchase_note`, `subscriptions.user_disabled` (Alembic `0095` / `0103` already in the remnabot lineage). `User.is_partner` already exists.
- Produces: `User.panel_brand_prefix: str | None`, `Subscription.purchase_note: str | None`, `Subscription.user_disabled: bool`

- [x] **Step 1: Inspect DB (no migration)**

If a rehearsal/RC postgres for the grafted graph is running, confirm columns exist. Do **not** autogenerate. Example (adjust container name if different):

```bash
docker ps --format '{{.Names}}' | rg -i 'rehearsal|remnabot1.*postgres' || true
```

If you can exec into the grafted bot DB:

```sql
SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name IN ('panel_brand_prefix', 'purchase_note', 'user_disabled');
```

Expected: three rows. If a column is missing, **stop** with `PLAN REVISION REQUIRED: day-1 ORM column missing` — do not invent a new revision in this task.

- [x] **Step 2: Write the failing test**

Create `/opt/remnabot1/tests/database/test_day1_orm_columns.py`:

```python
from app.database.models import Subscription, User


def test_user_has_panel_brand_prefix() -> None:
    assert hasattr(User, 'panel_brand_prefix')


def test_subscription_has_purchase_note_and_user_disabled() -> None:
    assert hasattr(Subscription, 'purchase_note')
    assert hasattr(Subscription, 'user_disabled')
```

- [x] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/database/test_day1_orm_columns.py -v`

Expected: FAIL (`AttributeError` / assert on `hasattr`)

- [x] **Step 4: Write minimal implementation**

On `User`, immediately after `wholesale_discount_bps = Column(...)`:

```python
    panel_brand_prefix = Column(String(24), nullable=True)
```

On `Subscription`, immediately after the `remnawave_short_id = Column(...)` block:

```python
    purchase_note = Column(Text, nullable=True)
    user_disabled = Column(Boolean, default=False, nullable=False)
```

`Text` is already imported in `models.py` (used elsewhere). If the import is missing, add `Text` next to the other SQLAlchemy types at the top of the file.

- [x] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/database/test_day1_orm_columns.py -v`

Expected: PASS

- [x] **Step 6: Commit**

```bash
git add app/database/models.py tests/database/test_day1_orm_columns.py
git commit -m "feat(day1): map brand prefix, purchase note, and user_disabled on ORM"
```

---

### Task 3: fa.json keys for list, search, pause, partner, rich wording

**Files:**
- Modify: `/opt/remnabot1/app/localization/locales/fa.json` (merge keys only; never replace the file)
- Test: `/opt/remnabot1/tests/localization/test_day1_fa_keys.py` (create)

**Interfaces:**
- Consumes: existing `load_locale` / `fa.json`
- Produces: keys listed in the test below

- [x] **Step 1: Write the failing test**

Create `/opt/remnabot1/tests/localization/test_day1_fa_keys.py`:

```python
import json
from pathlib import Path

FA = Path('app/localization/locales/fa.json')

REQUIRED = (
    'MY_SUB_LIST_TITLE',
    'MY_SUB_LIST_EMPTY',
    'MY_SUB_TRAFFIC_LINE',
    'MY_SUB_DEVICES_LINE',
    'MY_SUB_DEVICES_COUNT_SHORT',
    'MY_SUB_UNTIL_LINE',
    'MY_SUB_STATUS_EXPIRED',
    'MY_SUB_STATUS_DISABLED',
    'MY_SUB_STATUS_LIMITED',
    'MY_SUB_DEFAULT_NAME',
    'MY_SUB_SEARCH',
    'MY_SUB_SEARCH_PROMPT',
    'MY_SUB_SEARCH_RESET',
    'MY_SUB_SEARCH_CANCEL',
    'MY_SUB_SEARCH_CANCELLED',
    'MY_SUB_SEARCH_EMPTY_QUERY',
    'MY_SUB_SEARCH_STATE_LOST',
    'MY_SUB_SEARCH_ACTIVE',
    'MY_SUB_SEARCH_NO_RESULTS',
    'MY_SUB_BACK',
    'MY_SUB_BTN_DISABLE',
    'MY_SUB_BTN_ENABLE',
    'PARTNER_PURCHASE_NOTE_BTN',
    'PARTNER_PURCHASE_NOTE_PROMPT',
    'PARTNER_BRAND_TOGGLE_ON',
    'PARTNER_BRAND_TOGGLE_OFF',
)


def test_day1_fa_keys_present_and_persian() -> None:
    data = json.loads(FA.read_text(encoding='utf-8'))
    for key in REQUIRED:
        assert key in data, key
        assert data[key].strip()
    assert 'تعرفه' not in data['MAIN_MENU_RICH_TABLE_TARIFF']
    assert 'سرویس' in data['MAIN_MENU_RICH_TABLE_TARIFF']
    assert 'دستگاه' not in data['MAIN_MENU_RICH_DEVICES']
    assert 'کاربر' in data['MAIN_MENU_RICH_DEVICES']
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/localization/test_day1_fa_keys.py -v`

Expected: FAIL (missing keys and/or still `تعرفه` / `دستگاه` on those two rich keys)

- [x] **Step 3: Merge keys into fa.json**

Keep JSON valid. Update existing rich keys in place:

- `MAIN_MENU_RICH_TABLE_TARIFF`: `سرویس`
- `MAIN_MENU_RICH_TARIFF`: `📦 سرویس: {tariff}`
- `MAIN_MENU_RICH_DEVICES`: `📱 تعداد کاربر: {devices}`

Add (values must use English digits):

```json
"MY_SUB_LIST_TITLE": "📋 <b>اشتراک‌های من</b>",
"MY_SUB_LIST_EMPTY": "📋 <b>اشتراک‌های من</b>\n\nاشتراکی ندارید.",
"MY_SUB_TRAFFIC_LINE": "   📊 ترافیک: {traffic}",
"MY_SUB_DEVICES_LINE": "   👥 تعداد کاربر: {devices}",
"MY_SUB_DEVICES_COUNT_SHORT": "{count} کاربر",
"MY_SUB_UNTIL_LINE": "   📅 تا: {end_date}",
"MY_SUB_STATUS_EXPIRED": " (منقضی)",
"MY_SUB_STATUS_DISABLED": " (غیرفعال)",
"MY_SUB_STATUS_LIMITED": " (اتمام حجم)",
"MY_SUB_DEFAULT_NAME": "اشتراک",
"MY_SUB_SEARCH": "جستجو 🔍",
"MY_SUB_SEARCH_PROMPT": "نام، سریال یا یادداشت را بفرستید.",
"MY_SUB_SEARCH_RESET": "❌ حذف جستجو",
"MY_SUB_SEARCH_CANCEL": "✖️ انصراف",
"MY_SUB_SEARCH_CANCELLED": "✖️ جستجو لغو شد",
"MY_SUB_SEARCH_EMPTY_QUERY": "❌ متن جستجو خالی است",
"MY_SUB_SEARCH_STATE_LOST": "❌ جلسه منقضی شد. دوباره «اشتراک‌های من» را باز کنید.",
"MY_SUB_SEARCH_ACTIVE": "جستجو: <b>{query}</b>",
"MY_SUB_SEARCH_NO_RESULTS": "نتیجه‌ای پیدا نشد.",
"MY_SUB_BACK": "◀️ قبلی",
"MY_SUB_BTN_DISABLE": "⏸ توقف اشتراک",
"MY_SUB_BTN_ENABLE": "🟢 روشن کردن اشتراک",
"PARTNER_PURCHASE_NOTE_BTN": "📝 یادداشت خرید",
"PARTNER_PURCHASE_NOTE_PROMPT": "یادداشت این خرید را بفرستید (حداکثر 500 نویسه).",
"PARTNER_BRAND_TOGGLE_ON": "🏷 برند: روشن",
"PARTNER_BRAND_TOGGLE_OFF": "🏷 برند: خاموش"
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/localization/test_day1_fa_keys.py -v`

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add app/localization/locales/fa.json tests/localization/test_day1_fa_keys.py
git commit -m "i18n(fa): day-1 My Subscriptions, search, pause, and rich wording"
```

---

### Task 4: List display helper

**Files:**
- Create: `/opt/remnabot1/app/utils/subscription_list_display.py`
- Test: `/opt/remnabot1/tests/utils/test_subscription_list_display.py`

**Interfaces:**
- Consumes: `format_user_datetime`; Task 2 ORM fields via `getattr` (fail-open); `User.is_partner`
- Produces:
  - `subscription_list_identity(sub, user, texts) -> str`
  - `format_subscription_list_line(sub, idx, texts, language, user) -> str`
  - `filter_subscriptions_by_query(subscriptions, query, texts, user) -> list`

- [x] **Step 1: Write the failing test**

Create `/opt/remnabot1/tests/utils/test_subscription_list_display.py`:

```python
from datetime import UTC, datetime
from types import SimpleNamespace

from app.utils.subscription_list_display import (
    filter_subscriptions_by_query,
    format_subscription_list_line,
    subscription_list_identity,
)


class DummyTexts:
    language = 'fa'

    def t(self, key, default=None):
        return {
            'MY_SUB_DEFAULT_NAME': 'اشتراک',
            'MY_SUB_TRAFFIC_LINE': '   📊 ترافیک: {traffic}',
            'MY_SUB_DEVICES_LINE': '   👥 تعداد کاربر: {devices}',
            'MY_SUB_DEVICES_COUNT_SHORT': '{count} کاربر',
            'MY_SUB_UNTIL_LINE': '   📅 تا: {end_date}',
            'MY_SUB_STATUS_EXPIRED': ' (منقضی)',
            'MY_SUB_STATUS_DISABLED': ' (غیرفعال)',
            'MY_SUB_STATUS_LIMITED': ' (اتمام حجم)',
        }.get(key, default or key)


def _sub(**kwargs):
    base = dict(
        id=1,
        tariff=SimpleNamespace(name='تانل شده (همه نت ها)'),
        actual_status='active',
        traffic_limit_gb=50,
        traffic_used_gb=31.6,
        device_limit=5,
        end_date=datetime(2026, 7, 9, tzinfo=UTC),
        remnawave_short_id='67258',
        purchase_note=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_identity_brand_serial_for_partner() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    assert subscription_list_identity(_sub(), user, DummyTexts()) == 'Moonvpn_67258'


def test_identity_falls_back_to_tariff() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    assert 'تانل' in subscription_list_identity(_sub(), user, DummyTexts())


def test_line_is_jalali_fa_and_not_cyrillic() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    line = format_subscription_list_line(_sub(), 1, DummyTexts(), 'fa', user)
    assert '18.04.1405' in line
    assert 'کاربر' in line
    assert 'Устройства' not in line
    assert 'Трафик' not in line
    assert 'Moonvpn_67258' in line


def test_search_matches_serial_and_brand() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    subs = [_sub(), _sub(id=2, remnawave_short_id='1159', tariff=SimpleNamespace(name='دیگر'))]
    hit = filter_subscriptions_by_query(subs, '67258', DummyTexts(), user)
    assert len(hit) == 1
    hit2 = filter_subscriptions_by_query(subs, 'moonvpn', DummyTexts(), user)
    assert {s.remnawave_short_id for s in hit2} == {'67258'}
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_subscription_list_display.py -v`

Expected: FAIL (`ModuleNotFoundError: subscription_list_display`)

- [x] **Step 3: Write minimal implementation**

Create `/opt/remnabot1/app/utils/subscription_list_display.py`:

```python
from __future__ import annotations

from typing import Any

from app.utils.jalali_datetime import format_user_datetime


def _status_emoji(sub: Any) -> str:
    actual = getattr(sub, 'actual_status', None)
    if actual in ('active', 'trial'):
        return '🟢'
    if actual == 'limited':
        return '🟡'
    return '🔴'


def _status_label(sub: Any, texts: Any) -> str:
    actual = getattr(sub, 'actual_status', None)
    if actual == 'expired':
        return texts.t('MY_SUB_STATUS_EXPIRED', ' (Истекла)')
    if actual == 'disabled':
        return texts.t('MY_SUB_STATUS_DISABLED', ' (Отключена)')
    if actual == 'limited':
        return texts.t('MY_SUB_STATUS_LIMITED', ' (Лимит)')
    return ''


def subscription_list_identity(sub: Any, user: Any, texts: Any) -> str:
    brand = (getattr(user, 'panel_brand_prefix', None) or '').strip()
    serial = (getattr(sub, 'remnawave_short_id', '') or '').strip()
    if getattr(user, 'is_partner', False) and brand and serial:
        return f'{brand}_{serial}'
    tariff = getattr(sub, 'tariff', None)
    if tariff and getattr(tariff, 'name', None):
        return str(tariff.name)
    return texts.t('MY_SUB_DEFAULT_NAME', 'Подписка')


def format_subscription_list_line(
    sub: Any,
    idx: int,
    texts: Any,
    language: str,
    user: Any,
) -> str:
    name = subscription_list_identity(sub, user, texts)
    emoji = _status_emoji(sub)
    label = _status_label(sub, texts)
    if getattr(sub, 'traffic_limit_gb', 0) == 0:
        traffic = '∞'
    else:
        used = f'{sub.traffic_used_gb:.1f}' if getattr(sub, 'traffic_used_gb', None) else '0'
        traffic = f'{used}/{sub.traffic_limit_gb} GB'
    devices = ''
    if getattr(sub, 'device_limit', None) is not None:
        count = texts.t('MY_SUB_DEVICES_COUNT_SHORT', '{count} устр.').format(count=sub.device_limit)
        devices = count
    end_date = (
        format_user_datetime(sub.end_date, language=language, fmt='%d.%m.%Y')
        if getattr(sub, 'end_date', None)
        else '—'
    )
    parts = [f'{emoji} <b>{idx}. {name}</b>{label}']
    parts.append(texts.t('MY_SUB_TRAFFIC_LINE', '   📊 Трафик: {traffic}').format(traffic=traffic))
    if devices:
        parts.append(texts.t('MY_SUB_DEVICES_LINE', '   📱 Устройства: {devices}').format(devices=devices))
    parts.append(texts.t('MY_SUB_UNTIL_LINE', '   📅 До: {end_date}').format(end_date=end_date))
    return '\n'.join(parts)


def _matches(sub: Any, query: str, texts: Any, user: Any) -> bool:
    q = (query or '').strip().lower()
    if not q:
        return True
    identity = subscription_list_identity(sub, user, texts).lower()
    if q in identity:
        return True
    if q in str(getattr(sub, 'id', '')):
        return True
    serial = (getattr(sub, 'remnawave_short_id', '') or '').strip().lower()
    if serial and q in serial:
        return True
    note = (getattr(sub, 'purchase_note', None) or '').strip().lower()
    if note and q in note:
        return True
    tariff = getattr(sub, 'tariff', None)
    tariff_name = (getattr(tariff, 'name', None) or '').strip().lower()
    return bool(tariff_name and q in tariff_name)


def filter_subscriptions_by_query(
    subscriptions: list,
    query: str,
    texts: Any,
    user: Any,
) -> list:
    q = (query or '').strip()
    if not q:
        return list(subscriptions)
    return [s for s in subscriptions if _matches(s, q, texts, user)]
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_subscription_list_display.py -v`

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add app/utils/subscription_list_display.py tests/utils/test_subscription_list_display.py
git commit -m "feat(day1): subscription list identity, Jalali line, and search filter"
```

---

### Task 5: Wire helper into My Subscriptions (drop hardcoded Cyrillic)

**Files:**
- Modify: `/opt/remnabot1/app/handlers/subscription/my_subscriptions.py`
- Modify: `/opt/remnabot1/tests/handlers/test_my_subscriptions_pagination.py`

**Interfaces:**
- Consumes: `format_subscription_list_line`, `subscription_list_identity`, `get_texts`
- Produces: list caption and gear buttons use helper; `_format_subscription_line` either delegates or is deleted

- [x] **Step 1: Extend pagination tests (they will fail until the handler changes)**

In `/opt/remnabot1/tests/handlers/test_my_subscriptions_pagination.py`, add a user to `_fake_sub` usage and replace caption builder + add guards. Keep existing pagination tests working by changing `_format_subscription_line` to accept optional texts/user **or** switch caption test to the helper.

Add:

```python
from pathlib import Path

from app.utils.subscription_list_display import format_subscription_list_line


def test_list_source_has_no_hardcoded_cyrillic() -> None:
    src = Path('app/handlers/subscription/my_subscriptions.py').read_text(encoding='utf-8')
    for needle in ('Устройства', 'Мои подписки', 'Трафик:', 'Назад'):
        assert needle not in src, needle


def test_page_caption_uses_helper_and_fits() -> None:
    items = [_fake_sub(i) for i in range(5)]
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)

    class T:
        language = 'fa'

        def t(self, key, default=None):
            return default or key

    lines = ['title\n']
    for idx, sub in enumerate(items, 1):
        lines.append(format_subscription_list_line(sub, idx, T(), 'fa', user))
    assert len('\n'.join(lines)) <= 1024
```

Update `test_page_caption_fits_telegram_limit` so it no longer requires the Russian title `Мои подписки`. If it still calls `_format_subscription_line(sub, idx)`, change it to the helper as above **in the same edit as the handler** if the old function signature changes.

- [x] **Step 2: Run tests to see Cyrillic guard fail**

Run: `uv run pytest tests/handlers/test_my_subscriptions_pagination.py::test_list_source_has_no_hardcoded_cyrillic -v`

Expected: FAIL (`Устройства` / `Мои подписки` still in the handler)

- [x] **Step 3: Wire the handler**

In `my_subscriptions.py`:

1. Import:

```python
from app.utils.subscription_list_display import (
    format_subscription_list_line,
    subscription_list_identity,
)
```

2. Replace `_format_subscription_line` body with a delegate (keep the name if pagination tests still import it):

```python
def _format_subscription_line(sub, idx: int, texts=None, language: str = 'ru', db_user=None) -> str:
    texts = texts or get_texts(language)
    user = db_user or SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    return format_subscription_list_line(sub, idx, texts, texts.language, user)
```

Add `from types import SimpleNamespace` if used.

3. In `_build_subscriptions_keyboard`, add `db_user=None`. Button label:

```python
label = subscription_list_identity(sub, db_user or SimpleNamespace(is_partner=False), texts)
text=f'⚙️ {label}'
```

Back button:

```python
types.InlineKeyboardButton(text=texts.t('MY_SUB_BACK', '◀️ Назад'), callback_data='back_to_menu')
```

4. In `show_my_subscriptions`, replace hardcoded titles:

```python
if not subscriptions:
    text = texts.t('MY_SUB_LIST_EMPTY', '📋 <b>Мои подписки</b>\n\nУ вас нет подписок.')
else:
    page_items, page, total_pages = paginate_items(subscriptions, page, MY_SUBS_PAGE_SIZE)
    start_idx = (page - 1) * MY_SUBS_PAGE_SIZE
    title = texts.t('MY_SUB_LIST_TITLE', '📋 <b>Мои подписки</b>')
    lines = [f'{title} ({page}/{total_pages})\n']
    for idx, sub in enumerate(page_items, start_idx + 1):
        lines.append(format_subscription_list_line(sub, idx, texts, db_user.language, db_user))
        lines.append('')
    text = '\n'.join(lines)
    keyboard = _build_subscriptions_keyboard(
        page_items,
        db_user.language,
        gift_enabled=gift_enabled,
        page=page,
        total_pages=total_pages,
        db_user=db_user,
    )
```

Pass `db_user` into `_build_subscriptions_keyboard` from the empty-list branch too if it builds buy/gift/back only (no identity).

5. In `show_subscription_detail`, replace Cyrillic status/traffic/device/date strings with `texts.t(...)` and `format_user_datetime(..., language=db_user.language)`. Title uses `subscription_list_identity(subscription, db_user, texts)`.

6. Replace remaining hardcoded `'◀️ К списку подписок'`, `'◀️ Назад'` in this file with `texts.t`.

Do **not** add search in this task.

- [x] **Step 4: Fix pagination tests for the new keyboard signature**

`_build_subscriptions_keyboard(..., db_user=None)` must remain valid for `test_keyboard_keeps_buy_and_does_not_dump_all_rows`.

- [x] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/handlers/test_my_subscriptions_pagination.py tests/utils/test_subscription_list_display.py -v
```

Expected: PASS

- [x] **Step 6: Commit**

```bash
git add app/handlers/subscription/my_subscriptions.py tests/handlers/test_my_subscriptions_pagination.py
git commit -m "feat(day1): overlay My Subscriptions list chrome via helper"
```

---

### Task 6: Search FSM on My Subscriptions

**Files:**
- Modify: `/opt/remnabot1/app/states.py` (`SubscriptionStates`)
- Modify: `/opt/remnabot1/app/handlers/subscription/my_subscriptions.py`
- Modify: `/opt/remnabot1/app/handlers/subscription/purchase.py` (`register_handlers`)
- Modify: `/opt/remnabot1/tests/handlers/test_my_subscriptions_pagination.py`

**Interfaces:**
- Consumes: `filter_subscriptions_by_query`; FSM key `my_subs_search_query`
- Produces: callbacks `my_subs_search`, `my_subs_search_reset`; state `SubscriptionStates.searching_my_subscriptions`

- [x] **Step 1: Write failing keyboard test**

Append to `test_my_subscriptions_pagination.py`:

```python
def test_keyboard_includes_search_and_keeps_gift() -> None:
    page_items = [_fake_sub(i) for i in range(1, 3)]
    keyboard = _build_subscriptions_keyboard(
        page_items,
        'fa',
        gift_enabled=True,
        page=1,
        total_pages=1,
        show_search=True,
    )
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert 'my_subs_search' in callbacks
    assert 'subscription_gift' in callbacks
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/handlers/test_my_subscriptions_pagination.py::test_keyboard_includes_search_and_keeps_gift -v`

Expected: FAIL (`TypeError` unknown kwarg `show_search` or missing callback)

- [x] **Step 3: Implement search**

`states.py` — inside `SubscriptionStates`:

```python
    searching_my_subscriptions = State()
```

`_build_subscriptions_keyboard`: add `show_search: bool = False`, `search_query: str = ''`. After the buy row, if `show_search`:

```python
if search_query:
    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t('MY_SUB_SEARCH_RESET', '❌ Сбросить поиск'),
            callback_data='my_subs_search_reset',
        )
    ])
else:
    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t('MY_SUB_SEARCH', '🔍 Поиск'),
            callback_data='my_subs_search',
        )
    ])
```

`show_my_subscriptions`: read FSM:

```python
search_query = ''
if state:
    data = await state.get_data()
    search_query = (data.get('my_subs_search_query') or '').strip()
from app.utils.subscription_list_display import filter_subscriptions_by_query
visible = (
    filter_subscriptions_by_query(subscriptions, search_query, texts, db_user)
    if search_query
    else subscriptions
)
```

Paginate `visible`, not the unfiltered list. If `search_query` and not `visible`, show `MY_SUB_SEARCH_NO_RESULTS` plus reset. Pass `show_search=True`, `search_query=search_query` into the keyboard.

Add handlers in `my_subscriptions.py`:

```python
async def start_my_subs_search(callback, db_user, db, state: FSMContext):
    texts = get_texts(db_user.language)
    await callback.answer()
    await state.set_state(SubscriptionStates.searching_my_subscriptions)
    await callback.message.answer(texts.t('MY_SUB_SEARCH_PROMPT', 'Введите текст поиска'))


async def reset_my_subs_search(callback, db_user, db, state: FSMContext):
    await state.update_data(my_subs_search_query=None)
    await show_my_subscriptions(callback, db_user, db, state)


async def receive_my_subs_search(message: types.Message, db_user, db, state: FSMContext):
    texts = get_texts(db_user.language)
    raw = (message.text or '').strip()
    if not raw:
        await message.answer(texts.t('MY_SUB_SEARCH_EMPTY_QUERY', '❌ Введите текст'))
        return
    await state.update_data(my_subs_search_query=raw)
    await state.set_state(None)
    await message.answer(texts.t('MY_SUB_SEARCH_ACTIVE', 'Поиск: {query}').format(query=raw))
```

Empty query / lost state: keyed messages from Task 3; do not crash.

In `purchase.py` `register_handlers`, after `ms_pg:`:

```python
from app.handlers.subscription.my_subscriptions import (
    receive_my_subs_search,
    reset_my_subs_search,
    start_my_subs_search,
)
from app.states import SubscriptionStates

dp.callback_query.register(start_my_subs_search, F.data == 'my_subs_search')
dp.callback_query.register(reset_my_subs_search, F.data == 'my_subs_search_reset')
dp.message.register(receive_my_subs_search, SubscriptionStates.searching_my_subscriptions)
```

Export the new functions from `app/handlers/subscription/__init__.py` only if that module already re-exports `show_my_subscriptions` and a test imports from there; otherwise skip.

- [x] **Step 4: Run tests**

Run: `uv run pytest tests/handlers/test_my_subscriptions_pagination.py tests/utils/test_subscription_list_display.py -v`

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add app/states.py app/handlers/subscription/my_subscriptions.py app/handlers/subscription/purchase.py tests/handlers/test_my_subscriptions_pagination.py
git commit -m "feat(day1): My Subscriptions search overlay on 4.2 list"
```

---

### Task 7: Rich `/start` Jalali + purchase expire date

**Files:**
- Modify: `/opt/remnabot1/app/utils/rich_menu.py` (`_build_subscriptions_table`, ~403–410)
- Modify: `/opt/remnabot1/app/handlers/subscription/purchase.py` (~563 `expire_date = purchase.expires_at.strftime`)
- Modify: `/opt/remnabot1/tests/utils/test_rich_menu.py`

**Interfaces:**
- Consumes: `format_user_datetime`; `texts.language`
- Produces: table fallback string Jalali for `fa`; keyboard structure unchanged

- [x] **Step 1: Write failing rich-menu test**

In `tests/utils/test_rich_menu.py` add (reuse `_make_subscription` already in that file):

```python
def test_subscriptions_table_fa_fallback_is_jalali():
    from datetime import UTC, datetime, timedelta

    class FaTexts(DummyTexts):
        language = 'fa'

    now = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    sub = _make_subscription(now, tariff_name='Plan-A')
    sub.end_date = datetime(2026, 7, 9, tzinfo=UTC)
    html_out = rich_menu._build_subscriptions_table([sub], FaTexts())
    assert '18.04.1405' in html_out
```

If `_make_subscription` forces `end_date = now + timedelta(...)`, set `end_date` after as above. If the helper name differs, use the same factory the file already uses for `_build_subscriptions_table`.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_rich_menu.py::test_subscriptions_table_fa_fallback_is_jalali -v`

Expected: FAIL (Gregorian `09.07.2026` from `format_local_datetime`)

- [x] **Step 3: Implement**

`rich_menu.py`:

```python
from app.utils.jalali_datetime import format_user_datetime
```

Replace the fallback line in `_build_subscriptions_table`:

```python
end_date_text = (
    format_user_datetime(end_date, language=getattr(texts, 'language', 'ru'), fmt='%d.%m.%Y')
    if end_date
    else ''
)
```

Keep `_tg_time(...)` as-is (client timezone widget). Wrap formatting in try/except `Exception` and fall back to `format_local_datetime` so `/start` cannot crash.

`purchase.py` around the gift/expire strftime:

```python
from app.utils.jalali_datetime import format_user_datetime
expire_date = format_user_datetime(
    purchase.expires_at, language=db_user.language, fmt='%d.%m.%Y'
)
```

Use the actual local variable name for the user in that function (`db_user` or `user`).

Do **not** add 3.60 grid buttons. Do **not** change callback_data `menu_subscription` / `menu_balance`.

- [x] **Step 4: Run tests**

Run: `uv run pytest tests/utils/test_rich_menu.py tests/utils/test_jalali_datetime.py -v`

Expected: PASS. Existing `test_build_subscriptions_table` still looks for `[MAIN_MENU_RICH_DAYS_LEFT]` with `DummyTexts.language = 'ru'`.

- [x] **Step 5: Commit**

```bash
git add app/utils/rich_menu.py app/handlers/subscription/purchase.py tests/utils/test_rich_menu.py
git commit -m "feat(day1): Jalali fallback on rich-menu table and purchase expire date"
```

---

### Task 8: Partner checkout overlay (Telegram confirm)

**Files:**
- Create: `/opt/remnabot1/app/utils/remnawave_panel_identity.py`
- Create: `/opt/remnabot1/app/utils/partner_checkout_telegram.py`
- Modify: `/opt/remnabot1/app/states.py`
- Modify: `/opt/remnabot1/app/handlers/subscription/tariff_purchase.py` (`get_tariff_confirm_keyboard`, confirm screen ~1698, `confirm_tariff_purchase`)
- Modify: `/opt/remnabot1/app/handlers/subscription/purchase.py` (register note/brand callbacks)
- Test: `/opt/remnabot1/tests/utils/test_partner_checkout_telegram.py`

**Interfaces:**
- Consumes: `User.is_partner`, `User.panel_brand_prefix`, `Subscription.purchase_note`
- Produces:
  - `validate_brand_prefix(raw: str) -> str | None`
  - `sanitize_purchase_note(value: str | None) -> str | None`
  - `checkout_partner_options(user, state_data) -> dict`
  - `extend_confirm_keyboard(buttons, user, tariff_id, period, texts) -> list`
  - `apply_partner_checkout_from_state(db, user, subscription, state_data) -> None` (no-op if not partner or fields missing)

- [x] **Step 1: Write failing tests**

Create `/opt/remnabot1/tests/utils/test_partner_checkout_telegram.py`:

```python
from types import SimpleNamespace

from app.utils.partner_checkout_telegram import (
    checkout_partner_options,
    extend_confirm_keyboard,
    sanitize_purchase_note,
)
from app.utils.remnawave_panel_identity import validate_brand_prefix


def test_validate_brand_prefix() -> None:
    assert validate_brand_prefix('Moonvpn') == 'Moonvpn'
    assert validate_brand_prefix('ab') is None


def test_options_fail_open_without_partner() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix='Moonvpn')
    opts = checkout_partner_options(user, {'purchase_note': 'x', 'use_brand_prefix': True})
    assert opts['use_brand_prefix'] is False


class DummyTexts:
    def t(self, key, default=None):
        return default or key


def test_extend_keyboard_noop_for_non_partner() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    buttons = [['confirm']]
    assert extend_confirm_keyboard(buttons, user, 1, 30, DummyTexts()) == buttons
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/utils/test_partner_checkout_telegram.py -v`

Expected: FAIL (import error)

- [x] **Step 3: Implement helpers**

`/opt/remnabot1/app/utils/remnawave_panel_identity.py`:

```python
from __future__ import annotations

import re

MAX_PURCHASE_NOTE_LEN = 500
BRAND_PREFIX_PATTERN = re.compile(r'^[A-Za-z0-9_-]{3,20}$')


def validate_brand_prefix(raw: str | None) -> str | None:
    value = (raw or '').strip()
    if not BRAND_PREFIX_PATTERN.fullmatch(value):
        return None
    return value
```

`/opt/remnabot1/app/utils/partner_checkout_telegram.py`:

```python
from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton

from app.utils.remnawave_panel_identity import MAX_PURCHASE_NOTE_LEN, validate_brand_prefix


def sanitize_purchase_note(value: str | None) -> str | None:
    note = (value or '').strip()
    if not note:
        return None
    return note[:MAX_PURCHASE_NOTE_LEN]


def checkout_partner_options(user: Any, state_data: dict) -> dict:
    if not getattr(user, 'is_partner', False):
        return {'purchase_note': None, 'use_brand_prefix': False, 'has_brand_prefix': False}
    if not hasattr(user, 'panel_brand_prefix'):
        return {'purchase_note': None, 'use_brand_prefix': False, 'has_brand_prefix': False}
    has_brand = bool((getattr(user, 'panel_brand_prefix', None) or '').strip())
    use_brand = state_data.get('use_brand_prefix')
    if use_brand is None:
        use_brand = has_brand
    return {
        'purchase_note': sanitize_purchase_note(state_data.get('purchase_note')),
        'use_brand_prefix': bool(use_brand) if has_brand else False,
        'has_brand_prefix': has_brand,
    }


def extend_confirm_keyboard(buttons: list, user: Any, tariff_id: int, period: int) -> list:
    if not getattr(user, 'is_partner', False) or not hasattr(user, 'panel_brand_prefix'):
        return buttons
    extra = [
        [InlineKeyboardButton(text='📝', callback_data=f'pnote:{tariff_id}:{period}')],
        [InlineKeyboardButton(text='🏷', callback_data=f'pbrand:{tariff_id}:{period}')],
    ]
    # Insert before the last row (Back)
    return buttons[:-1] + extra + buttons[-1:]
```

Use `texts.t` for button labels inside `extend_confirm_keyboard` by passing `language` if tests stay icon-only; for production, pass `get_texts` into the extender:

```python
def extend_confirm_keyboard(buttons, user, tariff_id, period, texts) -> list:
    ...
    extra = [
        [InlineKeyboardButton(text=texts.t('PARTNER_PURCHASE_NOTE_BTN', '📝'), callback_data=f'pnote:{tariff_id}:{period}')],
        [InlineKeyboardButton(text=texts.t('PARTNER_BRAND_TOGGLE_ON' if opts['use_brand_prefix'] else 'PARTNER_BRAND_TOGGLE_OFF', '🏷'), callback_data=f'pbrand:{tariff_id}:{period}')],
    ]
```

Update the unit test to pass a DummyTexts. Keep fail-open: if `panel_brand_prefix` is missing on the class, return `buttons` unchanged.

- [x] **Step 4: Hook tariff confirm**

`get_tariff_confirm_keyboard` — add optional `db_user=None`. After building `buttons`, if `db_user` is not None:

```python
from app.utils.partner_checkout_telegram import extend_confirm_keyboard
buttons = extend_confirm_keyboard(buttons, db_user, tariff_id, period, texts)
```

At the confirm **display** callsite (~1698) pass `db_user=db_user`. Leave other callsites working (`db_user` default None = no extra buttons).

`states.py`:

```python
    waiting_for_purchase_note = State()
```

Add handlers in `partner_checkout_telegram.py` or `my_subscriptions.py` is the wrong file — put handlers in `/opt/remnabot1/app/handlers/subscription/partner_checkout.py` (new, thin):

- `pnote:{tariff_id}:{period}` → set state, prompt `PARTNER_PURCHASE_NOTE_PROMPT`
- message in that state → `state.update_data(purchase_note=sanitize...)` → re-show confirm
- `pbrand:{tariff_id}:{period}` → toggle `use_brand_prefix` in FSM → re-show confirm

Register those in `purchase.py` `register_handlers`.

In `confirm_tariff_purchase`, after the subscription row exists (the `existing_sub` or newly created sub variable in that function — use the name the function already uses for the saved subscription), call:

```python
from app.utils.partner_checkout_telegram import apply_partner_checkout_from_state

state_data = await state.get_data()
await apply_partner_checkout_from_state(db, db_user, saved_sub, state_data)
```

Implement `apply_partner_checkout_from_state`:

```python
async def apply_partner_checkout_from_state(db, user, subscription, state_data: dict) -> None:
    if subscription is None or not getattr(user, 'is_partner', False):
        return
    if not hasattr(subscription, 'purchase_note'):
        return
    opts = checkout_partner_options(user, state_data)
    subscription.purchase_note = opts['purchase_note']
    if opts['use_brand_prefix'] is False:
        return
    # prefix already on user; nothing else if validate would fail
```

Do not reimplement `PricingEngine`. Do not touch cabinet forms.

- [x] **Step 5: Run tests**

Run: `uv run pytest tests/utils/test_partner_checkout_telegram.py tests/test_tariff_insufficient_balance_keyboard.py -v`

Expected: PASS (`get_tariff_confirm_keyboard` extra optional arg must not break existing tests)

- [x] **Step 6: Commit**

```bash
git add app/utils/remnawave_panel_identity.py app/utils/partner_checkout_telegram.py app/handlers/subscription/partner_checkout.py app/handlers/subscription/tariff_purchase.py app/handlers/subscription/purchase.py app/states.py tests/utils/test_partner_checkout_telegram.py
git commit -m "feat(day1): partner note and brand overlay on 4.2 tariff confirm"
```

---

### Task 9: Telegram pause (`user_disabled`)

**Files:**
- Create: `/opt/remnabot1/app/services/subscription_user_toggle_service.py`
- Modify: `/opt/remnabot1/app/handlers/subscription/my_subscriptions.py` (`_build_subscription_detail_keyboard`, new handlers)
- Modify: `/opt/remnabot1/app/handlers/subscription/purchase.py` (register `sub_disable:` / `sub_enable:`)
- Test: `/opt/remnabot1/tests/services/test_subscription_user_toggle.py`

**Interfaces:**
- Consumes: `Subscription.user_disabled`, `Subscription.remnawave_id` (int, 3.x), `deactivate_subscription`, `reactivate_subscription`, `SubscriptionService.disable_remnawave_user` / `enable_remnawave_user`
- Produces: `disable_user_subscription`, `enable_user_subscription`, `SubscriptionToggleError`

- [x] **Step 1: Write failing tests**

Create `/opt/remnabot1/tests/services/test_subscription_user_toggle.py`:

```python
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.subscription_user_toggle_service import (
    SubscriptionToggleError,
    disable_user_subscription,
)


@pytest.mark.asyncio
async def test_disable_rejects_expired() -> None:
    sub = SimpleNamespace(actual_status='expired', user_disabled=False)
    with pytest.raises(SubscriptionToggleError) as exc:
        await disable_user_subscription(AsyncMock(), sub, SimpleNamespace())
    assert exc.value.code == 'not_active'


@pytest.mark.asyncio
async def test_disable_sets_flag_and_calls_panel() -> None:
    sub = SimpleNamespace(
        actual_status='active',
        user_disabled=False,
        remnawave_id=99,
        is_daily_tariff=False,
        id=1,
        user_id=2,
    )
    db = AsyncMock()
    with (
        patch(
            'app.services.subscription_user_toggle_service.deactivate_subscription',
            new_callable=AsyncMock,
        ) as deact,
        patch(
            'app.services.subscription_user_toggle_service.SubscriptionService'
        ) as svc_cls,
    ):
        svc_cls.return_value.disable_remnawave_user = AsyncMock(return_value=True)
        result = await disable_user_subscription(db, sub, SimpleNamespace(id=2))
    assert result.user_disabled is True
    deact.assert_awaited()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/services/test_subscription_user_toggle.py -v`

Expected: FAIL (import error)

- [x] **Step 3: Implement service**

Port donor logic but **use numeric `subscription.remnawave_id`**, not uuid:

```python
panel_id = getattr(subscription, 'remnawave_id', None)
if panel_id:
    ok = await SubscriptionService().disable_remnawave_user(int(panel_id), db=db)
```

Match donor rules: only `active`/`trial`/`limited` can disable; enable only when `user_disabled` and not expired. On panel failure raise `SubscriptionToggleError('panel_error', ...)`.

Hide the button when `not hasattr(subscription, 'user_disabled')`.

- [x] **Step 4: Wire detail keyboard + handlers**

In `_build_subscription_detail_keyboard`, after building the inactive/active rows, if `sub is not None and hasattr(sub, 'user_disabled')` and `sub.actual_status in ('active', 'trial', 'limited')`:

```python
if getattr(sub, 'user_disabled', False):
    # enable-only keyboard (donor behavior): enable + back
else:
    buttons.append([types.InlineKeyboardButton(
        text=texts.t('MY_SUB_BTN_DISABLE', '⏸'),
        callback_data=f'sub_disable:{sub_id}',
    )])
```

Pass `language` into this builder (it currently has no language — add `language: str = 'ru'` and `get_texts(language)` for the new labels). Existing Russian button strings can stay for this task **except** the new pause labels, or replace them if the Cyrillic guard from Task 5 already forbids remaining Cyrillic in this file.

Handlers `handle_subscription_user_disable` / `handle_subscription_user_enable`: `callback.answer()` first, then service, then `show_subscription_detail`.

Register in `purchase.py`:

```python
dp.callback_query.register(handle_subscription_user_disable, F.data.startswith('sub_disable:'))
dp.callback_query.register(handle_subscription_user_enable, F.data.startswith('sub_enable:'))
```

- [x] **Step 5: Run tests**

Run: `uv run pytest tests/services/test_subscription_user_toggle.py tests/handlers/test_my_subscriptions_pagination.py -v`

Expected: PASS

- [x] **Step 6: Commit**

```bash
git add app/services/subscription_user_toggle_service.py app/handlers/subscription/my_subscriptions.py app/handlers/subscription/purchase.py tests/services/test_subscription_user_toggle.py
git commit -m "feat(day1): Telegram pause/resume via user_disabled"
```

---

### Task 10: Joint day-1 operator smoke (no code)

**Files:** none in remnabot1 app. Evidence: `docs/superpowers/evidence/smoke-2026-09-04-day1-overlay.md`.

**Depends on:** Part A Tasks 1–9 **and** Part B Tasks 1–6 (cabinet Layer A, same file).

Do **not** start M7. Do **not** use the production bot token. RC bot is the test token / `@mrj7_bot`.

**Status:** **PASS** — operator `تایید` 2026-09-04 (incl. A4.2 pause + paused-sub list order). Bot `e716cb83`, cabinet `0173edae`.

- [x] **Step 1: Telegram `/start`**

On the RC test bot: rich 4.2 shell still shows Connect / Subscription / Balance (not the 3.60 grid). Chrome is Persian. Subscription preview fallback date is Jalali for fa. Balance is Toman (already ported).

- [x] **Step 2: My Subscriptions**

Opens paginated list. Title Persian with page/total. Lines use ترافیک / تعداد کاربر / Jalali. Search button works. Gift button still present. If the account has `panel_brand_prefix` + serial, identity looks like `Moonvpn_67258`.

- [x] **Step 3: Pause (if an active test sub exists)**

Detail shows pause. Confirm → pause → detail/`sm:` OK; paused row stays in active-tier list order (`e716cb83`).

- [x] **Step 4: Partner confirm (optional)**

SKIP — no isolated partner test account this round.

- [x] **Step 5: Cabinet**

`https://panel.rookari.com` first paint fa/RTL, Jalali, wording, subscription sheets — per Layer A smoke map. B1–B5 PASS.

- [x] **Step 6: Stop**

Do not start M7-T1 from this smoke. Next cutover pointer remains the MVP plan named-start (**M7-T1**).

---

## Self-review (author)

| Spec requirement | Task |
|---|---|
| Keep 4.2 rich `/start` | 7 (strings/dates only); 10 verifies callbacks |
| Jalali on rich preview + list + purchase date | 1, 4, 5, 7 |
| My Subs search, page/total, brand+serial, تعداد کاربر | 3, 4, 5, 6 |
| Gift stays | 6 test |
| No 3.60 file replace | 5 overlay |
| ORM map 0095/0103, no autogenerate | 2 |
| Partner confirm overlay, fail-open | 8 |
| Pause Telegram only | 9 |
| Cabinet Layer A | Part B Tasks 1–6; Task 10 |
| No M7 / Layer C | Global constraints + Task 10 |

No TBD remaining. Helper signatures in Tasks 5–6 match Task 4. Pause uses `remnawave_id` (4.2 / Remnawave 3.x), not donor uuid.

---

# Part B — Cabinet Layer A (`/opt/cabinet`)

Work tree: `/opt/cabinet` `prod-cutover`. Spec: `docs/superpowers/specs/2026-09-03-cabinet-b2-overlay-design.md`. Do not edit `/opt/remnabot1` app code in Part B. Do not replace `Referral.tsx`, `TariffPurchaseForm.tsx`, or whole `fa.json`. After each Part B commit: `cd /opt/cabinet && npm test` and `npx biome check` on touched files. Tasks below keep their original numbers (Task 1–6) **inside Part B**.

## File map

| File | Responsibility |
|---|---|
| `/opt/cabinet/src/i18n.ts` | Default `fa`, localStorage-only detect, no Telegram auto-lang |
| `/opt/cabinet/index.html` | First paint `lang="fa" dir="rtl"` |
| `/opt/cabinet/src/utils/uiLocale.ts` | fa → `fa-IR-u-ca-persian-nu-latn` |
| `/opt/cabinet/src/utils/formatDate.ts` | Explicit Jalali/Gregorian helper |
| `/opt/cabinet/src/utils/ltrIsolate.tsx` | `dir="ltr"` + `unicode-bidi: isolate` wrapper |
| `/opt/cabinet/src/styles/globals.css` | `.url-ltr` class |
| `/opt/cabinet/src/components/subscription/TrafficUsageText.tsx` | LTR traffic amounts |
| `/opt/cabinet/src/components/subscription/ConfigDeliverySheet.tsx` | QR/copy sheet (new) |
| `/opt/cabinet/src/utils/subscriptionDisplayLabel.ts` | Hide `user_unknown_*` if field present later |
| `/opt/cabinet/src/locales/fa.json` | User-path terminology + onboarding keys |
| `/opt/cabinet/src/pages/Subscription.tsx` | Wire traffic isolate, URL class, checklist, delivery sheet |
| `/opt/cabinet/src/components/subscription/SubscriptionListCard.tsx` | `formatUserDate` for end date |

---

### Task 1: Default Persian + first-paint RTL

**Files:**
- Modify: `/opt/cabinet/src/i18n.ts`
- Modify: `/opt/cabinet/index.html` (html tag only)
- Test: `/opt/cabinet/src/i18n.defaults.test.ts`

**Interfaces:**
- Consumes: existing i18next init in `i18n.ts`
- Produces: `DEFAULT_LNG = 'fa'`; `applyTelegramLanguage()` must not switch language when `cabinet_language` is unset (stay on `fa`)

- [x] **Step 1: Write the failing test**

Create `/opt/cabinet/src/i18n.defaults.test.ts`:

```ts
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

describe('cabinet default language (Layer A)', () => {
  it('index.html first-paints fa rtl', () => {
    const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
    expect(html).toMatch(/<html[^>]*lang="fa"/);
    expect(html).toMatch(/dir="rtl"/);
  });

  it('i18n.ts pins DEFAULT_LNG fa and localStorage-only detection', () => {
    const src = readFileSync(new URL('./i18n.ts', import.meta.url), 'utf8');
    expect(src).toMatch(/const DEFAULT_LNG = 'fa'/);
    expect(src).toMatch(/fallbackLng:\s*\[DEFAULT_LNG,\s*FALLBACK_LNG,\s*'en'\]/);
    expect(src).toMatch(/order:\s*\['localStorage'\]/);
    expect(src).not.toMatch(/order:\s*\['localStorage',\s*'navigator'\]/);
  });
});
```

- [x] **Step 2: Run test to verify it fails**

```bash
cd /opt/cabinet && npx vitest run src/i18n.defaults.test.ts
```

Expected: FAIL (`lang="ru"` / no `DEFAULT_LNG`).

- [x] **Step 3: Minimal implementation**

In `/opt/cabinet/index.html` change the opening html tag from `lang="ru"` to:

```html
<html lang="fa" dir="rtl" class="dark">
```

In `/opt/cabinet/src/i18n.ts`:

1. After `SUPPORTED_LANGS`, add:

```ts
/** Deployment default — matches bot DEFAULT_LANGUAGE (fa). */
const DEFAULT_LNG = 'fa';
```

2. Change `i18n.init` to:

```ts
  .init({
    lng: DEFAULT_LNG,
    fallbackLng: [DEFAULT_LNG, FALLBACK_LNG, 'en'],
    supportedLngs: SUPPORTED_LANGS,
    partialBundledLanguages: true,

    detection: {
      order: ['localStorage'],
      caches: ['localStorage'],
      lookupLocalStorage: 'cabinet_language',
    },
```

3. Change startup load to always load fa + ru:

```ts
const detectedLng = i18n.language?.split('-')[0] || DEFAULT_LNG;
const langsToLoad = [
  DEFAULT_LNG,
  FALLBACK_LNG,
  ...(detectedLng !== DEFAULT_LNG && detectedLng !== FALLBACK_LNG ? [detectedLng] : []),
];
Promise.all(langsToLoad.map(loadLanguage));
```

4. Update the comment that says `index.html ships with lang="ru"` to `lang="fa"`.

5. Replace `applyTelegramLanguage` so Telegram client language is **not** auto-applied (donor pattern). Keep the export so `main.tsx` still compiles:

```ts
/**
 * Explicit LanguageSwitcher choice wins. Otherwise stay on DEFAULT_LNG (fa).
 * Telegram client language is not auto-applied (Layer A).
 */
export function applyCabinetLanguagePreference(preferred?: string | null): void {
  try {
    if (localStorage.getItem(LANGUAGE_STORAGE_KEY)) return;
  } catch {
    return;
  }
  const raw = preferred?.split('-')[0]?.toLowerCase();
  const code = raw && SUPPORTED_LANGS.includes(raw) ? raw : DEFAULT_LNG;
  if (i18n.language?.split('-')[0] !== code) {
    i18n.changeLanguage(code);
  }
}

/** @deprecated Use applyCabinetLanguagePreference — Telegram client lang is not auto-applied. */
export function applyTelegramLanguage(): void {
  applyCabinetLanguagePreference();
}
```

Do not remove the `getTelegramLanguageCode` import if still unused — if unused after this change, remove the import (Biome unused import).

- [x] **Step 4: Run tests**

```bash
cd /opt/cabinet && npx vitest run src/i18n.defaults.test.ts
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
cd /opt/cabinet
git add src/i18n.ts index.html src/i18n.defaults.test.ts
git commit -m "$(cat <<'EOF'
fix(i18n): default fa and rtl first paint (Layer A)

EOF
)"
```

---

### Task 2: Jalali dates (uiLocale + formatDate)

**Files:**
- Create: `/opt/cabinet/src/utils/formatDate.ts`
- Modify: `/opt/cabinet/src/utils/uiLocale.ts`
- Modify: `/opt/cabinet/src/utils/uiLocale.test.ts`
- Test: `/opt/cabinet/src/utils/formatDate.test.ts`
- Modify: `/opt/cabinet/src/components/subscription/SubscriptionListCard.tsx` (local `formatDate` that uses `i18n.language` without calendar)

**Interfaces:**
- Consumes: i18next language
- Produces: `uiLocale()` for `fa` returns `fa-IR-u-ca-persian-nu-latn`; `formatUserDate(iso, lang)` / `formatUserDateTime(iso, lang)` as in donor

Pages that already call `toLocaleDateString(uiLocale())` (Profile, Balance, Gift, Support, Wheel, Merge, Subscription) pick up Jalali **without** a bulk rewrite once `uiLocale` changes.

- [x] **Step 1: Write the failing tests**

Create `/opt/cabinet/src/utils/formatDate.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { formatUserDate, formatUserDateTime } from './formatDate';

const ANCHOR = '2026-07-09T12:00:00Z';

describe('formatUserDate', () => {
  it('returns em dash for null', () => {
    expect(formatUserDate(null)).toBe('—');
  });

  it('uses Persian calendar and Latin digits for fa', () => {
    const rendered = formatUserDate(ANCHOR, 'fa');
    expect(rendered).toMatch(/1405/);
    expect(rendered).toMatch(/04/);
    expect(rendered).toMatch(/18/);
    expect(rendered).not.toMatch(/[۰-۹]/);
  });

  it('stays Gregorian for en', () => {
    const rendered = formatUserDate(ANCHOR, 'en');
    expect(rendered).toMatch(/2026/);
  });
});

describe('formatUserDateTime', () => {
  it('includes a time part for fa', () => {
    const rendered = formatUserDateTime(ANCHOR, 'fa');
    expect(rendered.length).toBeGreaterThan(formatUserDate(ANCHOR, 'fa').length);
  });
});
```

In `/opt/cabinet/src/utils/uiLocale.test.ts`, change the fa expectation:

```ts
    await i18next.changeLanguage('fa');
    expect(uiLocale()).toBe('fa-IR-u-ca-persian-nu-latn');
```

Add:

```ts
  it('fa dates use Persian calendar with Latin digits', async () => {
    await i18next.changeLanguage('fa');
    const date = new Date('2026-07-09T12:00:00Z');
    const rendered = date.toLocaleDateString(uiLocale(), { timeZone: 'UTC' });
    expect(rendered).toMatch(/1405/);
    expect(rendered).not.toMatch(/[۰-۹]/);
  });
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd /opt/cabinet && npx vitest run src/utils/formatDate.test.ts src/utils/uiLocale.test.ts
```

Expected: FAIL (`Module not found: formatDate` and `fa-IR` !== `fa-IR-u-ca-persian-nu-latn`).

- [x] **Step 3: Minimal implementation**

Create `/opt/cabinet/src/utils/formatDate.ts` (donor `/opt/remnabot/cabinet/src/utils/formatDate.ts` verbatim):

```ts
const LOCALE_MAP: Record<string, string> = {
  ru: 'ru-RU',
  en: 'en-US',
  zh: 'zh-CN',
  fa: 'fa-IR-u-nu-latn',
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

In `/opt/cabinet/src/utils/uiLocale.ts` change the fa row:

```ts
  fa: 'fa-IR-u-ca-persian-nu-latn',
```

In `/opt/cabinet/src/components/subscription/SubscriptionListCard.tsx`:

- Add `import { formatUserDate } from '../../utils/formatDate';`
- Delete the local `function formatDate(...)`.
- Replace `{formatDate(subscription.end_date, i18n.language)}` with `{formatUserDate(subscription.end_date, i18n.language)}`.

- [x] **Step 4: Run tests**

```bash
cd /opt/cabinet && npx vitest run src/utils/formatDate.test.ts src/utils/uiLocale.test.ts
```

Expected: PASS (Jalali string is `1405/04/18` on this host).

- [x] **Step 5: Commit**

```bash
cd /opt/cabinet
git add src/utils/formatDate.ts src/utils/formatDate.test.ts src/utils/uiLocale.ts src/utils/uiLocale.test.ts src/components/subscription/SubscriptionListCard.tsx
git commit -m "$(cat <<'EOF'
feat(i18n): Jalali dates with Latin digits for fa

EOF
)"
```

---

### Task 3: RTL isolate for amounts and subscription URLs

**Files:**
- Create: `/opt/cabinet/src/utils/ltrIsolate.tsx`
- Test: `/opt/cabinet/src/utils/ltrIsolate.test.tsx` (node + react-dom/server) **or** keep it CSS-only if jsdom is painful — prefer a static class test + TrafficUsageText unit test that does not need jsdom
- Create: `/opt/cabinet/src/components/subscription/TrafficUsageText.tsx`
- Test: `/opt/cabinet/src/components/subscription/TrafficUsageText.test.ts`
- Modify: `/opt/cabinet/src/styles/globals.css` (`@layer components` block, add `.url-ltr`)
- Modify: `/opt/cabinet/src/pages/Subscription.tsx` (traffic span + subscription URL)

**Interfaces:**
- Consumes: `formatTraffic` from `/opt/cabinet/src/utils/formatTraffic.ts`
- Produces: `LtrIsolate` props `{ children, className?: string }`; `TrafficUsageText({ usedGb, limitGb?, isUnlimited?, className?, style? })`; CSS class `url-ltr`

`TrafficUsageText.test.ts` can assert the exported function exists by rendering to a string via `react-dom/server` if available; simpler: test `formatTraffic` is used by importing the component and using `react-dom/server.renderToStaticMarkup` — check package has `react-dom`. It does.

- [x] **Step 1: Write failing tests**

`/opt/cabinet/src/components/subscription/TrafficUsageText.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement } from 'react';
import { TrafficUsageText } from './TrafficUsageText';

describe('TrafficUsageText', () => {
  it('sets dir=ltr and unicode-bidi isolate', () => {
    const html = renderToStaticMarkup(
      createElement(TrafficUsageText, { usedGb: 0, limitGb: 10, isUnlimited: false }),
    );
    expect(html).toContain('dir="ltr"');
    expect(html).toMatch(/unicode-bidi:isolate|unicode-bidi: isolate/);
  });
});
```

`/opt/cabinet/src/utils/ltrIsolate.test.ts`:

```ts
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

describe('url-ltr css', () => {
  it('defines isolate for RTL URL fields', () => {
    const css = readFileSync(new URL('../styles/globals.css', import.meta.url), 'utf8');
    expect(css).toMatch(/\.url-ltr\s*\{/);
    expect(css).toMatch(/unicode-bidi:\s*isolate/);
  });
});
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd /opt/cabinet && npx vitest run src/components/subscription/TrafficUsageText.test.ts src/utils/ltrIsolate.test.ts
```

Expected: FAIL (module / class missing).

- [x] **Step 3: Minimal implementation**

Create `/opt/cabinet/src/utils/ltrIsolate.tsx`:

```tsx
import type { ReactNode } from 'react';

export function LtrIsolate({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span dir="ltr" className={`inline-block [unicode-bidi:isolate] ${className}`}>
      {children}
    </span>
  );
}
```

Create `/opt/cabinet/src/components/subscription/TrafficUsageText.tsx`:

```tsx
import { formatTraffic } from '../../utils/formatTraffic';

interface TrafficUsageTextProps {
  usedGb: number;
  limitGb?: number;
  isUnlimited?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

/** LTR-isolated traffic amounts for RTL layouts (e.g. 0 MB / 10.0 GB). */
export function TrafficUsageText({
  usedGb,
  limitGb,
  isUnlimited = false,
  className = '',
  style,
}: TrafficUsageTextProps) {
  const text =
    isUnlimited || limitGb === undefined
      ? formatTraffic(usedGb)
      : `${formatTraffic(usedGb)} / ${formatTraffic(limitGb)}`;

  return (
    <span
      dir="ltr"
      className={`inline-block font-mono tabular-nums [unicode-bidi:isolate] ${className}`}
      style={style}
    >
      {text}
    </span>
  );
}
```

In `/opt/cabinet/src/styles/globals.css` inside `@layer components {` after the opening (before `.bento-card` is fine):

```css
  /* URL / deep-link fields in RTL (fa) UI — show https:// start, not the tail */
  .url-ltr {
    direction: ltr;
    text-align: left;
    unicode-bidi: isolate;
  }
```

In `/opt/cabinet/src/pages/Subscription.tsx`:

- Add `import { TrafficUsageText } from '../components/subscription/TrafficUsageText';`
- Replace the traffic amount `<span className="font-mono text-[11px] text-dark-50/30">` block (~lines 934–938) with:

```tsx
                    <span className="font-mono text-[11px] text-dark-50/30">
                      <TrafficUsageText
                        usedGb={usedGb}
                        limitGb={subscription.traffic_limit_gb}
                        isUnlimited={isUnlimited}
                      />
                    </span>
```

- Find where `subscription.subscription_url` is shown as text (copy/link field). Add `className="url-ltr"` (or append it) on that element. If the URL is only used as `navigate(...)` and not displayed as a string, wrap the visible copy-target if any. At minimum, any `<code>` or input showing the URL must include `url-ltr`.

Also wrap the list-card traffic numbers in `SubscriptionListCard.tsx` (the `${trafficUsed.toFixed(1)} / ${trafficLimit}` span) with `dir="ltr"` + `[unicode-bidi:isolate]` or `TrafficUsageText` if `usedGb` is in GB already (`trafficUsed` is fine to pass as `usedGb` if it is already GB).

- [x] **Step 4: Run tests**

```bash
cd /opt/cabinet && npx vitest run src/components/subscription/TrafficUsageText.test.ts src/utils/ltrIsolate.test.ts
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
cd /opt/cabinet
git add src/utils/ltrIsolate.tsx src/utils/ltrIsolate.test.ts src/components/subscription/TrafficUsageText.tsx src/components/subscription/TrafficUsageText.test.ts src/styles/globals.css src/pages/Subscription.tsx src/components/subscription/SubscriptionListCard.tsx
git commit -m "$(cat <<'EOF'
fix(ui): isolate traffic amounts and subscription URLs in RTL

EOF
)"
```

---

### Task 4: User-facing fa terminology (دستگاه / تعرفه)

**Files:**
- Modify: `/opt/cabinet/src/locales/fa.json` (merge only)
- Test: `/opt/cabinet/src/locales/fa-user-terminology.test.ts`

**Interfaces:**
- Consumes: donor `/opt/remnabot/cabinet/src/locales/fa.json` (read-only)
- Produces: user-root keys without `دستگاه` / user `تعرفه` where donor already says `سرویس` or `کاربر`; **admin.** keys unchanged

User roots (prefix of dotted path): `common`, `subscription`, `dashboard`, `gift`, `balance`, `profile`, `support`, `wheel`, `merge`, `quickPurchase`, `purchase`, `traffic`, `devices`, `nav` — **exclude** any path starting with `admin.`.

- [x] **Step 1: Write the failing test**

```ts
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const USER_ROOTS = new Set([
  'common',
  'subscription',
  'dashboard',
  'gift',
  'balance',
  'profile',
  'support',
  'wheel',
  'merge',
  'quickPurchase',
  'purchase',
  'traffic',
  'devices',
  'nav',
]);

function walk(obj: unknown, prefix: string, visit: (path: string, value: string) => void): void {
  if (typeof obj === 'string') {
    visit(prefix, obj);
    return;
  }
  if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      walk(v, prefix ? `${prefix}.${k}` : k, visit);
    }
  }
}

describe('fa user terminology', () => {
  const fa = JSON.parse(readFileSync(new URL('./fa.json', import.meta.url), 'utf8')) as unknown;

  it('user roots do not say دستگاه', () => {
    const hits: string[] = [];
    walk(fa, '', (path, value) => {
      const root = path.split('.')[0];
      if (root === 'admin') return;
      if (!USER_ROOTS.has(root)) return;
      if (value.includes('دستگاه')) hits.push(path);
    });
    expect(hits).toEqual([]);
  });
});
```

- [x] **Step 2: Run test to verify it fails**

```bash
cd /opt/cabinet && npx vitest run src/locales/fa-user-terminology.test.ts
```

Expected: FAIL with a list of paths (today ~dozens under `subscription` / `dashboard`).

- [x] **Step 3: Overlay donor values (do not replace the file)**

Run this **once** from `/opt/cabinet` (script is throwaway; do not commit the script unless it is useful — prefer inline node):

```bash
cd /opt/cabinet && node --input-type=module <<'EOF'
import { readFileSync, writeFileSync } from 'node:fs';

const USER_ROOTS = new Set([
  'common','subscription','dashboard','gift','balance','profile','support',
  'wheel','merge','quickPurchase','purchase','traffic','devices','nav',
]);

const a = JSON.parse(readFileSync('/opt/remnabot/cabinet/src/locales/fa.json', 'utf8'));
const b = JSON.parse(readFileSync('./src/locales/fa.json', 'utf8'));

function get(obj, path) {
  return path.split('.').reduce((acc, k) => (acc == null ? acc : acc[k]), obj);
}
function set(obj, path, value) {
  const parts = path.split('.');
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    if (cur[parts[i]] == null || typeof cur[parts[i]] !== 'object') cur[parts[i]] = {};
    cur = cur[parts[i]];
  }
  cur[parts[parts.length - 1]] = value;
}
function walk(obj, prefix, visit) {
  if (typeof obj === 'string') { visit(prefix, obj); return; }
  if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
    for (const [k, v] of Object.entries(obj)) walk(v, prefix ? `${prefix}.${k}` : k, visit);
  }
}

walk(b, '', (path, bVal) => {
  const root = path.split('.')[0];
  if (root === 'admin' || !USER_ROOTS.has(root)) return;
  const aVal = get(a, path);
  if (typeof aVal !== 'string') return;
  const dirty = bVal.includes('دستگاه') || (bVal.includes('تعرفه') && !bVal.includes('تعرفه.') );
  if (dirty && aVal !== bVal) set(b, path, aVal);
});

writeFileSync('./src/locales/fa.json', JSON.stringify(b, null, 2) + '\n');
EOF
```

Then add **missing** onboarding keys from donor if absent (`subscription.volumeEmptyHint`, `subscription.firstConnectChecklist`, `subscription.configDelivery`) with **ASCII digits**:

```json
    "volumeEmptyHint": "هنوز مصرفی ثبت نشده — کل حجم در دسترس است",
    "firstConnectChecklist": {
      "title": "راهنمای اولین اتصال",
      "step1": "1. «دریافت کانفیگ» را بزنید (QR همین‌جا)",
      "step2": "2. «راهنمای اتصال» → برنامه را انتخاب و نصب کنید",
      "step3": "3. وصل شوید"
    },
    "configDelivery": {
      "title": "کانفیگ شما آماده است",
      "subtitle": "لینک را کپی کنید یا QR را اسکن کنید",
      "copyConfig": "کپی کانفیگ",
      "copied": "کانفیگ کپی شد!",
      "getConfig": "دریافت کانفیگ",
      "qrHint": "با دوربین گوشی اسکن کنید",
      "openGuide": "راهنمای اتصال (نصب برنامه)"
    }
```

Insert under the existing `subscription` object in `fa.json` (pretty-print must remain valid JSON). Do not add `earn.*` keys.

If donor overlay still leaves `دستگاه` in a user root, replace remaining `دستگاه‌ها` → `تعداد کاربر` and `دستگاه` → `کاربر` only in those leftover user paths, then re-run the test.

Keep `admin.*` untouched.

- [x] **Step 4: Run test**

```bash
cd /opt/cabinet && npx vitest run src/locales/fa-user-terminology.test.ts
python3 -c "import json; json.load(open('/opt/cabinet/src/locales/fa.json'))"
```

Expected: vitest PASS; JSON parses.

- [x] **Step 5: Commit**

```bash
cd /opt/cabinet
git add src/locales/fa.json src/locales/fa-user-terminology.test.ts
git commit -m "$(cat <<'EOF'
i18n(fa): user terminology overlay from production cabinet

EOF
)"
```

---

### Task 5: Subscription first-connect UX (no file replace)

**Files:**
- Create: `/opt/cabinet/src/components/subscription/ConfigDeliverySheet.tsx` (copy donor)
- Create: `/opt/cabinet/src/utils/subscriptionDisplayLabel.ts`
- Test: `/opt/cabinet/src/utils/subscriptionDisplayLabel.test.ts`
- Modify: `/opt/cabinet/src/pages/Subscription.tsx`
- Modify: `/opt/cabinet/src/components/subscription/SubscriptionListCard.tsx` (title via display label)

**Interfaces:**
- Consumes: `subscription_url`, `traffic_used_gb`, `id`; optional `panel_username?: string` on list items (1.67 type may omit it — helper must accept a structural type, not require a bot API change)
- Produces: `getSubscriptionDisplayLabel(sub, t)`; `ConfigDeliverySheet` props as donor

Skip `DisableSubscriptionSheet` (no `user_disabled` on 1.67 types).

- [x] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from 'vitest';
import { getSubscriptionDisplayLabel } from './subscriptionDisplayLabel';

const t = (_key: string, fallback: string) => fallback;

describe('getSubscriptionDisplayLabel', () => {
  it('hides user_unknown prefix', () => {
    const label = getSubscriptionDisplayLabel(
      { tariff_name: 'Moon', panel_username: 'user_unknown_abc' },
      t,
    );
    expect(label).toBe('Moon');
    expect(label).not.toMatch(/user_unknown/);
  });

  it('uses panel username when real', () => {
    expect(
      getSubscriptionDisplayLabel({ tariff_name: 'Moon', panel_username: 'mobile_x_1001' }, t),
    ).toBe('mobile_x_1001');
  });
});
```

- [x] **Step 2: Run test to verify it fails**

```bash
cd /opt/cabinet && npx vitest run src/utils/subscriptionDisplayLabel.test.ts
```

Expected: FAIL (module not found).

- [x] **Step 3: Implementation**

Create `/opt/cabinet/src/utils/subscriptionDisplayLabel.ts`:

```ts
export type SubscriptionLabelSource = {
  tariff_name?: string | null;
  panel_username?: string | null;
  account_sequence?: number | null;
};

const USER_UNKNOWN_PREFIX = 'user_unknown_';

export function getSubscriptionDisplayLabel(
  sub: SubscriptionLabelSource,
  t: (key: string, fallback: string) => string,
  isMultiTariff = false,
): string {
  let panel = (sub.panel_username ?? '').trim();
  if (panel.startsWith(USER_UNKNOWN_PREFIX)) {
    panel = '';
  }
  if (panel) return panel;

  const defaultName = t('subscription.defaultName', 'Подписка');
  if (isMultiTariff && sub.account_sequence) {
    return `${sub.tariff_name || defaultName} #${sub.account_sequence}`;
  }
  return sub.tariff_name || defaultName;
}
```

Copy `/opt/remnabot/cabinet/src/components/subscription/ConfigDeliverySheet.tsx` to `/opt/cabinet/src/components/subscription/ConfigDeliverySheet.tsx` unchanged (uses existing `@/components/primitives/Sheet` and `qrcode.react` already in 1.67).

In `/opt/cabinet/src/pages/Subscription.tsx`:

1. Import `ConfigDeliverySheet`, `useState` already present.
2. Add state: `const [configSheetOpen, setConfigSheetOpen] = useState(false);`
3. After the traffic block, if `usedGb === 0` (or `traffic_used_gb === 0`), render:

```tsx
<p className="mb-3 text-[11px] text-dark-50/40">{t('subscription.volumeEmptyHint')}</p>
```

4. Add first-connect checklist (once per detail view, above the connect button):

```tsx
<div className="mb-4 rounded-[14px] p-3 text-[12px] text-dark-50/70">
  <div className="mb-1 font-semibold">{t('subscription.firstConnectChecklist.title')}</div>
  <ul className="list-disc space-y-1 ps-4">
    <li>{t('subscription.firstConnectChecklist.step1')}</li>
    <li>{t('subscription.firstConnectChecklist.step2')}</li>
    <li>{t('subscription.firstConnectChecklist.step3')}</li>
  </ul>
</div>
```

5. Change the connect button `onClick` so it opens the sheet instead of only navigating:

```tsx
onClick={() => {
  if (isAtDeviceLimit) {
    haptic.notification('error');
    return;
  }
  setConfigSheetOpen(true);
}}
```

6. Mount at the end of the detail return (next to other sheets):

```tsx
<ConfigDeliverySheet
  open={configSheetOpen}
  onClose={() => setConfigSheetOpen(false)}
  configUrl={subscription.subscription_url}
  subscriptionId={subscription.id}
/>
```

In `SubscriptionListCard.tsx`, replace the title text `subscription.tariff_name || t('subscription.defaultName', ...)` with `getSubscriptionDisplayLabel(subscription, t)`.

- [x] **Step 4: Run tests + type-check**

```bash
cd /opt/cabinet && npx vitest run src/utils/subscriptionDisplayLabel.test.ts src/locales/fa-user-terminology.test.ts
cd /opt/cabinet && npm run type-check
```

Expected: tests PASS; `tsc` clean. If `ConfigDeliverySheet` fails types, fix only that file.

- [x] **Step 5: Commit**

```bash
cd /opt/cabinet
git add src/components/subscription/ConfigDeliverySheet.tsx src/utils/subscriptionDisplayLabel.ts src/utils/subscriptionDisplayLabel.test.ts src/pages/Subscription.tsx src/components/subscription/SubscriptionListCard.tsx src/locales/fa.json
git commit -m "$(cat <<'EOF'
feat(cabinet): first-connect sheet and subscription labels

EOF
)"
```

---

### Task 6: Agent verification + user smoke (STOP)

**Status:** **PASS** — operator `تایید` 2026-09-04 (joint Day-1 smoke).

**Files:** none required if Task 1–5 PASS.

- [x] **Step 1: Agent suite**

```bash
cd /opt/cabinet && npx vitest run src/i18n.defaults.test.ts src/utils/formatDate.test.ts src/utils/uiLocale.test.ts src/utils/ltrIsolate.test.ts src/components/subscription/TrafficUsageText.test.ts src/locales/fa-user-terminology.test.ts src/utils/subscriptionDisplayLabel.test.ts
cd /opt/cabinet && npm run type-check
cd /opt/cabinet && npx biome check src/i18n.ts src/utils/formatDate.ts src/utils/uiLocale.ts src/utils/ltrIsolate.tsx src/components/subscription/TrafficUsageText.tsx src/components/subscription/ConfigDeliverySheet.tsx src/utils/subscriptionDisplayLabel.ts src/pages/Subscription.tsx src/components/subscription/SubscriptionListCard.tsx
```

Expected: all PASS. If Biome fails, `npx biome check --write` on those files and amend **only if** the commit is yours, unpushed, and the hook modified files — otherwise a new commit `chore: biome Layer A`.

- [x] **Step 2: Recreate cabinet frontend only** (do not rebuild remnawave_bot)

```bash
cd /opt/cabinet && docker compose -f docker-compose.yml -f docker-compose.rc.yml up -d --build cabinet_frontend
```

Expected: container healthy; `GET https://panel.rookari.com/` still 200.

- [x] **Step 3: User smoke (STOP — user-visible)**

مسیر / انتظار:

1. مسیر: باز کردن `https://panel.rookari.com` بدون `cabinet_language` در localStorage (پنجرهٔ ناشناس). انتظار: اولین رنگ UI فارسی و راست‌به‌چپ است، نه روسی.
2. مسیر: ورود با تلگرام تست → اشتراک من. انتظار: تاریخ پایان شمسی با رقم انگلیسی (مثلاً `1405/...`)؛ حجم به صورت LTR؛ لینک کانفیگ از `https://` شروع می‌شود.
3. مسیر: دکمهٔ اتصال / دریافت کانفیگ. انتظار: شیت QR + کپی؛ متن «دستگاه» روی مسیر کاربر دیده نشود (تعداد کاربر / اتصال).

Operator replies `تایید` or `2 FAIL: …`.

Do **not** start M7 from this smoke. Layer C (`/sales`) stays a later plan.

---

## Spec coverage (self-review)

| Spec Layer A | Task |
|---|---|
| A1 fa + RTL html | Task 1 |
| A2 Jalali | Task 2 |
| A3 wording | Task 4 |
| A4 RTL isolate | Task 3 |
| A5 subscription UX | Task 5 (Disable sheet skipped — no API) |
| Layer B/C / M7 | Explicitly out of plan |

Placeholders: none. `applyTelegramLanguage` kept as a deprecated wrapper so `main.tsx` does not need a third commit.
