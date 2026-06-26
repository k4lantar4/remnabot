# Main Menu UX (Low-Risk) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder the bot main menu in `default` mode so balance appears in the caption (not the first button), cabinet + wallet sit paired below buy/subscription actions, `menu_info` is removed from the main menu, and referrals opens the cabinet `/referral` page (partner apply + invite in one place).

**Architecture:** Keep `MAIN_MENU_MODE=default` and `MENU_LAYOUT_ENABLED=false`. Touch only `fa.json`, `menu.py` (caption balance line), and `inline.py` (`get_main_menu_keyboard`). Use `WebAppInfo` + `build_cabinet_url()` for cabinet/referral buttons (same pattern as connect flows). No cabinet admin MenuEditorTab changes.

**Tech Stack:** Python 3 / aiogram 3, `app/localization/locales/fa.json`, pytest, Docker agent smoke (`import main`).

---

## File map

| File | Responsibility |
|------|----------------|
| [`app/localization/locales/fa.json`](app/localization/locales/fa.json) | New button labels + optional `MAIN_MENU` tweak |
| [`app/handlers/menu.py`](app/handlers/menu.py) | Inject `MAIN_MENU_BALANCE_LINE` into caption |
| [`app/keyboards/inline.py`](app/keyboards/inline.py) | Reorder `get_main_menu_keyboard` rows |
| [`tests/keyboards/test_main_menu_keyboard_layout.py`](tests/keyboards/test_main_menu_keyboard_layout.py) | Layout regression tests (new) |
| [`tests/handlers/test_main_menu_text.py`](tests/handlers/test_main_menu_text.py) | Balance line in caption test |
| [`docs/templates/smoke-map.md`](docs/templates/smoke-map.md) | User smoke checklist (fill after staging deploy) |

**Out of scope:** `MENU_LAYOUT_ENABLED`, `MAIN_MENU_MODE=cabinet`, connect per-subscription flow (`my_subscriptions.py`), `get_info_menu_keyboard` (still used from info sub-pages / broadcast).

---

## Target keyboard layout

### User without active subscription

```
[ trial ]  [ buy ]              (when visible)
[ cabinet WebApp ]  [ wallet → menu_balance ]
[ promocode ]  [ referrals WebApp → /referral ]
[ support ]
```

### User with active subscription (multi-tariff)

```
[ Happ ]                        (optional row)
[ my subscriptions ]  [ buy ]   (buy when show_buy)
[ cabinet WebApp ]  [ wallet ]
[ promocode ]  [ referrals WebApp ]
[ support ]
```

**Caption:** includes `💰 موجودی: X تومان` via `texts.format_balance()`.

**Removed from main menu:** standalone top balance row, `menu_info` button.

---

## Referrals dual-purpose decision

**Chosen approach (Option A):** Main-menu referrals button opens cabinet WebApp `/referral`, which already contains partner application CTA and referral program UI ([`cabinet/src/pages/Referral.tsx`](cabinet/src/pages/Referral.tsx)).

**Fallback:** If `MINIAPP_CUSTOM_URL` is unset, keep `callback_data='menu_referrals'` (bot-native referral screen).

**Button label:** `MENU_REFERRALS` → `🤝 همکاری و دعوت` in `fa.json`.

---

### Task 1: fa.json labels

**Files:**
- Modify: [`app/localization/locales/fa.json`](app/localization/locales/fa.json)

- [ ] **Step 1: Add / update keys**

Add or update these keys (Persian values):

```json
"MAIN_MENU_BALANCE_LINE": "💰 موجودی: {balance}",
"MENU_CABINET_BTN": "📱 پنل کاربری",
"MENU_WALLET_BTN": "💳 شارژ موجودی",
"MENU_REFERRALS": "🤝 همکاری و دعوت"
```

Do **not** change `BALANCE_BUTTON` / `BALANCE_BUTTON_DEFAULT` (may still be used elsewhere).

- [ ] **Step 2: Agent smoke**

```bash
docker compose run --rm --no-deps bot python -c "import main"
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git checkout -b i18n/main-menu-ux-low-risk   # from main if not already on feature branch
git add app/localization/locales/fa.json
git commit -m "i18n(fa): main menu wallet, cabinet, and referrals labels"
```

---

### Task 2: Balance line in main menu caption

**Files:**
- Modify: [`app/handlers/menu.py`](app/handlers/menu.py) — `get_main_menu_text` (after `base_text` is built, before promo/test hints)
- Test: [`tests/handlers/test_main_menu_text.py`](tests/handlers/test_main_menu_text.py)

- [ ] **Step 1: Write the failing test**

Append to `tests/handlers/test_main_menu_text.py`:

```python
@pytest.mark.asyncio
async def test_main_menu_text_includes_balance_line() -> None:
    from app.handlers.menu import get_main_menu_text

    user = SimpleNamespace(
        id=1,
        full_name='Ali',
        balance_kopeks=150_000,
        language='fa',
        subscription=None,
    )
    texts = get_texts('fa')
    db = AsyncMock()

    with (
        patch('app.config.settings.is_multi_tariff_enabled', return_value=True),
        patch(
            'app.handlers.menu._get_multi_tariff_status',
            new_callable=AsyncMock,
            return_value=('❌ بدون اشتراک', ''),
        ),
        patch('app.handlers.menu.build_promo_offer_hint', new_callable=AsyncMock, return_value=None),
        patch('app.handlers.menu.build_test_access_hint', new_callable=AsyncMock, return_value=None),
        patch('app.handlers.menu.get_random_active_message', new_callable=AsyncMock, return_value=None),
    ):
        result = await get_main_menu_text(user, texts, db)

    assert texts.format_balance(150_000) in result
    assert 'موجودی' in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose run --rm --no-deps bot python -m pytest tests/handlers/test_main_menu_text.py::test_main_menu_text_includes_balance_line -v
```

Expected: FAIL (balance not in text yet).

- [ ] **Step 3: Implement balance line injection**

In `get_main_menu_text`, after `base_text` is assembled (both multi-tariff and single-tariff branches), before the `info_sections` block (~line 1228), insert:

```python
    balance_line = texts.t('MAIN_MENU_BALANCE_LINE', '💰 Баланс: {balance}').format(
        balance=texts.format_balance(getattr(user, 'balance_kopeks', 0) or 0),
    )
    action_prompt = texts.t('MAIN_MENU_ACTION_PROMPT', 'Выберите действие:')
    if action_prompt in base_text:
        base_text = base_text.replace(action_prompt, f'{balance_line}\n\n{action_prompt}')
    else:
        base_text = f'{base_text.rstrip()}\n\n{balance_line}\n'
```

Remove the duplicate `action_prompt = ...` assignment later in the function if it becomes redundant (keep one binding used by `_insert_random_message`).

- [ ] **Step 4: Run test to verify it passes**

```bash
docker compose run --rm --no-deps bot python -m pytest tests/handlers/test_main_menu_text.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Agent smoke**

```bash
docker compose run --rm --no-deps bot python -c "import main"
```

- [ ] **Step 6: Commit**

```bash
git add app/handlers/menu.py tests/handlers/test_main_menu_text.py
git commit -m "feat(menu): show balance in main menu caption"
```

---

### Task 3: Reorder main menu keyboard

**Files:**
- Modify: [`app/keyboards/inline.py`](app/keyboards/inline.py) — `get_main_menu_keyboard` (~lines 629–825)
- Create: [`tests/keyboards/test_main_menu_keyboard_layout.py`](tests/keyboards/test_main_menu_keyboard_layout.py)

- [ ] **Step 1: Write failing layout tests**

Create `tests/keyboards/test_main_menu_keyboard_layout.py`:

```python
"""Regression tests for default-mode main menu keyboard layout."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.keyboards.inline import get_main_menu_keyboard


@pytest.fixture(autouse=True)
def _default_menu_mode():
    with (
        patch('app.keyboards.inline.settings.is_cabinet_mode', return_value=False),
        patch('app.keyboards.inline.settings.MENU_LAYOUT_ENABLED', False),
        patch('app.keyboards.inline.settings.is_multi_tariff_enabled', return_value=True),
        patch('app.keyboards.inline.settings.MINIAPP_CUSTOM_URL', 'https://cabinet.example.com'),
        patch('app.keyboards.inline.settings.is_referral_program_enabled', return_value=True),
        patch('app.keyboards.inline.settings.SIMPLE_SUBSCRIPTION_ENABLED', True),
        patch('app.keyboards.inline.settings.CONTESTS_ENABLED', False),
        patch('app.keyboards.inline.settings.is_language_selection_enabled', return_value=False),
        patch('app.keyboards.inline.settings.ACTIVATE_BUTTON_VISIBLE', False),
    ):
        yield


def _flat_buttons(markup):
    return [btn for row in markup.inline_keyboard for btn in row]


def _callback_data_set(markup) -> set[str]:
    return {btn.callback_data for btn in _flat_buttons(markup) if btn.callback_data}


def _webapp_urls(markup) -> list[str]:
    return [btn.web_app.url for btn in _flat_buttons(markup) if btn.web_app]


def test_new_user_wallet_row_below_buy_not_first() -> None:
    kb = get_main_menu_keyboard(
        language='fa',
        balance_kopeks=50_000,
        has_active_subscription=False,
        subscription_is_active=False,
        has_had_paid_subscription=False,
    )
    buttons = _flat_buttons(kb)
    labels = [b.text for b in buttons]
    buy_idx = next(i for i, b in enumerate(buttons) if b.callback_data == 'menu_buy')
    wallet_idx = next(i for i, b in enumerate(buttons) if b.callback_data == 'menu_balance')
    assert wallet_idx > buy_idx
    assert buttons[0].callback_data != 'menu_balance'


def test_wallet_button_uses_fixed_label_not_dynamic_balance() -> None:
    kb = get_main_menu_keyboard(language='fa', balance_kopeks=999_999)
    wallet = next(b for b in _flat_buttons(kb) if b.callback_data == 'menu_balance')
    # format_balance would include formatted amount; fixed label must not duplicate it on button
    from app.localization.texts import get_texts
    texts = get_texts('fa')
    assert texts.format_balance(999_999) not in wallet.text


def test_menu_info_removed_from_main_menu() -> None:
    kb = get_main_menu_keyboard(language='fa', balance_kopeks=0)
    assert 'menu_info' not in _callback_data_set(kb)


def test_cabinet_and_referral_webapp_urls() -> None:
    kb = get_main_menu_keyboard(language='fa', balance_kopeks=0)
    urls = _webapp_urls(kb)
    assert 'https://cabinet.example.com' in urls
    assert 'https://cabinet.example.com/referral' in urls


def test_cabinet_wallet_share_a_row() -> None:
    kb = get_main_menu_keyboard(language='fa', balance_kopeks=0, has_active_subscription=False)
    for row in kb.inline_keyboard:
        cbs = {b.callback_data for b in row if b.callback_data}
        webapps = [b.web_app.url for b in row if b.web_app]
        if 'menu_balance' in cbs:
            assert any(url == 'https://cabinet.example.com' for url in webapps)
            assert len(row) == 2
            break
    else:
        pytest.fail('wallet row not found')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose run --rm --no-deps bot python -m pytest tests/keyboards/test_main_menu_keyboard_layout.py -v
```

Expected: FAIL on layout assertions.

- [ ] **Step 3: Refactor `get_main_menu_keyboard`**

Add import at top of function or module:

```python
from app.utils.miniapp_buttons import build_cabinet_url
```

**3a. Remove** the standalone balance row:

```python
# DELETE this block (~line 712):
keyboard.append([InlineKeyboardButton(text=balance_button_text, callback_data='menu_balance')])
```

Also remove or stop using `balance_button_text` if nothing else in the function needs it.

**3b. Add helper** inside `get_main_menu_keyboard` (local function is fine):

```python
def _flush_paired(target: list, buttons: list[InlineKeyboardButton], *, per_row: int = 2) -> None:
    for i in range(0, len(buttons), per_row):
        target.append(buttons[i : i + per_row])
    buttons.clear()
```

**3c. After** subscription-related buttons are collected in `paired_buttons` (after `custom_buttons` / cart / trial / buy / `MY_SUBSCRIPTIONS`), **flush** them to `keyboard`:

```python
_flush_paired(keyboard, paired_buttons)
```

**3d. Append cabinet + wallet row** immediately after that flush:

```python
wallet_btn = InlineKeyboardButton(
    text=texts.t('MENU_WALLET_BTN', '💳 Пополнить баланс'),
    callback_data='menu_balance',
)
cabinet_url = build_cabinet_url('/')
if cabinet_url:
    cabinet_btn = InlineKeyboardButton(
        text=texts.t('MENU_CABINET_BTN', '📱 Личный кабинет'),
        web_app=types.WebAppInfo(url=cabinet_url),
    )
    keyboard.append([cabinet_btn, wallet_btn])
else:
    keyboard.append([wallet_btn])
```

**3e. Build second `paired_buttons` batch** for lower menu:

```python
lower_buttons: list[InlineKeyboardButton] = []
lower_buttons.append(InlineKeyboardButton(text=texts.MENU_PROMOCODE, callback_data='menu_promocode'))

if settings.is_referral_program_enabled():
    referral_url = build_cabinet_url('/referral')
    if referral_url:
        lower_buttons.append(
            InlineKeyboardButton(
                text=texts.MENU_REFERRALS,
                web_app=types.WebAppInfo(url=referral_url),
            )
        )
    else:
        lower_buttons.append(
            InlineKeyboardButton(text=texts.MENU_REFERRALS, callback_data='menu_referrals'),
        )
```

Add contests / support / activate / language to `lower_buttons` as today (skip `menu_info` entirely).

```python
_flush_paired(keyboard, lower_buttons)
```

**3f. Remove** the old end-of-function loop:

```python
# DELETE:
for i in range(0, len(paired_buttons), 2):
    row = paired_buttons[i : i + 2]
    keyboard.append(row)
```

**3g. Keep** admin / moderator rows unchanged after keyboard is built.

**Order note:** `happ_row` is still appended to `keyboard` before subscription `paired_buttons` when subscriber — that preserves Happ above subscription actions.

- [ ] **Step 4: Run layout tests**

```bash
docker compose run --rm --no-deps bot python -m pytest tests/keyboards/test_main_menu_keyboard_layout.py -v
```

Expected: PASS.

- [ ] **Step 5: Full agent smoke**

```bash
docker compose run --rm --no-deps bot python -c "import main"
grep -r get_admin_texts app/ | wc -l   # expect 0
docker compose run --rm --no-deps bot python -m pytest tests/handlers/test_main_menu_text.py tests/keyboards/test_main_menu_keyboard_layout.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/keyboards/inline.py tests/keyboards/test_main_menu_keyboard_layout.py
git commit -m "feat(menu): reorder main keyboard — cabinet, wallet, referrals WebApp"
```

---

### Task 4: Staging deploy and smoke map

**Files:**
- Modify: [`docs/templates/smoke-map.md`](docs/templates/smoke-map.md)

- [ ] **Step 1: Deploy staging**

```bash
cp app/localization/locales/fa.json ./locales/fa.json
make staging-rebuild
make staging-health
```

- [ ] **Step 2: Fill smoke map**

Telegram `@mrj7_bot` checklist:

| # | Action | Expected |
|---|--------|----------|
| 1 | `/start` → main menu | Caption shows `💰 موجودی: …` |
| 2 | First action row | NOT balance-only row |
| 3 | Row with `📱 پنل کاربری` + `💳 شارژ موجودی` | Below buy / my subs |
| 4 | Tap `💳 شارژ موجودی` | Balance / top-up flow |
| 5 | Tap `📱 پنل کاربری` | Cabinet mini-app opens |
| 6 | Tap `🤝 همکاری و دعوت` | Cabinet `/referral` with partner CTA |
| 7 | No `ℹ️ اطلاعات` on main menu | `menu_info` absent |
| 8 | Active sub → `اشتراک‌های من` → detail → connect | Unchanged per-sub flow |

- [ ] **Step 3: User sign-off**

Wait for operator `تایید` before `CONFIRM_SHIP=1 make ship`.

---

## Self-review (spec coverage)

| Requirement | Task |
|-------------|------|
| Balance in caption, not first button | Task 2 + Task 3 (remove top row, fixed wallet label) |
| Cabinet + wallet paired below buy/subs | Task 3 |
| Remove `menu_info` | Task 3 |
| Partner + referrals one button | Task 1 label + Task 3 WebApp `/referral` |
| Low risk (no MENU_LAYOUT / cabinet mode) | Architecture section |
| multi-tariff connect stays per-sub | Out of scope |
| Tests | Tasks 2–3 |

No placeholders remain in task steps.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-26-main-menu-ux-low-risk.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — implement all tasks in this session with checkpoints

Which approach?
