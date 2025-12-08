import logging
from datetime import datetime

from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy import update
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
async def start_yookassa_payment(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    
    if not settings.is_yookassa_enabled():
        await callback.answer(texts.t("YOOKASSA_CARD_UNAVAILABLE", "❌ Card payment via YooKassa temporarily unavailable"), show_alert=True)
        return
    
    min_amount_rub = settings.YOOKASSA_MIN_AMOUNT_KOPEKS / 100
    max_amount_rub = settings.YOOKASSA_MAX_AMOUNT_KOPEKS / 100
    
    if settings.YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED and not settings.DISABLE_TOPUP_BUTTONS:
        message_text = texts.t(
            "YOOKASSA_CARD_PROMPT_QUICK",
            "💳 <b>Card payment</b>\n\nChoose a top-up amount or enter manually from {min} to {max} RUB:"
        ).format(min=f"{min_amount_rub:.0f}", max=f"{max_amount_rub:,.0f}")
    else:
        message_text = texts.t(
            "YOOKASSA_CARD_PROMPT",
            "💳 <b>Card payment</b>\n\nEnter a top-up amount from {min} to {max} RUB:"
        ).format(min=f"{min_amount_rub:.0f}", max=f"{max_amount_rub:,.0f}")
    
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
    await state.update_data(payment_method="yookassa")
    await state.update_data(
        yookassa_prompt_message_id=callback.message.message_id,
        yookassa_prompt_chat_id=callback.message.chat.id,
    )
    await callback.answer()


@error_handler
async def start_yookassa_sbp_payment(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    
    if not settings.is_yookassa_enabled() or not settings.YOOKASSA_SBP_ENABLED:
        await callback.answer(
            texts.t(
                "YOOKASSA_SBP_UNAVAILABLE",
                "❌ SBP payments are temporarily unavailable",
            ),
            show_alert=True,
        )
        return
    
    min_amount_rub = settings.YOOKASSA_MIN_AMOUNT_KOPEKS / 100
    max_amount_rub = settings.YOOKASSA_MAX_AMOUNT_KOPEKS / 100
    
    if settings.YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED and not settings.DISABLE_TOPUP_BUTTONS:
        message_text = texts.t(
            "YOOKASSA_SBP_PROMPT_QUICK",
            "🏦 <b>SBP payment</b>\n\nChoose or enter an amount from {min_amount} to {max_amount} RUB:",
        ).format(min_amount=f"{min_amount_rub:.0f}", max_amount=f"{max_amount_rub:,.0f}")
    else:
        message_text = texts.t(
            "YOOKASSA_SBP_PROMPT",
            "🏦 <b>SBP payment</b>\n\nEnter an amount from {min_amount} to {max_amount} RUB:",
        ).format(min_amount=f"{min_amount_rub:.0f}", max_amount=f"{max_amount_rub:,.0f}")
    
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
    await state.update_data(payment_method="yookassa_sbp")
    await state.update_data(
        yookassa_prompt_message_id=callback.message.message_id,
        yookassa_prompt_chat_id=callback.message.chat.id,
    )
    await callback.answer()


@error_handler
async def process_yookassa_payment_amount(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    
    if not settings.is_yookassa_enabled():
        await message.answer(texts.t("YOOKASSA_UNAVAILABLE", "❌ YooKassa payments temporarily unavailable"))
        return
    
    if amount_kopeks < settings.YOOKASSA_MIN_AMOUNT_KOPEKS:
        min_rubles = settings.YOOKASSA_MIN_AMOUNT_KOPEKS / 100
        await message.answer(texts.t("YOOKASSA_MIN_CARD", "❌ Minimum card payment amount: {amount} ₽").format(amount=f"{min_rubles:.0f}"))
        return
    
    if amount_kopeks > settings.YOOKASSA_MAX_AMOUNT_KOPEKS:
        max_rubles = settings.YOOKASSA_MAX_AMOUNT_KOPEKS / 100
        await message.answer(texts.t("YOOKASSA_MAX_CARD", "❌ Maximum card payment amount: {amount} ₽").format(amount=f"{max_rubles:,.0f}".replace(',', ' ')))
        return
    
    try:
        payment_service = PaymentService(message.bot)
        
        payment_result = await payment_service.create_yookassa_payment(
            db=db,
            user_id=db_user.id,
            amount_kopeks=amount_kopeks,
            description=settings.get_balance_payment_description(amount_kopeks),
            receipt_email=None,
            receipt_phone=None,
            metadata={
                "user_telegram_id": str(db_user.telegram_id),
                "user_username": db_user.username or "",
                "purpose": "balance_topup"
            }
        )
        
        if not payment_result:
            await message.answer(texts.t("PAYMENT_CREATE_ERROR", "❌ Error creating payment. Please try again later or contact support."))
            await state.clear()
            return
        
        confirmation_url = payment_result.get("confirmation_url")
        if not confirmation_url:
            await message.answer(texts.t("PAYMENT_LINK_ERROR", "❌ Error getting payment link. Please contact support."))
            await state.clear()
            return
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("YOOKASSA_PAY_CARD_BTN", "💳 Pay by card"), url=confirmation_url)],
            [types.InlineKeyboardButton(text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"), callback_data=f"check_yookassa_{payment_result['local_payment_id']}")],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")]
        ])
        
        state_data = await state.get_data()
        prompt_message_id = state_data.get("yookassa_prompt_message_id")
        prompt_chat_id = state_data.get("yookassa_prompt_chat_id", message.chat.id)

        try:
            await message.delete()
        except Exception as delete_error:  # pragma: no cover - depends on bot rights
            logger.warning("Failed to delete YooKassa amount message: %s", delete_error)

        if prompt_message_id:
            try:
                await message.bot.delete_message(prompt_chat_id, prompt_message_id)
            except Exception as delete_error:  # pragma: no cover - diagnostic log
                logger.warning("Failed to delete YooKassa prompt message: %s", delete_error)

        invoice_message = await message.answer(
            texts.t(
                "YOOKASSA_CARD_INVOICE",
                "💳 <b>Card payment</b>\n\n"
                "💰 Amount: {amount}\n"
                "🆔 Payment ID: {pid}...\n\n"
                "📱 <b>Instructions:</b>\n"
                "1. Tap 'Pay by card'\n"
                "2. Enter your card details\n"
                "3. Confirm the payment\n"
                "4. Funds will be credited automatically\n\n"
                "🔒 Payment is processed via secure YooKassa\n"
                "✅ Cards accepted: Visa, MasterCard, MIR\n\n"
                "❓ If you have issues, contact {support}"
            ).format(
                amount=settings.format_price(amount_kopeks),
                pid=payment_result['yookassa_payment_id'][:8],
                support=settings.get_support_contact_display_html(),
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        try:
            from app.services import payment_service as payment_module

            payment = await payment_module.get_yookassa_payment_by_local_id(
                db, payment_result["local_payment_id"]
            )
            if payment:
                metadata = dict(getattr(payment, "metadata_json", {}) or {})
                metadata["invoice_message"] = {
                    "chat_id": invoice_message.chat.id,
                    "message_id": invoice_message.message_id,
                }
                await db.execute(
                    update(payment.__class__)
                    .where(payment.__class__.id == payment.id)
                    .values(metadata_json=metadata, updated_at=datetime.utcnow())
                )
                await db.commit()
        except Exception as error:  # pragma: no cover - diagnostic log
            logger.warning("Failed to store YooKassa message metadata: %s", error)

        await state.update_data(
            yookassa_invoice_message_id=invoice_message.message_id,
            yookassa_invoice_chat_id=invoice_message.chat.id,
        )

        await state.clear()
        logger.info(
            "Created YooKassa payment for user %s: %s₽, ID: %s",
            db_user.telegram_id,
            amount_kopeks // 100,
            payment_result["yookassa_payment_id"],
        )
        
    except Exception as e:
        logger.error(f"Error creating YooKassa payment: {e}")
        await message.answer(texts.t("PAYMENT_CREATE_ERROR", "❌ Error creating payment. Please try again later or contact support."))
        await state.clear()


@error_handler
async def process_yookassa_sbp_payment_amount(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    
    if not settings.is_yookassa_enabled() or not settings.YOOKASSA_SBP_ENABLED:
        await message.answer(
            texts.t(
                "YOOKASSA_SBP_UNAVAILABLE",
                "❌ SBP payments are temporarily unavailable",
            )
        )
        return
    
    if amount_kopeks < settings.YOOKASSA_MIN_AMOUNT_KOPEKS:
        min_rubles = settings.YOOKASSA_MIN_AMOUNT_KOPEKS / 100
        await message.answer(
            texts.t(
                "YOOKASSA_SBP_MIN",
                "❌ Minimum SBP amount: {amount} ₽",
            ).format(amount=f"{min_rubles:.0f}")
        )
        return
    
    if amount_kopeks > settings.YOOKASSA_MAX_AMOUNT_KOPEKS:
        max_rubles = settings.YOOKASSA_MAX_AMOUNT_KOPEKS / 100
        await message.answer(
            texts.t(
                "YOOKASSA_SBP_MAX",
                "❌ Maximum SBP amount: {amount} ₽",
            ).format(amount=f"{max_rubles:,.0f}".replace(",", " "))
        )
        return
    
    try:
        payment_service = PaymentService(message.bot)
        
        payment_result = await payment_service.create_yookassa_sbp_payment(
            db=db,
            user_id=db_user.id,
            amount_kopeks=amount_kopeks,
            description=settings.get_balance_payment_description(amount_kopeks),
            receipt_email=None,
            receipt_phone=None,
            metadata={
                "user_telegram_id": str(db_user.telegram_id),
                "user_username": db_user.username or "",
                "purpose": "balance_topup_sbp"
            }
        )
        
        if not payment_result:
            await message.answer(
                texts.t(
                    "YOOKASSA_SBP_CREATE_ERROR",
                    "❌ Could not create SBP payment. Try again later or contact support.",
                )
            )
            await state.clear()
            return
        
        confirmation_url = payment_result.get("confirmation_url")
        qr_confirmation_data = payment_result.get("qr_confirmation_data")
        
        if not confirmation_url and not qr_confirmation_data:
            await message.answer(
                texts.t(
                    "YOOKASSA_SBP_DATA_ERROR",
                    "❌ Could not get SBP payment data. Contact support.",
                )
            )
            await state.clear()
            return
        
        # Prepare QR code for insertion into main message
        qr_photo = None
        if qr_confirmation_data:
            try:
                # Import required modules for QR code generation
                import base64
                from io import BytesIO
                import qrcode
                from aiogram.types import BufferedInputFile
                
                # Create QR code from received data
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(qr_confirmation_data)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Save image to bytes
                img_bytes = BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                qr_photo = BufferedInputFile(img_bytes.getvalue(), filename="qrcode.png")
            except ImportError:
                logger.warning("qrcode library is not installed; QR will not be generated")
            except Exception as e:
                logger.error(f"QR code generation failed: {e}")
        
        # If no QR data from YooKassa but URL exists, generate QR code from URL
        if not qr_photo and confirmation_url:
            try:
                # Import required modules for QR code generation
                import base64
                from io import BytesIO
                import qrcode
                from aiogram.types import BufferedInputFile
                
                # Create QR code from URL
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(confirmation_url)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Save image to bytes
                img_bytes = BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                qr_photo = BufferedInputFile(img_bytes.getvalue(), filename="qrcode.png")
            except ImportError:
                logger.warning("qrcode library is not installed; QR will not be generated")
            except Exception as e:
                logger.error(f"QR code generation from URL failed: {e}")
        
        # Create keyboard with buttons for payment link and status check
        keyboard_buttons = []

        # Add payment button if link is available
        if confirmation_url:
            keyboard_buttons.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t(
                            "YOOKASSA_SBP_OPEN_PAYMENT_LINK",
                            "🔗 Go to payment",
                        ),
                        url=confirmation_url,
                    )
                ]
            )
        else:
            keyboard_buttons.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t(
                            "YOOKASSA_SBP_PAY_IN_BANK_APP",
                            "📱 Pay in your bank app",
                        ),
                        callback_data="temp_disabled",
                    )
                ]
            )

        keyboard_buttons.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                    callback_data=f"check_yookassa_{payment_result['local_payment_id']}",
                )
            ]
        )
        keyboard_buttons.append([types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")])

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        state_data = await state.get_data()
        prompt_message_id = state_data.get("yookassa_prompt_message_id")
        prompt_chat_id = state_data.get("yookassa_prompt_chat_id", message.chat.id)

        try:
            await message.delete()
        except Exception as delete_error:  # pragma: no cover - depends on bot rights
            logger.warning("Failed to delete YooKassa SBP amount message: %s", delete_error)

        if prompt_message_id:
            try:
                await message.bot.delete_message(prompt_chat_id, prompt_message_id)
            except Exception as delete_error:  # pragma: no cover - diagnostic log
                logger.warning(
                    "Failed to delete YooKassa SBP prompt message: %s",
                    delete_error,
                )

        message_text = texts.t(
            "YOOKASSA_SBP_INVOICE_HEADER",
            "🔗 <b>SBP payment</b>\n\n"
            "💰 Amount: {amount}\n"
            "🆔 Payment ID: {payment_id}...\n\n",
        ).format(
            amount=settings.format_price(amount_kopeks),
            payment_id=payment_result["yookassa_payment_id"][:8],
        )

        if not confirmation_url:
            message_text += texts.t(
                "YOOKASSA_SBP_OFFLINE_INSTRUCTIONS",
                "📱 <b>How to pay:</b>\n"
                "1. Open your banking app\n"
                "2. Find SBP/fast payment transfer\n"
                "3. Enter payment ID: <code>{payment_id}</code>\n"
                "4. Confirm the payment in the app\n"
                "5. Funds will be credited automatically\n\n",
            ).format(payment_id=payment_result["yookassa_payment_id"])

        message_text += texts.t(
            "YOOKASSA_SBP_FOOTER",
            "🔒 Payment is processed via secure YooKassa\n"
            "✅ SBP is accepted from all participating banks\n\n"
            "❓ If you have issues, contact {support}",
        ).format(support=settings.get_support_contact_display_html())

        # Send message with instructions and keyboard
        # If QR code exists, send it as media message
        if qr_photo:
            # Use media group or photo with caption method
            invoice_message = await message.answer_photo(
                photo=qr_photo,
                caption=message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # If QR code is unavailable, send regular text message
            invoice_message = await message.answer(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        try:
            from app.services import payment_service as payment_module

            payment = await payment_module.get_yookassa_payment_by_local_id(
                db, payment_result["local_payment_id"]
            )
            if payment:
                metadata = dict(getattr(payment, "metadata_json", {}) or {})
                metadata["invoice_message"] = {
                    "chat_id": invoice_message.chat.id,
                    "message_id": invoice_message.message_id,
                }
                await db.execute(
                    update(payment.__class__)
                    .where(payment.__class__.id == payment.id)
                    .values(metadata_json=metadata, updated_at=datetime.utcnow())
                )
                await db.commit()
        except Exception as error:  # pragma: no cover - diagnostic log
            logger.warning("Failed to store YooKassa SBP invoice message: %s", error)

        await state.update_data(
            yookassa_invoice_message_id=invoice_message.message_id,
            yookassa_invoice_chat_id=invoice_message.chat.id,
        )

        await state.clear()
        logger.info(
            "Created YooKassa SBP payment for user %s: %s₽, ID: %s",
            db_user.telegram_id,
            amount_kopeks // 100,
            payment_result["yookassa_payment_id"],
        )
        
    except Exception as e:
        logger.error(f"Failed to create YooKassa SBP payment: {e}")
        await message.answer(
            texts.t(
                "YOOKASSA_SBP_CREATE_ERROR",
                "❌ Could not create SBP payment. Try again later or contact support.",
            )
        )
        await state.clear()





@error_handler
async def check_yookassa_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession
):
    try:
        local_payment_id = int(callback.data.split('_')[-1])
        
        from app.database.crud.yookassa import get_yookassa_payment_by_local_id
        payment = await get_yookassa_payment_by_local_id(db, local_payment_id)
        
        if not payment:
            await callback.answer(
                texts.t(
                    "YOOKASSA_PAYMENT_NOT_FOUND",
                    "❌ Payment not found",
                ),
                show_alert=True,
            )
            return
        
        status_emoji = {
            "pending": "⏳",
            "waiting_for_capture": "⌛",
            "succeeded": "✅",
            "canceled": "❌",
            "failed": "❌"
        }
        
        status_text = {
            "pending": texts.t("YOOKASSA_STATUS_PENDING", "Waiting for payment"),
            "waiting_for_capture": texts.t("YOOKASSA_STATUS_WAITING_FOR_CAPTURE", "Awaiting confirmation"),
            "succeeded": texts.t("YOOKASSA_STATUS_SUCCEEDED", "Paid"),
            "canceled": texts.t("YOOKASSA_STATUS_CANCELED", "Canceled"),
            "failed": texts.t("YOOKASSA_STATUS_FAILED", "Failed")
        }
        
        emoji = status_emoji.get(payment.status, "❓")
        status = status_text.get(payment.status, texts.t("YOOKASSA_STATUS_UNKNOWN", "Unknown"))
        
        message_text = texts.t(
            "YOOKASSA_STATUS_MESSAGE",
            "💳 Payment status:\n\n"
            "🆔 ID: {pid}...\n"
            "💰 Amount: {amount}\n"
            "📊 Status: {emoji} {status}\n"
            "📅 Created: {created}\n",
        ).format(
            pid=payment.yookassa_payment_id[:8],
            amount=settings.format_price(payment.amount_kopeks),
            emoji=emoji,
            status=status,
            created=payment.created_at.strftime('%d.%m.%Y %H:%M'),
        )
        
        if payment.is_succeeded:
            message_text += texts.t(
                "YOOKASSA_STATUS_SUCCESS",
                "\n✅ Payment completed. Funds are on the balance.",
            )
        elif payment.is_pending:
            message_text += texts.t(
                "YOOKASSA_STATUS_PENDING_HINT",
                "\n⏳ Payment is awaiting completion. Tap Pay above.",
            )
        elif payment.is_failed:
            message_text += texts.t(
                "YOOKASSA_STATUS_FAILED_HINT",
                "\n❌ Payment failed. Contact {support}",
            ).format(support=settings.get_support_contact_display())
        
        await callback.answer(message_text, show_alert=True)
        
    except Exception as e:
        logger.error(f"Payment status check failed: {e}")
        await callback.answer(
            texts.t(
                "YOOKASSA_STATUS_CHECK_ERROR",
                "❌ Failed to check status",
            ),
            show_alert=True,
        )