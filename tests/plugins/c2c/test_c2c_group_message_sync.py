"""Tests for C2C inbox-to-group admin message sync."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest

from app.plugins.c2c.handlers.admin import sync_c2c_group_admin_message


def _receipt(*, admin_chat_id: int | None = -1001, admin_message_id: int | None = 42) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        admin_chat_id=admin_chat_id,
        admin_message_id=admin_message_id,
    )


@pytest.mark.asyncio
async def test_sync_passes_reply_markup_to_group_message():
    bot = AsyncMock()
    markup = SimpleNamespace()
    receipt = _receipt()

    await sync_c2c_group_admin_message(
        bot,
        receipt,
        status_html='✅ resolved body',
        reply_markup=markup,
    )

    bot.edit_message_text.assert_awaited_once_with(
        text='✅ resolved body',
        chat_id=-1001,
        message_id=42,
        reply_markup=markup,
        parse_mode='HTML',
    )


@pytest.mark.asyncio
async def test_sync_edits_group_message_text():
    bot = AsyncMock()
    receipt = _receipt()

    await sync_c2c_group_admin_message(
        bot,
        receipt,
        status_html='✅ <b>Approved</b> — receipt #7',
    )

    bot.edit_message_text.assert_awaited_once_with(
        text='✅ <b>Approved</b> — receipt #7',
        chat_id=-1001,
        message_id=42,
        reply_markup=None,
        parse_mode='HTML',
    )
    bot.edit_message_caption.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_falls_back_to_caption_on_photo_message():
    bot = AsyncMock()
    bot.edit_message_text = AsyncMock(
        side_effect=TelegramBadRequest(method='editMessageText', message='there is no text in the message to edit')
    )
    receipt = _receipt()

    await sync_c2c_group_admin_message(
        bot,
        receipt,
        status_html='❌ <b>Rejected</b> — receipt #7',
    )

    bot.edit_message_caption.assert_awaited_once_with(
        caption='❌ <b>Rejected</b> — receipt #7',
        chat_id=-1001,
        message_id=42,
        reply_markup=None,
        parse_mode='HTML',
    )


@pytest.mark.asyncio
async def test_sync_skips_when_message_already_edited_in_group():
    bot = AsyncMock()
    receipt = _receipt(admin_message_id=99)

    await sync_c2c_group_admin_message(
        bot,
        receipt,
        status_html='✅ done',
        skip_message_id=99,
    )

    bot.edit_message_text.assert_not_awaited()
    bot.edit_message_caption.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_noop_without_stored_group_message():
    bot = AsyncMock()
    receipt = _receipt(admin_chat_id=None, admin_message_id=None)

    await sync_c2c_group_admin_message(bot, receipt, status_html='✅ done')

    bot.edit_message_text.assert_not_awaited()
    bot.edit_message_caption.assert_not_awaited()
