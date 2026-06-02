"""Tests for C2cAdminCallbackMiddleware short-circuit behavior."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Chat, Message, User

from app.config import Settings
from app.plugins.c2c.middleware import C2cAdminCallbackMiddleware


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


def _callback_query(
    *,
    data: str = 'c2c:a:5',
    chat_id: int = ADMIN_CHAT_ID,
    user_id: int = ADMIN_USER_ID,
    message_thread_id: int | None = 1034,
) -> CallbackQuery:
    chat = Chat(id=chat_id, type=ChatType.SUPERGROUP)
    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=chat,
        message_thread_id=message_thread_id,
        text='receipt',
    )
    from_user = User(id=user_id, is_bot=False, first_name='Admin', username='admin')
    return CallbackQuery(
        id='cb-test-1',
        from_user=from_user,
        chat_instance='test',
        data=data,
        message=message,
    )


@pytest.mark.asyncio
async def test_middleware_short_circuits_without_inner_handler(monkeypatch: pytest.MonkeyPatch):
    cfg = _settings()
    monkeypatch.setattr('app.plugins.c2c.middleware.settings', cfg)

    inner_handler = AsyncMock(return_value='handled')
    middleware = C2cAdminCallbackMiddleware()
    callback = _callback_query()

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(CallbackQuery, 'answer', new_callable=AsyncMock) as mock_answer,
        patch('app.plugins.c2c.middleware.AsyncSessionLocal', return_value=session),
        patch('app.plugins.c2c.middleware.execute_c2c_approve', new_callable=AsyncMock) as mock_approve,
    ):
        result = await middleware(inner_handler, callback, {})

    assert result is None
    inner_handler.assert_not_awaited()
    mock_answer.assert_awaited_once_with()
    mock_approve.assert_awaited_once_with(callback, session, ADMIN_USER_ID)


@pytest.mark.asyncio
async def test_middleware_wrong_chat_answers_alert_and_short_circuits(monkeypatch: pytest.MonkeyPatch):
    cfg = _settings()
    monkeypatch.setattr('app.plugins.c2c.middleware.settings', cfg)

    inner_handler = AsyncMock()
    middleware = C2cAdminCallbackMiddleware()
    callback = _callback_query(chat_id=-1009999999999)

    with (
        patch.object(CallbackQuery, 'answer', new_callable=AsyncMock) as mock_answer,
        patch('app.plugins.c2c.middleware.execute_c2c_approve', new_callable=AsyncMock) as mock_approve,
    ):
        result = await middleware(inner_handler, callback, {})

    assert result is None
    inner_handler.assert_not_awaited()
    mock_approve.assert_not_awaited()
    mock_answer.assert_awaited_once_with('Wrong chat', show_alert=True)


@pytest.mark.asyncio
async def test_middleware_non_admin_access_denied_without_credit(monkeypatch: pytest.MonkeyPatch):
    cfg = _settings()
    monkeypatch.setattr('app.plugins.c2c.middleware.settings', cfg)

    inner_handler = AsyncMock()
    middleware = C2cAdminCallbackMiddleware()
    callback = _callback_query(user_id=NON_ADMIN_USER_ID)

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(CallbackQuery, 'answer', new_callable=AsyncMock) as mock_answer,
        patch('app.plugins.c2c.middleware.AsyncSessionLocal', return_value=session),
        patch('app.plugins.c2c.middleware.execute_c2c_approve', new_callable=AsyncMock) as mock_approve,
        patch('app.plugins.c2c.middleware.get_texts') as mock_get_texts,
    ):
        mock_get_texts.return_value = SimpleNamespace(ACCESS_DENIED='❌ Access denied')
        result = await middleware(inner_handler, callback, {})

    assert result is None
    inner_handler.assert_not_awaited()
    mock_approve.assert_not_awaited()
    mock_answer.assert_awaited_once_with('❌ Access denied', show_alert=True)


@pytest.mark.asyncio
async def test_middleware_passes_through_non_c2c_callbacks(monkeypatch: pytest.MonkeyPatch):
    cfg = _settings()
    monkeypatch.setattr('app.plugins.c2c.middleware.settings', cfg)

    inner_handler = AsyncMock(return_value='ok')
    middleware = C2cAdminCallbackMiddleware()
    callback = _callback_query(data='balance:topup')

    with patch.object(CallbackQuery, 'answer', new_callable=AsyncMock) as mock_answer:
        result = await middleware(inner_handler, callback, {})

    assert result == 'ok'
    inner_handler.assert_awaited_once_with(callback, {})
    mock_answer.assert_not_awaited()
