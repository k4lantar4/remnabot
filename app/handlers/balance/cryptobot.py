import html

import structlog
from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

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


def _unavailable_text(texts) -> str:
    return texts.t('CRYPTOBOT_TOPUP_UNAVAILABLE', '❌ Crypto top-up is not available right now.')


@error_handler
async def start_cryptobot_payment(callback: types.CallbackQuery, db_user: User, state: FSMContext):
    texts = get_texts(db_user.language)

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

    if not settings.is_cryptobot_enabled() or not toman_rates.is_cryptobot_toman_ready():
        await callback.answer(_unavailable_text(texts), show_alert=True)
        return

    # Fixed admin-set Toman-per-USDT rate (never a live exchange API).
    min_toman, max_toman = toman_rates.cryptobot_topup_limits_toman()
    message_text = texts.t(
        'CRYPTOBOT_TOPUP_PROMPT',
        '🪙 <b>Top up with crypto</b>\n\nEnter an amount from {min} to {max}.\n\n'
        '💱 Rate: 1 USDT = {rate}\nYou pay the equivalent in USDT through CryptoBot.',
    ).format(
        min=texts.format_balance(min_toman),
        max=texts.format_balance(max_toman),
        rate=texts.format_balance(int(toman_rates.cryptobot_toman_rate())),
    )

    keyboard = await get_topup_amount_keyboard('cryptobot', db_user.language, back_callback='back_to_menu')

    await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode='HTML')

    await state.set_state(BalanceStates.waiting_for_amount)
    await state.update_data(
        payment_method='cryptobot',
        cryptobot_prompt_message_id=callback.message.message_id,
        cryptobot_prompt_chat_id=callback.message.chat.id,
    )
    await callback.answer()


@error_handler
async def process_cryptobot_payment_amount(
    message: types.Message, db_user: User, db: AsyncSession, amount_kopeks: int, state: FSMContext
):
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

    if not settings.is_cryptobot_enabled() or not toman_rates.is_cryptobot_toman_ready():
        await message.answer(_unavailable_text(texts))
        return

    # amount_kopeks is the bot's top-up scale (Toman x100); the balance is credited in Toman.
    topup_toman = amount_kopeks
    min_toman, max_toman = toman_rates.cryptobot_topup_limits_toman()
    if not min_toman <= topup_toman <= max_toman:
        await message.answer(
            texts.t('TOPUP_AMOUNT_OUT_OF_RANGE', 'Enter an amount from {min} to {max}.').format(
                min=texts.format_balance(min_toman), max=texts.format_balance(max_toman)
            ),
            reply_markup=get_back_keyboard(db_user.language),
        )
        return

    try:
        amount_usdt = toman_rates.quote_usdt_for_toman(topup_toman)

        payment_service = PaymentService(message.bot)

        payment_result = await payment_service.create_cryptobot_payment(
            db=db,
            user_id=db_user.id,
            amount_usd=float(amount_usdt),
            asset=toman_rates.CRYPTOBOT_TOMAN_ASSET,
            description=texts.t('CRYPTOBOT_TOPUP_INVOICE_DESCRIPTION', 'Balance top-up: {amount}').format(
                amount=texts.format_balance(topup_toman)
            ),
            payload=toman_rates.build_toman_topup_payload(db_user.id, topup_toman),
        )

        if not payment_result:
            await message.answer('❌ Ошибка создания платежа. Попробуйте позже или обратитесь в поддержку.')
            await state.clear()
            return

        bot_invoice_url = payment_result.get('bot_invoice_url')
        mini_app_invoice_url = payment_result.get('mini_app_invoice_url')

        payment_url = bot_invoice_url or mini_app_invoice_url

        if not payment_url:
            await message.answer('❌ Ошибка получения ссылки для оплаты. Обратитесь в поддержку.')
            await state.clear()
            return

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t('CRYPTOBOT_PAY_BUTTON', '🪙 Pay'), url=payment_url)],
                [
                    types.InlineKeyboardButton(
                        text=texts.t('CRYPTOBOT_CHECK_STATUS_BUTTON', '📊 Check status'),
                        callback_data=f'check_cryptobot_{payment_result["local_payment_id"]}',
                    )
                ],
                [types.InlineKeyboardButton(text=texts.BACK, callback_data='balance_topup')],
            ]
        )

        state_data = await state.get_data()
        prompt_message_id = state_data.get('cryptobot_prompt_message_id')
        prompt_chat_id = state_data.get('cryptobot_prompt_chat_id', message.chat.id)

        try:
            await message.delete()
        except Exception as delete_error:  # pragma: no cover - depends on bot rights
            logger.warning('Не удалось удалить сообщение с суммой CryptoBot', delete_error=delete_error)

        if prompt_message_id and prompt_message_id != message.message_id:
            try:
                await message.bot.delete_message(prompt_chat_id, prompt_message_id)
            except Exception as delete_error:  # pragma: no cover - diagnostics
                logger.warning('Не удалось удалить сообщение с запросом суммы CryptoBot', delete_error=delete_error)

        invoice_message = await message.answer(
            texts.t(
                'CRYPTOBOT_TOPUP_INVOICE_MESSAGE',
                '🪙 <b>Pay with crypto</b>\n\n💰 Top-up amount: {amount}\n💵 To pay: {usdt} {asset}\n'
                '💱 Rate: 1 USDT = {rate}\n🆔 Payment ID: {invoice_id}...\n\n'
                'Tap “Pay”, send the amount in CryptoBot and your balance is topped up automatically.\n\n'
                '❓ Problems? Contact {support}',
            ).format(
                amount=texts.format_balance(topup_toman),
                usdt=f'{amount_usdt:.2f}',
                asset=payment_result['asset'],
                rate=texts.format_balance(int(toman_rates.cryptobot_toman_rate())),
                invoice_id=payment_result['invoice_id'][:8],
                support=settings.get_support_contact_display_html(),
            ),
            reply_markup=keyboard,
            parse_mode='HTML',
        )

        await state.update_data(
            cryptobot_invoice_message_id=invoice_message.message_id,
            cryptobot_invoice_chat_id=invoice_message.chat.id,
        )

        await state.clear()

        logger.info(
            'Создан CryptoBot платеж',
            telegram_id=db_user.telegram_id,
            topup_toman=topup_toman,
            amount_usdt=str(amount_usdt),
            payment_result=payment_result['invoice_id'],
        )

    except Exception as e:
        logger.error('Ошибка создания CryptoBot платежа', error=e)
        await message.answer('❌ Ошибка создания платежа. Попробуйте позже или обратитесь в поддержку.')
        await state.clear()


@error_handler
async def check_cryptobot_payment_status(callback: types.CallbackQuery, db: AsyncSession):
    try:
        local_payment_id = int(callback.data.split('_')[-1])

        from app.database.crud.cryptobot import get_cryptobot_payment_by_id

        payment = await get_cryptobot_payment_by_id(db, local_payment_id)

        if not payment:
            await callback.answer('❌ Платеж не найден', show_alert=True)
            return

        status_emoji = {'active': '⏳', 'paid': '✅', 'expired': '❌'}

        status_text = {'active': 'Ожидает оплаты', 'paid': 'Оплачен', 'expired': 'Истек'}

        emoji = status_emoji.get(payment.status, '❓')
        status = status_text.get(payment.status, 'Неизвестно')

        message_text = (
            f'🪙 Статус платежа:\n\n'
            f'🆔 ID: {payment.invoice_id[:8]}...\n'
            f'💰 Сумма: {payment.amount} {payment.asset}\n'
            f'📊 Статус: {emoji} {status}\n'
            f'📅 Создан: {payment.created_at.strftime("%d.%m.%Y %H:%M")}\n'
        )

        if payment.is_paid:
            message_text += '\n✅ Платеж успешно завершен!\n\nСредства зачислены на баланс.'
        elif payment.is_pending:
            message_text += "\n⏳ Платеж ожидает оплаты. Нажмите кнопку 'Оплатить' выше."
        elif payment.is_expired:
            message_text += f'\n❌ Платеж истек. Обратитесь в {settings.get_support_contact_display()}'

        await callback.answer(message_text, show_alert=True)

    except Exception as e:
        logger.error('Ошибка проверки статуса CryptoBot платежа', error=e)
        await callback.answer('❌ Ошибка проверки статуса', show_alert=True)
