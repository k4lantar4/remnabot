"""Tests for bot subscription disable/enable handlers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.handlers.subscription.my_subscriptions import (
    _build_subscription_detail_keyboard,
    _subscription_status_display,
    handle_subscription_disable_confirm,
    handle_subscription_enable,
)
from app.services.subscription_user_toggle_service import SubscriptionToggleError


def _callbacks(keyboard) -> list[str]:
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def test_user_disabled_status_display() -> None:
    from app.localization.texts import get_texts

    texts = get_texts('fa')
    sub = SimpleNamespace(user_disabled=True, actual_status='disabled', is_trial=False)
    assert _subscription_status_display(sub, texts) == 'خاموش شده'


def test_user_disabled_keyboard_shows_enable_without_renew(monkeypatch: pytest.MonkeyPatch) -> None:
    sub = SimpleNamespace(actual_status='disabled', user_disabled=True)
    monkeypatch.setattr(
        'app.utils.subscription_utils.resolve_connect_webapp_url',
        AsyncMock(return_value=None),
    )

    import asyncio

    keyboard = asyncio.run(_build_subscription_detail_keyboard(sub_id=5, sub=sub))

    callbacks = _callbacks(keyboard)
    assert 'sub_enable:5' in callbacks
    assert 'se:5' not in callbacks
    assert 'sub_del:5' not in callbacks


@pytest.mark.anyio('asyncio')
async def test_disable_confirm_shows_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = SimpleNamespace(
        id=9,
        actual_status='active',
        tariff=SimpleNamespace(name='Pro'),
        panel_username='shop',
        account_sequence=1,
    )
    monkeypatch.setattr(
        'app.handlers.subscription.my_subscriptions.get_subscription_by_id_for_user',
        AsyncMock(return_value=subscription),
    )

    message = SimpleNamespace(edit_text=AsyncMock())
    callback = SimpleNamespace(
        data='sub_disable:9',
        answer=AsyncMock(),
        message=message,
    )
    db_user = SimpleNamespace(id=1, language='fa')

    await handle_subscription_disable_confirm(callback, db_user, AsyncMock(), SimpleNamespace())

    message.edit_text.assert_awaited_once()
    text = message.edit_text.await_args.args[0]
    assert 'se:9' not in str(message.edit_text.await_args)
    assert 'روشن کردن' in text or 'فعال' in text or 'VPN' in text


@pytest.mark.anyio('asyncio')
async def test_enable_handler_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = SimpleNamespace(id=4, actual_status='disabled', user_disabled=True)
    enable_mock = AsyncMock(return_value=subscription)
    show_detail = AsyncMock()

    monkeypatch.setattr(
        'app.handlers.subscription.my_subscriptions.get_subscription_by_id_for_user',
        AsyncMock(return_value=subscription),
    )
    monkeypatch.setattr(
        'app.handlers.subscription.my_subscriptions.enable_user_subscription',
        enable_mock,
    )
    monkeypatch.setattr(
        'app.handlers.subscription.my_subscriptions.show_subscription_detail',
        show_detail,
    )

    callback = SimpleNamespace(
        data='sub_enable:4',
        answer=AsyncMock(),
        message=SimpleNamespace(),
    )
    db_user = SimpleNamespace(id=1, language='fa')

    await handle_subscription_enable(callback, db_user, AsyncMock(), SimpleNamespace())

    enable_mock.assert_awaited_once()
    show_detail.assert_awaited_once()


@pytest.mark.anyio('asyncio')
async def test_enable_handler_surfaces_panel_error(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = SimpleNamespace(id=4, actual_status='disabled', user_disabled=True)
    monkeypatch.setattr(
        'app.handlers.subscription.my_subscriptions.get_subscription_by_id_for_user',
        AsyncMock(return_value=subscription),
    )
    monkeypatch.setattr(
        'app.handlers.subscription.my_subscriptions.enable_user_subscription',
        AsyncMock(side_effect=SubscriptionToggleError('panel_error', 'panel')),
    )

    callback = SimpleNamespace(
        data='sub_enable:4',
        answer=AsyncMock(),
        message=SimpleNamespace(),
    )

    await handle_subscription_enable(
        callback,
        SimpleNamespace(id=1, language='fa'),
        AsyncMock(),
        SimpleNamespace(),
    )

    callback.answer.assert_awaited()
    assert callback.answer.await_args.kwargs.get('show_alert') is True
