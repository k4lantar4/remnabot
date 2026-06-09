# fa-i18n Remaining Work Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all user-visible Persian gaps (cabinet UI, bot copy, code leaks), then admin/notify surfaces, with native Iranian UX terminology — zero Russian fallback on hot paths for `language=fa`.

**Architecture:** Locale-first: add missing keys to `cabinet/src/locales/fa.json` and `app/localization/locales/fa.json` (never bulk-edit `ru.json`). Guard with new `tests/test_cabinet_locale_integrity.py`. Copywriting is locale-only commits. Code leaks fixed by replacing hardcoded Cyrillic restriction strings with `texts.t('USER_RESTRICTION_DEFAULT_REASON', ...)`. One namespace (or one copywriting slice) per commit. Deploy bot locales via `cp app/localization/locales/fa.json ./locales/fa.json` + restart; cabinet via `npm run build`.

**Tech Stack:** Python 3, pytest, aiogram, FastAPI cabinet, React 18, react-i18next, `fa.json`, Docker smoke (`import main`).

**Living status:** `.cursor/rules/fa-i18n-status.mdc` — update after each task.

**Audit outline:** `docs/superpowers/plans/2026-06-09-fa-i18n-remaining.md`

**User priority order:** P1 UI → P2 admin/notify → P3 copywriting → P4 edge cases.

---

## File map

| File | Responsibility |
|------|----------------|
| `cabinet/src/locales/fa.json` | Cabinet UI strings (nested i18next) — **322 user keys missing** |
| `cabinet/src/locales/ru.json` | Source of truth for cabinet key set (read-only) |
| `app/localization/locales/fa.json` | Bot + miniapp flat keys — complete; copywriting edits here |
| `tests/test_cabinet_locale_integrity.py` | **Create** — parity + no-Cyrillic guards for cabinet fa |
| `tests/test_restriction_fallback.py` | **Create** — no bare hardcoded restriction reason outside `texts.t` fallback |
| `app/handlers/balance/*.py` | Restriction fallback leaks (~20 files) |
| `app/plugins/c2c/handlers/user.py` | Restriction fallback (×2) |
| `app/plugins/c2c/integration.py` | Restriction fallback (×1) |
| `.cursor/rules/fa-i18n-status.mdc` | Living status — append Done/Next per task |

**Out of scope (separate plans):** email templates (`docs/superpowers/plans/2026-06-06-fa-i18n-cabinet-email.md`), FX/currency, `app/handlers/balance/**` payment wiring.

---

## Baseline (run once before Task 1)

```bash
cd /opt/bot-remnawave
git checkout -b i18n/fa-remaining
python3 << 'PY'
import json
from pathlib import Path
def flat(d,p=''):
  for k,v in d.items():
    key=f'{p}.{k}' if p else k
    if isinstance(v,dict): yield from flat(v,key)
    else: yield key
ru=set(flat(json.loads(Path('cabinet/src/locales/ru.json').read_text())))
fa=set(flat(json.loads(Path('cabinet/src/locales/fa.json').read_text())))
user=[k for k in ru-fa if not k.startswith('admin.')]
print('cabinet user missing:', len(user))
PY
# Expected: cabinet user missing: 322
```

**Optional gate (user approval):** merge `i18n/fa-jalali-dates` and `i18n/p1-remainder-b` before starting if not already on `main`.

---

### Task 1: Cabinet locale integrity test

**Files:**
- Create: `tests/test_cabinet_locale_integrity.py`
- Reference: `tests/test_locale_integrity.py` (bot pattern)

- [ ] **Step 1: Write the failing test**

```python
"""Cabinet locale guards — missing fa keys fall back to Russian in the UI."""

import json
import re
from pathlib import Path

import pytest

CABINET_LOCALES = Path(__file__).resolve().parents[1] / 'cabinet' / 'src' / 'locales'
CYRILLIC_RE = re.compile(r'[А-Яа-яЁё]')
# User-visible namespaces — admin.* excluded from Cyrillic scan
USER_PREFIXES = (
    'subscription.', 'gift.', 'dashboard.', 'notifications.', 'resetPassword.',
    'balance.', 'support.', 'landing.', 'wheel.', 'promo.', 'news.', 'banSystem.',
)


def _flatten(d: dict, prefix: str = '') -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


@pytest.fixture(scope='module')
def cabinet_locales():
    ru = json.loads((CABINET_LOCALES / 'ru.json').read_text(encoding='utf-8'))
    fa = json.loads((CABINET_LOCALES / 'fa.json').read_text(encoding='utf-8'))
    return {'ru': _flatten(ru), 'fa': _flatten(fa)}


def test_cabinet_fa_has_all_ru_keys(cabinet_locales):
    ru_keys = set(cabinet_locales['ru'])
    fa_keys = set(cabinet_locales['fa'])
    missing = sorted(ru_keys - fa_keys)
    assert not missing, (
        f'fa.json missing {len(missing)} keys vs ru (UI falls back to Russian). '
        f'First 20: {missing[:20]}'
    )


def test_cabinet_user_fa_has_no_cyrillic(cabinet_locales):
    problems = []
    for key, val in cabinet_locales['fa'].items():
        if key.startswith('admin.'):
            continue
        if not any(key.startswith(p) for p in USER_PREFIXES):
            continue
        if isinstance(val, str) and CYRILLIC_RE.search(val):
            problems.append(f'{key}: {val[:60]}')
    assert not problems, 'Cyrillic in user-facing cabinet fa:\n' + '\n'.join(problems[:20])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cabinet_locale_integrity.py -v`
Expected: FAIL — `fa.json missing 912 keys` (or 322 if scoped to user-only — full parity test uses all ru keys)

- [ ] **Step 3: Commit test only**

```bash
git add tests/test_cabinet_locale_integrity.py
git commit -m "test(i18n): add cabinet fa locale integrity guards"
```

---

### Task 2: Cabinet `subscription.*` — 75 missing keys (P1)

**Files:**
- Modify: `cabinet/src/locales/fa.json` — under `subscription` object
- Test: `tests/test_cabinet_locale_integrity.py`

**Note:** Persian uses identical text for `_one` / `_few` / `_many` (no Russian-style declension). Keep `{{count}}` placeholders identical to `ru.json`.

- [ ] **Step 1: Add keys to `subscription` root** (insert after existing `"devices_other"` block ~line 312)

```json
    "devices_one": "{{count}} دستگاه",
    "devices_few": "{{count}} دستگاه",
    "devices_many": "{{count}} دستگاه",
    "servers_one": "{{count}} سرور",
    "servers_few": "{{count}} سرور",
    "servers_many": "{{count}} سرور",
    "locations_one": "{{count}} مکان",
    "locations_few": "{{count}} مکان",
    "locations_many": "{{count}} مکان",
    "days_one": "{{count}} روز",
    "days_few": "{{count}} روز",
    "days_many": "{{count}} روز",
    "hours_one": "{{count}} ساعت",
    "hours_few": "{{count}} ساعت",
    "hours_many": "{{count}} ساعت",
    "minutes_one": "{{count}} دقیقه",
    "minutes_few": "{{count}} دقیقه",
    "minutes_many": "{{count}} دقیقه",
    "daysBeforeExpiry_one": "{{count}} روز تا پایان اشتراک",
    "daysBeforeExpiry_few": "{{count}} روز تا پایان اشتراک",
    "daysBeforeExpiry_many": "{{count}} روز تا پایان اشتراک",
    "devicesFree_one": "{{count}} دستگاه رایگان",
    "devicesFree_few": "{{count}} دستگاه رایگان",
    "devicesFree_many": "{{count}} دستگاه رایگان",
    "extraDevicesIncluded_one": "شامل {{count}} دستگاه اضافی",
    "extraDevicesIncluded_few": "شامل {{count}} دستگاه اضافی",
    "extraDevicesIncluded_many": "شامل {{count}} دستگاه اضافی",
    "connectedAt": "زمان اتصال",
    "allDevicesDeleted": "همه دستگاه‌ها حذف شدند",
    "deviceDeleted": "دستگاه حذف شد",
    "model": "مدل",
    "platform": "پلتفرم",
    "insufficientBalance": "موجودی کافی نیست. {{missing}} تومان کم دارید"
```

- [ ] **Step 2: Add keys under `subscription.additionalOptions`** (inside existing object ~line 422)

```json
      "alreadyAtMinDeviceLimit": "به حداقل مجاز دستگاه برای سرویس شما رسیده‌اید",
      "connectedDevices_one": "دستگاه متصل: {{count}}",
      "connectedDevices_few": "دستگاه متصل: {{count}}",
      "connectedDevices_many": "دستگاه متصل: {{count}}",
      "currentDeviceLimit_one": "محدودیت فعلی: {{count}} دستگاه",
      "currentDeviceLimit_few": "محدودیت فعلی: {{count}} دستگاه",
      "currentDeviceLimit_many": "محدودیت فعلی: {{count}} دستگاه",
      "disconnectDevicesFirst_one": "ابتدا دستگاه‌ها را قطع کنید تا محدودیت کمتر از {{count}} دستگاه شود",
      "disconnectDevicesFirst_few": "ابتدا دستگاه‌ها را قطع کنید تا محدودیت کمتر از {{count}} دستگاه شود",
      "disconnectDevicesFirst_many": "ابتدا دستگاه‌ها را قطع کنید تا محدودیت کمتر از {{count}} دستگاه شود",
      "minDeviceLimit_one": "حداقل سرویس: {{count}} دستگاه",
      "minDeviceLimit_few": "حداقل سرویس: {{count}} دستگاه",
      "minDeviceLimit_many": "حداقل سرویس: {{count}} دستگاه",
      "newDeviceLimit_one": "محدودیت جدید: {{count}} دستگاه",
      "newDeviceLimit_few": "محدودیت جدید: {{count}} دستگاه",
      "newDeviceLimit_many": "محدودیت جدید: {{count}} دستگاه"
```

- [ ] **Step 3: Add `subscription.connection.instructions`**

Under `subscription.connection` add:
```json
      "instructions": "راهنمای اتصال"
```

- [ ] **Step 4: Add `subscription.pause` object** (new sibling under `subscription`)

```json
    "pause": {
      "dailyOnly": "توقف فقط برای سرویس روزانه فعال است",
      "days_one": "{{count}} روز",
      "days_few": "{{count}} روز",
      "days_many": "{{count}} روز",
      "pausedMessage": "اشتراک متوقف شد",
      "resumedMessage": "اشتراک از سر گرفته شد"
    },
```

- [ ] **Step 5: Add `subscription.switchTariff` missing keys**

Under existing `switchTariff` add:
```json
      "notEnoughBalance": "موجودی کافی نیست",
      "preview": "پیش‌نمایش",
      "switched": "سرویس تغییر کرد"
```

- [ ] **Step 6: Add `subscription.switchTraffic` object** (new under `subscription`)

```json
    "switchTraffic": {
      "title": "تغییر حجم ترافیک",
      "currentPackage": "بسته فعلی",
      "newPackage": "بسته جدید",
      "switch": "تغییر",
      "switched": "ترافیک تغییر کرد"
    },
```

- [ ] **Step 7: Add `subscription.trial` + `trialBanner` + `trialInfo`**

```json
    "trial": {
      "days_one": "{{count}} روز",
      "days_few": "{{count}} روز",
      "days_many": "{{count}} روز",
      "devices_one": "{{count}} دستگاه",
      "devices_few": "{{count}} دستگاه",
      "devices_many": "{{count}} دستگاه",
      "titlePaid": "اشتراک آزمایشی"
    },
    "trialBanner": {
      "title": "دوره آزمایشی فعال است",
      "description": "{{days}} روز از دوره آزمایشی باقی مانده. برای ادامه استفاده، اشتراک تهیه کنید.",
      "upgrade": "انتخاب سرویس"
    },
    "trialInfo": {
      "upgradeNow": "انتخاب سرویس"
    },
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/test_cabinet_locale_integrity.py::test_cabinet_fa_has_all_ru_keys -v`
Expected: FAIL with fewer missing keys (912 → 837)

Run: `cd cabinet && npm run build`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add cabinet/src/locales/fa.json
git commit -m "i18n(fa): add cabinet subscription namespace (75 keys)"
```

---

### Task 3: Cabinet `gift` + `dashboard` + `notifications` (37 keys, P1)

**Files:**
- Modify: `cabinet/src/locales/fa.json`
- Test: `tests/test_cabinet_locale_integrity.py`

- [ ] **Step 1: Add `gift` keys** (find `gift` section or create at root)

```json
  "gift": {
    "activating": "در حال فعال‌سازی…",
    "codeCopied": "کد کپی شد!",
    "copyCode": "کپی کد",
    "deviceCount_one": "{{count}} دستگاه",
    "deviceCount_few": "{{count}} دستگاه",
    "deviceCount_many": "{{count}} دستگاه",
    "devicesShort_one": "دستگاه",
    "devicesShort_few": "دستگاه",
    "devicesShort_many": "دستگاه",
    "sentGiftsTitle": "هدایای ارسالی",
    "sharePreview": "پیام برای ارسال",
    "statusDelivered": "تحویل شد",
    "statusExpired": "منقضی شد",
    "statusFailed": "ناموفق",
    "statusPending": "در انتظار",
    "statusPendingActivation": "در انتظار فعال‌سازی"
  },
```

- [ ] **Step 2: Add `dashboard` keys**

```json
  "dashboard": {
    "daysRemaining": "روز باقی‌مانده",
    "devicesConnected": "{{count}} متصل",
    "devicesShort": "دستگاه",
    "expired": {
      "expiredDate_trial": "منقضی شد"
    },
    "stats": {
      "earnings": "درآمد",
      "subscription": "اشتراک"
    },
    "trafficUsage": "{{used}} / {{limit}} گیگ",
    "usedTraffic": "{{amount}} مصرف شده",
    "zone": {
      "critical": "بحرانی",
      "danger": "بالا",
      "normal": "عادی",
      "warning": "متوسط"
    }
  },
```

- [ ] **Step 3: Add `notifications` keys**

```json
  "notifications": {
    "daysAgo_one": "{{count}} روز پیش",
    "daysAgo_few": "{{count}} روز پیش",
    "daysAgo_many": "{{count}} روز پیش",
    "hoursAgo_one": "{{count}} ساعت پیش",
    "hoursAgo_few": "{{count}} ساعت پیش",
    "hoursAgo_many": "{{count}} ساعت پیش",
    "minutesAgo_one": "{{count}} دقیقه پیش",
    "minutesAgo_few": "{{count}} دقیقه پیش",
    "minutesAgo_many": "{{count}} دقیقه پیش"
  },
```

- [ ] **Step 4: Run tests + build**

Run: `pytest tests/test_cabinet_locale_integrity.py -v`
Run: `cd cabinet && npm run build`

- [ ] **Step 5: Commit**

```bash
git add cabinet/src/locales/fa.json
git commit -m "i18n(fa): add cabinet gift, dashboard, notifications keys"
```

---

### Task 4: Cabinet `resetPassword` + `balance` + `support` (25 keys, P1)

**Files:**
- Modify: `cabinet/src/locales/fa.json`

- [ ] **Step 1: Add keys**

```json
  "resetPassword": {
    "enterNewPassword": "رمز عبور جدید را در زیر وارد کنید.",
    "invalidToken": "لینک نامعتبر است",
    "redirectingToLogin": "در حال انتقال به صفحه ورود…",
    "setPassword": "تنظیم رمز عبور",
    "success": "رمز عبور تغییر کرد!",
    "title": "رمز عبور جدید",
    "tokenExpiredOrInvalid": "لینک بازیابی رمز عبور نامعتبر یا منقضی شده است."
  },
```

Under existing `balance` add:
```json
    "paymentOption": "روش پرداخت",
    "selectPaymentOption": "روش پرداخت را انتخاب کنید",
    "paymentMethods": {
      "aurapay": { "description": "پرداخت از طریق AuraPay" },
      "cloudpayments": { "description": "پرداخت با کارت بانکی از طریق CloudPayments" },
      "freekassa": { "description": "پرداخت از طریق FreeKassa" },
      "freekassa_card": { "description": "پرداخت با کارت" },
      "freekassa_sbp": { "description": "پرداخت با QR" },
      "heleket": { "description": "پرداخت رمزارز از طریق Heleket" },
      "kassa_ai": { "description": "پرداخت از طریق Kassa AI" },
      "mulenpay": { "description": "پرداخت از طریق MulenPay" },
      "pal24": { "description": "پرداخت از طریق PAL24" },
      "paypear": { "description": "پرداخت از طریق PayPear" },
      "platega": { "description": "پرداخت از طریق Platega" },
      "riopay": { "description": "پرداخت از طریق RioPay" },
      "rollypay": { "description": "پرداخت از طریق RollyPay" },
      "wata": { "description": "پرداخت از طریق Wata" }
    }
```

```json
  "support": {
    "goToProfile": "رفتن به پروفایل",
    "useProfile": "برای دریافت پشتیبانی به پروفایل ربات بروید"
  },
```

- [ ] **Step 2: Verify user-key count**

```bash
python3 << 'PY'
import json
from pathlib import Path
def flat(d,p=''):
  for k,v in d.items():
    key=f'{p}.{k}' if p else k
    if isinstance(v,dict): yield from flat(v,key)
    else: yield key
ru=set(flat(json.loads(Path('cabinet/src/locales/ru.json').read_text())))
fa=set(flat(json.loads(Path('cabinet/src/locales/fa.json').read_text())))
user=[k for k in ru-fa if not k.startswith('admin.')]
print('user missing:', len(user))
PY
```
Expected: `user missing: 0` (or only `banSystem.*` / `landing.*` / secondary if not yet done)

- [ ] **Step 3: Commit**

```bash
git add cabinet/src/locales/fa.json
git commit -m "i18n(fa): complete cabinet user-facing locale keys"
```

---

### Task 5: Copywriting — «خرید ساده» → «خرید سرویس» (P3)

**Files:**
- Modify: `app/localization/locales/fa.json`
- Modify: `cabinet/src/locales/fa.json` — `admin.settings.subs_simple` if present

- [ ] **Step 1: Update bot keys in `app/localization/locales/fa.json`**

| Key | New value |
|-----|-----------|
| `MENU_SIMPLE_SUBSCRIPTION` | `⚡ خرید سرویس` |
| `SIMPLE_SUBSCRIPTION_TITLE` | `⚡ <b>خرید سرویس</b>` |
| `CB_SIMPLE_SUB_UNAVAILABLE` | `❌ خرید سرویس موقتاً در دسترس نیست` |
| `SIMPLE_SUB_CONFIRM_ACTIVE_PAID_WARNING` | `⚠️ اشتراک پولی فعال دارید. خرید سرویس پارامترهای اشتراک فعلی را تغییر می‌دهد. تأیید لازم است.` |
| `SIMPLE_SUB_PAYMENT_STARS_DESCRIPTION` | `خرید سرویس\nدوره: {days} روز\nدستگاه: {devices}\nترافیک: {traffic}` |

- [ ] **Step 2: Update cabinet admin label**

In `cabinet/src/locales/fa.json` find `subs_simple` and set to `"خرید سرویس"`.

- [ ] **Step 3: Smoke**

```bash
docker compose run --rm --no-deps bot python -c "import main"
cp app/localization/locales/fa.json ./locales/fa.json
grep -c 'خرید ساده' app/localization/locales/fa.json
```
Expected: `0`

- [ ] **Step 4: Commit**

```bash
git add app/localization/locales/fa.json cabinet/src/locales/fa.json
git commit -m "i18n(fa): rename خرید ساده to خرید سرویس"
```

---

### Task 6: Copywriting — revoke/reissue labels (P3)

**Files:**
- Modify: `app/localization/locales/fa.json`
- Modify: `cabinet/src/locales/fa.json` — `subscription.revoke`

**Decision (per user):** Button = `🔄 صدور مجدد لینک`; longer action = `تغییر لینک و قطع دستگاه‌ها` in warning body where appropriate.

- [ ] **Step 1: Update bot keys**

| Key | New value |
|-----|-----------|
| `MY_SUB_BTN_REISSUE` | `🔄 صدور مجدد لینک` |
| `SUBSCRIPTION_REVOKE_BTN` | `🔄 صدور مجدد لینک` |
| `SUBSCRIPTION_REVOKE_TITLE` | `⚠️ صدور مجدد لینک اتصال` |
| `SUBSCRIPTION_REVOKE_WARNING` | `⚠️ <b>تغییر لینک و قطع دسترسی</b>\n\nاین عمل:\n• لینک اتصال جدیدی تولید می‌کند\n• تمام دستگاه‌های متصل قطع می‌شوند\n• لینک قدیمی دیگر کار نخواهد کرد\n\nادامه می‌دهید؟` |
| `SUBSCRIPTION_REVOKE_SUCCESS` | (keep — already clear) |
| `SUBSCRIPTION_REVOKE_COOLDOWN` | `⏱ صدور مجدد لینک {minutes} دقیقه و {seconds} ثانیه دیگر در دسترس است.` |
| `SUBSCRIPTION_REVOKE_DISABLED` | `صدور مجدد لینک در دسترس نیست` |
| `SUBSCRIPTION_REVOKE_ERROR` | `❌ خطا در صدور مجدد لینک. لطفاً بعداً دوباره امتحان کنید.` |

- [ ] **Step 2: Update cabinet `subscription.revoke`**

```json
    "revoke": {
      "title": "صدور مجدد لینک اتصال",
      "button": "صدور مجدد لینک",
      "description": "لینک جدید صادر می‌شود و همه دستگاه‌ها قطع می‌شوند",
      "warning": "لینک اتصال جدید صادر می‌شود، همه دستگاه‌های متصل قطع می‌شوند و لینک قبلی نامعتبر می‌شود. ادامه می‌دهید؟",
      "confirmBtn": "تغییر لینک و قطع دستگاه‌ها",
      "cooldown": "صدور مجدد لینک تا {{minutes}} دقیقه و {{seconds}} ثانیه دیگر"
    },
```

- [ ] **Step 3: Commit + deploy copy**

```bash
git add app/localization/locales/fa.json cabinet/src/locales/fa.json
git commit -m "i18n(fa): clarify revoke/reissue labels for Persian UX"
cp app/localization/locales/fa.json ./locales/fa.json
```

---

### Task 7: Copywriting — user-facing «تعرفه» → «سرویس» (P3, scoped)

**Files:**
- Modify: `app/localization/locales/fa.json` — **user keys only** (not `ADMIN_*`)
- Modify: `cabinet/src/locales/fa.json` — user `subscription.*` / `landing.*`

- [ ] **Step 1: Update bot user keys (grep-scoped list)**

```bash
cd /opt/bot-remnawave
python3 << 'PY'
import json, re
from pathlib import Path
fa = json.loads(Path('app/localization/locales/fa.json').read_text())
USER_PREFIXES = ('TARIFF_', 'CHANGE_TARIFF_', 'MENU_', 'MY_SUB_', 'SUBSCRIPTION_', 'CB_TARIFF', 'CB_NO_TARIFF', 'MSG_TARIFF', 'NOT_DAILY', 'AUTOPAY_', 'DAILY_', 'CAMPAIGN_BONUS_TARIFF', 'MINIAPP_TARIFF')
for k,v in sorted(fa.items()):
    if k.startswith('ADMIN_'): continue
    if 'تعرفه' in str(v) and any(k.startswith(p) for p in USER_PREFIXES):
        print(k)
PY
```

Replace `تعرفه` → `سرویس` in each printed key. **Minimum set:**

| Key | New value (example) |
|-----|---------------------|
| `CHANGE_TARIFF_BUTTON` | `📦 سرویس` |
| `TARIFF_SELECT_TITLE` | `📦 <b>سرویس را انتخاب کنید</b>` |
| `TARIFF_NO_AVAILABLE` | `😔 <b>سرویسی موجود نیست</b>\n\nمتأسفانه اکنون سرویسی برای خرید وجود ندارد.` |
| `MY_SUB_BTN_BUY_ANOTHER` | `خرید سرویس جدید` |
| `SUBSCRIPTION_SELECT_TARIFF_BUTTON` | `📦 انتخاب سرویس` |

- [ ] **Step 2: Update cabinet user strings**

In `subscription.legacy`, `switchTariff`, `chooseDifferentTariff` — replace `تعرفه` with `سرویس` where user-visible.

- [ ] **Step 3: Verify no user-facing «تعرفه» on hot paths**

```bash
grep -n 'تعرفه' app/localization/locales/fa.json | grep -v ADMIN_ | head -20
```
Review output — admin keys may keep `تعرفه`.

- [ ] **Step 4: Commit**

```bash
git add app/localization/locales/fa.json cabinet/src/locales/fa.json
git commit -m "i18n(fa): user-facing تعرفه to سرویس copywriting"
```

---

### Task 8: Restriction fallback code leak + test (P4)

**Files:**
- Create: `tests/test_restriction_fallback.py`
- Modify: `app/plugins/c2c/handlers/user.py`
- Modify: `app/plugins/c2c/integration.py`
- Modify: all `app/handlers/balance/*.py` with bare hardcode (see Step 3)

- [ ] **Step 1: Write the failing test**

```python
"""No bare Russian restriction reason outside texts.t() fallback argument."""

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / 'app'
BARE = re.compile(
    r"getattr\(db_user,\s*'restriction_reason',\s*None\)\s*or\s*'Действие ограничено администратором'"
)
# texts.t(..., 'Действие...') as second arg is OK
ALLOWED = re.compile(r"texts\.t\(\s*'USER_RESTRICTION_DEFAULT_REASON'")


def test_no_bare_restriction_reason_hardcode():
    offenders = []
    for path in APP.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        if BARE.search(text) and not ALLOWED.search(text):
            # allow if every match is inside texts.t fallback — simplify: flag file
            for i, line in enumerate(text.splitlines(), 1):
                if BARE.search(line) and 'texts.t(' not in line:
                    offenders.append(f'{path.relative_to(APP.parent)}:{i}')
    assert not offenders, 'Bare restriction hardcode:\n' + '\n'.join(offenders)
```

- [ ] **Step 2: Run test — verify FAIL**

Run: `pytest tests/test_restriction_fallback.py -v`
Expected: FAIL listing `app/plugins/c2c/handlers/user.py`, `app/handlers/balance/yookassa.py`, etc.

- [ ] **Step 3: Fix pattern in each offender**

Replace:
```python
reason = html.escape(getattr(db_user, 'restriction_reason', None) or 'Действие ограничено администратором')
```

With (ensure `texts = get_texts(db_user.language)` exists above):
```python
reason = html.escape(
    getattr(db_user, 'restriction_reason', None)
    or texts.t('USER_RESTRICTION_DEFAULT_REASON', 'Действие ограничено администратором')
)
```

**Reference (already correct):** `app/handlers/balance/main.py:349`, `app/handlers/subscription/purchase.py:884`.

Files to fix (run to list):
```bash
rg -l "getattr\(db_user, 'restriction_reason', None\) or 'Действие ограничено администратором'" app/
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_restriction_fallback.py tests/test_locale_integrity.py -v`
Run: `docker compose run --rm --no-deps bot python -c "import main"`

- [ ] **Step 5: Commit**

```bash
git add tests/test_restriction_fallback.py app/plugins/c2c/ app/handlers/balance/
git commit -m "i18n(fa): route restriction fallback through USER_RESTRICTION_DEFAULT_REASON"
```

---

### Task 9: P2 — `banSystem` user-visible messages (148 keys, if feature enabled)

**Files:**
- Modify: `cabinet/src/locales/fa.json`

**Gate:** Only execute if ban system is enabled in production `.env`.

- [ ] **Step 1: List missing banSystem keys**

```bash
python3 << 'PY'
import json
from pathlib import Path
def flat(d,p=''):
  for k,v in d.items():
    key=f'{p}.{k}' if p else k
    if isinstance(v,dict): yield from flat(v,key)
    else: yield key,v
ru=dict(flat(json.loads(Path('cabinet/src/locales/ru.json').read_text())))
fa=set(flat(json.loads(Path('cabinet/src/locales/fa.json').read_text())))
for k in sorted(ru):
    if k.startswith('banSystem.') and k not in fa:
        print(k)
PY
```

- [ ] **Step 2: Add Persian translations** (batch by subsection: `banSystem.user`, `banSystem.admin`, …) — one commit per subsection, max ~50 keys per commit.

- [ ] **Step 3: Commit each subsection**

```bash
git commit -m "i18n(fa): add cabinet banSystem.<section> keys"
```

---

### Task 10: P2 — Cabinet admin `admin.settings` (485 keys, chunked)

**Files:**
- Modify: `cabinet/src/locales/fa.json`

**Approach:** Use helper script to merge missing keys with machine-assisted Persian from `ru` values — human review required for admin terminology.

- [ ] **Step 1: Generate missing key report**

```bash
python3 << 'PY'
import json
from pathlib import Path
def flat(d,p=''):
  for k,v in d.items():
    key=f'{p}.{k}' if p else k
    if isinstance(v,dict): yield from flat(v,key)
    else: yield key,v
ru=dict(flat(json.loads(Path('cabinet/src/locales/ru.json').read_text())))
fa=set(flat(json.loads(Path('cabinet/src/locales/fa.json').read_text())))
missing=[k for k in sorted(ru) if k.startswith('admin.settings.') and k not in fa]
print(len(missing), 'admin.settings keys missing')
PY
```

- [ ] **Step 2: Translate in chunks of ~80 keys** — 6 commits. Keep `admin.*` using `تعرفه`/`سرور` consistently with P3 admin copy (نود → سرور).

- [ ] **Step 3: After all chunks, full parity test passes**

Run: `pytest tests/test_cabinet_locale_integrity.py -v`
Expected: PASS (0 missing keys)

---

### Task 11: P2 — Bot admin «نود» → «سرور» + edge fix (P4)

**Files:**
- Modify: `app/localization/locales/fa.json`

- [ ] **Step 1: Update admin node keys**

| Key | New value |
|-----|-----------|
| `ADMIN_MAINTENANCE_PANEL_NODES` | `🖥️ سرور آنلاین: {online}/{total}` |
| `ADMIN_REMNAWAVE_MANAGE_NODES` | `🖥️ مدیریت سرورها` |
| `ADMIN_RW_NODES_EMPTY` | `🖥️ سروری یافت نشد یا خطای اتصال` |
| `ADMIN_RW_NODES_TITLE` | `🖥️ <b>مدیریت سرورها</b>` |
| `ADMIN_RW_NODE_ACTION_OK` | `✅ سرور {action}` |
| `ADMIN_SUBS_BTN_NODES` | `📊 آمار سرورها` |
| `ADMIN_RW_NODE_NOT_FOUND` | `❌ سرور یافت نشد` |

- [ ] **Step 2: Commit + deploy**

```bash
git add app/localization/locales/fa.json
git commit -m "i18n(fa): admin نود to سرور terminology"
cp app/localization/locales/fa.json ./locales/fa.json
```

---

### Task 12: Update living status doc

**Files:**
- Modify: `.cursor/rules/fa-i18n-status.mdc`

- [ ] **Step 1: Append Done section**

```markdown
## Done (fa-remaining — Jun 9 2026)

- [x] Cabinet locale integrity test
- [x] P1 cabinet user keys (subscription, gift, dashboard, notifications, resetPassword, balance, support)
- [x] P3 copywriting: خرید سرویس, revoke labels, user-facing سرویس
- [x] P4 restriction fallback sweep
- [x] P2 banSystem (if enabled) / admin.settings chunks
- [x] P2 admin نود → سرور
```

- [ ] **Step 2: Commit**

```bash
git add .cursor/rules/fa-i18n-status.mdc
git commit -m "docs(i18n): update fa-i18n-status after remaining work"
```

---

## Final smoke checklist

```bash
pytest tests/test_cabinet_locale_integrity.py tests/test_restriction_fallback.py tests/test_locale_integrity.py -v
docker compose run --rm --no-deps bot python -c "import main"
cp app/localization/locales/fa.json ./locales/fa.json
docker compose restart bot
cd cabinet && npm run build
grep -r get_admin_texts app/   # must be 0
```

**Manual smoke (fa user):**
1. منوی ربات → «خرید سرویس» (نه خرید ساده)
2. اشتراک‌های من → دکمه «صدور مجدد لینک»
3. کابینت → صفحه Subscription → trial banner، switch traffic، device plurals — همه فارسی
4. محدودیت top-up (اگر فعال) → پیام فارسی نه روسی

---

## Self-review

| Spec requirement | Task |
|------------------|------|
| P1 user UI cabinet keys | Tasks 2–4 |
| P1 code leaks | Task 8 |
| P2 admin + notify | Tasks 9–11 |
| P3 copywriting | Tasks 5–7 |
| P4 edge cases | Tasks 8, 11 |
| Tests / TDD | Tasks 1, 8 |
| Status doc update | Task 12 |
| Email templates | Out of scope — separate plan |
| Pending branch merges | Baseline optional gate |

**Placeholder scan:** No TBD steps — all keys and code patterns specified.
