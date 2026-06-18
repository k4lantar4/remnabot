"""Partner checkout extras for tariff purchase confirm step."""

from __future__ import annotations

import html

from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.tariff import get_tariff_by_id
from app.database.models import User
from app.localization.texts import get_texts
from app.states import SubscriptionStates
from app.utils.decorators import error_handler
from app.utils.purchase_confirm import format_tariff_purchase_confirm_text
from app.utils.remnawave_panel_identity import MAX_PURCHASE_NOTE_LEN


def checkout_partner_options(db_user: User, state_data: dict) -> dict:
    has_brand = bool(db_user.is_partner and (db_user.panel_brand_prefix or '').strip())
    use_brand = state_data.get('use_brand_prefix')
    if use_brand is None:
        use_brand = has_brand
    return {
        'purchase_note': (state_data.get('purchase_note') or '').strip() or None,
        'use_brand_prefix': bool(use_brand) if has_brand else False,
        'has_brand_prefix': has_brand,
    }


def append_purchase_note_preview(text: str, texts, purchase_note: str | None) -> str:
    if not purchase_note:
        return text
    return text + '\n\n' + texts.t('PARTNER_PURCHASE_NOTE_PREVIEW', '📝 یادdاشت: {note}').format(
        note=html.escape(purchase_note)
    ).replace('یادdاشت', 'یاد\u062fاشت')


def get_partner_tariff_confirm_keyboard(
    tariff_id: int,
    period: int,
    language: str,
    *,
    db_user: User | None = None,
    purchase_note: str | None = None,
    use_brand_prefix: bool = False,
    show_brand_toggle: bool = False,
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    rows: list[list[InlineKeyboardButton]] = []

    if db_user and db_user.is_partner:
        rows.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PARTNER_BRAND_SETTINGS_BTN', '🏷 نام برند'),
                    callback_data='partner_brand_settings',
                )
            ]
        )
    if show_brand_toggle:
        key = 'PARTNER_BRAND_TOGGLE_ON' if use_brand_prefix else 'PARTNER_BRAND_TOGGLE_OFF'
        fallback = '✅ استفاده از نام برند' if use_brand_prefix else '⬜ استفاده از نام برند'
        rows.append(
            [
                InlineKeyboardButton(
                    text=texts.t(key, fallback),
                    callback_data=f'tariff_brand_toggle:{tariff_id}:{period}',
                )
            ]
        )

    note_key = 'PARTNER_PURCHASE_NOTE_SET_BTN' if purchase_note else 'PARTNER_PURCHASE_NOTE_BTN'
    note_text = texts.t(note_key, '📝 یادdاشت ✓' if purchase_note else '📝 یادdاشت')
    rows.append(
        [
            InlineKeyboardButton(
                text=note_text,
                callback_data=f'tariff_purchase_note:{tariff_id}:{period}',
            )
        ]
    )
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
    message: types.Message,
    *,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    tariff_id: int,
    period: int,
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
    body = append_purchase_note_preview(
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
    )
    await message.edit_text(
        body,
        reply_markup=get_partner_tariff_confirm_keyboard(
            tariff_id,
            period,
            db_user.language,
            db_user=db_user,
            purchase_note=partner_opts['purchase_note'],
            use_brand_prefix=partner_opts['use_brand_prefix'],
            show_brand_toggle=partner_opts['has_brand_prefix'],
        ),
        parse_mode='HTML',
    )


@error_handler
async def prompt_tariff_purchase_note(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    parts = callback.data.split(':')
    tariff_id, period = int(parts[1]), int(parts[2])
    await callback.answer()
    await state.update_data(purchase_note_tariff_id=tariff_id, purchase_note_period=period)
    await state.set_state(SubscriptionStates.entering_purchase_note)
    await callback.message.edit_text(
        texts.t(
            'PARTNER_PURCHASE_NOTE_PROMPT',
            '📝 یادdاشت اختیاری (حداکثر {max} کاراکتر). /skip برای رد.',
        ).format(max=MAX_PURCHASE_NOTE_LEN).replace('یادdاشت', 'یاد\u062fاشت'),
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
    note = None if raw.lower() in ('/skip', 'skip', '-') else (raw[:MAX_PURCHASE_NOTE_LEN] if raw else None)
    await state.update_data(purchase_note=note)
    await state.set_state(None)
    await render_tariff_confirm_screen(
        message,
        db_user=db_user,
        db=db,
        state=state,
        tariff_id=int(tariff_id),
        period=int(period),
    )


@error_handler
async def toggle_tariff_brand_prefix(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    if not db_user.is_partner or not (db_user.panel_brand_prefix or '').strip():
        await callback.answer(texts.t('PARTNER_BRAND_NOT_SET', '— تنظیم نشده —'), show_alert=True)
        return

    parts = callback.data.split(':')
    tariff_id, period = int(parts[1]), int(parts[2])
    state_data = await state.get_data()
    current = state_data.get('use_brand_prefix', True)
    await state.update_data(use_brand_prefix=not current)
    await callback.answer()
    await render_tariff_confirm_screen(
        callback.message,
        db_user=db_user,
        db=db,
        state=state,
        tariff_id=tariff_id,
        period=period,
    )


def register_partner_checkout_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(prompt_tariff_purchase_note, F.data.startswith('tariff_purchase_note:'))
    dp.callback_query.register(toggle_tariff_brand_prefix, F.data.startswith('tariff_brand_toggle:'))
    dp.message.register(handle_tariff_purchase_note_input, SubscriptionStates.entering_purchase_note)
