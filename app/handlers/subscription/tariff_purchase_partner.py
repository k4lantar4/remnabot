"""Partner checkout extras for tariff purchase confirm step."""

from __future__ import annotations

import html

from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.tariff import get_tariff_by_id
from app.database.crud.user import update_user
from app.database.models import User
from app.localization.texts import get_texts
from app.states import SubscriptionStates
from app.utils.decorators import error_handler
from app.utils.message_edit import edit_bot_message_text_or_caption
from app.utils.purchase_confirm import format_tariff_purchase_confirm_text
from app.utils.remnawave_panel_identity import MAX_PURCHASE_NOTE_LEN, validate_brand_prefix


def _sanitize_purchase_note(value: str | None) -> str | None:
    note = (value or '').strip()
    if not note:
        return None
    return note[:MAX_PURCHASE_NOTE_LEN]


def checkout_partner_options(db_user: User, state_data: dict) -> dict:
    has_brand = bool(db_user.is_partner and (db_user.panel_brand_prefix or '').strip())
    use_brand = state_data.get('use_brand_prefix')
    if use_brand is None:
        use_brand = has_brand
    return {
        'purchase_note': _sanitize_purchase_note(state_data.get('purchase_note')),
        'use_brand_prefix': bool(use_brand) if has_brand else False,
        'has_brand_prefix': has_brand,
    }


def partner_checkout_cart_fields(db_user: User, state_data: dict) -> dict:
    if not db_user.is_partner:
        return {}
    opts = checkout_partner_options(db_user, state_data)
    fields: dict = {'use_brand_prefix': opts['use_brand_prefix']}
    if opts['purchase_note']:
        fields['purchase_note'] = opts['purchase_note']
    return fields


def append_purchase_note_preview(text: str, texts, purchase_note: str | None) -> str:
    if not purchase_note:
        return text
    return text + '\n\n' + texts.t('PARTNER_PURCHASE_NOTE_PREVIEW', '📝 یادداشت: {note}').format(
        note=html.escape(purchase_note)
    )


def append_brand_prefix_preview(text: str, texts, prefix: str | None) -> str:
    if prefix:
        return text + '\n\n' + texts.t(
            'PARTNER_BRAND_NAME_PREVIEW',
            '🏷 نام دلخواه: <code>{prefix}</code>',
        ).format(prefix=html.escape(prefix))
    return text + '\n\n' + texts.t(
        'PARTNER_BRAND_NAME_NOT_SET',
        '🏷 نام دلخواه: هنوز انتخاب نشده',
    )


def get_partner_tariff_confirm_keyboard(
    tariff_id: int,
    period: int,
    language: str,
    *,
    db_user: User | None = None,
    purchase_note: str | None = None,
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    rows: list[list[InlineKeyboardButton]] = []

    if db_user and db_user.is_partner:
        partner_row: list[InlineKeyboardButton] = []
        note_key = 'PARTNER_PURCHASE_NOTE_SET_BTN' if purchase_note else 'PARTNER_PURCHASE_NOTE_BTN'
        note_fallback = '📝 یادداشت ✓' if purchase_note else '📝 یادداشت'
        partner_row.append(
            InlineKeyboardButton(
                text=texts.t(note_key, note_fallback),
                callback_data=f'tariff_purchase_note:{tariff_id}:{period}',
            )
        )
        brand_key = (
            'PARTNER_BRAND_NAME_SET_BTN'
            if (db_user.panel_brand_prefix or '').strip()
            else 'PARTNER_BRAND_NAME_BTN'
        )
        partner_row.append(
            InlineKeyboardButton(
                text=texts.t(brand_key, '🏷 نام دلخواه'),
                callback_data=f'tariff_purchase_brand:{tariff_id}:{period}',
            )
        )
        rows.append(partner_row)

    rows.append(
        [
            InlineKeyboardButton(text=texts.BACK, callback_data=f'tariff_select:{tariff_id}'),
            InlineKeyboardButton(
                text=texts.t('TARIFF_CONFIRM_PURCHASE_BTN', '✅ Подтвердить покупку'),
                callback_data=f'tariff_confirm:{tariff_id}:{period}',
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def render_tariff_confirm_screen(
    *,
    bot,
    chat_id: int,
    message_id: int,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    tariff_id: int,
    period: int,
    fallback_message: types.Message | None = None,
) -> None:
    texts = get_texts(db_user.language)
    tariff = await get_tariff_by_id(db, tariff_id)
    if not tariff or not tariff.is_active:
        return

    state_data = await state.get_data()
    traffic_gb = state_data.get('custom_traffic_gb', tariff.traffic_limit_gb)

    from app.services.pricing_engine import pricing_engine

    result = await pricing_engine.calculate_tariff_purchase_price(
        tariff,
        period,
        device_limit=tariff.device_limit,
        custom_traffic_gb=traffic_gb if tariff.can_purchase_custom_traffic() else None,
        user=db_user,
    )
    partner_opts = checkout_partner_options(db_user, state_data)
    body = append_brand_prefix_preview(
        append_purchase_note_preview(
            format_tariff_purchase_confirm_text(
                texts,
                tariff=tariff,
                traffic_gb=traffic_gb,
                period_days=period,
                result=result,
                balance_kopeks=db_user.balance_kopeks or 0,
                language=db_user.language,
                user=db_user,
            ),
            texts,
            partner_opts['purchase_note'],
        ),
        texts,
        (db_user.panel_brand_prefix or '').strip() or None,
    )
    await edit_bot_message_text_or_caption(
        bot,
        chat_id,
        message_id,
        body,
        get_partner_tariff_confirm_keyboard(
            tariff_id,
            period,
            db_user.language,
            db_user=db_user,
            purchase_note=partner_opts['purchase_note'],
        ),
        parse_mode='HTML',
        fallback_message=fallback_message,
    )


@error_handler
async def prompt_tariff_purchase_note(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    if not db_user.is_partner:
        await callback.answer(texts.t('PARTNER_ONLY', 'فقط برای همکاران'), show_alert=True)
        return

    parts = callback.data.split(':')
    tariff_id, period = int(parts[1]), int(parts[2])
    await callback.answer()
    await state.update_data(
        purchase_note_tariff_id=tariff_id,
        purchase_note_period=period,
        purchase_note_chat_id=callback.message.chat.id,
        purchase_note_message_id=callback.message.message_id,
    )
    await state.set_state(SubscriptionStates.entering_purchase_note)
    await callback.message.edit_text(
        texts.t(
            'PARTNER_PURCHASE_NOTE_PROMPT',
            '📝 یادداشت اختیاری برای این خرید (حداکثر {max} کاراکتر).\nبرای رد کردن /skip را بفرستید.',
        ).format(max=MAX_PURCHASE_NOTE_LEN),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=texts.BACK, callback_data=f'tariff_period:{tariff_id}:{period}')]
            ]
        ),
    )


@error_handler
async def handle_tariff_purchase_note_input(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    tariff_id = state_data.get('purchase_note_tariff_id')
    period = state_data.get('purchase_note_period')
    if not tariff_id or not period:
        await state.set_state(None)
        return

    raw = (message.text or '').strip()
    if raw.lower() in ('/skip', 'skip', '-'):
        note = None
    elif not raw:
        texts = get_texts(db_user.language)
        await message.answer(
            texts.t(
                'PARTNER_PURCHASE_NOTE_PROMPT',
                '📝 یادداشت اختیاری برای این خرید (حداکثر {max} کاراکتر).\nبرای رد کردن /skip را بفرستید.',
            ).format(max=MAX_PURCHASE_NOTE_LEN)
        )
        return
    else:
        note = _sanitize_purchase_note(raw)

    chat_id = state_data.get('purchase_note_chat_id')
    message_id = state_data.get('purchase_note_message_id')
    if not chat_id or not message_id:
        await state.set_state(None)
        return

    await state.update_data(purchase_note=note)
    await state.set_state(None)
    await render_tariff_confirm_screen(
        bot=message.bot,
        chat_id=int(chat_id),
        message_id=int(message_id),
        db_user=db_user,
        db=db,
        state=state,
        tariff_id=int(tariff_id),
        period=int(period),
        fallback_message=message,
    )
    try:
        await message.delete()
    except Exception:
        pass


@error_handler
async def prompt_tariff_purchase_brand(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    if not db_user.is_partner:
        await callback.answer(texts.t('PARTNER_ONLY', 'فقط برای همکاران'), show_alert=True)
        return

    parts = callback.data.split(':')
    tariff_id, period = int(parts[1]), int(parts[2])
    await callback.answer()
    await state.update_data(
        purchase_brand_tariff_id=tariff_id,
        purchase_brand_period=period,
        purchase_brand_chat_id=callback.message.chat.id,
        purchase_brand_message_id=callback.message.message_id,
    )
    await state.set_state(SubscriptionStates.entering_purchase_brand)
    await callback.message.edit_text(
        texts.t(
            'PARTNER_BRAND_NAME_PROMPT',
            '🏷 نام دلخواه برای اشتراک‌های جدید (۳ تا ۲۰ کاراکتر انگلیسی/عدد/_/-).\n'
            'برای رد کردن /skip را بفرستید.',
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=texts.BACK, callback_data=f'tariff_period:{tariff_id}:{period}')]
            ]
        ),
    )


@error_handler
async def handle_tariff_purchase_brand_input(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    tariff_id = state_data.get('purchase_brand_tariff_id')
    period = state_data.get('purchase_brand_period')
    if not tariff_id or not period:
        await state.set_state(None)
        return

    texts = get_texts(db_user.language)
    raw = (message.text or '').strip()
    if raw.lower() in ('/skip', 'skip', '-'):
        chat_id = state_data.get('purchase_brand_chat_id')
        message_id = state_data.get('purchase_brand_message_id')
        if not chat_id or not message_id:
            await state.set_state(None)
            return
        await state.set_state(None)
        await render_tariff_confirm_screen(
            bot=message.bot,
            chat_id=int(chat_id),
            message_id=int(message_id),
            db_user=db_user,
            db=db,
            state=state,
            tariff_id=int(tariff_id),
            period=int(period),
            fallback_message=message,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return
    if not raw:
        await message.answer(
            texts.t(
                'PARTNER_BRAND_NAME_PROMPT',
                '🏷 نام دلخواه برای اشتراک‌های جدید (۳ تا ۲۰ کاراکتر انگلیسی/عدد/_/-).\n'
                'برای رد کردن /skip را بفرستید.',
            )
        )
        return
    prefix = validate_brand_prefix(raw)
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
    db_user.panel_brand_prefix = prefix

    chat_id = state_data.get('purchase_brand_chat_id')
    message_id = state_data.get('purchase_brand_message_id')
    if not chat_id or not message_id:
        await state.set_state(None)
        return

    await state.update_data(use_brand_prefix=True)
    await state.set_state(None)
    await render_tariff_confirm_screen(
        bot=message.bot,
        chat_id=int(chat_id),
        message_id=int(message_id),
        db_user=db_user,
        db=db,
        state=state,
        tariff_id=int(tariff_id),
        period=int(period),
        fallback_message=message,
    )
    try:
        await message.delete()
    except Exception:
        pass


def register_partner_checkout_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(prompt_tariff_purchase_note, F.data.startswith('tariff_purchase_note:'))
    dp.callback_query.register(prompt_tariff_purchase_brand, F.data.startswith('tariff_purchase_brand:'))
    dp.message.register(handle_tariff_purchase_note_input, SubscriptionStates.entering_purchase_note)
    dp.message.register(handle_tariff_purchase_brand_input, SubscriptionStates.entering_purchase_brand)
