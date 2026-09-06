# Sales Buy-New Isolation + Panel Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do **not** invoke finishing-a-development-branch until the operator smoke in Task 4 passes. Do **not** start M7-T1 / DNS / production token.

**Goal:** Catalog and cabinet `intent=new` create a new bot row and Remnawave account; detail renew/traffic-top-up stay on the pinned row; extend no longer aborts SQL before the panel call.

**Architecture:** Reuse `should_extend_multi_tariff`. Wire the two leftover Telegram confirms and the cabinet purchase API the same way period-confirm already works. Skip the Lava shift when Lava is off; rollback if a query still aborts the session. `TRAFFIC_SELECTION_MODE=selectable` on RC env only.

**Tech Stack:** Python 3.13 / pytest (`uv run pytest`) on `/opt/remnabot1` branch `prod-cutover`. Donor read-only: `/opt/remnabot`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-07-sales-buy-new-panel-sync-design.md` (operator تایید 2026-09-07).
- Work order: Tasks 1–2 buy-new isolation, Task 3 Lava session, Task 4 env + smoke. Do not skip ahead.
- Do not replace `tariff_purchase.py` or cabinet React wholesale. No new Alembic. Do not create `lava_subscriptions`.
- Do not switch `MAIN_MENU_MODE` to `cabinet`. Do not start M7-T1.
- `PricingEngine` stays the only price brain. Do not invert period price onto traffic.
- Commit **only** the files named in that task. Working tree may have unrelated dirty files (`menu_layout/service.py`, docs, `0112_*`).
- One concern per commit. English digits. Do not commit `.env` / `.env.rehearsal`.
- Donor for confirm/API shape: `/opt/remnabot/app/handlers/subscription/tariff_purchase.py` (`handle_custom_confirm` ~1822) and `/opt/remnabot/app/cabinet/routes/subscription_modules/purchase.py` (~993).

---

## File map

| File | Responsibility |
|---|---|
| `/opt/remnabot1/app/utils/subscription_purchase_intent.py` | Unchanged helper: `should_extend_multi_tariff(state_data, *, existing_sub, renew_only=False) -> bool` |
| `/opt/remnabot1/app/handlers/subscription/tariff_purchase.py` | `handle_custom_confirm` (~1358) and `confirm_daily_tariff_purchase` (~2320): pin-only load + predicate |
| `/opt/remnabot1/tests/services/test_tariff_purchase_subscription_pinning.py` | AST pins for those two functions |
| `/opt/remnabot1/app/cabinet/routes/subscription_modules/purchase.py` | Empty `subscription_id` → create; delete tariff-id fallback |
| `/opt/remnabot1/tests/cabinet/test_purchase_tariff_expired_trial_reuse.py` | Invert: no `get_subscription_by_user_and_tariff(` call |
| `/opt/remnabot1/app/services/payment/lava.py` | `shift_lava_next_charge_after_manual_extension`: no-op if Lava off; rollback on error |
| `/opt/remnabot1/tests/services/test_lava_recurrent.py` | Guard when Lava disabled |
| RC `.env` / `.env.rehearsal` | `TRAFFIC_SELECTION_MODE=selectable` (not git) |

---

### Task 1: Telegram custom + daily confirms use the pin

**Files:**
- Modify: `/opt/remnabot1/app/handlers/subscription/tariff_purchase.py` (`handle_custom_confirm` ~1358–1381, `confirm_daily_tariff_purchase` ~2320–2328)
- Test: `/opt/remnabot1/tests/services/test_tariff_purchase_subscription_pinning.py`

**Interfaces:**
- Consumes: `should_extend_multi_tariff(state_data: dict, *, existing_sub: Any, renew_only: bool = False) -> bool`; `get_subscription_by_id_for_user(db, sub_id, user_id)` (already imported)
- Produces: empty `target_subscription_id` → `create_paid_subscription`; pinned matching row → existing extend/mutate branch

- [ ] **Step 1: Write the failing AST tests**

Append to `/opt/remnabot1/tests/services/test_tariff_purchase_subscription_pinning.py`:

```python
def test_handle_custom_confirm_uses_pin_not_tariff_lookup() -> None:
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'handle_custom_confirm')
    body = _function_source(source, func)
    assert 'target_subscription_id' in body
    assert 'should_extend_multi_tariff' in body
    assert 'get_subscription_by_id_for_user' in body
    assert body.find('get_subscription_by_user_and_tariff(') < 0
    assert 's.tariff_id == tariff.id' not in body


def test_confirm_daily_tariff_purchase_uses_pin_not_tariff_lookup() -> None:
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'confirm_daily_tariff_purchase')
    body = _function_source(source, func)
    assert 'target_subscription_id' in body
    assert 'should_extend_multi_tariff' in body
    assert 'get_subscription_by_id_for_user' in body
    assert body.find('get_subscription_by_user_and_tariff(') < 0
    assert 's.tariff_id == tariff.id' not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/remnabot1 && uv run pytest tests/services/test_tariff_purchase_subscription_pinning.py::test_handle_custom_confirm_uses_pin_not_tariff_lookup tests/services/test_tariff_purchase_subscription_pinning.py::test_confirm_daily_tariff_purchase_uses_pin_not_tariff_lookup -v`

Expected: FAIL — `s.tariff_id == tariff.id` still in both bodies; `should_extend_multi_tariff` missing from those functions.

- [ ] **Step 3: Wire `handle_custom_confirm`**

This function already has `state_data = await state.get_data()` near the top (custom_days / custom_traffic). Reuse that dict. Do not fetch FSM twice.

Replace the block starting at `# Проверяем есть ли уже подписка` through `if existing_subscription:` (the extend call) with the production shape (`/opt/remnabot/app/handlers/subscription/tariff_purchase.py` ~1822–1834):

```python
    if settings.is_multi_tariff_enabled():
        _pinned_sub_id = state_data.get('target_subscription_id')
        existing_subscription = None
        if _pinned_sub_id:
            existing_subscription = await get_subscription_by_id_for_user(db, int(_pinned_sub_id), db_user.id)
            if existing_subscription and existing_subscription.tariff_id != tariff.id:
                existing_subscription = None
    else:
        existing_subscription = await get_subscription_by_user_id(db, db_user.id)

    try:
        if should_extend_multi_tariff(state_data, existing_sub=existing_subscription) and existing_subscription:
```

Keep the existing extend_subscription / create_paid_subscription bodies under that `if` / `else`. Do not change refund or Remnawave sync below.

- [ ] **Step 4: Wire `confirm_daily_tariff_purchase`**

This function does **not** already load FSM. Immediately before the `# Проверяем есть ли уже подписка` block, fetch once, then pin-load like custom confirm:

```python
    _state_data = await state.get_data() if state else {}
    if settings.is_multi_tariff_enabled():
        _pinned_sub_id = _state_data.get('target_subscription_id')
        existing_subscription = None
        if _pinned_sub_id:
            existing_subscription = await get_subscription_by_id_for_user(db, int(_pinned_sub_id), db_user.id)
            if existing_subscription and existing_subscription.tariff_id != tariff.id:
                existing_subscription = None
    else:
        existing_subscription = await get_subscription_by_user_id(db, db_user.id)

    try:
        if should_extend_multi_tariff(_state_data, existing_sub=existing_subscription) and existing_subscription:
```

Keep the existing daily mutate branch and the `else: create_paid_subscription` branch. Do not copy production `reset_period` / MAX_ACTIVE guard from period-confirm into this daily path.

- [ ] **Step 5: Run tests**

Run: `cd /opt/remnabot1 && uv run pytest tests/services/test_tariff_purchase_subscription_pinning.py tests/utils/test_subscription_purchase_intent.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /opt/remnabot1
git add app/handlers/subscription/tariff_purchase.py tests/services/test_tariff_purchase_subscription_pinning.py
git commit -m "$(cat <<'EOF'
fix(sales): create on custom and daily catalog confirms when pin is empty

EOF
)"
```

---

### Task 2: Cabinet purchase API empty pin creates

**Files:**
- Modify: `/opt/remnabot1/app/cabinet/routes/subscription_modules/purchase.py` (~753–779 lookup, ~876 assignment)
- Modify: `/opt/remnabot1/tests/cabinet/test_purchase_tariff_expired_trial_reuse.py`

**Interfaces:**
- Consumes: `request.subscription_id: int | None`; `get_subscription_by_id_for_user`
- Produces: multi-tariff + `subscription_id is None` → `subscription is None` → `create_paid_subscription`. Renew with an id still extends that row (including expired trial of that id).

- [ ] **Step 1: Rewrite the cabinet source test**

Replace the body of `test_purchase_tariff_tariff_lookup_includes_inactive` (keep the helper functions) with:

```python
def test_purchase_tariff_empty_pin_does_not_lookup_by_tariff() -> None:
    """Catalog / intent=new must not resolve an existing row by (user, tariff)."""
    source = PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'purchase_tariff')
    body = _function_source(source, func)
    assert body.find('get_subscription_by_user_and_tariff(') < 0, (
        'purchase_tariff must not call get_subscription_by_user_and_tariff when '
        'the cabinet catalog pin is empty — that silent-extends an existing row'
    )
    assert 'request.subscription_id is None' in body
    assert 'subscription = None' in body


def test_purchase_tariff_pinned_id_uses_ownership_lookup() -> None:
    source = PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'purchase_tariff')
    body = _function_source(source, func)
    assert 'get_subscription_by_id_for_user' in body
```

Update the module docstring to say: empty pin creates; expired-trial reuse is only via pinned `subscription_id` from the detail renew path, not catalog tariff lookup.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/remnabot1 && uv run pytest tests/cabinet/test_purchase_tariff_expired_trial_reuse.py -v`

Expected: FAIL — `get_subscription_by_user_and_tariff(` still present.

- [ ] **Step 3: Remove the tariff fallback and force create on empty pin**

In `purchase_tariff`, delete this block (currently after the divergent-tariff warning):

```python
            if existing_subscription is None:
                from app.database.crud.subscription import get_subscription_by_user_and_tariff

                existing_subscription = await get_subscription_by_user_and_tariff(
                    db, user.id, tariff.id, include_inactive=True
                )
```

Keep the pin load via `get_subscription_by_id_for_user` when `request.subscription_id is not None`. Keep setting `existing_subscription = None` on tariff divergence (do not look up by tariff).

Immediately after `subscription = existing_subscription` add:

```python
        subscription = existing_subscription
        if settings.is_multi_tariff_enabled() and request.subscription_id is None:
            subscription = None
```

Do not change `create_paid_subscription` / `extend_subscription` bodies below. Trial conversion on a **pinned** expired row still goes through extend.

- [ ] **Step 4: Run tests**

Run: `cd /opt/remnabot1 && uv run pytest tests/cabinet/test_purchase_tariff_expired_trial_reuse.py tests/crud/test_trial_conversion_on_paid_purchase.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /opt/remnabot1
git add app/cabinet/routes/subscription_modules/purchase.py tests/cabinet/test_purchase_tariff_expired_trial_reuse.py
git commit -m "$(cat <<'EOF'
fix(sales): cabinet catalog purchase creates when subscription_id is absent

EOF
)"
```

---

### Task 3: Lava shift must not abort the SQL session

**Files:**
- Modify: `/opt/remnabot1/app/services/payment/lava.py` (`shift_lava_next_charge_after_manual_extension` ~1308)
- Test: `/opt/remnabot1/tests/services/test_lava_recurrent.py`

**Interfaces:**
- Consumes: `settings.is_lava_enabled() -> bool`; `db: AsyncSession`; `subscription_id: int`; `days: int`
- Produces: `shift_lava_next_charge_after_manual_extension(db, subscription_id, days) -> None` — returns without querying when Lava is off; on any exception logs, `await db.rollback()`, returns (does not raise)

- [ ] **Step 1: Write the failing tests**

Append to `/opt/remnabot1/tests/services/test_lava_recurrent.py`:

```python
async def test_shift_next_charge_skips_when_lava_disabled(monkeypatch):
    from unittest.mock import AsyncMock

    from app.config import settings
    from app.services.payment.lava import shift_lava_next_charge_after_manual_extension

    monkeypatch.setattr(type(settings), 'is_lava_enabled', lambda self: False)
    db = AsyncMock()
    await shift_lava_next_charge_after_manual_extension(db, 1, 30)
    db.execute.assert_not_awaited()
    db.rollback.assert_not_awaited()


async def test_shift_next_charge_rollbacks_after_query_error(monkeypatch):
    from unittest.mock import AsyncMock

    from app.config import settings
    from app.database.crud import lava_subscription as sub_crud
    from app.services.payment.lava import shift_lava_next_charge_after_manual_extension

    monkeypatch.setattr(type(settings), 'is_lava_enabled', lambda self: True)
    db = AsyncMock()
    db.rollback = AsyncMock()
    monkeypatch.setattr(
        sub_crud,
        'get_active_lava_subscription_by_subscription',
        AsyncMock(side_effect=RuntimeError('relation "lava_subscriptions" does not exist')),
    )
    await shift_lava_next_charge_after_manual_extension(db, 1, 30)
    db.rollback.assert_awaited()
```

Do not add `@pytest.mark.asyncio` unless neighboring tests in this file use it (they currently do not).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/remnabot1 && uv run pytest tests/services/test_lava_recurrent.py::test_shift_next_charge_skips_when_lava_disabled tests/services/test_lava_recurrent.py::test_shift_next_charge_rollbacks_after_query_error -v`

Expected: FAIL — query still runs when disabled, or rollback not called.

- [ ] **Step 3: Implement skip + rollback**

In `shift_lava_next_charge_after_manual_extension`, after `if days <= 0: return`:

```python
    from app.config import settings

    if not settings.is_lava_enabled():
        return
```

In the existing `except Exception as error:` block, after the `logger.warning(...)`, add:

```python
        try:
            await db.rollback()
        except Exception:
            pass
```

Do not create tables. Do not change `extend_subscription` callers unless a test proves the helper is not used.

- [ ] **Step 4: Run tests**

Run: `cd /opt/remnabot1 && uv run pytest tests/services/test_lava_recurrent.py -v`

Expected: PASS. If an existing shift test now no-ops because `is_lava_enabled` is False, add `monkeypatch.setattr(type(settings), 'is_lava_enabled', lambda self: True)` only inside that test (or `_agent`), not in RC env.

- [ ] **Step 5: Commit**

```bash
cd /opt/remnabot1
git add app/services/payment/lava.py tests/services/test_lava_recurrent.py
git commit -m "$(cat <<'EOF'
fix(sales): skip Lava next-charge shift when disabled so extend can sync the panel

EOF
)"
```

---

### Task 4: RC selectable + agent gate + operator smoke (STOP)

**Files:**
- Modify (not git): `/opt/remnabot1/.env` and `/opt/remnabot1/.env.rehearsal` — set `TRAFFIC_SELECTION_MODE=selectable`
- Create after operator تایید: `/opt/remnabot1/docs/superpowers/evidence/smoke-2026-09-07-sales-buy-new.md`

**Interfaces:**
- Consumes: Tasks 1–3 on `prod-cutover`
- Produces: RC catalog shows predefined traffic packages then period (production order). Smoke evidence only after operator `تایید`.

- [ ] **Step 1: Set env (do not commit)**

Set `TRAFFIC_SELECTION_MODE=selectable` in `/opt/remnabot1/.env.rehearsal` (the file `rehearsal_bot` loads). If `/opt/remnabot1/.env` also has the key, set it there too. Do not commit either file.

Rebuild and recreate only the rehearsal bot:

```bash
cd /opt/remnabot1
docker compose -p rehearsal -f docker-compose.rehearsal.yml --profile bot-app build rehearsal_bot
docker compose -p rehearsal -f docker-compose.rehearsal.yml --profile bot-app up -d rehearsal_bot
docker inspect -f '{{.State.Health.Status}}' rehearsal_bot
curl -sS http://127.0.0.1:8081/health
```

Expected: health `healthy`; `/health` 200. Confirm selectable with:

```bash
docker exec rehearsal_bot grep '^TRAFFIC_SELECTION_MODE=' /app/.env || docker exec rehearsal_bot printenv TRAFFIC_SELECTION_MODE
```

Expected: `selectable`. Do not `compose up` production volumes or sandbox `remnawave_bot`.

- [ ] **Step 2: Agent automated gate**

Run: `cd /opt/remnabot1 && uv run pytest tests/services/test_tariff_purchase_subscription_pinning.py tests/utils/test_subscription_purchase_intent.py tests/cabinet/test_purchase_tariff_expired_trial_reuse.py tests/crud/test_trial_conversion_on_paid_purchase.py tests/services/test_lava_recurrent.py -v`

Expected: PASS

- [ ] **Step 3: STOP — operator checklist**

Do not start M7. Ask the operator to:

1. Telegram: خرید سرویس → tariff → **traffic packages** → period → wallet (if balance covers) → **second** row + new Remnawave user.
2. Detail → تمدید → traffic → period → **same** row / same panel account, later expiry.
3. Detail → افزایش ترافیک → packages only, **no period**, same row.
4. Cabinet `https://panel.rookari.com/subscription/purchase?intent=new` → same as (1).
5. Low balance → C2C / wallet methods visible.

On `تایید`, write the short evidence note and stop. On FAIL, do not start M7.

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|---|---|
| Custom-days empty pin creates | Task 1 |
| Daily empty pin creates | Task 1 |
| Cabinet `subscription_id is None` creates | Task 2 |
| Renew from detail still extends pinned id | Task 1–2 (predicate / id load kept) |
| Traffic top-up unchanged (no period) | No code (out of these files) |
| `TRAFFIC_SELECTION_MODE=selectable` | Task 4 env |
| Lava skip, no table, rollback | Task 3 |
| Telegram + cabinet both sales; no `MAIN_MENU_MODE=cabinet` | Constraints |
| No M7 | Task 4 STOP |
| No React files | File map |
| PricingEngine unchanged | Constraints |
