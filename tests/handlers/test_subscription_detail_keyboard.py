"""Pins the autopay button on the multi-tariff subscription detail card.

Regression: in multi-tariff mode (`MULTI_TARIFF_ENABLED=true`), the detail
keyboard for a single subscription used to show 6 buttons (link / extend /
traffic / devices / reissue / back). The 💳 Автоплатеж button was only
present in the legacy single-subscription menu, so users in multi-tariff
mode had no way to reach the autopay menu from a specific subscription.

This test file pins:
  1. The autopay button is present on active subscriptions
  2. The autopay button is NOT shown on expired/disabled subscriptions
     (no point auto-renewing what's already inactive — and the rest of
     the action set is also stripped for those statuses)
  3. The autopay button uses the legacy callback `subscription_autopay`
     without sub_id — multi-tariff resolution flows through FSM's
     active_subscription_id which `show_subscription_detail` must set.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.handlers.subscription import my_subscriptions
from app.handlers.subscription.my_subscriptions import (
    _build_subscription_detail_keyboard,
    show_subscription_detail,
)


def _callbacks(keyboard) -> list[str]:
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


@pytest.fixture
def mock_connect_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        'app.utils.subscription_utils.resolve_connect_webapp_url',
        AsyncMock(return_value=None),
    )


@pytest.mark.anyio('asyncio')
async def test_autopay_button_present_for_active_subscription(mock_connect_url) -> None:
    sub = SimpleNamespace(actual_status='active', user_disabled=False)

    keyboard = await _build_subscription_detail_keyboard(sub_id=42, sub=sub)

    callbacks = _callbacks(keyboard)
    assert 'subscription_autopay' in callbacks, (
        'Multi-tariff detail card must expose 💳 Автоплатеж; without this button '
        'users with multiple subscriptions have no entry point to the autopay menu.'
    )


@pytest.mark.anyio('asyncio')
async def test_autopay_button_uses_legacy_callback_without_sub_id(mock_connect_url) -> None:
    sub_id = 99999937
    sub = SimpleNamespace(actual_status='active', user_disabled=False)

    keyboard = await _build_subscription_detail_keyboard(sub_id=sub_id, sub=sub)

    autopay_buttons = [
        button for row in keyboard.inline_keyboard for button in row if button.callback_data == 'subscription_autopay'
    ]
    assert len(autopay_buttons) == 1
    assert autopay_buttons[0].callback_data == 'subscription_autopay'
    assert str(sub_id) not in autopay_buttons[0].callback_data


@pytest.mark.anyio('asyncio')
async def test_autopay_button_hidden_on_expired_subscription(mock_connect_url) -> None:
    sub = SimpleNamespace(actual_status='expired', user_disabled=False)

    keyboard = await _build_subscription_detail_keyboard(sub_id=42, sub=sub)

    assert 'subscription_autopay' not in _callbacks(keyboard)


@pytest.mark.anyio('asyncio')
async def test_autopay_button_hidden_on_disabled_subscription(mock_connect_url) -> None:
    sub = SimpleNamespace(actual_status='disabled', user_disabled=False)

    keyboard = await _build_subscription_detail_keyboard(sub_id=42, sub=sub)

    assert 'subscription_autopay' not in _callbacks(keyboard)


@pytest.mark.anyio('asyncio')
async def test_user_disabled_keyboard_has_enable_not_renew(mock_connect_url) -> None:
    sub = SimpleNamespace(actual_status='disabled', user_disabled=True)

    keyboard = await _build_subscription_detail_keyboard(sub_id=42, sub=sub)

    callbacks = _callbacks(keyboard)
    assert 'sub_enable:42' in callbacks
    assert 'se:42' not in callbacks
    assert 'subscription_autopay' not in callbacks


@pytest.mark.anyio('asyncio')
async def test_active_keyboard_has_two_column_rows(mock_connect_url) -> None:
    sub = SimpleNamespace(actual_status='active', user_disabled=False)

    keyboard = await _build_subscription_detail_keyboard(sub_id=42, sub=sub)

    assert len(keyboard.inline_keyboard[0]) == 2
    assert len(keyboard.inline_keyboard[1]) == 2
    assert len(keyboard.inline_keyboard[2]) == 2
    assert len(keyboard.inline_keyboard[3]) == 1
    assert 'sub_edit_note:42' in _callbacks(keyboard)
    assert 'sub_disable:42' in _callbacks(keyboard)


@pytest.mark.anyio('asyncio')
async def test_autopay_button_present_when_status_unknown(mock_connect_url) -> None:
    keyboard = await _build_subscription_detail_keyboard(sub_id=42, sub=None)

    assert 'subscription_autopay' in _callbacks(keyboard)


@pytest.mark.anyio('asyncio')
async def test_show_subscription_detail_writes_active_subscription_id_to_fsm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole multi-tariff autopay fix hinges on this side effect: opening a
    subscription detail card writes its id to FSM so downstream handlers that fire
    sub_id-less callbacks (subscription_autopay, etc.) can resolve the right sub.

    Without a test pinning this write, a refactor that removes the
    state.update_data(active_subscription_id=sub_id) line silently re-introduces
    the multi-tariff bug while the keyboard-structure tests remain green."""
    sub_id = 77
    subscription = SimpleNamespace(
        id=sub_id,
        actual_status='active',
        tariff=SimpleNamespace(name='X'),
        traffic_limit_gb=10,
        traffic_used_gb=1.0,
        device_limit=1,
        end_date=None,
        autopay_enabled=False,
        autopay_days_before=3,
    )

    monkeypatch.setattr(my_subscriptions, 'get_subscription_by_id_for_user', AsyncMock(return_value=subscription))

    state = SimpleNamespace(update_data=AsyncMock())
    db_user = SimpleNamespace(id=1, language='ru')
    callback = SimpleNamespace(
        data=f'sm:{sub_id}',
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
    )

    try:
        await show_subscription_detail(callback, db_user, SimpleNamespace(), state)
    except Exception:
        # The handler may try to render text/keyboard using attrs we haven't fully mocked.
        # That's fine — we only care that the FSM write happened BEFORE any rendering.
        pass

    # The contract: active_subscription_id MUST be written with the resolved sub_id.
    state.update_data.assert_awaited()
    assert state.update_data.await_args.kwargs.get('active_subscription_id') == sub_id


@pytest.mark.anyio('asyncio')
async def test_show_subscription_detail_does_not_write_fsm_on_idor_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the subscription doesn't belong to the requesting user (IDOR check returns
    None), the handler must short-circuit BEFORE writing to FSM. Otherwise a malicious
    callback with a foreign sub_id would poison the user's FSM with someone else's id."""
    monkeypatch.setattr(my_subscriptions, 'get_subscription_by_id_for_user', AsyncMock(return_value=None))

    state = SimpleNamespace(update_data=AsyncMock())
    db_user = SimpleNamespace(id=1, language='ru')
    callback = SimpleNamespace(
        data='sm:999',
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock()),
    )

    await show_subscription_detail(callback, db_user, SimpleNamespace(), state)

    state.update_data.assert_not_called()
    callback.answer.assert_awaited_once()
