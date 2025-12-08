import logging
from datetime import datetime
from typing import Optional

from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.services.payment_service import PaymentService
from app.states import BalanceStates
from app.utils.decorators import error_handler

logger = logging.getLogger(__name__)


@error_handler
async def start_heleket_payment(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)

    if not settings.is_heleket_enabled():
        await callback.answer(
            texts.get_text(
                "balance.heleket.unavailable",
                "❌ Heleket payments are unavailable right now",
            ),
            show_alert=True,
        )
        return

    markup = settings.get_heleket_markup_percent()
    markup_text: Optional[str]
    if markup > 0:
        label = texts.t("PAYMENT_HELEKET_MARKUP_LABEL", "Provider markup")
        markup_text = f"{label}: {markup:.0f}%"
    elif markup < 0:
        label = texts.t("PAYMENT_HELEKET_DISCOUNT_LABEL", "Provider discount")
        markup_text = f"{label}: {abs(markup):.0f}%"
    else:
        markup_text = None

    message_lines = [
        texts.get_text(
            "balance.heleket.prompt.title",
            "🪙 <b>Top up via Heleket</b>",
        ),
        "\n",
        texts.get_text(
            "balance.heleket.prompt.amount_hint",
            "Enter an amount from 100 to 100,000 ₽:",
        ),
        "",
        texts.get_text(
            "balance.heleket.prompt.fast_credit",
            "⚡ Instant credit",
        ),
        texts.get_text(
            "balance.heleket.prompt.secure",
            "🔒 Secure payment",
        ),
    ]

    if markup_text:
        message_lines.extend(["", markup_text])

    keyboard = get_back_keyboard(db_user.language)

    if settings.YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED and not settings.DISABLE_TOPUP_BUTTONS:
        from .main import get_quick_amount_buttons

        quick_buttons = get_quick_amount_buttons(db_user.language, db_user)
        if quick_buttons:
            keyboard.inline_keyboard = quick_buttons + keyboard.inline_keyboard

    await callback.message.edit_text(
        "\n".join(filter(None, message_lines)),
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    await state.set_state(BalanceStates.waiting_for_amount)
    await state.update_data(
        payment_method="heleket",
        heleket_prompt_message_id=callback.message.message_id,
        heleket_prompt_chat_id=callback.message.chat.id,
    )
    await callback.answer()


@error_handler
async def process_heleket_payment_amount(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)

    if not settings.is_heleket_enabled():
        await message.answer(
            texts.get_text(
                "balance.heleket.unavailable",
                "❌ Heleket payments are unavailable right now",
            )
        )
        return

    amount_rubles = amount_kopeks / 100

    if amount_rubles < 100:
        await message.answer(
            texts.get_text(
                "balance.heleket.min_amount",
                "Minimum top-up amount: 100 ₽",
            )
        )
        return

    if amount_rubles > 100000:
        await message.answer(
            texts.get_text(
                "balance.heleket.max_amount",
                "Maximum top-up amount: 100,000 ₽",
            )
        )
        return

    payment_service = PaymentService(message.bot)

    result = await payment_service.create_heleket_payment(
        db=db,
        user_id=db_user.id,
        amount_kopeks=amount_kopeks,
        description=f"Balance top-up {amount_rubles:.0f} ₽",
        language=db_user.language,
    )

    if not result:
        await message.answer(
            texts.get_text(
                "balance.heleket.create_error",
                "❌ Could not create Heleket invoice. Try again later or contact support.",
            )
        )
        await state.clear()
        return

    payment_url = result.get("payment_url")
    if not payment_url:
        await message.answer(
            texts.get_text(
                "balance.heleket.link_error",
                "❌ Failed to get Heleket payment link",
            )
        )
        await state.clear()
        return

    payer_amount = result.get("payer_amount")
    payer_currency = result.get("payer_currency")
    exchange_rate = result.get("exchange_rate")
    discount_percent = result.get("discount_percent")

    details = [
        texts.get_text(
            "balance.heleket.invoice.title",
            "🪙 <b>Heleket payment</b>",
        ),
        "",
        texts.get_text(
            "balance.heleket.invoice.amount_credit",
            "💰 Amount to credit: {amount} ₽",
        ).format(amount=amount_rubles),
    ]

    if payer_amount and payer_currency:
        details.append(
            texts.get_text(
                "balance.heleket.invoice.amount_to_pay",
                "🪙 To pay: {amount} {currency}",
            ).format(amount=payer_amount, currency=payer_currency)
        )

    markup_percent: Optional[float] = None
    if discount_percent is not None:
        try:
            discount_int = int(discount_percent)
            markup_percent = -discount_int
        except (TypeError, ValueError):
            markup_percent = None

    if markup_percent:
        label_markup = texts.t("PAYMENT_HELEKET_MARKUP_LABEL", "Provider markup")
        label_discount = texts.t("PAYMENT_HELEKET_DISCOUNT_LABEL", "Provider discount")
        absolute = abs(markup_percent)
        if markup_percent > 0:
            details.append(f"📈 {label_markup}: +{absolute}%")
        else:
            details.append(f"📉 {label_discount}: {absolute}%")

    if payer_amount and payer_currency:
        try:
            payer_amount_float = float(payer_amount)
            if payer_amount_float > 0:
                rub_per_currency = amount_rubles / payer_amount_float
                details.append(
                    texts.get_text(
                        "balance.heleket.invoice.rate",
                        "💱 Rate: 1 {currency} ≈ {rate:.2f} ₽",
                    ).format(currency=payer_currency, rate=rub_per_currency)
                )
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    details.extend(
        [
            "",
            texts.get_text(
                "balance.heleket.instructions.title",
                "📱 Instructions:",
            ),
            texts.get_text(
                "balance.heleket.instructions.step_pay",
                "1. Tap the 'Pay' button",
            ),
            texts.get_text(
                "balance.heleket.instructions.step_open",
                "2. Go to the Heleket page",
            ),
            texts.get_text(
                "balance.heleket.instructions.step_transfer",
                "3. Pay the specified amount",
            ),
            texts.get_text(
                "balance.heleket.instructions.step_credit",
                "4. Funds will be credited automatically",
            ),
        ]
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.get_text(
                    "balance.heleket.pay_button",
                    "🪙 Pay via Heleket",
                ),
                url=payment_url,
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                callback_data=f"check_heleket_{result['local_payment_id']}"
            )
        ],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")],
    ])

    state_data = await state.get_data()
    prompt_message_id = state_data.get("heleket_prompt_message_id")
    prompt_chat_id = state_data.get("heleket_prompt_chat_id", message.chat.id)

    try:
        await message.delete()
    except Exception as delete_error:  # pragma: no cover - depends on bot rights
        logger.warning(
            "Failed to delete Heleket amount message: %s",
            delete_error,
        )

    if prompt_message_id:
        try:
            await message.bot.delete_message(prompt_chat_id, prompt_message_id)
        except Exception as delete_error:  # pragma: no cover - diagnostic
            logger.warning(
                "Failed to delete Heleket prompt message: %s",
                delete_error,
            )

    invoice_message = await message.answer(
        "\n".join(details), parse_mode="HTML", reply_markup=keyboard
    )

    try:
        from app.services import payment_service as payment_module

        payment = await payment_module.get_heleket_payment_by_id(db, result["local_payment_id"])
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
    except Exception as error:  # pragma: no cover - diagnostics
        logger.warning("Failed to save Heleket message: %s", error)

    await state.update_data(
        heleket_invoice_message_id=invoice_message.message_id,
        heleket_invoice_chat_id=invoice_message.chat.id,
    )

    await state.clear()


@error_handler
async def check_heleket_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession,
) -> None:
    texts = get_texts(settings.DEFAULT_LANGUAGE)
    try:
        local_payment_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.get_text(
                "balance.heleket.invalid_id",
                "Invalid payment identifier",
            ),
            show_alert=True,
        )
        return

    from app.database.crud.heleket import get_heleket_payment_by_id

    payment = await get_heleket_payment_by_id(db, local_payment_id)
    if not payment:
        await callback.answer(
            texts.get_text(
                "balance.heleket.not_found",
                "Payment not found",
            ),
            show_alert=True,
        )
        return

    language = getattr(payment.user, "language", None) or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)

    if payment.is_paid:
        message = texts.t("HELEKET_PAYMENT_ALREADY_PAID", "✅ Payment has already been credited")
        await callback.answer(message, show_alert=True)
        return

    payment_service = PaymentService(callback.bot)
    updated_payment = await payment_service.sync_heleket_payment_status(
        db,
        local_payment_id=local_payment_id,
    )

    if updated_payment:
        payment = updated_payment

    if payment.is_paid:
        message = texts.t("HELEKET_PAYMENT_SUCCESS", "✅ Payment credited to balance")
        await callback.answer(message, show_alert=True)
        return

    status_normalized = (payment.status or "").lower()
    status_messages = {
        "check": texts.t("HELEKET_STATUS_CHECK", "⏳ Waiting for payment"),
        "process": texts.t("HELEKET_STATUS_PROCESS", "⚙️ Payment is being processed"),
        "confirm_check": texts.t("HELEKET_STATUS_CONFIRM_CHECK", "⛓ Waiting for network confirmations"),
        "wrong_amount": texts.t("HELEKET_STATUS_WRONG_AMOUNT", "❗️ Incorrect amount paid"),
        "wrong_amount_waiting": texts.t(
            "HELEKET_STATUS_WRONG_AMOUNT_WAITING",
            "❗️ Insufficient amount, waiting for additional payment",
        ),
        "paid_over": texts.t("HELEKET_STATUS_PAID_OVER", "✅ Payment credited (overpaid)"),
        "paid": texts.t("HELEKET_STATUS_PAID", "✅ Payment credited"),
        "cancel": texts.t("HELEKET_STATUS_CANCEL", "🚫 Payment was cancelled"),
        "fail": texts.t("HELEKET_STATUS_FAIL", "❌ Payment failed"),
        "system_fail": texts.t("HELEKET_STATUS_SYSTEM_FAIL", "❌ Heleket system error"),
        "refund_process": texts.t("HELEKET_STATUS_REFUND_PROCESS", "↩️ Refund in progress"),
        "refund_fail": texts.t("HELEKET_STATUS_REFUND_FAIL", "⚠️ Refund failed"),
        "refund_paid": texts.t("HELEKET_STATUS_REFUND_PAID", "✅ Refund completed"),
        "locked": texts.t("HELEKET_STATUS_LOCKED", "🔒 Funds are locked"),
    }

    message = status_messages.get(status_normalized)
    if message is None:
        template = texts.t("HELEKET_STATUS_UNKNOWN", "ℹ️ Payment status: {status}")
        status_value = payment.status or status_normalized or "—"
        try:
            message = template.format(status=status_value)
        except Exception:  # pragma: no cover - defensive formatting
            message = f"ℹ️ Payment status: {status_value}"

    await callback.answer(message, show_alert=True)
