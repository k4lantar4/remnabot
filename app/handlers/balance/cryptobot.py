import logging
from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.services.payment_service import PaymentService
from app.utils.decorators import error_handler
from app.states import BalanceStates

logger = logging.getLogger(__name__)


@error_handler
async def start_cryptobot_payment(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    
    if not settings.is_cryptobot_enabled():
        await callback.answer(texts.t("CRYPTOBOT_UNAVAILABLE", "❌ Cryptocurrency payment temporarily unavailable"), show_alert=True)
        return
    
    from app.utils.currency_converter import currency_converter
    try:
        current_rate = await currency_converter.get_usd_to_rub_rate()
        rate_text = texts.t("CRYPTOBOT_RATE_CURRENT", "💱 Current rate: 1 USD = {rate}").format(rate=f"{current_rate:.2f} ₽")
    except Exception as e:
        logger.warning(f"Failed to get exchange rate: {e}")
        current_rate = 95.0
        rate_text = texts.t("CRYPTOBOT_RATE_APPROX", "💱 Rate: 1 USD ≈ {rate}").format(rate=f"{current_rate:.0f} ₽")
    
    available_assets = settings.get_cryptobot_assets()
    assets_text = ", ".join(available_assets)
    
    if settings.YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED and not settings.DISABLE_TOPUP_BUTTONS:
        message_text = texts.t(
            "CRYPTOBOT_PROMPT_WITH_BUTTONS",
            "🪙 <b>Cryptocurrency top-up</b>\n\n"
            "Choose an amount or enter manually from 100 to 100,000 ₽:\n\n"
            "💰 Available assets: {assets}\n"
            "⚡ Instant balance credit\n"
            "🔒 Secure payment via CryptoBot\n\n"
            "{rate}\n"
            "Amount will be automatically converted to USD for payment."
        ).format(assets=assets_text, rate=rate_text)
    else:
        message_text = texts.t(
            "CRYPTOBOT_PROMPT",
            "🪙 <b>Cryptocurrency top-up</b>\n\n"
            "Enter amount from 100 to 100,000 ₽:\n\n"
            "💰 Available assets: {assets}\n"
            "⚡ Instant balance credit\n"
            "🔒 Secure payment via CryptoBot\n\n"
            "{rate}\n"
            "Amount will be automatically converted to USD for payment."
        ).format(assets=assets_text, rate=rate_text)
    
    keyboard = get_back_keyboard(db_user.language)
    
    if settings.YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED and not settings.DISABLE_TOPUP_BUTTONS:
        from .main import get_quick_amount_buttons
        quick_amount_buttons = get_quick_amount_buttons(db_user.language, db_user)
        if quick_amount_buttons:
            keyboard.inline_keyboard = quick_amount_buttons + keyboard.inline_keyboard
    
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(BalanceStates.waiting_for_amount)
    await state.update_data(
        payment_method="cryptobot",
        current_rate=current_rate,
        cryptobot_prompt_message_id=callback.message.message_id,
        cryptobot_prompt_chat_id=callback.message.chat.id,
    )
    await callback.answer()


@error_handler
async def process_cryptobot_payment_amount(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    
    if not settings.is_cryptobot_enabled():
        await message.answer(texts.t("CRYPTOBOT_UNAVAILABLE", "❌ Cryptocurrency payment temporarily unavailable"))
        return
    
    amount_rubles = amount_kopeks / 100
    
    if amount_rubles < 100:
        await message.answer(texts.t("MIN_AMOUNT_100", "Minimum top-up amount: 100 ₽"))
        return
    
    if amount_rubles > 100000:
        await message.answer(texts.t("MAX_AMOUNT_100K", "Maximum top-up amount: 100,000 ₽"))
        return
    
    try:
        data = await state.get_data()
        current_rate = data.get('current_rate')
        
        if not current_rate:
            from app.utils.currency_converter import currency_converter
            current_rate = await currency_converter.get_usd_to_rub_rate()
        
        amount_usd = amount_rubles / current_rate
        
        amount_usd = round(amount_usd, 2)
        
        if amount_usd < 1:
            await message.answer(texts.t("CRYPTOBOT_MIN_USD", "❌ Minimum amount for USD payment: 1.00 USD"))
            return
        
        if amount_usd > 1000:
            await message.answer(texts.t("CRYPTOBOT_MAX_USD", "❌ Maximum amount for USD payment: 1,000 USD"))
            return
        
        payment_service = PaymentService(message.bot)
        
        payment_result = await payment_service.create_cryptobot_payment(
            db=db,
            user_id=db_user.id,
            amount_usd=amount_usd,
            asset=settings.CRYPTOBOT_DEFAULT_ASSET,
            description=f"Balance top-up {amount_rubles:.0f} RUB ({amount_usd:.2f} USD)",
            payload=f"balance_{db_user.id}_{amount_kopeks}"
        )
        
        if not payment_result:
            await message.answer(texts.t("PAYMENT_CREATE_ERROR", "❌ Error creating payment. Please try again later or contact support."))
            await state.clear()
            return
        
        bot_invoice_url = payment_result.get("bot_invoice_url")
        mini_app_invoice_url = payment_result.get("mini_app_invoice_url")
        
        payment_url = bot_invoice_url or mini_app_invoice_url
        
        if not payment_url:
            await message.answer(texts.t("PAYMENT_LINK_ERROR", "❌ Error getting payment link. Please contact support."))
            await state.clear()
            return
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("PAY_BUTTON", "🪙 Pay"), url=payment_url)],
            [types.InlineKeyboardButton(text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"), callback_data=f"check_cryptobot_{payment_result['local_payment_id']}")],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")]
        ])

        state_data = await state.get_data()
        prompt_message_id = state_data.get("cryptobot_prompt_message_id")
        prompt_chat_id = state_data.get("cryptobot_prompt_chat_id", message.chat.id)

        try:
            await message.delete()
        except Exception as delete_error:  # pragma: no cover - depends on bot rights
            logger.warning(
                "Failed to delete CryptoBot amount message: %s",
                delete_error,
            )

        if prompt_message_id:
            try:
                await message.bot.delete_message(prompt_chat_id, prompt_message_id)
            except Exception as delete_error:  # pragma: no cover - diagnostics
                logger.warning(
                    "Failed to delete CryptoBot prompt message: %s",
                    delete_error,
                )

        invoice_message = await message.answer(
            texts.t(
                "CRYPTOBOT_INVOICE_MESSAGE",
                "🪙 <b>Cryptocurrency payment</b>\n\n"
                "💰 Amount to credit: {amount_rub} ₽\n"
                "💵 To pay: {amount_usd} USD\n"
                "🪙 Asset: {asset}\n"
                "💱 Rate: 1 USD = {rate} ₽\n"
                "🆔 Payment ID: {payment_id}...\n\n"
                "📱 <b>Instructions:</b>\n"
                "1. Click the 'Pay' button\n"
                "2. Choose your preferred asset\n"
                "3. Transfer the specified amount\n"
                "4. Funds will be credited automatically\n\n"
                "🔒 Payment is processed via secure CryptoBot system\n"
                "⚡ Supported assets: USDT, TON, BTC, ETH\n\n"
                "❓ If you have any issues, contact {support}"
            ).format(
                amount_rub=f"{amount_rubles:.0f}",
                amount_usd=f"{amount_usd:.2f}",
                asset=payment_result['asset'],
                rate=f"{current_rate:.2f}",
                payment_id=payment_result['invoice_id'][:8],
                support=settings.get_support_contact_display_html()
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.update_data(
            cryptobot_invoice_message_id=invoice_message.message_id,
            cryptobot_invoice_chat_id=invoice_message.chat.id,
        )

        await state.clear()
        
        logger.info(f"Created CryptoBot payment for user {db_user.telegram_id}: "
                   f"{amount_rubles:.0f} RUB ({amount_usd:.2f} USD), ID: {payment_result['invoice_id']}")
        
    except Exception as e:
        logger.error(f"Error creating CryptoBot payment: {e}")
        await message.answer(texts.t("PAYMENT_CREATE_ERROR", "❌ Error creating payment. Please try again later or contact support."))
        await state.clear()


@error_handler
async def check_cryptobot_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession,
    db_user: User = None
):
    texts = get_texts(db_user.language if db_user else "en")
    try:
        local_payment_id = int(callback.data.split('_')[-1])
        
        from app.database.crud.cryptobot import get_cryptobot_payment_by_id
        payment = await get_cryptobot_payment_by_id(db, local_payment_id)
        
        if not payment:
            await callback.answer(texts.t("PAYMENT_NOT_FOUND", "❌ Payment not found"), show_alert=True)
            return
        
        status_emoji = {
            "active": "⏳",
            "paid": "✅",
            "expired": "❌"
        }
        
        status_labels = {
            "active": texts.t("STATUS_AWAITING_PAYMENT", "Awaiting payment"),
            "paid": texts.t("STATUS_PAID", "Paid"),
            "expired": texts.t("STATUS_EXPIRED", "Expired")
        }
        
        emoji = status_emoji.get(payment.status, "❓")
        status = status_labels.get(payment.status, texts.t("STATUS_UNKNOWN", "Unknown"))
        
        message_text = texts.t(
            "CRYPTOBOT_STATUS_MESSAGE",
            "🪙 Payment status:\n\n"
            "🆔 ID: {payment_id}...\n"
            "💰 Amount: {amount} {asset}\n"
            "📊 Status: {emoji} {status}\n"
            "📅 Created: {created_at}\n"
        ).format(
            payment_id=payment.invoice_id[:8],
            amount=payment.amount,
            asset=payment.asset,
            emoji=emoji,
            status=status,
            created_at=payment.created_at.strftime('%d.%m.%Y %H:%M')
        )
        
        if payment.is_paid:
            message_text += texts.t("PAYMENT_SUCCESS_CREDITED", "\n✅ Payment completed successfully!\n\nFunds credited to balance.")
        elif payment.is_pending:
            message_text += texts.t("PAYMENT_AWAITING", "\n⏳ Payment awaiting. Click the 'Pay' button above.")
        elif payment.is_expired:
            message_text += texts.t(
                "PAYMENT_EXPIRED_SUPPORT",
                "\n❌ Payment expired. Contact {support}"
            ).format(support=settings.get_support_contact_display())
        
        await callback.answer(message_text, show_alert=True)
        
    except Exception as e:
        logger.error(f"Error checking CryptoBot payment status: {e}")
        await callback.answer(texts.t("STATUS_CHECK_ERROR", "❌ Error checking status"), show_alert=True)