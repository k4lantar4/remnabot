# fa-i18n P1 — User Surfaces (Bot, Cabinet, Miniapp) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate user-visible raw Russian text for `language=fa` on Bot UX, Cabinet web, and Mini App API — without structural refactors, payment-provider changes, or admin-panel scope.

**Architecture:** Reuse existing `get_texts(user.language).t('KEY', 'ru fallback')` in handlers/keyboards; add missing Persian strings only in `app/localization/locales/fa.json` (never bulk-edit `ru.json`). Cabinet routes gain the same pattern via `get_texts(user.language)` on `HTTPException.detail` and JSON `message` fields. One handler/route file (+ `fa.json` if needed) per commit per `localization-upstream.mdc`. Cyrillic stays in code fallbacks (second `t()` argument).

**Tech Stack:** Python 3, aiogram handlers, FastAPI cabinet routes, `app/localization/texts.py`, `fa.json`, Docker smoke (`import main`).

**Related plans (out of scope here — separate branches):**
- `docs/superpowers/plans/2026-06-06-fa-i18n-p2-admin-bot.md` (Admin Telegram + cabinet admin)
- `docs/superpowers/plans/2026-06-06-fa-i18n-cabinet-email.md` (email templates ru/uk → fa)

---

## Prerequisites

### Branch & baseline

- [ ] **Step 1:** Create feature branch from `main`

```bash
git checkout main
git pull remnabot main   # if remote available
git checkout -b i18n/p1-user-surfaces
```

- [ ] **Step 2:** Record baseline breakage count (user surfaces only)

```bash
cd /opt/bot-remnawave
python3 << 'PYEOF'
import re, json, os
from pathlib import Path

CYR = re.compile(r'[А-Яа-яЁё]')
with open('app/localization/locales/fa.json') as f:
    fa = set(json.load(f).keys()) if False else None
# flatten fa keys
def flat(d, p=''):
    for k,v in d.items():
        key = f"{p}.{k}" if p else k
        if isinstance(v, dict): yield from flat(v, key)
        else: yield key
with open('app/localization/locales/fa.json') as f:
    import json as J
    data = J.load(f)
fa_keys = set(flat(data))

def scan(root, skip_admin=False, skip_balance=False):
    n = 0
    for fp in Path(root).rglob('*.py'):
        rel = str(fp)
        if skip_admin and '/admin/' in rel: continue
        if skip_balance and '/balance/' in rel: continue
        if 'admin_' in fp.name: continue
        for i, line in enumerate(fp.read_text().splitlines(), 1):
            if not CYR.search(line): continue
            if 'logger' in line or line.strip().startswith('#'): continue
            m = re.search(r"texts\.t\(\s*['\"]([^'\"]+)['\"]", line)
            if m and m.group(1) in fa_keys: continue
            if 'texts.t(' in line:
                m2 = re.search(r"texts\.t\(\s*['\"]([^'\"]+)['\"]", line)
                if m2 and m2.group(1) in fa_keys: continue
            # still cyrillic visible if no fa key
            if 'texts.t(' in line:
                m3 = re.search(r"texts\.t\(\s*['\"]([^'\"]+)['\"]", line)
                if m3 and m3.group(1) not in fa_keys:
                    n += 1; continue
            if not re.search(r"f?['\"][^'\"]*[А-Яа-яЁё]", line): continue
            n += 1
    return n

print('P1 bot handlers:', scan('app/handlers', skip_admin=True, skip_balance=True))
print('P1 keyboards (non-admin):', scan('app/keyboards') - scan('app/keyboards/admin.py'))
print('P1 cabinet user:', scan('app/cabinet'))
PYEOF
```

Expected: non-zero counts; save output in PR description for before/after comparison.

### Rules (do not violate)

| Rule file | Constraint |
|-----------|------------|
| `localization-upstream.mdc` | Max **one** handler/keyboard/route file + `fa.json` per commit |
| `user-surface-parity.mdc` | Price/balance user strings: touch bot **and** cabinet **and** miniapp in same slice |
| `currency-display-toman.mdc` | Use `texts.format_price` / `settings.format_price`; no new `₽` in user strings |
| `delivery-cycle.mdc` | Agent smoke after every commit; user Telegram/cabinet smoke before merge |
| Out of scope | `app/handlers/balance/**`, `app/services/payment/**`, admin handlers |

### Verification commands (every commit)

```bash
docker compose run --rm --no-deps bot python -c "import main"
grep -r get_admin_texts app/   # must output nothing
# if fa.json changed:
cp app/localization/locales/fa.json ./locales/fa.json
docker compose restart bot
```

### Per-file grep (find real breakage in one file)

Cyrillic in `texts.t` **fallback** is OK when the key exists in `fa.json`. Use:

```bash
FILE=app/handlers/subscription/purchase.py
rg -n '[А-Яа-яЁё]' "$FILE" | rg -v 'logger\.|#' 
# Manually skip lines where texts.t KEY is already in fa.json
```

---

## File map (P1 touch order)

| Phase | File | UI path | Est. breakage |
|-------|------|---------|---------------|
| A1 | `app/handlers/subscription/purchase.py` | Bot → کارت اشتراک / «Моя подписка» | ~80 hardcoded fragments (templates mostly keyed) |
| A2 | `app/handlers/subscription/tariff_purchase.py` | Bot → ویزارد خرید تعرفه | ~180 |
| A3 | `app/handlers/simple_subscription.py` | Bot → خرید ساده | ~230 |
| A4 | `app/handlers/menu.py` | Bot → منوی اصلی، اینفو، وضعیت | ~45 true hardcoded |
| B1 | `app/handlers/subscription/traffic.py` | Bot → ترافیک | ~70 |
| B2 | `app/handlers/subscription/devices.py` | Bot → دستگاه‌ها | ~110 |
| B3 | `app/handlers/subscription/countries.py` | Bot → کشورها | ~50 |
| B4 | `app/handlers/subscription/autopay.py` | Bot → اتوپей | ~20 |
| B5 | `app/handlers/subscription/links.py` + `happ.py` | Bot → اتصال / Happ | ~25 |
| B6 | `app/handlers/subscription/my_subscriptions.py` | Bot → لیست اشتراک | ~10 |
| B7 | `app/handlers/subscription/revoke.py` | Bot → перевыпуск | ~15 |
| B8 | `app/handlers/subscription/promo.py` | Bot → پرومو-آفر | ~18 |
| C1 | `app/handlers/referral.py` | Bot → رفرال (بدنه‌های پایین فایل) | ~40 |
| C2 | `app/handlers/start.py` | Bot → ثبت‌نام / هدیه | ~60 |
| C3 | `app/handlers/promocode.py` | Bot → پروموکد | ~11 |
| C4 | `app/handlers/tickets.py` | Bot → تیکت | ~25 |
| C5 | `app/handlers/common.py` | Bot → دستور نامعتبر | 2 |
| C6 | `app/handlers/stars_payments.py` | Bot → چرخ شانس | ~40 |
| D1 | `app/keyboards/inline.py` | Bot → دکمه‌های inline | ~15 user-visible (excl. language labels) |
| E1 | `app/cabinet/routes/subscription_modules/traffic.py` | Cabinet → ترافیک API | ~14 RU `detail=` |
| E2 | `app/cabinet/routes/subscription_modules/devices.py` | Cabinet → دستگاه API | ~25 |
| E3 | `app/cabinet/routes/subscription_modules/purchase.py` | Cabinet → خرید | ~15 |
| E4 | `app/cabinet/routes/subscription_modules/tariff_switch.py` | Cabinet → تعویض تعرفه | ~12 |
| E5 | `app/cabinet/routes/subscription_modules/renewal.py` | Cabinet → تمدید | ~3 |
| E6 | `app/cabinet/routes/balance.py` | Cabinet → وضعیت پرداخت | ~90 status labels |
| E7 | `app/cabinet/routes/wheel.py` | Cabinet → چرخ | ~9 |
| F1 | `app/webapi/routes/miniapp.py` | Miniapp → پیام success/error | ~40 user `message` strings |

---

## Phase A — Subscription hot path (Bot)

### Task 1: `purchase.py` — remaining hardcoded subscription card strings

**Files:**
- Modify: `app/handlers/subscription/purchase.py` (lines with Cyrillic **not** already covered by `fa.json` keys)
- Modify: `app/localization/locales/fa.json` (new keys only)
- Test: agent smoke (no pytest suite for handlers)

**Known gaps (examples — wire to new or existing keys):**

| Line area | Russian hardcode | Suggested key |
|-----------|------------------|---------------|
| ~281 | `\n🔴 истекает через несколько минут!` | `SUBSCRIPTION_WARNING_MINUTES` |
| ~294–299 | traffic display `ГБ`, `безлимит` | `SUBSCRIPTION_TRAFFIC_UNLIMITED_LINE`, `SUBSCRIPTION_TRAFFIC_LIMIT_LINE` |
| ~421, 451 | `Осталось:`, `До списания:` | `DAILY_TIME_UNTIL_CHARGE`, `DAILY_TIME_REMAINING` |
| ~595–599 | purchased traffic bullets | reuse `TRAFFIC_PURCHASED_*` family |
| ~617–621 | connection link block | `SUBSCRIPTION_CONNECT_LINK_*` |
| ~712+ | purchase wizard steps | prefix `PURCHASE_` |

- [ ] **Step 1: Inventory Cyrillic lines**

```bash
rg -n '[А-Яа-яЁё]' app/handlers/subscription/purchase.py | rg -v 'logger\.|#' > /tmp/purchase-cyr.txt
wc -l /tmp/purchase-cyr.txt
```

- [ ] **Step 2: Cross-check existing `fa.json` keys before adding**

```bash
rg -n 'SUBSCRIPTION_|TRAFFIC_|PURCHASE_|DAILY_' app/localization/locales/fa.json | head -40
```

- [ ] **Step 3: Add Persian keys to `fa.json`**

Example entries (extend for every new key):

```json
"SUBSCRIPTION_WARNING_MINUTES": "\n🔴 تا چند دقیقه دیگر منقضی می‌شود!",
"SUBSCRIPTION_TRAFFIC_UNLIMITED_LINE": "∞ (نامحدود) | مصرف‌شده: {used} گیگ",
"SUBSCRIPTION_TRAFFIC_LIMIT_LINE": "{used} / {limit} گیگ"
```

- [ ] **Step 4: Replace hardcoded strings in `purchase.py`**

Pattern (keep Cyrillic in second argument):

```python
warning_text = texts.t(
    'SUBSCRIPTION_WARNING_MINUTES',
    '\n🔴 истекает через несколько минут!',
)
```

For multi-line templates already using `texts.t('SUBSCRIPTION_OVERVIEW_TEMPLATE', ...)`: **no code change** — keys already Persian in `fa.json` (lines ~471–497).

- [ ] **Step 5: Agent smoke**

```bash
docker compose run --rm --no-deps bot python -c "import main"
```

Expected: exit 0, no `KeyError` on import.

- [ ] **Step 6: Commit**

```bash
git add app/handlers/subscription/purchase.py app/localization/locales/fa.json
git commit -m "$(cat <<'EOF'
i18n(fa): localize remaining purchase subscription card strings

Wire hardcoded Russian fragments on the subscription overview and purchase
flow to fa.json so Persian users never see Cyrillic on the hot path.
EOF
)"
```

- [ ] **Step 7: User smoke (owner)** — Telegram: open «Моя подписка» / purchase card; confirm Persian labels for traffic, devices, daily charge timer.

---

### Task 2: `tariff_purchase.py` — purchase confirmation & errors

**Files:**
- Modify: `app/handlers/subscription/tariff_purchase.py`
- Modify: `app/localization/locales/fa.json`

**Priority strings (lines ~671–733, ~1000+):**

```python
# Before (hardcoded):
'✅ <b>Подтверждение покупки</b>\n\n'
# After:
texts.t('TARIFF_PURCHASE_CONFIRM_HEADER', '✅ <b>Подтверждение покупки</b>\n\n')
```

```json
"TARIFF_PURCHASE_CONFIRM_HEADER": "✅ <b>تأیید خرید</b>\n\n",
"TARIFF_PURCHASE_CONFIRM_DAILY_BODY": "📦 تعرفه: <b>{name}</b>\n📊 ترافیک: {traffic}\n📱 دستگاه: {devices}\n🔄 نوع: <b>روزانه</b>\n\n💰 <b>قیمت: {price}/روز</b>{discount}\n\n💳 موجودی: {balance}\n\nℹ️ مبلغ روزانه به‌صورت خودکار کسر می‌شود.\nمی‌توانید هر زمان اشتراک را متوقف کنید.",
"TARIFF_PURCHASE_INSUFFICIENT_FUNDS": "❌ <b>موجودی کافی نیست</b>\n\n",
"TARIFF_PURCHASE_CART_SAVED": "🛒 <i>سبد ذخیره شد! پس از شارژ، اشتراک خودکار فعال می‌شود.</i>"
```

- [ ] **Step 1:** `rg -n '[А-Яа-яЁё]' app/handlers/subscription/tariff_purchase.py | rg -v 'logger|#'`
- [ ] **Step 2:** Add keys to `fa.json` (mirror `{name}`, `{traffic}`, `{price}` placeholders from `ru.json` if keys exist there)
- [ ] **Step 3:** Replace each hardcoded user message with `texts.t(...)`; preserve `callback.answer()` **before** slow I/O per `telegram-callback-ux.mdc`
- [ ] **Step 4:** `docker compose run --rm --no-deps bot python -c "import main"`
- [ ] **Step 5:** Commit `i18n(fa): localize tariff purchase confirmation flow`
- [ ] **Step 6:** User smoke — buy tariff from balance; insufficient-funds path; cart-saved message.

---

### Task 3: `simple_subscription.py`

**Files:**
- Modify: `app/handlers/simple_subscription.py`
- Modify: `app/localization/locales/fa.json`

- [ ] **Step 1:** Inventory (~230 Cyrillic user strings; skip log-only lines)
- [ ] **Step 2:** Group keys: `SIMPLE_SUB_BLOCKED_*`, `SIMPLE_SUB_TRIAL_EXISTS_*`, `SIMPLE_SUB_CONFIRM_*`, `SIMPLE_SUB_PAYMENT_*`
- [ ] **Step 3:** Implement `texts.t` replacements
- [ ] **Step 4:** Agent smoke + commit `i18n(fa): localize simple subscription flow`
- [ ] **Step 5:** User smoke — simple purchase happy path + blocked message.

---

### Task 4: `menu.py` — true hardcoded only

**Files:**
- Modify: `app/handlers/menu.py`
- Modify: `app/localization/locales/fa.json`

**Note:** Lines ~1093–1136 already use `texts.t('SUB_STATUS_*')` with Persian in `fa.json` — **do not change**. Fix only lines flagged as bare literals, e.g.:

| Line | Hardcoded | Action |
|------|-----------|--------|
| 116 | `⏳ Скидки за длительный период:` | `PROMO_GROUP_PERIOD_DISCOUNTS_HEADER` |
| 147+ | `Ошибка: пользователь не найден.` | `ERROR_USER_NOT_FOUND` (check if key exists) |
| 331 | `Промогруппы с автовыдачей ещё не настроены.` | new key |
| 377–411 | promo group level lines | `PROMO_GROUP_SPENT_*`, `PROMO_GROUP_LEVEL_*` |
| 679–825 | privacy/offer pagination | `PRIVACY_*`, `OFFER_*` keys |

- [ ] **Step 1:** `rg -n "['\"][^'\"]*[А-Яа-яЁё]" app/handlers/menu.py | rg -v 'texts\.t'`
- [ ] **Step 2:** Add fa keys + wire `texts.t`
- [ ] **Step 3:** Smoke + commit `i18n(fa): localize menu info and promo group hardcoded strings`
- [ ] **Step 4:** User smoke — main menu, Info → privacy/offer, promo groups screen.

---

## Phase B — Subscription modules (Bot)

### Task 5: `traffic.py`

**Files:** `app/handlers/subscription/traffic.py`, `fa.json`

- [ ] Replace: `Добавить трафик`, `Сброс трафика`, `докупка недоступна`, price breakdown `💡 Расчет цены`
- [ ] Keys prefix: `TRAFFIC_TOPUP_*`, `TRAFFIC_RESET_*` (check duplicates in fa.json first)
- [ ] Smoke + commit `i18n(fa): localize subscription traffic handler`

### Task 6: `devices.py`

**Files:** `app/handlers/subscription/devices.py`, `fa.json`

- [ ] Replace device change UI (~110 strings): `Изменение количества устройств`, limit errors, confirm dialogs
- [ ] Keys prefix: `DEVICES_CHANGE_*`, `DEVICES_LIMIT_*`
- [ ] Smoke + commit `i18n(fa): localize subscription devices handler`

### Task 7: `countries.py`

**Files:** `app/handlers/subscription/countries.py`, `fa.json`

- [ ] Replace country management legend and insufficient-funds block
- [ ] Keys prefix: `COUNTRIES_*`
- [ ] Smoke + commit `i18n(fa): localize subscription countries handler`

### Task 8: `autopay.py`

**Files:** `app/handlers/subscription/autopay.py`, `fa.json`

- [ ] Full autopay menu strings (`💳 Автоплатеж`, card list, period picker)
- [ ] Keys prefix: `AUTOPAY_*`
- [ ] Smoke + commit `i18n(fa): localize subscription autopay handler`

### Task 9: `links.py` + `happ.py`

**Files:** both handlers, `fa.json`

- [ ] Connect flow, Happ download, config-not-set errors
- [ ] Smoke + commit `i18n(fa): localize subscription connect and happ handlers`

### Task 10: `my_subscriptions.py`, `revoke.py`, `promo.py`

**Files:** three handlers ( **three separate commits** ), `fa.json` each time

- [ ] `my_subscriptions.py`: delete confirm, `Купить ещё тариф`
- [ ] `revoke.py`: revoke confirm + success
- [ ] `promo.py`: offer activation messages
- [ ] Three commits: `i18n(fa): localize my subscriptions|revoke|promo offer handlers`

---

## Phase C — Other Bot user handlers

### Task 11: `referral.py` — lower-half hardcoded blocks

**Files:** `app/handlers/referral.py`, `fa.json`

**Note:** Lines 52–87 already use `REFERRAL_STATS_*` in `fa.json`. Focus on lines ~149+ (`Последние начисления`, referral list pagination, analytics).

- [ ] `rg -n '[А-Яа-яЁё]' app/handlers/referral.py | tail -60`
- [ ] Wire `REFERRAL_EARNINGS_*`, `REFERRAL_LIST_*`, `REFERRAL_ANALYTICS_*` keys
- [ ] Smoke + commit `i18n(fa): localize referral list and analytics strings`

### Task 12: `start.py`

**Files:** `app/handlers/start.py`, `fa.json`

- [ ] Gift self-activation, referral/promo cooldown, registration messages
- [ ] Keys prefix: `START_*`, `GIFT_*`
- [ ] Smoke + commit `i18n(fa): localize start registration and gift strings`

### Task 13: `promocode.py`, `tickets.py`, `common.py`

**Files:** one commit per file

- [ ] `promocode.py`: validation, subscription picker, error toasts
- [ ] `tickets.py`: FSM validation + ticket detail view
- [ ] `common.py`: 2 unknown-command strings → `UNKNOWN_COMMAND`, `UNKNOWN_MESSAGE`

### Task 14: `stars_payments.py`

**Files:** `app/handlers/stars_payments.py`, `fa.json`

- [ ] Wheel unavailable, trial via Stars, refund messages
- [ ] Do **not** change Stars/ruble conversion (FX layer 3)
- [ ] Smoke + commit `i18n(fa): localize stars payments and wheel messages`

---

## Phase D — Keyboards

### Task 15: `inline.py` user-visible fallbacks

**Files:** `app/keyboards/inline.py`, `fa.json`

**Skip (intentional):** `🇷🇺 Русский` language picker labels.

**Fix:**
- L480: `'MENU_PROFILE', '👤 Личный кабинет'` → ensure `MENU_PROFILE` in fa.json (Persian only if missing)
- L554: `'🖥 Веб-Админка'` → `ADMIN_WEB_BUTTON` key
- L613: `'💰 Баланс: {balance}'` → `BALANCE_BUTTON_DEFAULT` (verify fa)
- L1423–1463: traffic/limit buttons `Безлимит`, `Бесплатно`, `назад`

- [ ] Verify each `texts.t` first arg exists in fa.json; if Persian present, no code change
- [ ] Fix only bare literals and missing keys
- [ ] Smoke + commit `i18n(fa): localize inline keyboard fallbacks`

---

## Phase E — Cabinet user routes (parity)

### Cabinet helper pattern (apply in every Task 16–22)

At top of route module:

```python
from app.localization.texts import get_texts

def _t(user: User, key: str, fallback: str, **fmt) -> str:
    text = get_texts(user.language).t(key, fallback)
    return text.format(**fmt) if fmt else text
```

Replace:

```python
# Before
raise HTTPException(status_code=400, detail='У вас нет активной подписки')
# After
raise HTTPException(
    status_code=400,
    detail=_t(user, 'CABINET_NO_ACTIVE_SUBSCRIPTION', 'У вас нет активной подписки'),
)
```

Add matching keys to `fa.json` with prefix `CABINET_`.

### Task 16: `subscription_modules/traffic.py`

**Files:** `app/cabinet/routes/subscription_modules/traffic.py`, `fa.json`

- [ ] Replace Russian `detail=` strings (lines ~450–535) while keeping existing English errors as-is or key them separately (`CABINET_TRAFFIC_*`)
- [ ] Smoke: `docker compose run --rm --no-deps bot python -c "import main"` (imports cabinet app)
- [ ] Commit `i18n(fa): localize cabinet traffic API errors`

### Task 17: `subscription_modules/devices.py`

**Files:** devices route, `fa.json`

- [ ] All `Ваша подписка неактивна`, `Докупка устройств недоступна`, purchase descriptions
- [ ] Commit `i18n(fa): localize cabinet devices API errors`

### Task 18: `subscription_modules/purchase.py`

**Files:** purchase route, `fa.json`

- [ ] `Недостаточно средств`, `Покупка тарифа`, `♾️ Безлимит`
- [ ] **Parity:** keys align with Task 2 bot tariff purchase where messages match
- [ ] Commit `i18n(fa): localize cabinet tariff purchase API messages`

### Task 19: `tariff_switch.py` + `renewal.py`

**Files:** two commits

- [ ] Switch: `Повышение тарифа недоступно`, transition descriptions
- [ ] Renewal: `Продление подписки`, insufficient funds (use same key as bot if text matches)

### Task 20: `balance.py` — payment status labels (display only)

**Files:** `app/cabinet/routes/balance.py`, `fa.json`

**Scope:** User-visible status mapping functions (~L1052–1105): `Ожидает оплаты`, `Оплачено`, etc. **Do not** change provider integration or invoice titles in same commit.

```python
def _payment_status_label(user: User, provider: str, status: str) -> tuple[str, str]:
    texts = get_texts(user.language)
    mapping = {
        'pending': (texts.t('PAYMENT_STATUS_PENDING_EMOJI', '⏳'), texts.t('PAYMENT_STATUS_PENDING', 'Ожидает оплаты')),
        # ...
    }
```

```json
"PAYMENT_STATUS_PENDING": "در انتظار پرداخت",
"PAYMENT_STATUS_PAID": "پرداخت‌شده",
"PAYMENT_STATUS_CANCELLED": "لغو شده"
```

- [ ] Commit `i18n(fa): localize cabinet balance payment status labels`

### Task 21: `wheel.py`, `withdrawal.py`, `dependencies.py`

**Files:** three small commits

- [ ] Wheel errors; withdrawal cancel guards; `Доступ запрещен` → `CABINET_ACCESS_DENIED`

---

## Phase F — Miniapp API

### Task 22: `miniapp.py` user messages

**Files:** `app/webapi/routes/miniapp.py`, `fa.json`

**Pattern:** Where handler has `user`/`db_user`, use `get_texts(user.language).t(...)`.

**Priority messages (grep `message =` and f-strings with Cyrillic):**

```python
message = get_texts(user.language).t(
    'MINIAPP_TRIAL_ACTIVATED_DAYS',
    'Триал активирован на {days} дн. Приятного пользования!',
).format(days=duration_days)
```

```json
"MINIAPP_TRIAL_ACTIVATED_DAYS": "آزمایشی به مدت {days} روز فعال شد. خوش استفاده!",
"MINIAPP_SUBSCRIPTION_RENEWED": "اشتراک{tariff_label} تا {date_label} تمدید شد. مبلغ {amount_label} کسر شد.",
"MINIAPP_INSUFFICIENT_BALANCE_TOPUP": "موجودی کافی نیست. {amount_label} را از طریق {method_title} پرداخت کنید."
```

- [ ] Also fix `daily_price_label` suffix `/день` → `MINIAPP_DAILY_PRICE_SUFFIX` = `/روز`
- [ ] Fix `{gb} ГБ` in tariff payload → use keyed format string
- [ ] Smoke + commit `i18n(fa): localize miniapp user-facing API messages`
- [ ] User smoke — open Mini App: trial activate, renew, daily tariff price label.

---

## Phase G — Wrap-up

### Task 23: Update living doc

**Files:** `.cursor/rules/fa-i18n-status.mdc`

- [ ] Add Done section: P1 user surfaces slices (list commit SHAs)
- [ ] Update Next: point to P2 admin plan

### Task 24: Deploy sync

- [ ] `cp app/localization/locales/fa.json ./locales/fa.json`
- [ ] `docker compose build bot && docker compose restart bot`
- [ ] Re-run baseline script from Prerequisites; attach before/after counts to PR

### Task 25: PR checklist

- [ ] Branch `i18n/p1-user-surfaces` → `dev-local` (after user approval only)
- [ ] PR notes: cabinet/miniapp parity commits included
- [ ] No `get_admin_texts` introduced
- [ ] No balance provider files touched
- [ ] User smoke passed: bot purchase path, cabinet traffic top-up error, miniapp renew message

---

## Self-review (plan author)

| Check | Status |
|-------|--------|
| Audit P1 surfaces covered | Tasks 1–22 map to audit file list |
| One file per commit rule | Each task states single handler/route; Task 9/10 split |
| Cabinet/miniapp parity | Tasks 16–22 explicitly paired with bot phases |
| No placeholders | Keys and code patterns are concrete |
| TDD | Project uses Docker smoke + user smoke instead of pytest for handlers — documented per task |
| Out of scope deferred | Admin (P2), email templates, balance providers — separate plan refs |
| FX/currency safe | Tasks avoid payment provider internals; format_price noted |

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-06-fa-i18n-p1-user-surfaces.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per Task (1–22), review between tasks, fast iteration. REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`.

2. **Inline Execution** — run tasks sequentially in one session with checkpoints after each Phase (A→B→C→D→E→F). REQUIRED SUB-SKILL: `superpowers:executing-plans`.

**Which approach?**
