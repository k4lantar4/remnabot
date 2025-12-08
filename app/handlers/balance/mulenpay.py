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
async def start_mulenpay_payment(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    mulenpay_name = settings.get_mulenpay_display_name()
    mulenpay_name_html = settings.get_mulenpay_display_name_html()

    if not settings.is_mulenpay_enabled():
        await callback.answer(
            texts.t(
                "MULENPAY_UNAVAILABLE",
                "❌ Payments via {provider} are temporarily unavailable",
            ).format(provider=mulenpay_name),
            show_alert=True,
        )
        return

    message_template = texts.t(
        "MULENPAY_TOPUP_PROMPT",
        (
            "💳 <b>Payment via {mulenpay_name_html}</b>\n\n"
            "Enter a top-up amount from 100 to 100,000 ₽.\n"
            "Payment is processed via secure {mulenpay_name}."
        ),
    )
    message_text = message_template.format(
        mulenpay_name=mulenpay_name,
        mulenpay_name_html=mulenpay_name_html,
    )

    keyboard = get_back_keyboard(db_user.language)

    if settings.YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED and not settings.DISABLE_TOPUP_BUTTONS:
        from .main import get_quick_amount_buttons
        quick_amount_buttons = get_quick_amount_buttons(db_user.language, db_user)
        if quick_amount_buttons:
            keyboard.inline_keyboard = quick_amount_buttons + keyboard.inline_keyboard

    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    await state.set_state(BalanceStates.waiting_for_amount)
    await state.update_data(
        payment_method="mulenpay",
        mulenpay_prompt_message_id=callback.message.message_id,
        mulenpay_prompt_chat_id=callback.message.chat.id,
    )
    await callback.answer()


@error_handler
async def process_mulenpay_payment_amount(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    mulenpay_name = settings.get_mulenpay_display_name()
    mulenpay_name_html = settings.get_mulenpay_display_name_html()

    if not settings.is_mulenpay_enabled():
        await message.answer(
            texts.t(
                "MULENPAY_UNAVAILABLE",
                "❌ Payments via {provider} are temporarily unavailable",
            ).format(provider=mulenpay_name)
        )
        return

    if amount_kopeks < settings.MULENPAY_MIN_AMOUNT_KOPEKS:
        await message.answer(
            texts.t(
                "MULENPAY_MIN_AMOUNT",
                "Minimum top-up amount: {amount}",
            ).format(amount=settings.format_price(settings.MULENPAY_MIN_AMOUNT_KOPEKS))
        )
        return

    if amount_kopeks > settings.MULENPAY_MAX_AMOUNT_KOPEKS:
        await message.answer(
            texts.t(
                "MULENPAY_MAX_AMOUNT",
                "Maximum top-up amount: {amount}",
            ).format(amount=settings.format_price(settings.MULENPAY_MAX_AMOUNT_KOPEKS))
        )
        return

    amount_rubles = amount_kopeks / 100

    state_data = await state.get_data()
    prompt_message_id = state_data.get("mulenpay_prompt_message_id")
    prompt_chat_id = state_data.get("mulenpay_prompt_chat_id", message.chat.id)

    try:
        await message.delete()
    except Exception as delete_error:  # pragma: no cover - depends on bot permissions
        logger.warning(
            "Failed to delete MulenPay amount message: %s",
            delete_error,
        )

    if prompt_message_id:
        try:
            await message.bot.delete_message(prompt_chat_id, prompt_message_id)
        except Exception as delete_error:  # pragma: no cover - diagnostic
            logger.warning(
                "Failed to delete MulenPay prompt message: %s",
                delete_error,
            )

    try:
        payment_service = PaymentService(message.bot)
        payment_result = await payment_service.create_mulenpay_payment(
            db=db,
            user_id=db_user.id,
            amount_kopeks=amount_kopeks,
            description=settings.get_balance_payment_description(amount_kopeks),
            language=db_user.language,
        )

        if not payment_result or not payment_result.get("payment_url"):
            await message.answer(
                texts.t(
                    "MULENPAY_PAYMENT_ERROR",
                    "❌ Error creating {mulenpay_name} payment. Try again later or contact support.",
                ).format(mulenpay_name=mulenpay_name)
            )
            await state.clear()
            return

        payment_url = payment_result.get("payment_url")
        mulen_payment_id = payment_result.get("mulen_payment_id")
        local_payment_id = payment_result.get("local_payment_id")

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t(
                            "MULENPAY_PAY_BUTTON",
                            "💳 Pay via {mulenpay_name}",
                        ).format(mulenpay_name=mulenpay_name),
                        url=payment_url,
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                        callback_data=f"check_mulenpay_{local_payment_id}",
                    )
                ],
                [types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")],
            ]
        )

        payment_id_display = mulen_payment_id if mulen_payment_id is not None else local_payment_id

        message_template = texts.t(
            "MULENPAY_PAYMENT_INSTRUCTIONS",
            (
                "💳 <b>Payment via {mulenpay_name_html}</b>\n\n"
                "💰 Amount: {amount}\n"
                "🆔 Payment ID: {payment_id}\n\n"
                "📱 <b>Instructions:</b>\n"
                "1. Tap 'Pay via {mulenpay_name}'\n"
                "2. Follow the payment system prompts\n"
                "3. Confirm the transfer\n"
                "4. Funds will be credited automatically\n\n"
                "❓ If you have any issues, contact {support}"
            ),
        )

        message_text = message_template.format(
            amount=settings.format_price(amount_kopeks),
            payment_id=payment_id_display,
            support=settings.get_support_contact_display_html(),
            mulenpay_name=mulenpay_name,
            mulenpay_name_html=mulenpay_name_html,
        )

        invoice_message = await message.answer(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        try:
            from app.services import payment_service as payment_module

            payment = await payment_module.get_mulenpay_payment_by_local_id(
                db, local_payment_id
            )
            if payment:
                payment_metadata = dict(
                    getattr(payment, "metadata_json", {}) or {}
                )
                payment_metadata["invoice_message"] = {
                    "chat_id": invoice_message.chat.id,
                    "message_id": invoice_message.message_id,
                }
                await payment_module.update_mulenpay_payment_metadata(
                    db,
                    payment=payment,
                    metadata=payment_metadata,
                )
        except Exception as error:  # pragma: no cover - diagnostic logging only
            logger.warning(
                "Failed to save MulenPay invoice message metadata: %s",
                error,
            )

        await state.update_data(
            mulenpay_invoice_message_id=invoice_message.message_id,
            mulenpay_invoice_chat_id=invoice_message.chat.id,
        )

        await state.clear()

        logger.info(
            "Created %s payment for user %s: %s₽, ID: %s",
            mulenpay_name,
            db_user.telegram_id,
            amount_rubles,
            payment_id_display,
        )

    except Exception as e:
        logger.error(f"Error creating {mulenpay_name} payment: {e}")
        await message.answer(
            texts.t(
                "MULENPAY_PAYMENT_ERROR",
                "❌ Error creating {mulenpay_name} payment. Try again later or contact support.",
            ).format(mulenpay_name=mulenpay_name)
        )
        await state.clear()


@error_handler
async def check_mulenpay_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession
):
    try:
        local_payment_id = int(callback.data.split('_')[-1])
        payment_service = PaymentService(callback.bot)
        status_info = await payment_service.get_mulenpay_payment_status(db, local_payment_id)

        if not status_info:
            texts = get_texts(settings.DEFAULT_LANGUAGE)
            await callback.answer(
                texts.t("MULENPAY_PAYMENT_NOT_FOUND", "❌ Payment not found"),
                show_alert=True,
            )
            return

        payment = status_info["payment"]

        status_labels = {
            "created": ("⏳", "MULENPAY_STATUS_CREATED"),
            "processing": ("⌛", "MULENPAY_STATUS_PROCESSING"),
            "success": ("✅", "MULENPAY_STATUS_SUCCESS"),
            "canceled": ("❌", "MULENPAY_STATUS_CANCELED"),
            "error": ("⚠️", "MULENPAY_STATUS_ERROR"),
            "hold": ("🔒", "MULENPAY_STATUS_HOLD"),
            "unknown": ("❓", "MULENPAY_STATUS_UNKNOWN"),
        }

        emoji, status_key = status_labels.get(payment.status, ("❓", "MULENPAY_STATUS_UNKNOWN"))
        texts = get_texts(getattr(payment.user, "language", None) or settings.DEFAULT_LANGUAGE)
        status_label = texts.t(
            status_key,
            {
                "MULENPAY_STATUS_CREATED": "Awaiting payment",
                "MULENPAY_STATUS_PROCESSING": "Processing",
                "MULENPAY_STATUS_SUCCESS": "Paid",
                "MULENPAY_STATUS_CANCELED": "Canceled",
                "MULENPAY_STATUS_ERROR": "Error",
                "MULENPAY_STATUS_HOLD": "Hold",
                "MULENPAY_STATUS_UNKNOWN": "Unknown",
            }.get(status_key, "Unknown"),
        )

        mulenpay_name = settings.get_mulenpay_display_name()
        message_lines = [
            texts.t("MULENPAY_STATUS_TITLE", "💳 {provider} payment status:").format(
                provider=mulenpay_name
            ),
            "",
            texts.t("MULENPAY_STATUS_ID", "🆔 ID: {pid}").format(
                pid=payment.mulen_payment_id or payment.id
            ),
            texts.t("MULENPAY_STATUS_AMOUNT", "💰 Amount: {amount}").format(
                amount=settings.format_price(payment.amount_kopeks)
            ),
            texts.t("MULENPAY_STATUS_STATE", "📊 Status: {emoji} {status}").format(
                emoji=emoji, status=status_label
            ),
            texts.t("MULENPAY_STATUS_CREATED_AT", "📅 Created: {date}").format(
                date=payment.created_at.strftime('%d.%m.%Y %H:%M')
            ),
        ]

        if payment.is_paid:
            message_lines.append("")
            message_lines.append(
                texts.t(
                    "MULENPAY_STATUS_PAID",
                    "✅ Payment completed successfully! Funds are on the balance.",
                )
            )
        elif payment.status in {"created", "processing"}:
            message_lines.append(
                texts.t(
                    "MULENPAY_STATUS_PENDING",
                    "⏳ Payment is not finished yet. Complete the payment via the link and check status later.",
                )
            )
            if payment.payment_url:
                message_lines.append(
                    texts.t("MULENPAY_STATUS_LINK", "🔗 Payment link: {url}").format(
                        url=payment.payment_url
                    )
                )
        elif payment.status in {"canceled", "error"}:
            message_lines.append(
                texts.t(
                    "MULENPAY_STATUS_FAILED",
                    "❌ Payment failed. Create a new payment or contact {support}",
                ).format(support=settings.get_support_contact_display())
            )

        message_text = "".join(message_lines)

        if len(message_text) > 190:
            await callback.message.answer(message_text)
            await callback.answer(
                texts.t("MULENPAY_STATUS_SENT", "ℹ️ Status sent to chat"),
                show_alert=True,
            )
        else:
            await callback.answer(message_text, show_alert=True)

    except Exception as e:
        logger.error(
            "Error checking %s status: %s",
            settings.get_mulenpay_display_name(),
            e,
        )
        texts = get_texts(settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("MULENPAY_STATUS_ERROR", "❌ Error checking status"),
            show_alert=True,
        )