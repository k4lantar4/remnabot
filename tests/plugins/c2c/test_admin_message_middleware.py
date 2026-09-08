"""Tests for C2cAdminMessageMiddleware short-circuit behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, Message, User

from app.config import Settings
from app.plugins.c2c.middleware import C2cAdminMessageMiddleware
from app.states import AdminStates


ADMIN_CHAT_ID = -1003108542917
ADMIN_USER_ID = 9001
NON_ADMIN_USER_ID = 9002


def _settings(**overrides: object) -> Settings:
    base = {
        'ADMIN_IDS': str(ADMIN_USER_ID),
        'ADMIN_NOTIFICATIONS_CHAT_ID': str(ADMIN_CHAT_ID),
        'C2C_ADMIN_CHAT_ID': '',
    }
    base.update(overrides)
    return Settings(**base)


def _admin_message(
    *,
    text: str = '205000',
    chat_id: int = ADMIN_CHAT_ID,
    user_id: int = ADMIN_USER_ID,
    message_thread_id: int | None = 1034,
) -> MagicMock:
    from_user = User(id=user_id, is_bot=False, first_name='Admin', username='admin')
    message = MagicMock(spec=Message)
    message.chat = Chat(id=chat_id, type=ChatType.SUPERGROUP)
    message.from_user = from_user
    message.text = text
    message.message_thread_id = message_thread_id
    message.bot = SimpleNamespace(id=123456)
    return message


@pytest.mark.asyncio
async def test_message_middleware_handles_custom_amount_fsm(monkeypatch: pytest.MonkeyPatch):
    cfg = _settings()
    monkeypatch.setattr('app.plugins.c2c.middleware.settings', cfg)

    inner_handler = AsyncMock(return_value='handled')
    middleware = C2cAdminMessageMiddleware()
    message = _admin_message()

    storage = MagicMock()
    storage.get_state = AsyncMock(return_value=AdminStates.c2c_custom_amount.state)
    storage.get_data = AsyncMock(return_value={'c2c_custom_receipt_id': 107})
    storage.set_state = AsyncMock()
    storage.set_data = AsyncMock()

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch('app.plugins.c2c.middleware.get_c2c_fsm_storage', return_value=storage),
        patch('app.plugins.c2c.middleware.AsyncSessionLocal', return_value=session),
        patch(
            'app.plugins.c2c.middleware._execute_c2c_custom_amount_input',
            new_callable=AsyncMock,
        ) as mock_execute,
    ):
        result = await middleware(inner_handler, message, {})

    assert result is None
    inner_handler.assert_not_awaited()
    mock_execute.assert_awaited_once()
    assert mock_execute.await_args.kwargs['receipt_id'] == 107


@pytest.mark.asyncio
async def test_message_middleware_drops_without_fsm_state(monkeypatch: pytest.MonkeyPatch):
    cfg = _settings()
    monkeypatch.setattr('app.plugins.c2c.middleware.settings', cfg)

    inner_handler = AsyncMock(return_value='handled')
    middleware = C2cAdminMessageMiddleware()
    message = _admin_message(text='hello')

    storage = MagicMock()
    storage.get_state = AsyncMock(return_value=None)

    with patch('app.plugins.c2c.middleware.get_c2c_fsm_storage', return_value=storage):
        result = await middleware(inner_handler, message, {})

    assert result is None
    inner_handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_message_middleware_drops_non_admin_in_admin_chat(monkeypatch: pytest.MonkeyPatch):
    cfg = _settings()
    monkeypatch.setattr('app.plugins.c2c.middleware.settings', cfg)

    inner_handler = AsyncMock()
    middleware = C2cAdminMessageMiddleware()
    message = _admin_message(user_id=NON_ADMIN_USER_ID)

    result = await middleware(inner_handler, message, {})

    assert result is None
    inner_handler.assert_not_awaited()
