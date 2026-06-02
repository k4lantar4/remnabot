"""Admin C2C approve/reject handlers."""

from __future__ import annotations

import structlog
from aiogram import F, types
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import C2cReceiptStatus, User
from app.plugins.c2c.constants import C2C_CALLBACK_APPROVE_PREFIX, C2C_CALLBACK_REJECT_PREFIX
from app.plugins.c2c.service import C2cPaymentService
from app.utils.decorators import admin_required, error_handler


logger = structlog.get_logger(__name__)


def _parse_receipt_id(callback_data: str, prefix: str) -> int | None:
    if not callback_data.startswith(prefix):
        return None
    try:
        return int(callback_data[len(prefix) :])
    except ValueError:
        return None


def _admin_chat_ok(callback: types.CallbackQuery) -> bool:
    admin_chat_id = settings.get_c2c_admin_chat_id()
    if not admin_chat_id or not callback.message:
        return False
    return callback.message.chat.id == admin_chat_id


@admin_required
@error_handler
async def handle_c2c_approve(callback: types.CallbackQuery, db_user: User, db: AsyncSession) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_APPROVE_PREFIX)
    if receipt_id is None:
        await callback.answer('Invalid callback', show_alert=True)
        return

    if not _admin_chat_ok(callback):
        await callback.answer('Wrong chat context', show_alert=True)
        return

    await callback.answer()

    service = C2cPaymentService(callback.bot)
    success, message, receipt = await service.approve_receipt(
        db,
        receipt_id,
        callback.from_user.id,
    )

    if not success:
        logger.warning('C2C approve failed', receipt_id=receipt_id, message=message)
        return

    admin_label = callback.from_user.username or str(callback.from_user.id)
    new_text = f'✅ <b>Approved</b> — receipt #{receipt_id} by @{admin_label}'
    if receipt and receipt.status == C2cReceiptStatus.APPROVED.value:
        try:
            if callback.message.text:
                await callback.message.edit_text(new_text, parse_mode='HTML', reply_markup=None)
            elif callback.message.caption:
                await callback.message.edit_caption(caption=new_text, parse_mode='HTML', reply_markup=None)
        except TelegramBadRequest as error:
            if 'message is not modified' not in str(error).lower():
                logger.warning('Could not edit C2C admin message on approve', error=error)


@admin_required
@error_handler
async def handle_c2c_reject(callback: types.CallbackQuery, db_user: User, db: AsyncSession) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_REJECT_PREFIX)
    if receipt_id is None:
        await callback.answer('Invalid callback', show_alert=True)
        return

    if not _admin_chat_ok(callback):
        await callback.answer('Wrong chat context', show_alert=True)
        return

    await callback.answer()

    service = C2cPaymentService(callback.bot)
    success, message, receipt = await service.reject_receipt(
        db,
        receipt_id,
        callback.from_user.id,
    )

    if not success:
        logger.warning('C2C reject failed', receipt_id=receipt_id, message=message)
        return

    admin_label = callback.from_user.username or str(callback.from_user.id)
    new_text = f'❌ <b>Rejected</b> — receipt #{receipt_id} by @{admin_label}'
    if receipt and receipt.status == C2cReceiptStatus.REJECTED.value:
        try:
            if callback.message.text:
                await callback.message.edit_text(new_text, parse_mode='HTML', reply_markup=None)
            elif callback.message.caption:
                await callback.message.edit_caption(caption=new_text, parse_mode='HTML', reply_markup=None)
        except TelegramBadRequest as error:
            if 'message is not modified' not in str(error).lower():
                logger.warning('Could not edit C2C admin message on reject', error=error)


def register_admin_handlers(dp) -> None:
    from aiogram import Dispatcher

    assert isinstance(dp, Dispatcher)

    dp.callback_query.register(
        handle_c2c_approve,
        F.data.startswith(C2C_CALLBACK_APPROVE_PREFIX),
    )
    dp.callback_query.register(
        handle_c2c_reject,
        F.data.startswith(C2C_CALLBACK_REJECT_PREFIX),
    )
