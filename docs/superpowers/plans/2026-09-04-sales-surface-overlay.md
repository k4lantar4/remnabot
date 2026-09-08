# Sales Surface Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do **not** invoke finishing-a-development-branch until the operator smoke in Task 13 passes. Do **not** start M7-T1 / DNS / production token.

**Goal:** Isolated catalog «خرید سرویس» (new row, not silent renew) with identity-A titles and production sales UX on Telegram 4.2 + cabinet 1.67, without merging upstream 4.4/1.69.

**Architecture:** Thin helpers own identity A, extend-vs-create, and `?intent=new`. Hot files get callsites only. `PricingEngine` stays the only price brain. Cabinet copies small donor modules and wires 1.67 pages; do not replace `Subscription.tsx` or `tariff_purchase.py`.

**Tech Stack:** Python 3.12 / pytest (`uv run pytest`) on `/opt/remnabot1` `prod-cutover`; Vite/React/vitest on `/opt/cabinet` `prod-cutover`. Donor read-only: `/opt/remnabot`, `ssh bot:/opt/bot-remnawave/cabinet`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-04-sales-surface-overlay-design.md` (operator تایید 2026-09-04).
- Identity A only: panel username (skip `user_unknown_*`); else `{tariff} #{account_sequence}`. No `brand_serial` titles.
- No new Alembic revision. No `alembic revision --autogenerate`. No restore of `uq_subscriptions_user_tariff_active` in the DB.
- `persist_identity` stays numeric-id-only. Username cache is a separate helper.
- Do not add `PartnerCheckoutFields`, note/disable sheets, Earn/`/sales`, or merge bot 4.4 / cabinet 1.69.
- Keep 4.2 rich `/start` shell. Do not restore the 3.60 keyboard grid.
- One concern per commit. Bot commits in `/opt/remnabot1`; cabinet commits in `/opt/cabinet`. Never mix trees.
- Working tree on remnabot1 may contain unrelated dirty files (`menu_layout/service.py`, docs, `0112_*`). Commit **only** the files named in that task.
- English digits in new fa strings. Missing keys keep `fa → en → ru`.
- Do not start M7-T1.

---

## File map

| File | Responsibility |
|---|---|
| `/opt/remnabot1/app/database/models.py` | Map `panel_username`, `account_sequence`; drop unique index from `__table_args__` |
| `/opt/remnabot1/app/custom/identity/panel_username.py` | `cache_panel_username(subscription, panel_user)` |
| `/opt/remnabot1/app/database/crud/subscription.py` | `get_next_account_sequence`; set it on `create_paid_subscription` insert |
| `/opt/remnabot1/app/utils/subscription_purchase_intent.py` | `should_extend_multi_tariff` |
| `/opt/remnabot1/app/utils/subscription_list_display.py` | Identity A + search haystack |
| `/opt/remnabot1/app/services/menu_layout/service.py` | Multi-tariff `show_buy` stays visible with an active sub |
| `/opt/remnabot1/app/handlers/subscription/purchase.py` | `menu_buy` clears `target_subscription_id` before tariff list |
| `/opt/remnabot1/app/handlers/subscription/tariff_purchase.py` | Confirm/preview/cart use predicate; no empty-pin tariff lookup |
| `/opt/remnabot1/app/utils/rich_menu.py` | Table identity cell uses identity A |
| `/opt/remnabot1/app/cabinet/routes/subscription_modules/multi_tariff.py` | DTO fields + search/offset/limit/total |
| `/opt/cabinet/src/components/subscription/purchase/purchaseRoutes.ts` | `NEW_PURCHASE_PATH`, `isNewPurchaseIntent` |
| `/opt/cabinet/src/utils/subscriptionDisplayLabel.ts` | Identity A + search helpers |
| `/opt/cabinet/src/pages/Subscriptions.tsx` | Search UI + buy CTA |
| `/opt/cabinet/src/pages/SubscriptionPurchase.tsx` | Unbind on `intent=new` |
| `/opt/cabinet/src/components/subscription/purchase/TariffPickerGrid.tsx` | `purchaseIntent` |
| `/opt/cabinet/src/pages/Dashboard.tsx` | Buy-another → `NEW_PURCHASE_PATH` |
| `/opt/cabinet/src/pages/Subscription.tsx` | Title A, gated first-connect, config+guide, buy-another row |
| `/opt/cabinet/src/components/icons/index.tsx` | RTL flip on Back/Chevron only |

---

### Task 1: Map identity columns + username cache

**Files:**
- Modify: `/opt/remnabot1/app/database/models.py` (`Subscription` around the unique index and column list)
- Create: `/opt/remnabot1/app/custom/identity/panel_username.py`
- Modify: `/opt/remnabot1/app/services/subscription_service.py` (each `persist_identity(subscription=...)` callsite)
- Modify: `/opt/remnabot1/tests/database/test_day1_orm_columns.py`
- Create: `/opt/remnabot1/tests/custom/test_cache_panel_username.py`

**Interfaces:**
- Consumes: grafted columns `0091` / `0092` already in the DB
- Produces: `Subscription.panel_username: str | None`, `Subscription.account_sequence: int`; `cache_panel_username(subscription, panel_user) -> None`

- [ ] **Step 1: Write the failing ORM test**

Add to `/opt/remnabot1/tests/database/test_day1_orm_columns.py`:

```python
def test_subscription_has_identity_a_columns() -> None:
    assert hasattr(Subscription, 'panel_username')
    assert hasattr(Subscription, 'account_sequence')


def test_subscription_model_does_not_declare_user_tariff_unique() -> None:
    index_names = {idx.name for idx in Subscription.__table__.indexes}
    assert 'uq_subscriptions_user_tariff_active' not in index_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/remnabot1 && uv run pytest tests/database/test_day1_orm_columns.py -v`
Expected: FAIL — `panel_username` missing and/or unique index still declared.

- [ ] **Step 3: Map columns and drop the unique index from the model**

On `class Subscription` in `models.py`:

1. Delete the `Index('uq_subscriptions_user_tariff_active', ...)` entry inside `__table_args__`.
2. Add after `user_disabled`:

```python
    account_sequence = Column(Integer, nullable=False, default=1)
    panel_username = Column(String(64), nullable=True)
```

Do not add a migration. Do not recreate the unique index.

- [ ] **Step 4: Write the failing cache helper test**

Create `/opt/remnabot1/tests/custom/test_cache_panel_username.py`:

```python
from types import SimpleNamespace

from app.custom.identity.panel_username import cache_panel_username
from app.custom.identity.persist import persist_identity


def test_cache_writes_trimmed_username() -> None:
    sub = SimpleNamespace(panel_username=None)
    cache_panel_username(sub, SimpleNamespace(username='  mobile_x_1001  '))
    assert sub.panel_username == 'mobile_x_1001'


def test_cache_skips_empty() -> None:
    sub = SimpleNamespace(panel_username='keep')
    cache_panel_username(sub, SimpleNamespace(username='  '))
    assert sub.panel_username == 'keep'


def test_persist_identity_does_not_write_username() -> None:
    sub = SimpleNamespace(remnawave_id=None, panel_username=None)
    persist_identity(subscription=sub, panel_user=SimpleNamespace(id=99, username='x'))
    assert sub.remnawave_id == 99
    assert sub.panel_username is None
```

- [ ] **Step 5: Implement helper and wire subscription_service**

Create `/opt/remnabot1/app/custom/identity/panel_username.py`:

```python
from __future__ import annotations

from typing import Any

def cache_panel_username(subscription: Any, panel_user: Any) -> None:
    name = (getattr(panel_user, 'username', None) or '').strip()
    if not name:
        return
    subscription.panel_username = name[:64]
```

In `subscription_service.py`, after every `persist_identity(subscription=subscription, panel_user=...)` (lines that pass `subscription=`), add:

```python
                    cache_panel_username(subscription, updated_user)  # or adopted / panel_user — same object passed to persist_identity
```

Import `cache_panel_username` next to `persist_identity`. Do not put username writes inside `persist.py`.

- [ ] **Step 6: Run tests**

Run: `cd /opt/remnabot1 && uv run pytest tests/database/test_day1_orm_columns.py tests/custom/test_cache_panel_username.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd /opt/remnabot1
git add app/database/models.py app/custom/identity/panel_username.py app/services/subscription_service.py tests/database/test_day1_orm_columns.py tests/custom/test_cache_panel_username.py
git commit -m "$(cat <<'EOF'
feat(sales): map panel_username and cache it beside persist_identity

EOF
)"
```

---

### Task 2: Assign `account_sequence` on paid create

**Files:**
- Modify: `/opt/remnabot1/app/database/crud/subscription.py`
- Create: `/opt/remnabot1/tests/crud/test_account_sequence.py`

**Interfaces:**
- Consumes: `Subscription.account_sequence` from Task 1
- Produces: `async def get_next_account_sequence(db: AsyncSession, user_id: int) -> int`

- [ ] **Step 1: Write the failing test**

Create `/opt/remnabot1/tests/crud/test_account_sequence.py`:

```python
import inspect

from app.database.crud import subscription as crud


def test_get_next_account_sequence_exists() -> None:
    assert inspect.iscoroutinefunction(crud.get_next_account_sequence)


def test_create_paid_subscription_source_sets_account_sequence() -> None:
    src = inspect.getsource(crud.create_paid_subscription)
    assert 'account_sequence' in src
    assert 'get_next_account_sequence' in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/remnabot1 && uv run pytest tests/crud/test_account_sequence.py -v`
Expected: FAIL — `get_next_account_sequence` missing.

- [ ] **Step 3: Port sequence helper and set it on insert**

Add near the top of `subscription.py` crud (after imports; `func` must already be imported from sqlalchemy — add it if missing):

```python
async def get_next_account_sequence(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(Subscription.account_sequence), 0)).where(Subscription.user_id == user_id)
    )
    return int(result.scalar_one()) + 1
```

In `create_paid_subscription`, immediately before `subscription = Subscription(`:

```python
    account_sequence = await get_next_account_sequence(db, user_id)
```

Pass `account_sequence=account_sequence` into the `Subscription(...)` constructor. Do not change the expired-revive / trial-conversion branches in this task.

- [ ] **Step 4: Run tests**

Run: `cd /opt/remnabot1 && uv run pytest tests/crud/test_account_sequence.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /opt/remnabot1
git add app/database/crud/subscription.py tests/crud/test_account_sequence.py
git commit -m "$(cat <<'EOF'
feat(sales): assign account_sequence on new paid subscriptions

EOF
)"
```

---

### Task 3: Identity A on Telegram list + rich table

**Files:**
- Modify: `/opt/remnabot1/app/utils/subscription_list_display.py`
- Modify: `/opt/remnabot1/tests/utils/test_subscription_list_display.py`
- Modify: `/opt/remnabot1/app/utils/rich_menu.py` (`_build_subscriptions_table`)

**Interfaces:**
- Consumes: `panel_username`, `account_sequence`, `tariff.name`
- Produces: `subscription_list_identity(sub, user, texts) -> str` now identity A (ignore partner brand)

- [ ] **Step 1: Replace identity tests (they must fail on current brand_serial)**

Replace `test_identity_brand_serial_for_partner`, `test_identity_falls_back_to_tariff`, `test_line_is_jalali_fa_and_not_cyrillic`, and `test_search_matches_serial_and_brand` in `tests/utils/test_subscription_list_display.py` with:

```python
def test_identity_uses_panel_username() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    sub = _sub(panel_username='mobile_x_1001', account_sequence=2)
    assert subscription_list_identity(sub, user, DummyTexts()) == 'mobile_x_1001'


def test_identity_strips_user_unknown() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    sub = _sub(panel_username='user_unknown_abc', account_sequence=3)
    assert subscription_list_identity(sub, user, DummyTexts()) == 'تانل شده (همه نت ها) #3'


def test_identity_falls_back_to_tariff_seq() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    sub = _sub(panel_username=None, account_sequence=4)
    assert subscription_list_identity(sub, user, DummyTexts()) == 'تانل شده (همه نت ها) #4'


def test_identity_never_brand_serial() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    sub = _sub(panel_username=None, remnawave_short_id='67258', account_sequence=1)
    assert 'Moonvpn_67258' not in subscription_list_identity(sub, user, DummyTexts())


def test_line_is_jalali_fa_and_not_cyrillic() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    line = format_subscription_list_line(
        _sub(panel_username='mobile_x_1001', account_sequence=1),
        1,
        DummyTexts(),
        'fa',
        user,
    )
    assert '18.04.1405' in line
    assert 'کاربر' in line
    assert 'Moonvpn_67258' not in line
    assert 'mobile_x_1001' in line


def test_search_matches_username_and_id() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    subs = [
        _sub(id=1, panel_username='mobile_x_1001', account_sequence=1),
        _sub(id=2, panel_username='mobile_x_1002', remnawave_short_id='1159', tariff=SimpleNamespace(name='دیگر'), account_sequence=2),
    ]
    hit = filter_subscriptions_by_query(subs, 'mobile_x_1001', DummyTexts(), user)
    assert [s.id for s in hit] == [1]
    hit_id = filter_subscriptions_by_query(subs, '2', DummyTexts(), user)
    assert [s.id for s in hit_id] == [2]
```

Also add `MY_SUB_ACCOUNT_LABEL` to `DummyTexts.t` map: `'{tariff} #{seq}'`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/remnabot1 && uv run pytest tests/utils/test_subscription_list_display.py -v`
Expected: FAIL — still returns `Moonvpn_67258` / tariff without `#seq`.

- [ ] **Step 3: Implement identity A**

Replace `subscription_list_identity` with:

```python
USER_UNKNOWN_PREFIX = 'user_unknown_'


def subscription_list_identity(sub: Any, user: Any, texts: Any) -> str:
    del user  # identity A does not use partner brand
    panel = (getattr(sub, 'panel_username', None) or '').strip()
    if panel.startswith(USER_UNKNOWN_PREFIX):
        panel = ''
    if panel:
        return panel
    tariff = getattr(sub, 'tariff', None)
    tariff_name = (
        str(getattr(tariff, 'name', None))
        if tariff and getattr(tariff, 'name', None)
        else texts.t('MY_SUB_DEFAULT_NAME', 'Подписка')
    )
    seq = getattr(sub, 'account_sequence', 1) or 1
    return texts.t('MY_SUB_ACCOUNT_LABEL', '{tariff} #{seq}').format(tariff=tariff_name, seq=seq)
```

In `_matches`, also match `panel_username` (already covered via identity) and drop the partner-brand haystack (`remnawave_short_id` may remain as extra search, not as title). Keep id / note / tariff matches.

- [ ] **Step 4: Rich-menu table cell**

In `_build_subscriptions_table` replace the `tariff_name = html.escape(subscription.tariff.name) ...` assignment with:

```python
        from app.utils.subscription_list_display import subscription_list_identity

        label = html.escape(subscription_list_identity(subscription, None, texts))
```

Use `label` in the `<td>` instead of `tariff_name`. Keep status/until columns.

Add fa key `MY_SUB_ACCOUNT_LABEL` in `app/localization/locales/fa.json` if missing: `"{tariff} #{seq}"`.

- [ ] **Step 5: Run tests**

Run: `cd /opt/remnabot1 && uv run pytest tests/utils/test_subscription_list_display.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /opt/remnabot1
git add app/utils/subscription_list_display.py tests/utils/test_subscription_list_display.py app/utils/rich_menu.py app/localization/locales/fa.json
git commit -m "$(cat <<'EOF'
fix(sales): identity A titles on Telegram list and rich menu

EOF
)"
```

---

### Task 4: Main-menu buy stays visible (multi-tariff)

**Files:**
- Modify: `/opt/remnabot1/app/services/menu_layout/service.py` (`_evaluate_conditions` `show_buy` block ~797)
- Modify: `/opt/remnabot1/app/handlers/subscription/purchase.py` (`start_subscription_purchase`)
- Modify: `/opt/remnabot1/tests/services/test_menu_layout_service.py`

**Interfaces:**
- Consumes: `settings.is_multi_tariff_enabled()`
- Produces: `menu_buy` visible with an active sub when multi-tariff is on; FSM pin cleared on `menu_buy`

- [ ] **Step 1: Write the failing visibility tests**

Append to `tests/services/test_menu_layout_service.py`:

```python
def test_show_buy_hidden_when_active_single_tariff():
    conditions = {'show_buy': True}
    context = MenuContext(
        language='fa',
        has_active_subscription=True,
        subscription_is_active=True,
    )
    with patch('app.services.menu_layout.service.settings') as settings:
        settings.is_multi_tariff_enabled.return_value = False
        assert MenuLayoutService._evaluate_conditions(conditions, context) is False


def test_show_buy_visible_when_active_multi_tariff():
    conditions = {'show_buy': True}
    context = MenuContext(
        language='fa',
        has_active_subscription=True,
        subscription_is_active=True,
    )
    with patch('app.services.menu_layout.service.settings') as settings:
        settings.is_multi_tariff_enabled.return_value = True
        assert MenuLayoutService._evaluate_conditions(conditions, context) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/remnabot1 && uv run pytest tests/services/test_menu_layout_service.py::test_show_buy_visible_when_active_multi_tariff -v`
Expected: FAIL — currently False.

- [ ] **Step 3: Change `show_buy` and clear pin on `menu_buy`**

Replace the `show_buy` block with:

```python
        if conditions.get('show_buy') is True:
            if not settings.is_multi_tariff_enabled():
                if context.has_active_subscription and context.subscription_is_active:
                    return False
```

At the **top** of `start_subscription_purchase` in `purchase.py`, before `is_tariffs_mode()`:

```python
    if settings.is_multi_tariff_enabled() and state:
        await state.update_data(target_subscription_id=None)
```

Do not rewrite the rest of the handler. Do not commit unrelated dirty hunks already in `menu_layout/service.py` — `git add -p` that file or copy only this condition if the file is dirty.

- [ ] **Step 4: Run tests**

Run: `cd /opt/remnabot1 && uv run pytest tests/services/test_menu_layout_service.py::test_show_buy_hidden_when_active_single_tariff tests/services/test_menu_layout_service.py::test_show_buy_visible_when_active_multi_tariff -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /opt/remnabot1
git add app/services/menu_layout/service.py app/handlers/subscription/purchase.py tests/services/test_menu_layout_service.py
git commit -m "$(cat <<'EOF'
feat(sales): keep menu_buy on /start for multi-tariff and clear the renew pin

EOF
)"
```

---

### Task 5: Extend-vs-create predicate

**Files:**
- Create: `/opt/remnabot1/app/utils/subscription_purchase_intent.py`
- Create: `/opt/remnabot1/tests/utils/test_subscription_purchase_intent.py`
- Modify: `/opt/remnabot1/app/handlers/subscription/tariff_purchase.py` (three sites: daily cart ~973, period preview ~1639, confirm ~1828 and ~1923)

**Interfaces:**
- Consumes: FSM `target_subscription_id`; loaded subscription row
- Produces: `should_extend_multi_tariff(state_data: dict, *, existing_sub, renew_only: bool = False) -> bool`

- [ ] **Step 1: Write the failing helper tests**

Create `/opt/remnabot1/tests/utils/test_subscription_purchase_intent.py`:

```python
from types import SimpleNamespace

from app.utils.subscription_purchase_intent import should_extend_multi_tariff


def test_extend_when_pinned_and_row_present() -> None:
    sub = SimpleNamespace(id=10, tariff_id=3)
    assert should_extend_multi_tariff({'target_subscription_id': 10}, existing_sub=sub) is True


def test_create_when_pin_cleared() -> None:
    sub = SimpleNamespace(id=10, tariff_id=3)
    assert should_extend_multi_tariff({'target_subscription_id': None}, existing_sub=sub) is False
    assert should_extend_multi_tariff({}, existing_sub=sub) is False


def test_create_when_no_row() -> None:
    assert should_extend_multi_tariff({'target_subscription_id': 10}, existing_sub=None) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/remnabot1 && uv run pytest tests/utils/test_subscription_purchase_intent.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement helper**

Create `/opt/remnabot1/app/utils/subscription_purchase_intent.py`:

```python
from __future__ import annotations

from typing import Any


def should_extend_multi_tariff(
    state_data: dict,
    *,
    existing_sub: Any,
    renew_only: bool = False,
) -> bool:
    pinned = state_data.get('target_subscription_id')
    if pinned and existing_sub:
        return True
    if renew_only:
        active = state_data.get('active_subscription_id')
        return bool(active and existing_sub and getattr(existing_sub, 'id', None) == active)
    return False
```

- [ ] **Step 4: Wire the three tariff_purchase sites**

Import: `from app.utils.subscription_purchase_intent import should_extend_multi_tariff`.

**Confirm (`confirm_tariff_purchase`, multi-tariff branch ~1827):** load by pin only; **delete** the fallback `get_subscription_by_user_and_tariff` when pin is empty:

```python
        _state_data = await state.get_data() if state else {}
        _pinned_sub_id = _state_data.get('target_subscription_id')
        existing_sub = None
        if _pinned_sub_id:
            existing_sub = await get_subscription_by_id_for_user(db, int(_pinned_sub_id), db_user.id)
            if existing_sub and existing_sub.tariff_id != tariff_id:
                existing_sub = None
```

Replace `if existing_subscription and existing_subscription.tariff_id == tariff.id:` (~1923) with:

```python
            if should_extend_multi_tariff(_state_data, existing_sub=existing_subscription) and existing_subscription and existing_subscription.tariff_id == tariff.id:
```

**Period preview (~1638):** if multi-tariff, read pin from `state`; if pinned, load that row for device pricing; else `_existing_sub = None` (do not look up by tariff).

**Daily insufficient-balance cart (~972):** set `'subscription_id'` from pin only (`state` data `target_subscription_id`), not from `get_subscription_by_user_and_tariff`.

Do not replace the rest of the file.

- [ ] **Step 5: Run tests**

Run: `cd /opt/remnabot1 && uv run pytest tests/utils/test_subscription_purchase_intent.py tests/services/test_tariff_purchase_subscription_pinning.py -v`
Expected: PASS (update pinning tests if they asserted the old tariff-lookup fallback).

- [ ] **Step 6: Commit**

```bash
cd /opt/remnabot1
git add app/utils/subscription_purchase_intent.py tests/utils/test_subscription_purchase_intent.py app/handlers/subscription/tariff_purchase.py tests/services/test_tariff_purchase_subscription_pinning.py
git commit -m "$(cat <<'EOF'
fix(sales): create a new row on menu_buy instead of extending by tariff id

EOF
)"
```

---

### Task 6: Price matrix (blocking)

**Files:**
- Modify: `/opt/remnabot1/tests/test_wholesale_pricing.py`
- Create: `/opt/remnabot1/tests/cabinet/test_sales_edges_use_pricing_engine.py`

**Interfaces:**
- Consumes: existing `PricingEngine.calculate_tariff_purchase_price`, `calculate_renewal_price`, `calculate_traffic_discount`, `get_addon_discount_percent`, `calculate_tariff_switch_cost`
- Produces: partner < retail on those five edges; cabinet modules import `PricingEngine`

- [ ] **Step 1: Write failing/extended engine tests**

Append to `tests/test_wholesale_pricing.py`:

```python
class TestSalesEdgeMatrix:
    @pytest.mark.asyncio
    async def test_purchase_partner_cheaper_than_retail(self):
        engine = PricingEngine()
        tariff = MagicMock()
        tariff.id = 1
        tariff.is_daily = False
        tariff.period_prices = {'30': 100000}
        tariff.device_limit = 1
        tariff.device_price_kopeks = 0
        tariff.custom_traffic_enabled = False
        tariff.can_purchase_custom_traffic = MagicMock(return_value=False)
        tariff.is_available_for_promo_group = MagicMock(return_value=True)
        retail = MagicMock(is_partner=False, wholesale_discount_bps=0, partner_status=None)
        retail.get_primary_promo_group = MagicMock(return_value=None)
        retail.promo_group = None
        partner = _partner_user(bps=2500)
        partner.get_primary_promo_group = MagicMock(return_value=None)
        partner.promo_group = None
        r = await engine.calculate_tariff_purchase_price(tariff, 30, device_limit=1, user=retail)
        p = await engine.calculate_tariff_purchase_price(tariff, 30, device_limit=1, user=partner)
        assert p.final_total < r.final_total

    def test_traffic_partner_cheaper_than_retail(self):
        retail = MagicMock(is_partner=False, wholesale_discount_bps=0)
        retail.get_primary_promo_group = MagicMock(return_value=None)
        retail.promo_group = None
        partner = _partner_user(bps=2000)
        p, _, _ = PricingEngine.calculate_traffic_discount(50000, partner)
        r, _, _ = PricingEngine.calculate_traffic_discount(50000, retail)
        assert p < r

    def test_devices_addon_uses_engine(self):
        partner = _partner_user(bps=2500)
        pct = PricingEngine.get_addon_discount_percent(partner, 'devices', 30)
        assert pct >= 0
```

If `calculate_tariff_purchase_price` needs more tariff mocks, copy the working mocks from `TestWholesaleTariffCore` / read the function signature and pass the same kwargs.

Create `/opt/remnabot1/tests/cabinet/test_sales_edges_use_pricing_engine.py`:

```python
from pathlib import Path

ROOT = Path('app/cabinet/routes/subscription_modules')


def test_purchase_renewal_traffic_devices_switch_import_engine() -> None:
    files = {
        'purchase.py': 'PricingEngine',
        'renewal.py': 'pricing_engine',
        'traffic.py': 'PricingEngine',
        'servers.py': 'PricingEngine',
        'tariff_switch.py': 'pricing_engine',
    }
    for name, token in files.items():
        text = (ROOT / name).read_text(encoding='utf-8')
        assert token in text, f'{name} must use PricingEngine'
```

- [ ] **Step 2: Run tests**

Run: `cd /opt/remnabot1 && uv run pytest tests/test_wholesale_pricing.py tests/cabinet/test_sales_edges_use_pricing_engine.py tests/services/test_wholesale_pricing.py -v`
Expected: PASS. If purchase/renewal/switch tests fail because of missing mocks, fix **tests** to match real signatures — do not add a second price formula. If a cabinet file does not import the engine, stop: `PLAN REVISION REQUIRED: sales edge missing PricingEngine` (do not invent math).

- [ ] **Step 3: Commit**

```bash
cd /opt/remnabot1
git add tests/test_wholesale_pricing.py tests/cabinet/test_sales_edges_use_pricing_engine.py
git commit -m "$(cat <<'EOF'
test(sales): partner vs retail price matrix on purchase traffic and cabinet edges

EOF
)"
```

---

### Task 7: Cabinet API list DTO + search

**Files:**
- Modify: `/opt/remnabot1/app/cabinet/routes/subscription_modules/multi_tariff.py`
- Create: `/opt/remnabot1/tests/cabinet/test_multi_tariff_search.py`

**Interfaces:**
- Consumes: `panel_username`, `account_sequence`, `purchase_note`
- Produces: `GET /cabinet/subscriptions?offset=&limit=&search=` with `total`, identity fields

- [ ] **Step 1: Write failing unit tests for search + DTO mapping**

Create `/opt/remnabot1/tests/cabinet/test_multi_tariff_search.py` using SimpleNamespace (no HTTP):

```python
from types import SimpleNamespace

from app.cabinet.routes.subscription_modules.multi_tariff import (
    _subscription_matches_search,
    _subscription_to_list_item,
)


def test_search_matches_username_and_id() -> None:
    sub = SimpleNamespace(
        id=82444,
        panel_username='mobile_x_1001',
        tariff=SimpleNamespace(name='Moon'),
        purchase_note=None,
    )
    assert _subscription_matches_search(sub, 'mobile_x') is True
    assert _subscription_matches_search(sub, '82444') is True
    assert _subscription_matches_search(sub, 'zzz') is False


def test_list_item_includes_identity_a_fields() -> None:
    sub = SimpleNamespace(
        id=1,
        actual_status='active',
        tariff_id=2,
        tariff=SimpleNamespace(name='Moon', is_daily=False),
        account_sequence=3,
        panel_username='mobile_x_1001',
        traffic_limit_gb=10,
        traffic_used_gb=1.0,
        device_limit=2,
        end_date=None,
        subscription_url=None,
        subscription_crypto_link=None,
        is_trial=False,
        is_daily_paused=False,
        autopay_enabled=False,
        connected_squads=[],
        purchase_note=None,
        user_disabled=False,
    )
    item = _subscription_to_list_item(sub)
    assert item.panel_username == 'mobile_x_1001'
    assert item.account_sequence == 3
```

- [ ] **Step 2: Run to verify fail**

Run: `cd /opt/remnabot1 && uv run pytest tests/cabinet/test_multi_tariff_search.py -v`
Expected: FAIL — helpers/fields missing.

- [ ] **Step 3: Port production list shape (fields + search only)**

Follow `/opt/remnabot/app/cabinet/routes/subscription_modules/multi_tariff.py` for:

- `SubscriptionListItem` fields: `account_sequence`, `panel_username`, `purchase_note`, `user_disabled`
- `SubscriptionsListResponse.total: int = 0`
- `_subscription_matches_search`
- `_subscription_to_list_item` mapping those fields
- `list_subscriptions` query params: `offset: int = 0`, `limit: int = 20`, `search: str | None = Query(None)` — filter then slice; `total` is the filtered count

Do **not** port note PATCH / disable POST endpoints (backlog).

`get_subscription_detail` must return the same DTO fields.

- [ ] **Step 4: Run tests**

Run: `cd /opt/remnabot1 && uv run pytest tests/cabinet/test_multi_tariff_search.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /opt/remnabot1
git add app/cabinet/routes/subscription_modules/multi_tariff.py tests/cabinet/test_multi_tariff_search.py
git commit -m "$(cat <<'EOF'
feat(sales): expose panel_username and search on cabinet subscription list

EOF
)"
```

---

### Task 8: Cabinet purchaseRoutes + identity helper + API types

**Files (all `/opt/cabinet`):**
- Create: `src/components/subscription/purchase/purchaseRoutes.ts`
- Create: `src/components/subscription/purchase/purchaseRoutes.test.ts`
- Modify: `src/utils/subscriptionDisplayLabel.ts`
- Modify: `src/utils/subscriptionDisplayLabel.test.ts`
- Modify: `src/types/index.ts` (`SubscriptionListItem`, `SubscriptionsListResponse`)
- Modify: `src/api/subscription.ts` (`getSubscriptions` params)

**Interfaces:**
- Produces: `NEW_PURCHASE_PATH = '/subscription/purchase?intent=new'`; `isNewPurchaseIntent(searchParams: URLSearchParams): boolean`; `getSubscriptionDisplayLabel(sub, t, isMultiTariff?)`

- [ ] **Step 1: Write failing vitest for routes + identity A fallback `#seq`**

Create `src/components/subscription/purchase/purchaseRoutes.test.ts`:

```typescript
import { describe, expect, it } from 'vitest';
import { NEW_PURCHASE_PATH, isNewPurchaseIntent } from './purchaseRoutes';

describe('purchaseRoutes', () => {
  it('detects intent=new', () => {
    expect(isNewPurchaseIntent(new URLSearchParams('intent=new'))).toBe(true);
    expect(isNewPurchaseIntent(new URLSearchParams('subscriptionId=1'))).toBe(false);
    expect(NEW_PURCHASE_PATH).toContain('intent=new');
  });
});
```

Add to `subscriptionDisplayLabel.test.ts`:

```typescript
  it('falls back to tariff #seq in multi-tariff', () => {
    expect(
      getSubscriptionDisplayLabel(
        { tariff_name: 'Moon', panel_username: null, account_sequence: 4 },
        t,
        true,
      ),
    ).toBe('Moon #4');
  });
```

- [ ] **Step 2: Run vitest to verify fail**

Run: `cd /opt/cabinet && npx vitest run src/components/subscription/purchase/purchaseRoutes.test.ts src/utils/subscriptionDisplayLabel.test.ts`
Expected: FAIL — `purchaseRoutes` missing; `#seq` test may already pass if helper exists but API types omit fields.

- [ ] **Step 3: Implement**

Copy donor `purchaseRoutes.ts` from `/opt/remnabot/cabinet/src/components/subscription/purchase/purchaseRoutes.ts` (two exports only).

Copy search helpers from donor `subscriptionDisplayLabel.ts` if missing (`subscriptionMatchesSearch`, `filterSubscriptionsByQuery`). Keep identity A (already in helper).

Extend `SubscriptionListItem` in `src/types/index.ts`:

```typescript
  account_sequence?: number;
  panel_username?: string | null;
  purchase_note?: string | null;
  user_disabled?: boolean;
```

And `SubscriptionsListResponse`:

```typescript
  total?: number;
```

Change `getSubscriptions` to accept `{ offset?, limit?, search? }` and pass them as axios `params` (same as donor `/opt/remnabot/cabinet/src/api/subscription.ts`).

- [ ] **Step 4: Run vitest**

Run: `cd /opt/cabinet && npx vitest run src/components/subscription/purchase/purchaseRoutes.test.ts src/utils/subscriptionDisplayLabel.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /opt/cabinet
git add src/components/subscription/purchase/purchaseRoutes.ts src/components/subscription/purchase/purchaseRoutes.test.ts src/utils/subscriptionDisplayLabel.ts src/utils/subscriptionDisplayLabel.test.ts src/types/index.ts src/api/subscription.ts
git commit -m "$(cat <<'EOF'
feat(cabinet): purchase intent=new helper and identity A list fields

EOF
)"
```

---

### Task 9: Cabinet list search + dashboard buy-another

**Files:**
- Modify: `/opt/cabinet/src/pages/Subscriptions.tsx`
- Modify: `/opt/cabinet/src/pages/Dashboard.tsx`
- Modify: `/opt/cabinet/src/components/subscription/SubscriptionListCard.tsx` (pass `isMultiTariff` into `getSubscriptionDisplayLabel`)

**Interfaces:**
- Consumes: Task 8 `NEW_PURCHASE_PATH`, `getSubscriptions({search, offset, limit})`

- [ ] **Step 1: Port search UI from donor Subscriptions.tsx (do not replace the 1.67 file wholesale)**

From `/opt/remnabot/cabinet/src/pages/Subscriptions.tsx` copy these behaviors into the 1.67 page: `searchQuery` + 300ms debounce, `showSearch` when `accountTotal >= 2`, search input + clear + no-results, `PAGE_LIMIT = 10` with offset pagination, and `NEW_PURCHASE_PATH` for empty/buy-another/browse CTAs. Use donor `getSubscriptions({ offset, limit, search })` plus a summary query (`limit: 100`) for `accountTotal` / `hasActivePaid`.

Keep 1.67 glass/skeleton imports. Replace every `navigate('/subscription/purchase')` with `navigate(NEW_PURCHASE_PATH)`.

In `SubscriptionListCard`, call `getSubscriptionDisplayLabel(subscription, t, true)` when the parent is multi-tariff (pass a boolean prop `isMultiTariff` from `Subscriptions.tsx`).

In `Dashboard.tsx`, change the three `to="/subscription/purchase"` links to `NEW_PURCHASE_PATH`.

- [ ] **Step 2: Typecheck / vitest**

Run: `cd /opt/cabinet && npx vitest run src/utils/subscriptionDisplayLabel.test.ts`
Expected: PASS. Fix TypeScript errors in the edited files.

- [ ] **Step 3: Commit**

```bash
cd /opt/cabinet
git add src/pages/Subscriptions.tsx src/pages/Dashboard.tsx src/components/subscription/SubscriptionListCard.tsx
git commit -m "$(cat <<'EOF'
feat(cabinet): subscription search and isolated buy-another CTAs

EOF
)"
```

---

### Task 10: Cabinet purchase page unbinds on intent=new

**Files:**
- Modify: `/opt/cabinet/src/pages/SubscriptionPurchase.tsx`
- Modify: `/opt/cabinet/src/components/subscription/purchase/TariffPickerGrid.tsx`

**Interfaces:**
- Consumes: `isNewPurchaseIntent`, `purchaseIntent?: 'new' | 'renew'`

- [ ] **Step 1: Port the donor unbind pattern (surgical)**

In `SubscriptionPurchase.tsx`, after reading `subscriptionId` from search params:

```typescript
  const isNewPurchase = isNewPurchaseIntent(searchParams);
  const effectiveSubscriptionId = isNewPurchase ? undefined : subscriptionId;
```

Use `effectiveSubscriptionId` in `getSubscription` / `getPurchaseOptions` query keys and calls. Set `const subscription = isNewPurchase ? null : (subscriptionResponse?.subscription ?? null)`. Disable the subscription query when `isNewPurchase && effectiveSubscriptionId == null`.

Pass `purchaseIntent={isNewPurchase ? 'new' : 'renew'}` and `subscriptionId={effectiveSubscriptionId}` into `TariffPickerGrid` / `TariffPurchaseForm`.

In `TariffPickerGrid.tsx`, add optional `purchaseIntent?: 'new' | 'renew'`. When `purchaseIntent === 'new'`, do not take renew/switch/legacy branches — show the purchase CTA (`subscription.buyNewAccount` with fallback `'خرید اکانت جدید'`). Copy the `isNewPurchase` branches from donor `TariffPickerGrid.tsx` rather than rewriting pricing display.

- [ ] **Step 2: Verify TypeScript**

Run: `cd /opt/cabinet && npx tsc --noEmit --pretty false | head`
Expected: no errors in the edited files.

- [ ] **Step 3: Commit**

```bash
cd /opt/cabinet
git add src/pages/SubscriptionPurchase.tsx src/components/subscription/purchase/TariffPickerGrid.tsx
git commit -m "$(cat <<'EOF'
fix(cabinet): intent=new catalog purchase does not bind an existing sub

EOF
)"
```

---

### Task 11: Cabinet detail sales UX

**Files:**
- Modify: `/opt/cabinet/src/pages/Subscription.tsx` (title, first-connect gate, connect+guide, buy-another row)

**Interfaces:**
- Consumes: `getSubscriptionDisplayLabel`, `NEW_PURCHASE_PATH`

- [ ] **Step 1: Title + copy**

Replace the `<h1>` that uses `subscription?.tariff_name` with identity A (`getSubscriptionDisplayLabel(subscription, t, isMultiTariff)`). Add a copy-username button next to the title when the label is a real panel username (same pattern as donor ~498–517). Use existing `CopyIcon` / `CheckIcon`.

- [ ] **Step 2: Gate first-connect**

Compute `showFirstConnectChecklist` as in donor:

```typescript
            const showFirstConnectChecklist =
              subscription.is_active &&
              !subscription.is_limited &&
              usedGb === 0 &&
              !shouldHideConnectionLink &&
              !!displayedConnectionUrl;
```

Wrap the existing checklist JSX in `{showFirstConnectChecklist && (...)}`. Keep `volumeEmptyHint` when `usedGb === 0`.

- [ ] **Step 3: Config + guide**

Next to (or instead of only) the single `HoverBorderGradient` connect control, add the donor two-button grid: «get config» opens `ConfigDeliverySheet`; «open guide» `navigate(\`/connection?sub=${subscriptionId}\`)`. Keep the existing sheet. Disable guide/config when at device limit.

- [ ] **Step 4: Buy-another in additional options**

Inside the additional-options card (before device/traffic sheets), if `isMultiTariff`:

```tsx
            {isMultiTariff && (
              <Link to={NEW_PURCHASE_PATH} className="mb-4 block w-full rounded-xl border p-4 text-start">
                <div className="font-medium">+ {t('subscriptions.buyAnother')}</div>
              </Link>
            )}
```

Do not add note/disable sheets.

- [ ] **Step 5: Commit**

```bash
cd /opt/cabinet
git add src/pages/Subscription.tsx
git commit -m "$(cat <<'EOF'
feat(cabinet): production sales UX on subscription detail (title, guide, buy-new)

EOF
)"
```

---

### Task 12: RTL directional icons

**Files:**
- Modify: `/opt/cabinet/src/components/icons/index.tsx` (`BackIcon`, `ChevronRightIcon`, `ArrowRightIcon` if used as forward chrome)
- Create: `/opt/cabinet/src/components/icons/directional.test.ts`

**Interfaces:**
- Produces: `rtl:scale-x-[-1]` on directional icons only

- [ ] **Step 1: Write a static test**

Create `src/components/icons/directional.test.ts`:

```typescript
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

describe('directional icons', () => {
  it('flips back and chevron in rtl', () => {
    const src = readFileSync(new URL('./index.tsx', import.meta.url), 'utf8');
    expect(src).toMatch(/export const BackIcon[\s\S]*rtl:scale-x-\[-1\]/);
    expect(src).toMatch(/export const ChevronRightIcon[\s\S]*rtl:scale-x-\[-1\]/);
    expect(src).not.toMatch(/export const SearchIcon[\s\S]*rtl:scale-x-\[-1\]/);
  });
});
```

- [ ] **Step 2: Run to fail, then add classes**

Run: `cd /opt/cabinet && npx vitest run src/components/icons/directional.test.ts`

On `BackIcon` and `ChevronRightIcon`, merge `rtl:scale-x-[-1]` into `cn(...)`. Do not add it to Search/Plus/Close.

- [ ] **Step 3: Run vitest PASS and commit**

```bash
cd /opt/cabinet
git add src/components/icons/index.tsx src/components/icons/directional.test.ts
git commit -m "$(cat <<'EOF'
fix(cabinet): mirror back and chevron icons in Persian RTL

EOF
)"
```

---

### Task 13: Operator smoke (no code)

**Files:** none to change except an evidence note after smoke: `/opt/remnabot1/docs/superpowers/evidence/smoke-2026-09-04-sales-surface.md` (create when operator `تایید`).

- [ ] **Step 1: Agent automated gate**

```bash
cd /opt/remnabot1 && uv run pytest tests/database/test_day1_orm_columns.py tests/custom/test_cache_panel_username.py tests/crud/test_account_sequence.py tests/utils/test_subscription_list_display.py tests/utils/test_subscription_purchase_intent.py tests/services/test_menu_layout_service.py tests/test_wholesale_pricing.py tests/cabinet/test_sales_edges_use_pricing_engine.py tests/cabinet/test_multi_tariff_search.py -q
cd /opt/cabinet && npx vitest run src/components/subscription/purchase/purchaseRoutes.test.ts src/utils/subscriptionDisplayLabel.test.ts src/components/icons/directional.test.ts
```

Expected: PASS.

- [ ] **Step 2: Operator checklist (STOP — user-visible)**

1. RC bot `/start` with an already-active sub: «خرید سرویس» visible; catalog purchase creates a **second** row; Toman prices; if a test partner exists, cheaper than retail on the same period.
2. Renew from that sub’s detail extends **that** row; traffic/device addons still priced.
3. `https://panel.rookari.com/subscriptions`: unique titles; search; buy-another does not renew the open sub.
4. `/subscriptions/<id>`: identity A title, gated first-connect, config + guide, buy-another row.
5. Mini-app fa: back/chevron point the logical way.

Do not start M7 from this smoke.

---

## Self-review (spec coverage)

| Spec requirement | Task |
|---|---|
| Identity A ORM + cache + no autogenerate | 1–2 |
| Identity A titles (list, rich, cabinet) | 3, 8–11 |
| Drop unique from model | 1 |
| Obsolete brand_serial titles | 3 |
| Main-menu buy + clear pin | 4 |
| Extend predicate, no empty-pin tariff lookup | 5 |
| PricingEngine matrix | 6 |
| Cabinet API search/DTO | 7 |
| `intent=new` + picker | 8, 10 |
| List search + dashboard CTA | 9 |
| Detail sales UX | 11 |
| RTL icons | 12 |
| Smoke; no M7 | 13 |
| Partner UI / 4.4 merge / file replace | out of scope (not tasked) |
