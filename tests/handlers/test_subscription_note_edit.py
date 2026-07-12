"""Tests for subscription note edit FSM."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.handlers.subscription.my_subscriptions import (
    handle_subscription_edit_note_input,
    handle_subscription_edit_note_start,
)
from app.states import SubscriptionStates


@pytest.mark.anyio('asyncio')
async def test_edit_note_start_sets_fsm(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = SimpleNamespace(id=12, actual_status='active')
    monkeypatch.setattr(
        'app.handlers.subscription.my_subscriptions.get_subscription_by_id_for_user',
        AsyncMock(return_value=subscription),
    )

    message = SimpleNamespace(edit_text=AsyncMock(), chat=SimpleNamespace(id=1), message_id=99)
    callback = SimpleNamespace(data='sub_edit_note:12', answer=AsyncMock(), message=message)
    state = SimpleNamespace(set_state=AsyncMock(), update_data=AsyncMock())

    await handle_subscription_edit_note_start(
        callback,
        SimpleNamespace(id=1, language='fa'),
        AsyncMock(),
        state,
    )

    state.set_state.assert_awaited_once_with(SubscriptionStates.editing_subscription_note)
    state.update_data.assert_awaited_once()
    message.edit_text.assert_awaited_once()


@pytest.mark.anyio('asyncio')
async def test_edit_note_input_saves_and_returns_to_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = SimpleNamespace(
        id=12,
        actual_status='active',
        user_disabled=False,
        purchase_note=None,
        tariff=None,
        traffic_limit_gb=10,
        traffic_used_gb=0.0,
        device_limit=1,
        end_date=None,
        start_date=None,
        autopay_enabled=False,
        autopay_days_before=3,
        is_trial=False,
    )
    monkeypatch.setattr(
        'app.handlers.subscription.my_subscriptions.get_subscription_by_id_for_user',
        AsyncMock(return_value=subscription),
    )
    monkeypatch.setattr(
        'app.handlers.subscription.my_subscriptions._build_subscription_detail_keyboard',
        AsyncMock(return_value=MagicMock()),
    )
    monkeypatch.setattr(
        'app.handlers.subscription.my_subscriptions.edit_bot_message_text_or_caption',
        edit_mock := AsyncMock(return_value=True),
    )

    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    state = SimpleNamespace(
        get_data=AsyncMock(
            return_value={
                'editing_subscription_note_sub_id': 12,
                'editing_subscription_note_chat_id': 1,
                'editing_subscription_note_message_id': 50,
            }
        ),
        set_state=AsyncMock(),
        update_data=AsyncMock(),
    )
    message = SimpleNamespace(
        text='  my note  ',
        answer=AsyncMock(),
        delete=AsyncMock(),
        bot=MagicMock(),
    )

    await handle_subscription_edit_note_input(
        message,
        SimpleNamespace(id=1, language='fa'),
        db,
        state,
    )

    assert subscription.purchase_note == 'my note'
    db.commit.assert_awaited_once()
    state.set_state.assert_awaited_once_with(None)
    message.answer.assert_not_awaited()
    edit_mock.assert_awaited_once()
