"""Admin C2C inbox list and detail handlers."""

from __future__ import annotations

import html

import structlog
from aiogram import F, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.localization.texts import get_texts
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.constants import (
    C2C_CALLBACK_ADMIN_INBOX,
    C2C_CALLBACK_INBOX_PREFIX,
    C2C_RECEIPT_TYPE_DOCUMENT,
    C2C_RECEIPT_TYPE_PHOTO,
    C2C_RECEIPT_TYPE_TEXT,
)
from app.plugins.c2c.admin_messages import build_c2c_admin_scan_lines
from app.plugins.c2c.keyboards import get_c2c_admin_review_keyboard, get_c2c_inbox_list_keyboard
from app.utils.decorators import admin_required, error_handler


logger = structlog.get_logger(__name__)

INBOX_PAGE_SIZE = 10


def _parse_inbox_page(callback_data: str) -> int | None:
    prefix = f'{C2C_CALLBACK_INBOX_PREFIX}page:'
    if not callback_data.startswith(prefix):
        return None
    try:
        return int(callback_data[len(prefix) :])
    except ValueError:
        return None


def _parse_inbox_receipt_id(callback_data: str) -> int | None:
    if not callback_data.startswith(C2C_CALLBACK_INBOX_PREFIX):
        return None
    suffix = callback_data[len(C2C_CALLBACK_INBOX_PREFIX) :]
    if suffix.startswith('page:'):
        return None
    try:
        return int(suffix)
    except ValueError:
        return None


def _format_user_label(user: User | None) -> str:
    if user is None:
        return '—'
    return user.full_name or user.username or f'ID {user.id}'


async def _build_inbox_list_payload(
    db: AsyncSession,
    *,
    page: int,
    language: str,
) -> tuple[str, InlineKeyboardMarkup]:
    texts = get_texts(language)
    expired_count = await c2c_crud.expire_stale_c2c_receipts(db)
    if expired_count:
        await db.commit()
    total_count = await c2c_crud.count_reviewable_pending_receipts(db)
    if total_count == 0:
        return (
            texts.t(
                'C2C_ADMIN_INBOX_EMPTY',
                '📥 <b>C2C inbox</b>\n\nNo pending receipts.',
            ),
            get_c2c_inbox_list_keyboard(
                [],
                page=0,
                total_count=0,
                page_size=INBOX_PAGE_SIZE,
                language=language,
            ),
        )

    max_page = max(0, (total_count - 1) // INBOX_PAGE_SIZE)
    page = max(0, min(page, max_page))
    receipts = await c2c_crud.list_reviewable_pending_receipts(
        db,
        limit=INBOX_PAGE_SIZE,
        offset=page * INBOX_PAGE_SIZE,
    )
    body = texts.t(
        'C2C_ADMIN_INBOX_TITLE',
        '📥 <b>C2C inbox</b>\n\nPending receipts: {count}',
    ).format(count=total_count)
    keyboard = get_c2c_inbox_list_keyboard(
        receipts,
        page=page,
        total_count=total_count,
        page_size=INBOX_PAGE_SIZE,
        language=language,
    )
    return body, keyboard


async def send_inbox_list_message(
    bot: types.Bot,
    chat_id: int,
    db: AsyncSession,
    language: str,
    *,
    page: int = 0,
) -> None:
    body, keyboard = await _build_inbox_list_payload(db, page=page, language=language)
    await bot.send_message(
        chat_id,
        body,
        reply_markup=keyboard,
        parse_mode='HTML',
    )


async def _render_inbox_list(
    callback: types.CallbackQuery,
    db: AsyncSession,
    *,
    page: int,
    language: str,
) -> None:
    body, keyboard = await _build_inbox_list_payload(db, page=page, language=language)
    await callback.message.edit_text(
        body,
        reply_markup=keyboard,
        parse_mode='HTML',
    )


@admin_required
@error_handler
async def show_c2c_inbox(callback: types.CallbackQuery, db_user: User, db: AsyncSession) -> None:
    await callback.answer()
    page = 0
    if callback.data and callback.data != C2C_CALLBACK_ADMIN_INBOX:
        parsed = _parse_inbox_page(callback.data)
        if parsed is not None:
            page = parsed
    await _render_inbox_list(callback, db, page=page, language=db_user.language)


@admin_required
@error_handler
async def show_c2c_inbox_detail(callback: types.CallbackQuery, db_user: User, db: AsyncSession) -> None:
    receipt_id = _parse_inbox_receipt_id(callback.data or '')
    if receipt_id is None:
        await callback.answer('Invalid callback', show_alert=True)
        return

    receipt = await c2c_crud.get_c2c_receipt_with_user(db, receipt_id)
    if not receipt:
        await callback.answer('Receipt not found', show_alert=True)
        return

    await callback.answer()
    texts = get_texts(db_user.language)
    user_label = _format_user_label(receipt.user)
    amount_display = settings.format_balance(receipt.amount_kopeks)
    card_label = receipt.card_label or '—'
    detail_text = '\n'.join(
        build_c2c_admin_scan_lines(receipt, receipt.user, lang=db_user.language),
    )

    if not c2c_crud.is_reviewable_pending_receipt(receipt):
        draft_text = texts.t(
            'C2C_ADMIN_INBOX_DRAFT',
            '⏳ <b>Receipt #{id}</b>\n\nThis request has not been uploaded by the user yet and was not sent to the admin group.\n\n👤 {user}\n💰 Requested: {amount}\n💳 Card: {card}',
        ).format(id=receipt.id, user=user_label, amount=amount_display, card=card_label)
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text='↩️', callback_data=C2C_CALLBACK_ADMIN_INBOX)]]
        )
        await callback.message.edit_text(draft_text, reply_markup=back_kb, parse_mode='HTML')
        return

    keyboard = get_c2c_admin_review_keyboard(
        receipt.id,
        amount_display,
        language=db_user.language,
        include_inbox_back=True,
    )

    if receipt.receipt_type == C2C_RECEIPT_TYPE_PHOTO and receipt.receipt_file_id:
        await callback.message.answer_photo(
            receipt.receipt_file_id,
            caption=detail_text,
            reply_markup=keyboard,
            parse_mode='HTML',
        )
    elif receipt.receipt_type == C2C_RECEIPT_TYPE_DOCUMENT and receipt.receipt_file_id:
        await callback.message.answer_document(
            receipt.receipt_file_id,
            caption=detail_text,
            reply_markup=keyboard,
            parse_mode='HTML',
        )
    elif receipt.receipt_type == C2C_RECEIPT_TYPE_TEXT and receipt.receipt_text:
        safe_receipt = html.escape(receipt.receipt_text)
        attach_label = texts.t('ADMIN_NOTIFY_C2C_RECEIPT_ATTACH', '📎 <b>Receipt:</b>')
        body = f'{detail_text}\n\n{attach_label}\n{safe_receipt}'
        await callback.message.answer(body, reply_markup=keyboard, parse_mode='HTML')
    else:
        await callback.message.edit_text(detail_text, reply_markup=keyboard, parse_mode='HTML')


def register_admin_inbox_handlers(dp) -> None:
    from aiogram import Dispatcher

    assert isinstance(dp, Dispatcher)

    dp.callback_query.register(show_c2c_inbox, F.data == C2C_CALLBACK_ADMIN_INBOX)
    dp.callback_query.register(show_c2c_inbox, F.data.startswith(f'{C2C_CALLBACK_INBOX_PREFIX}page:'))
    dp.callback_query.register(
        show_c2c_inbox_detail,
        F.data.regexp(r'^c2c:inbox:\d+$'),
    )
