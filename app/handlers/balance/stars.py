import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.services.blacklist_service import blacklist_service
from app.services.payment_service import PaymentService
from app.states import BalanceStates
from app.utils.decorators import error_handler
from app.external.telegram_stars import TelegramStarsService

logger = logging.getLogger(__name__)


@error_handler
async def start_stars_payment(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)

    if not settings.TELEGRAM_STARS_ENABLED:
        await callback.answer(texts.t("STARS_UNAVAILABLE"), show_alert=True)
        return

    if settings.YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED and not settings.DISABLE_TOPUP_BUTTONS:
        message_text = texts.t("STARS_PROMPT_WITH_BUTTONS")
    else:
        message_text = texts.TOP_UP_AMOUNT

    keyboard = get_back_keyboard(db_user.language)

    if settings.YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED and not settings.DISABLE_TOPUP_BUTTONS:
        from .main import get_quick_amount_buttons
        quick_amount_buttons = get_quick_amount_buttons(db_user.language, db_user)
        if quick_amount_buttons:
            keyboard.inline_keyboard = quick_amount_buttons + keyboard.inline_keyboard

    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard
    )

    await state.update_data(
        stars_prompt_message_id=callback.message.message_id,
        stars_prompt_chat_id=callback.message.chat.id,
    )

    await state.set_state(BalanceStates.waiting_for_amount)
    await state.update_data(payment_method="stars")
    await callback.answer()


@error_handler
async def process_stars_payment_amount(
    message: types.Message,
    db_user: User,
    amount_kopeks: int,
    state: FSMContext
):
    # Проверяем, находится ли пользователь в черном списке
    is_blacklisted, blacklist_reason = await blacklist_service.is_user_blacklisted(
        message.from_user.id,
        message.from_user.username
    )

    if is_blacklisted:
        logger.warning(f"🚫 Пользователь {message.from_user.id} находится в черном списке: {blacklist_reason}")
        try:
            await message.answer(
                f"🚫 Оплата невозможна\n\n"
                f"Причина: {blacklist_reason}\n\n"
                f"Если вы считаете, что это ошибка, обратитесь в поддержку."
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения о блокировке: {e}")
        return

    texts = get_texts(db_user.language)

    if not settings.TELEGRAM_STARS_ENABLED:
        await message.answer(texts.t("STARS_UNAVAILABLE"))
        return

    try:
        amount_rubles = amount_kopeks / 100
        stars_amount = TelegramStarsService.calculate_stars_from_rubles(amount_rubles)
        stars_rate = settings.get_stars_rate()

        payment_service = PaymentService(message.bot)
        invoice_link = await payment_service.create_stars_invoice(
            amount_kopeks=amount_kopeks,
            description=f"Balance top-up {texts.format_price(amount_kopeks)}",
            payload=f"balance_{db_user.id}_{amount_kopeks}"
        )

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("STARS_PAY_BUTTON"), url=invoice_link)],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")]
        ])

        state_data = await state.get_data()

        prompt_message_id = state_data.get("stars_prompt_message_id")
        prompt_chat_id = state_data.get("stars_prompt_chat_id", message.chat.id)

        try:
            await message.delete()
        except Exception as delete_error:  # pragma: no cover - depends on bot rights
            logger.warning("Failed to delete Stars amount message: %s", delete_error)

        if prompt_message_id:
            try:
                await message.bot.delete_message(prompt_chat_id, prompt_message_id)
            except Exception as delete_error:  # pragma: no cover - diagnostic log
                logger.warning(
                    "Failed to delete Stars prompt message: %s",
                    delete_error,
                )

        invoice_message = await message.answer(
            texts.t("STARS_INVOICE_MESSAGE").format(
                amount=texts.format_price(amount_kopeks),
                stars=stars_amount,
                rate=f"{stars_rate}₽"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.update_data(
            stars_invoice_message_id=invoice_message.message_id,
            stars_invoice_chat_id=invoice_message.chat.id,
        )

        await state.set_state(None)

    except Exception as e:
        logger.error(f"Error creating Stars invoice: {e}")
        await message.answer(texts.t("PAYMENT_CREATE_ERROR_SHORT"))
