import logging
from decimal import Decimal, ROUND_HALF_UP
from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.payment_service import PaymentService
from app.external.telegram_stars import TelegramStarsService
from app.database.crud.user import get_user_by_telegram_id
from app.localization.loader import DEFAULT_LANGUAGE
from app.localization.texts import get_texts

logger = logging.getLogger(__name__)


async def handle_pre_checkout_query(query: types.PreCheckoutQuery):
    texts = get_texts(DEFAULT_LANGUAGE)

    try:
        logger.info(
            "📋 Pre-checkout query from %s: %s XTR, payload: %s",
            query.from_user.id,
            query.total_amount,
            query.invoice_payload,
        )

        allowed_prefixes = ("balance_", "admin_stars_test_", "simple_sub_")

        if not query.invoice_payload or not query.invoice_payload.startswith(allowed_prefixes):
            logger.warning("Invalid Stars payload: %s", query.invoice_payload)
            await query.answer(
                ok=False,
                error_message=texts.t(
                    "STARS_PRECHECK_INVALID_PAYLOAD",
                    "Payment validation error. Try again.",
                ),
            )
            return

        try:
            from app.database.database import get_db

            async for db in get_db():
                user = await get_user_by_telegram_id(db, query.from_user.id)
                if not user:
                    logger.warning("User %s not found in DB", query.from_user.id)
                    await query.answer(
                        ok=False,
                        error_message=texts.t(
                            "STARS_PRECHECK_USER_NOT_FOUND",
                            "User not found. Contact support.",
                        ),
                    )
                    return
                texts = get_texts(user.language or DEFAULT_LANGUAGE)
                break
        except Exception as db_error:
            logger.error("DB error during pre_checkout_query: %s", db_error)
            await query.answer(
                ok=False,
                error_message=texts.t(
                    "STARS_PRECHECK_TECHNICAL_ERROR",
                    "Technical error. Please try later.",
                ),
            )
            return

        await query.answer(ok=True)
        logger.info("Pre-checkout approved for user %s", query.from_user.id)

    except Exception as e:
        logger.error("Error in pre_checkout_query: %s", e, exc_info=True)
        await query.answer(
            ok=False,
            error_message=texts.t(
                "STARS_PRECHECK_TECHNICAL_ERROR",
                "Technical error. Please try later.",
            ),
        )


async def handle_successful_payment(
    message: types.Message,
    db: AsyncSession,
    state: FSMContext,
    **kwargs
):
    texts = get_texts(DEFAULT_LANGUAGE)

    try:
        payment = message.successful_payment
        user_id = message.from_user.id

        logger.info(
            "💳 Stars payment success from %s: %s XTR, payload: %s, charge_id: %s",
            user_id,
            payment.total_amount,
            payment.invoice_payload,
            payment.telegram_payment_charge_id,
        )

        user = await get_user_by_telegram_id(db, user_id)
        texts = get_texts(user.language if user and user.language else DEFAULT_LANGUAGE)

        if not user:
            logger.error("User %s not found during Stars payment handling", user_id)
            await message.answer(
                texts.t(
                    "STARS_PAYMENT_USER_NOT_FOUND",
                    "❌ Error: user not found. Contact support.",
                )
            )
            return

        payment_service = PaymentService(message.bot)

        state_data = await state.get_data()
        prompt_message_id = state_data.get("stars_prompt_message_id")
        prompt_chat_id = state_data.get("stars_prompt_chat_id", message.chat.id)
        invoice_message_id = state_data.get("stars_invoice_message_id")
        invoice_chat_id = state_data.get("stars_invoice_chat_id", message.chat.id)

        for chat_id, message_id, label in [
            (prompt_chat_id, prompt_message_id, "amount prompt"),
            (invoice_chat_id, invoice_message_id, "Stars invoice"),
        ]:
            if message_id:
                try:
                    await message.bot.delete_message(chat_id, message_id)
                except Exception as delete_error:  # pragma: no cover - depends on bot rights
                    logger.warning(
                        "Failed to delete %s message after Stars payment: %s",
                        label,
                        delete_error,
                    )

        success = await payment_service.process_stars_payment(
            db=db,
            user_id=user.id,
            stars_amount=payment.total_amount,
            payload=payment.invoice_payload,
            telegram_payment_charge_id=payment.telegram_payment_charge_id
        )

        await state.update_data(
            stars_prompt_message_id=None,
            stars_prompt_chat_id=None,
            stars_invoice_message_id=None,
            stars_invoice_chat_id=None,
        )

        if success:
            rubles_amount = TelegramStarsService.calculate_rubles_from_stars(payment.total_amount)
            amount_kopeks = int((rubles_amount * Decimal(100)).to_integral_value(rounding=ROUND_HALF_UP))
            amount_text = settings.format_price(amount_kopeks).replace(" ₽", "")

            keyboard = await payment_service.build_topup_success_keyboard(user)

            transaction_id_short = payment.telegram_payment_charge_id[:8]

            await message.answer(
                texts.t(
                    "STARS_PAYMENT_SUCCESS",
                    "🎉 <b>Payment processed!</b>\n\n"
                    "⭐ Stars spent: {stars_spent}\n"
                    "💰 Credited to balance: {amount} ₽\n"
                    "🆔 Transaction ID: {transaction_id}...\n\n"
                    "⚠️ <b>Important:</b> Balance top-up does not activate a subscription automatically. "
                    "Activate your subscription separately!\n\n"
                    "🔄 If a subscription cart is saved and auto-buy is enabled, "
                    "it will be purchased automatically after the top-up.\n\n"
                    "Thanks for topping up! 🚀",
                ).format(
                    stars_spent=payment.total_amount,
                    amount=amount_text,
                    transaction_id=transaction_id_short,
                ),
                parse_mode="HTML",
                reply_markup=keyboard,
            )

            logger.info(
                "✅ Stars payment processed: user %s, %s stars → %s",
                user.id,
                payment.total_amount,
                settings.format_price(amount_kopeks),
            )
        else:
            logger.error("Stars payment processing failed for user %s", user.id)
            await message.answer(
                texts.t(
                    "STARS_PAYMENT_ENROLLMENT_ERROR",
                    "❌ Failed to credit funds. Contact support; the payment will be checked manually.",
                )
            )

    except Exception as e:
        logger.error(f"Error in successful_payment: {e}", exc_info=True)
        await message.answer(
            texts.t(
                "STARS_PAYMENT_PROCESSING_ERROR",
                "❌ Technical error while processing payment. "
                "Contact support for assistance.",
            )
        )


def register_stars_handlers(dp: Dispatcher):

    dp.pre_checkout_query.register(
        handle_pre_checkout_query,
        F.currency == "XTR"
    )

    dp.message.register(
        handle_successful_payment,
        F.successful_payment
    )

    logger.info("🌟 Telegram Stars payment handlers registered")
