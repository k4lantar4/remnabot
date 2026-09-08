"""Partner note/brand overlay on 4.2 tariff confirm (fail-open)."""

from __future__ import annotations

from types import SimpleNamespace

from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.localization.texts import get_texts
from app.states import SubscriptionStates
from app.utils.decorators import error_handler
from app.utils.partner_checkout_telegram import checkout_partner_options, sanitize_purchase_note


class _ConfirmMessage:
    def __init__(self, bot, chat_id: int, message_id: int):
        self.bot = bot
        self.chat = SimpleNamespace(id=chat_id)
        self.message_id = message_id

    async def edit_text(self, text, **kwargs):
        return await self.bot.edit_message_text(
            text=text,
            chat_id=self.chat.id,
            message_id=self.message_id,
            **kwargs,
        )


class _ReshowCallback:
    def __init__(self, *, data: str, message, answer_fn=None):
        self.data = data
        self.message = message
        self._answer_fn = answer_fn

    async def answer(self, *args, **kwargs):
        if self._answer_fn:
            return await self._answer_fn(*args, **kwargs)
        return None


async def _reshow_tariff_confirm(
    *,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    tariff_id: int,
    period: int,
    message,
    answer_fn=None,
) -> None:
    from app.handlers.subscription.tariff_purchase import select_tariff_period

    await select_tariff_period(
        _ReshowCallback(
            data=f'tariff_period:{tariff_id}:{period}',
            message=message,
            answer_fn=answer_fn,
        ),
        db_user,
        db,
        state,
    )


@error_handler
async def prompt_purchase_note(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    if not getattr(db_user, 'is_partner', False) or not hasattr(db_user, 'panel_brand_prefix'):
        await callback.answer()
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
    await state.set_state(SubscriptionStates.waiting_for_purchase_note)
    cancel_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t('CANCEL', '❌ Cancel'),
                    callback_data=f'pnote_cancel:{tariff_id}:{period}',
                )
            ]
        ]
    )
    await callback.message.edit_text(
        texts.t(
            'PARTNER_PURCHASE_NOTE_PROMPT',
            'Send a note for this purchase (max 500 characters).',
        ),
        reply_markup=None,
    )
    await callback.message.edit_reply_markup(reply_markup=cancel_keyboard)


@error_handler
async def handle_purchase_note_input(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    tariff_id = state_data.get('purchase_note_tariff_id')
    period = state_data.get('purchase_note_period')
    chat_id = state_data.get('purchase_note_chat_id')
    message_id = state_data.get('purchase_note_message_id')
    if not tariff_id or not period or not chat_id or not message_id:
        await state.set_state(None)
        return

    note = sanitize_purchase_note(message.text)
    if note is None:
        await state.set_state(None)
        await _reshow_tariff_confirm(
            db_user=db_user,
            db=db,
            state=state,
            tariff_id=int(tariff_id),
            period=int(period),
            message=_ConfirmMessage(message.bot, int(chat_id), int(message_id)),
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    await state.update_data(purchase_note=note)
    await state.set_state(None)
    await _reshow_tariff_confirm(
        db_user=db_user,
        db=db,
        state=state,
        tariff_id=int(tariff_id),
        period=int(period),
        message=_ConfirmMessage(message.bot, int(chat_id), int(message_id)),
    )
    try:
        await message.delete()
    except Exception:
        pass


@error_handler
async def cancel_purchase_note(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    if not getattr(db_user, 'is_partner', False) or not hasattr(db_user, 'panel_brand_prefix'):
        await callback.answer()
        return

    parts = callback.data.split(':')
    tariff_id, period = int(parts[1]), int(parts[2])
    await callback.answer()
    await state.set_state(None)
    await _reshow_tariff_confirm(
        db_user=db_user,
        db=db,
        state=state,
        tariff_id=tariff_id,
        period=period,
        message=callback.message,
    )


@error_handler
async def toggle_brand_prefix(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    if not getattr(db_user, 'is_partner', False) or not hasattr(db_user, 'panel_brand_prefix'):
        await callback.answer()
        return

    parts = callback.data.split(':')
    tariff_id, period = int(parts[1]), int(parts[2])
    await callback.answer()
    state_data = await state.get_data()
    opts = checkout_partner_options(db_user, state_data)
    await state.update_data(use_brand_prefix=not opts['use_brand_prefix'])
    await _reshow_tariff_confirm(
        db_user=db_user,
        db=db,
        state=state,
        tariff_id=tariff_id,
        period=period,
        message=callback.message,
    )


def register_partner_checkout_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(prompt_purchase_note, F.data.startswith('pnote:'))
    dp.callback_query.register(toggle_brand_prefix, F.data.startswith('pbrand:'))
    dp.message.register(
        handle_purchase_note_input, SubscriptionStates.waiting_for_purchase_note, F.text
    )
