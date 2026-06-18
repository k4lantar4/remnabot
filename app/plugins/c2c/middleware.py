"""Outer callback middleware for C2C admin approve/reject in group chats."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware, Dispatcher
from aiogram.types import CallbackQuery, TelegramObject

from app.config import settings
from app.database.database import AsyncSessionLocal
from app.localization.texts import get_texts
from app.plugins.c2c.constants import (
    C2C_CALLBACK_APPROVE_PREFIX,
    C2C_CALLBACK_CUSTOM_AMOUNT_PREFIX,
    C2C_CALLBACK_REJECT_PREFIX,
    C2C_CALLBACK_REJECT_REASON_PREFIX,
    C2C_CALLBACK_RESTORE_REVIEW_PREFIX,
)
from app.plugins.c2c.handlers.admin import (
    _parse_receipt_id,
    _parse_reject_reason_callback,
    execute_c2c_approve,
    execute_c2c_reject,
    restore_c2c_review_keyboard,
    show_c2c_reject_menu,
    start_c2c_custom_amount,
)


logger = structlog.get_logger(__name__)

_C2C_GROUP_CALLBACK_PREFIXES = (
    C2C_CALLBACK_REJECT_REASON_PREFIX,
    C2C_CALLBACK_APPROVE_PREFIX,
    C2C_CALLBACK_CUSTOM_AMOUNT_PREFIX,
    C2C_CALLBACK_RESTORE_REVIEW_PREFIX,
    C2C_CALLBACK_REJECT_PREFIX,
)


def _is_c2c_admin_review_callback(callback: CallbackQuery) -> bool:
    data = callback.data or ''
    return any(data.startswith(prefix) for prefix in _C2C_GROUP_CALLBACK_PREFIXES)


def _resolve_receipt_id(callback: CallbackQuery) -> int | None:
    data = callback.data or ''
    parsed_reason = _parse_reject_reason_callback(data)
    if parsed_reason is not None:
        return parsed_reason[0]
    for prefix in (
        C2C_CALLBACK_APPROVE_PREFIX,
        C2C_CALLBACK_CUSTOM_AMOUNT_PREFIX,
        C2C_CALLBACK_RESTORE_REVIEW_PREFIX,
        C2C_CALLBACK_REJECT_PREFIX,
    ):
        receipt_id = _parse_receipt_id(data, prefix)
        if receipt_id is not None:
            return receipt_id
    return None


class C2cAdminCallbackMiddleware(BaseMiddleware):
    """Handle C2C approve/reject before group chat middleware drops the update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery) or not _is_c2c_admin_review_callback(event):
            return await handler(event, data)

        callback = event
        admin_chat_id = settings.get_c2c_admin_chat_id()
        chat_id = callback.message.chat.id if callback.message else None
        message_thread_id = callback.message.message_thread_id if callback.message else None

        if not admin_chat_id or chat_id != admin_chat_id:
            await callback.answer('Wrong chat', show_alert=True)
            return None

        receipt_id = _resolve_receipt_id(callback)
        if receipt_id is None:
            await callback.answer('Invalid callback', show_alert=True)
            return None

        if not callback.from_user or not settings.is_admin(callback.from_user.id):
            texts = get_texts()
            await callback.answer(texts.ACCESS_DENIED, show_alert=True)
            return None

        await callback.answer()

        admin_telegram_id = callback.from_user.id
        callback_data = callback.data or ''
        async with AsyncSessionLocal() as db:
            if callback_data.startswith(C2C_CALLBACK_APPROVE_PREFIX):
                await execute_c2c_approve(callback, db, admin_telegram_id)
            elif callback_data.startswith(C2C_CALLBACK_REJECT_REASON_PREFIX):
                parsed = _parse_reject_reason_callback(callback_data)
                reason_key = parsed[1] if parsed else None
                await execute_c2c_reject(callback, db, admin_telegram_id, reason_key=reason_key)
            elif callback_data.startswith(C2C_CALLBACK_REJECT_PREFIX):
                await show_c2c_reject_menu(callback, db)
            elif callback_data.startswith(C2C_CALLBACK_CUSTOM_AMOUNT_PREFIX):
                await start_c2c_custom_amount(callback, db)
            elif callback_data.startswith(C2C_CALLBACK_RESTORE_REVIEW_PREFIX):
                await restore_c2c_review_keyboard(callback, db)

        logger.info(
            'C2C admin callback handled',
            receipt_id=receipt_id,
            chat_id=chat_id,
            message_thread_id=message_thread_id,
        )
        return None


def register_c2c_callback_middleware(dp: Dispatcher) -> None:
    dp.callback_query.outer_middleware(C2cAdminCallbackMiddleware())
