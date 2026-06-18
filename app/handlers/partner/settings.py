"""Partner panel settings — brand username prefix."""

from __future__ import annotations

import html

import structlog
from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.user import update_user
from app.database.models import User
from app.localization.texts import get_texts
from app.states import PartnerStates
from app.utils.decorators import error_handler
from app.utils.remnawave_panel_identity import validate_brand_prefix

logger = structlog.get_logger(__name__)


def _partner_settings_keyboard(language: str, *, current_prefix: str | None) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    rows: list[list[InlineKeyboardButton]] = []
    if current_prefix:
        rows.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PARTNER_BRAND_CLEAR_BTN', '🗑 حذف نام برند'),
                    callback_data='partner_brand_clear',
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=texts.BACK, callback_data='back_to_menu')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@error_handler
async def show_partner_brand_settings(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    if not db_user.is_partner:
        await callback.answer(texts.t('PARTNER_ONLY', 'فقط برای همکاران'), show_alert=True)
        return

    await callback.answer()
    await state.clear()

    current = (db_user.panel_brand_prefix or '').strip()
    body = texts.t(
        'PARTNER_BRAND_SETTINGS_BODY',
        '🏷 <b>نام برند اشتراک</b>\n\n'
        'این پیشوند در نام کاربری پنل هنگام <b>خرید جدید</b> استفاده می‌شود.\n'
        'مثال: <code>Mobile_x_shop</code>\n\n'
        'نام فعلی: {current}',
    ).format(current=html.escape(current) if current else texts.t('PARTNER_BRAND_NOT_SET', '— تنظیم نشده —'))

    await callback.message.edit_text(
        body,
        reply_markup=_partner_settings_keyboard(db_user.language, current_prefix=current or None),
        parse_mode='HTML',
    )
    await state.set_state(PartnerStates.entering_brand_prefix)


@error_handler
async def handle_partner_brand_input(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    if not db_user.is_partner:
        await state.clear()
        return

    prefix = validate_brand_prefix(message.text or '')
    if not prefix:
        await message.answer(
            texts.t(
                'PARTNER_BRAND_INVALID',
                '❌ نام برند نامعتبر است. فقط حروف انگلیسی، اعداد، _ و - (۳ تا ۲۰ کاراکتر).\n'
                'مثال: <code>Mobile_x_shop</code>',
            ),
            parse_mode='HTML',
        )
        return

    await update_user(db, db_user, panel_brand_prefix=prefix)
    await db.commit()
    await state.clear()

    await message.answer(
        texts.t('PARTNER_BRAND_SAVED', '✅ نام برند ذخیره شد: <code>{prefix}</code>').format(prefix=html.escape(prefix)),
        parse_mode='HTML',
    )


@error_handler
async def clear_partner_brand_prefix(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    if not db_user.is_partner:
        await callback.answer(texts.t('PARTNER_ONLY', 'فقط برای همکاران'), show_alert=True)
        return

    await update_user(db, db_user, panel_brand_prefix=None)
    await db.commit()
    await state.clear()
    await callback.answer(texts.t('PARTNER_BRAND_CLEARED', 'نام برند حذف شد'))

    body = texts.t(
        'PARTNER_BRAND_SETTINGS_BODY',
        '🏷 <b>نام برند اشتراک</b>\n\n'
        'این پیشوند در نام کاربری پنل هنگام <b>خرید جدید</b> استفاده می‌شود.\n'
        'مثال: <code>Mobile_x_shop</code>\n\n'
        'نام فعلی: {current}',
    ).format(current=texts.t('PARTNER_BRAND_NOT_SET', '— تنظیم نشده —'))

    await callback.message.edit_text(
        body,
        reply_markup=_partner_settings_keyboard(db_user.language, current_prefix=None),
        parse_mode='HTML',
    )
    await state.set_state(PartnerStates.entering_brand_prefix)


def register_partner_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(show_partner_brand_settings, F.data == 'partner_brand_settings')
    dp.callback_query.register(clear_partner_brand_prefix, F.data == 'partner_brand_clear')
    dp.message.register(handle_partner_brand_input, PartnerStates.entering_brand_prefix)
