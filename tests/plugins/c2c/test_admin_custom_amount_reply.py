"""Regression: Message.answer must not receive duplicate message_thread_id kwargs."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, Message, User

from app.plugins.c2c.handlers.admin import _execute_c2c_custom_amount_input


def _forum_message(*, text: str | None = 'abc') -> MagicMock:
    message = MagicMock(spec=Message)
    message.chat = Chat(id=-1003108542917, type=ChatType.SUPERGROUP)
    message.from_user = User(id=9001, is_bot=False, first_name='Admin', username='admin')
    message.text = text
    message.message_thread_id = 1034
    message.bot = SimpleNamespace(id=123456)
    message.answer = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_custom_amount_invalid_does_not_pass_message_thread_id_kwarg():
    message = _forum_message(text='not-a-number')
    db = AsyncMock()

    await _execute_c2c_custom_amount_input(
        message,
        db,
        receipt_id=107,
        language='fa',
    )

    message.answer.assert_awaited_once()
    kwargs = message.answer.await_args.kwargs
    assert 'message_thread_id' not in kwargs
