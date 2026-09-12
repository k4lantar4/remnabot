import html
import time

import structlog
from aiogram import types
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.keyboards.topup_amounts import get_topup_amount_keyboard
from app.localization.texts import get_texts
from app.services.payment_service import PaymentService
from app.states import BalanceStates
from app.utils import toman_rates
from app.utils.decorators import error_handler


logger = structlog.get_logger(__name__)


@error_handler
async def start_stars_payment(callback: types.CallbackQuery, db_user: User, state: FSMContext):
    texts = get_texts(db_user.language)

    if not settings.TELEGRAM_STARS_ENABLED:
        await callback.answer('❌ Пополнение через Stars временно недоступно', show_alert=True)
        return

    # Проверка ограничения на пополнение
    if getattr(db_user, 'restriction_topup', False):
        reason = html.escape(getattr(db_user, 'restriction_reason', None) or 'Действие ограничено администратором')
        support_url = settings.get_support_contact_url()
        keyboard = []
        if support_url:
            keyboard.append([types.InlineKeyboardButton(text='🆘 Обжаловать', url=support_url)])
        keyboard.append([types.InlineKeyboardButton(text=texts.BACK, callback_data='menu_balance')])

        await callback.message.edit_text(
            f'🚫 <b>Пополнение ограничено</b>\n\n{reason}\n\n'
            'Если вы считаете это ошибкой, вы можете обжаловать решение.',
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
        )
        await callback.answer()
        return

    message_text = texts.TOP_UP_AMOUNT

    keyboard = await get_topup_amount_keyboard('stars', db_user.language, back_callback='back_to_menu')

    await callback.message.edit_text(message_text, reply_markup=keyboard)

    await state.update_data(
        stars_prompt_message_id=callback.message.message_id,
        stars_prompt_chat_id=callback.message.chat.id,
    )

    await state.set_state(BalanceStates.waiting_for_amount)
    await state.update_data(payment_method='stars')
    await callback.answer()


@error_handler
async def process_stars_payment_amount(message: types.Message, db_user: User, amount_kopeks: int, state: FSMContext):
    texts = get_texts(db_user.language)

    # Проверка ограничения на пополнение
    if getattr(db_user, 'restriction_topup', False):
        reason = html.escape(getattr(db_user, 'restriction_reason', None) or 'Действие ограничено администратором')
        support_url = settings.get_support_contact_url()
        keyboard = []
        if support_url:
            keyboard.append([types.InlineKeyboardButton(text='🆘 Обжаловать', url=support_url)])
        keyboard.append([types.InlineKeyboardButton(text=texts.BACK, callback_data='menu_balance')])

        await message.answer(
            f'🚫 <b>Пополнение ограничено</b>\n\n{reason}\n\n'
            'Если вы считаете это ошибкой, вы можете обжаловать решение.',
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode='HTML',
        )
        await state.clear()
        return

    texts = get_texts(db_user.language)

    # amount_kopeks is the bot's top-up scale (Toman x100). Stars are quoted from the fixed
    # TELEGRAM_STARS_TOMAN_PER_STAR rate; the payload carries the Toman those stars credit.
    if not toman_rates.is_stars_toman_ready():
        await message.answer(texts.t('STARS_TOPUP_UNAVAILABLE', '⚠️ Telegram Stars top-up is not available right now.'))
        return

    topup_toman = amount_kopeks
    min_toman, max_toman = toman_rates.stars_topup_limits_toman()
    if not min_toman <= topup_toman <= max_toman:
        await message.answer(
            texts.t('TOPUP_AMOUNT_OUT_OF_RANGE', 'Enter an amount from {min} to {max}.').format(
                min=texts.format_balance(min_toman), max=texts.format_balance(max_toman)
            ),
            reply_markup=get_back_keyboard(db_user.language, callback_data='balance_topup'),
        )
        return

    try:
        quote = toman_rates.quote_stars_for_toman(topup_toman)

        payment_service = PaymentService(message.bot)
        invoice_link = await payment_service.create_stars_invoice(
            amount_kopeks=quote.credit_toman,
            title=texts.t('STARS_TOPUP_INVOICE_TITLE', 'Balance top-up'),
            description=texts.t(
                'STARS_TOPUP_INVOICE_DESCRIPTION', 'Top up your balance by {amount} ({stars} ⭐)'
            ).format(amount=texts.format_balance(quote.credit_toman), stars=quote.stars),
            payload=toman_rates.build_toman_topup_payload(db_user.id, quote.credit_toman, nonce=int(time.time())),
            stars_amount=quote.stars,
        )

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t('STARS_PAY_BUTTON', '⭐ Pay'), url=invoice_link)],
                [types.InlineKeyboardButton(text=texts.BACK, callback_data='balance_topup')],
            ]
        )

        state_data = await state.get_data()

        prompt_message_id = state_data.get('stars_prompt_message_id')
        prompt_chat_id = state_data.get('stars_prompt_chat_id', message.chat.id)

        try:
            await message.delete()
        except Exception as delete_error:  # pragma: no cover - зависит от прав бота
            logger.warning('Не удалось удалить сообщение с суммой Stars', delete_error=delete_error)

        if prompt_message_id and prompt_message_id != message.message_id:
            try:
                await message.bot.delete_message(prompt_chat_id, prompt_message_id)
            except Exception as delete_error:  # pragma: no cover - диагностический лог
                logger.warning('Не удалось удалить сообщение с запросом суммы Stars', delete_error=delete_error)

        invoice_message = await message.answer(
            texts.t(
                'STARS_TOPUP_INVOICE_MESSAGE',
                '⭐ <b>Pay with Telegram Stars</b>\n\n💰 Top-up amount: {amount}\n⭐ To pay: {stars} stars\n'
                '📊 Rate: {rate} per star\n\nTap the button below to pay:',
            ).format(
                amount=texts.format_balance(quote.credit_toman),
                stars=quote.stars,
                rate=texts.format_balance(toman_rates.stars_to_toman(1)),
            ),
            reply_markup=keyboard,
            parse_mode='HTML',
        )

        await state.update_data(
            stars_invoice_message_id=invoice_message.message_id,
            stars_invoice_chat_id=invoice_message.chat.id,
        )

        await state.set_state(None)

    except Exception as e:
        logger.error('Ошибка создания Stars invoice', error=e)
        await message.answer(texts.t('TOPUP_PAYMENT_CREATE_ERROR', '⚠️ Could not create the payment. Please try again.'))
