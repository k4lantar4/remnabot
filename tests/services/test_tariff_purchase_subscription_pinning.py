"""Source-level pin for the FSM-driven subscription_id resolution in
`app/handlers/subscription/tariff_purchase.py::confirm_tariff_purchase`.

Background — the bug this defends against
-----------------------------------------
User report (2026-05-16): a user with two subscriptions of the same
tariff (one expired, one active) tries to renew the active one. Money
is deducted, log says "Тариф уже активен у пользователя", money gets
refunded, subscription is NOT extended. User has to re-try.

Root cause: ``confirm_tariff_purchase`` re-queried the target sub by
``(user_id, tariff_id)`` instead of using the EXACT subscription_id
the user clicked on at preview time. Under a race with a concurrent
panel webhook that briefly flips the active sub's status, the lookup
returns ``None`` → falls through to ``create_paid_subscription`` →
the partial UNIQUE ``uq_subscriptions_user_tariff_active`` raises
``IntegrityError`` → "Тариф уже активен" log + refund.

Fix shape:
  1. ``select_tariff_period`` (preview handler) reads
     ``target_subscription_id`` from FSM. If pinned, it loads that row
     via ``get_subscription_by_id_for_user`` for device pricing; if the
     pin is empty, ``_existing_sub`` is None (new row — never a
     tariff-level lookup).
  2. ``confirm_tariff_purchase`` loads by pin only via
     ``get_subscription_by_id_for_user`` (ownership-checked). Empty pin
     → create a new row. Never ``get_subscription_by_user_and_tariff``.

These tests pin the SOURCE-LEVEL contract — a full integration test
would need a real DB + Redis + aiogram FSM dispatcher, which is heavy.
The bug class is "drop the pin", which is grep-detectable.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.config import Settings
from app.handlers.subscription import tariff_purchase as m


TARIFF_PURCHASE_PATH = Path(__file__).resolve().parents[2] / 'app' / 'handlers' / 'subscription' / 'tariff_purchase.py'


def _find_async_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f'async function {name!r} not found in tariff_purchase.py')


def _function_source(source: str, func: ast.AsyncFunctionDef) -> str:
    """Slice the literal source between the function's start and end lines.

    Used so we can grep ONLY inside the function body — assertions about
    "X must appear inside confirm_tariff_purchase" don't false-positive
    on identical names elsewhere in the file.
    """
    lines = source.splitlines(keepends=True)
    end_line = func.end_lineno or len(lines)
    return ''.join(lines[func.lineno - 1 : end_line])


# ---------------------------------------------------------------------------
# Preview handler must pin target_subscription_id.
# ---------------------------------------------------------------------------


def test_select_tariff_period_resolves_and_pins_target_subscription_id() -> None:
    """REGRESSION: ``select_tariff_period`` must honor the FSM pin.
    Pinned id → load that row for device pricing. Empty pin →
    ``_existing_sub = None`` (create a new row). Never look up by
    ``(user, tariff)``.
    """
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'select_tariff_period')
    body = _function_source(source, func)

    assert 'target_subscription_id' in body, (
        'select_tariff_period must read target_subscription_id from FSM — empty pin '
        'means create a new row, not look up by tariff'
    )
    assert 'get_subscription_by_id_for_user' in body, (
        'select_tariff_period must load a pinned subscription via '
        'get_subscription_by_id_for_user (IDOR-safe), not by (user, tariff)'
    )
    assert 'get_subscription_by_user_and_tariff' not in body, (
        'select_tariff_period must not look up by (user, tariff) when the pin is empty — '
        'that re-extends an existing row from catalog buy'
    )

    # Must store target_subscription_id in FSM. Pin the literal kwarg
    # name so a refactor that renames it (and breaks the confirm-side
    # reader) trips this test.
    assert 'target_subscription_id=' in body, (
        'select_tariff_period must write target_subscription_id into FSM state — '
        'confirm_tariff_purchase reads this key to pin the exact subscription user '
        'clicked on, avoiding the race that produced the "Тариф уже активен" bug'
    )


# ---------------------------------------------------------------------------
# Confirm handler must prefer the FSM-pinned id over tariff lookup.
# ---------------------------------------------------------------------------


def test_confirm_tariff_purchase_reads_target_subscription_id_from_fsm() -> None:
    """REGRESSION: ``confirm_tariff_purchase`` must load by FSM pin only.
    Empty pin → create a new row. Never ``get_subscription_by_user_and_tariff``.
    """
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'confirm_tariff_purchase')
    body = _function_source(source, func)

    assert 'target_subscription_id' in body, (
        'confirm_tariff_purchase must read target_subscription_id from FSM state to '
        'pin the exact subscription user confirmed on — without it, this handler '
        'races with concurrent panel webhooks and produces the duplicate-key bug'
    )

    # Must call the ownership-checked lookup, not the unscoped one.
    # ``get_subscription_by_id_for_user`` enforces ``Subscription.user_id == user_id``
    # which is the IDOR protection we want at the FSM-deserialization
    # boundary (the pinned id could in principle be stale or tampered).
    assert 'get_subscription_by_id_for_user' in body, (
        'confirm_tariff_purchase must look up the pinned subscription via '
        'get_subscription_by_id_for_user (IDOR-safe), not the unscoped variant'
    )

    assert 'should_extend_multi_tariff' in body, (
        'confirm_tariff_purchase must gate extend vs create on should_extend_multi_tariff '
        'so an empty pin never extends an existing row of the same tariff'
    )

    # Pin-only: the tariff-level CALL must be gone. A comment that names
    # the helper is allowed; a call with paren is the old fallback.
    fallback_call_idx = body.find('get_subscription_by_user_and_tariff(')
    assert fallback_call_idx < 0, (
        'confirm_tariff_purchase must not call get_subscription_by_user_and_tariff '
        'when the pin is empty — that re-extends an existing row from catalog buy'
    )


def test_confirm_tariff_purchase_guards_against_tariff_divergence() -> None:
    """If the FSM-pinned subscription's tariff_id no longer matches
    the confirm's tariff_id (admin swapped tariff between preview
    and confirm), we must fall back rather than extend a subscription
    of a different tariff with the new tariff's parameters.
    """
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'confirm_tariff_purchase')
    body = _function_source(source, func)

    # The divergence guard must compare tariff_ids. Pin the exact
    # pattern so a refactor that drops this check trips the test.
    assert 'tariff_id != tariff_id' in body or 'existing_sub.tariff_id != tariff_id' in body, (
        'confirm_tariff_purchase must guard against the pinned subscription '
        'pointing to a different tariff than the confirm carries — otherwise '
        'extending it with the wrong tariff parameters would corrupt state'
    )


# ---------------------------------------------------------------------------
# Negative-control: the buggy pattern must NOT remain. If anyone deletes
# the FSM-pin logic and reverts to "lookup by (user, tariff) only", these
# pins fail.
# ---------------------------------------------------------------------------


def test_confirm_tariff_purchase_does_not_use_only_tariff_lookup() -> None:
    """Pre-fix shape: confirm_tariff_purchase ran a single
    ``get_subscription_by_user_and_tariff`` call with no FSM-pinned
    override. Detect a regression to that shape.
    """
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'confirm_tariff_purchase')
    body = _function_source(source, func)

    # If `target_subscription_id` is absent, the fix has been removed.
    assert 'target_subscription_id' in body, (
        'confirm_tariff_purchase no longer pins the FSM target_subscription_id — '
        'this re-opens the race-condition bug fixed by commit handling the '
        'two-subscriptions-same-tariff renewal scenario'
    )


# ---------------------------------------------------------------------------
# Catalog already-active gate must not fire when the pin is empty.
# ---------------------------------------------------------------------------


def test_proceed_already_active_alert_is_gated_on_pin() -> None:
    """REGRESSION: empty pin (catalog / menu_buy) must not pop
    ``TARIFF_PURCHASE_ALREADY_ACTIVE``. Keep the alert only when a pin
    is present (renew accidentally on this handler).
    """
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, '_proceed_with_selected_tariff')
    body = _function_source(source, func)

    assert 'TARIFF_PURCHASE_ALREADY_ACTIVE' in body, (
        '_proceed_with_selected_tariff must still carry the already-active alert for the pinned renew-misroute path'
    )
    pin_idx = body.find("get('target_subscription_id')")
    alert_idx = body.find('TARIFF_PURCHASE_ALREADY_ACTIVE')
    assert pin_idx >= 0, (
        '_proceed_with_selected_tariff must read target_subscription_id from FSM '
        'before deciding whether to show TARIFF_PURCHASE_ALREADY_ACTIVE'
    )
    assert alert_idx > pin_idx, (
        'TARIFF_PURCHASE_ALREADY_ACTIVE must be gated on the FSM pin — empty pin '
        'is catalog buy and must create a new row even if the user already has '
        'that tariff'
    )
    assert 'if _pinned_sub_id:' in body, (
        'the already-active return must sit inside a non-empty pin check so '
        'catalog / menu_buy (cleared pin) can buy a second account of the same tariff'
    )


def _proceed_callback():
    return SimpleNamespace(
        data='tariff_select:77',
        message=SimpleNamespace(edit_text=AsyncMock()),
        answer=AsyncMock(),
    )


def _proceed_state(pin):
    state = MagicMock()
    state.clear = AsyncMock()
    state.update_data = AsyncMock()
    data = {} if pin is None else {'target_subscription_id': pin}
    state.get_data = AsyncMock(return_value=data)
    return state


def _proceed_user():
    user = MagicMock()
    user.id = 1
    user.language = 'ru'
    user.promo_group_id = None
    user.balance_kopeks = 100_000
    user.get_primary_promo_group = MagicMock(return_value=None)
    return user


def _proceed_period_tariff(tariff_id: int = 77):
    tariff = MagicMock()
    tariff.id = tariff_id
    tariff.name = 'Owned'
    tariff.is_active = True
    tariff.is_daily = False
    tariff.can_purchase_custom_days = MagicMock(return_value=False)
    tariff.can_purchase_custom_traffic = MagicMock(return_value=False)
    tariff.period_prices = {'30': 10000}
    tariff.device_limit = 1
    tariff.traffic_limit_gb = 0
    return tariff


async def test_proceed_allows_catalog_buy_when_pin_empty_and_tariff_owned(monkeypatch):
    """Empty pin + already-owned tariff → period keyboard, not the already-active alert."""
    tariff = _proceed_period_tariff(77)
    periods_kb = MagicMock(name='periods_kb')
    owned = SimpleNamespace(
        tariff_id=77,
        is_trial=False,
        end_date=datetime.now(UTC) + timedelta(days=10),
    )
    list_active = AsyncMock(return_value=[owned])

    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)
    monkeypatch.setattr(m, 'get_tariff_by_id', AsyncMock(return_value=tariff))
    monkeypatch.setattr(m, 'format_tariff_info_for_user', MagicMock(return_value='INFO'))
    monkeypatch.setattr(m, 'get_tariff_periods_keyboard', MagicMock(return_value=periods_kb))

    import app.database.crud.subscription as sub_crud

    monkeypatch.setattr(sub_crud, 'get_active_subscriptions_by_user_id', list_active)

    callback = _proceed_callback()
    await m._proceed_with_selected_tariff(callback, _proceed_user(), AsyncMock(), _proceed_state(None), 77)

    list_active.assert_not_awaited()
    alert_calls = [c for c in callback.answer.await_args_list if c.kwargs.get('show_alert')]
    assert alert_calls == [], 'catalog buy must not pop TARIFF_PURCHASE_ALREADY_ACTIVE'
    callback.message.edit_text.assert_awaited_once()
    assert callback.message.edit_text.await_args.kwargs['reply_markup'] is periods_kb


async def test_proceed_alerts_already_active_when_pin_present(monkeypatch):
    """Pinned renew misroute + already-owned tariff → keep the already-active popup."""
    tariff = _proceed_period_tariff(77)
    owned = SimpleNamespace(
        tariff_id=77,
        is_trial=False,
        end_date=datetime.now(UTC) + timedelta(days=10),
    )
    list_active = AsyncMock(return_value=[owned])

    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)
    monkeypatch.setattr(m, 'get_tariff_by_id', AsyncMock(return_value=tariff))
    monkeypatch.setattr(m, 'format_tariff_info_for_user', MagicMock(return_value='INFO'))
    monkeypatch.setattr(m, 'get_tariff_periods_keyboard', MagicMock(return_value=MagicMock()))

    import app.database.crud.subscription as sub_crud

    monkeypatch.setattr(sub_crud, 'get_active_subscriptions_by_user_id', list_active)

    callback = _proceed_callback()
    await m._proceed_with_selected_tariff(callback, _proceed_user(), AsyncMock(), _proceed_state(99), 77)

    list_active.assert_awaited_once()
    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once()
    assert callback.answer.await_args.kwargs.get('show_alert') is True
    answered = callback.answer.await_args.args[0]
    assert 'уже активен' in answered or 'Owned' in answered


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
