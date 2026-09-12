"""Channel-agnostic helpers for a decided C2C receipt.

Both review channels — the bot's admin group/inbox and the cabinet admin — produce the same resolved
group post, so no admin taps a stale approve/reject button after the other channel decided.
"""

from __future__ import annotations

import structlog
from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import C2cReceipt
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.admin_messages import (
    build_c2c_admin_receipt_body,
    build_c2c_resolved_keyboard,
)


logger = structlog.get_logger(__name__)


async def sync_group_admin_message(
    bot: types.Bot,
    receipt: C2cReceipt,
    *,
    status_html: str,
    reply_markup=None,
    skip_message_id: int | None = None,
) -> None:
    """Update stored admin supergroup receipt post after inbox action."""
    admin_chat_id = receipt.admin_chat_id
    admin_message_id = receipt.admin_message_id
    if not admin_chat_id or not admin_message_id:
        return
    if skip_message_id is not None and skip_message_id == admin_message_id:
        return

    chat_id = int(admin_chat_id)
    message_id = int(admin_message_id)
    try:
        await bot.edit_message_text(
            text=status_html,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode='HTML',
        )
    except TelegramBadRequest as error:
        error_message = str(error).lower()
        if 'message is not modified' in error_message:
            return
        if 'there is no text in the message to edit' not in error_message:
            logger.warning(
                'Could not sync C2C group admin message (text)',
                receipt_id=receipt.id,
                chat_id=chat_id,
                message_id=message_id,
                error=error,
            )
            return
        try:
            await bot.edit_message_caption(
                caption=status_html,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
                parse_mode='HTML',
            )
        except TelegramBadRequest as caption_error:
            if 'message is not modified' not in str(caption_error).lower():
                logger.warning(
                    'Could not sync C2C group admin message (caption)',
                    receipt_id=receipt.id,
                    chat_id=chat_id,
                    message_id=message_id,
                    error=caption_error,
                )


async def resolved_receipt_message(
    db: AsyncSession,
    receipt: C2cReceipt,
    admin_label: str,
    *,
    include_inbox_back: bool = False,
) -> tuple[str, types.InlineKeyboardMarkup]:
    lang = settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa'
    receipt_with_user = await c2c_crud.get_c2c_receipt_with_user(db, receipt.id)
    if receipt_with_user is not None:
        receipt = receipt_with_user
    body = build_c2c_admin_receipt_body(
        receipt,
        receipt.user,
        lang=lang,
        admin_label=admin_label,
    )
    keyboard = build_c2c_resolved_keyboard(
        receipt.id,
        receipt.status,
        lang=lang,
        include_inbox_back=include_inbox_back,
    )
    return body, keyboard
