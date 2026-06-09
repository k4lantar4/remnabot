"""Shared Telegram message edit helpers (text vs photo caption vs re-send)."""

from __future__ import annotations

import structlog
from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InaccessibleMessage


logger = structlog.get_logger(__name__)


async def edit_message_text_or_caption(
    message: types.Message,
    text: str,
    reply_markup: types.InlineKeyboardMarkup,
    parse_mode: str | None = 'HTML',
) -> types.Message:
    """Edit text; on photo messages fall back to caption or re-send."""
    if isinstance(message, InaccessibleMessage):
        return await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)

    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return message
    except TelegramBadRequest as error:
        error_message = str(error).lower()
        if 'message is not modified' in error_message:
            return message
        if 'there is no text in the message to edit' in error_message:
            if message.caption is not None:
                try:
                    await message.edit_caption(
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                    )
                    return message
                except TelegramBadRequest as caption_error:
                    if 'message is not modified' in str(caption_error).lower():
                        return message
            try:
                await message.delete()
            except Exception:
                pass
            return await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        raise


async def edit_bot_message_text_or_caption(
    bot: types.Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: types.InlineKeyboardMarkup,
    parse_mode: str | None = 'HTML',
    *,
    fallback_message: types.Message | None = None,
) -> bool:
    """Edit by chat/message id; caption fallback for logo-mode photo messages."""
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=int(chat_id),
            message_id=int(message_id),
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return True
    except TelegramBadRequest as error:
        error_message = str(error).lower()
        if 'message is not modified' in error_message:
            return True
        if 'there is no text in the message to edit' in error_message:
            try:
                await bot.edit_message_caption(
                    caption=text,
                    chat_id=int(chat_id),
                    message_id=int(message_id),
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                return True
            except TelegramBadRequest as caption_error:
                if 'message is not modified' in str(caption_error).lower():
                    return True
                logger.warning(
                    'bot message caption edit failed',
                    chat_id=chat_id,
                    message_id=message_id,
                    error=str(caption_error),
                )

    try:
        await bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
    except Exception:
        pass
    if fallback_message is not None:
        await fallback_message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    return False
