"""Handlers for Platega balance interactions."""

import logging
from typing import List

from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.services.payment_service import PaymentService
from app.states import BalanceStates
from app.utils.decorators import error_handler

logger = logging.getLogger(__name__)


def _get_active_methods() -> List[int]:
    methods = settings.get_platega_active_methods()
    return [code for code in methods if code in {2, 10, 11, 12, 13}]


async def _prompt_amount(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    method_code: int,
) -> None:
    texts = get_texts(db_user.language)
    method_name = settings.get_platega_method_display_title(method_code)

    # Always store selected method for subsequent processing
    await state.update_data(payment_method="platega", platega_method=method_code)

    data = await state.get_data()
    pending_amount = int(data.get("platega_pending_amount") or 0)

    if pending_amount > 0:
        # If amount is already known (e.g., after quick selection),
        # create payment immediately and reset temporary value.
        await state.update_data(platega_pending_amount=None)

        from app.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            await process_platega_payment_amount(
                message,
                db_user,
                db,
                pending_amount,
                state,
            )
        return

    min_amount_label = settings.format_price(settings.PLATEGA_MIN_AMOUNT_KOPEKS)
    max_amount_kopeks = settings.PLATEGA_MAX_AMOUNT_KOPEKS
    max_amount_label = (
        settings.format_price(max_amount_kopeks)
        if max_amount_kopeks and max_amount_kopeks > 0
        else ""
    )

    default_prompt_body = (
        texts.t(
            "PLATEGA_AMOUNT_PROMPT_WITH_MAX",
            "Enter a top-up amount from {min_amount} to {max_amount}.\n",
        )
        if max_amount_kopeks and max_amount_kopeks > 0
        else texts.t(
            "PLATEGA_AMOUNT_PROMPT_WITHOUT_MAX",
            "Enter a top-up amount from {min_amount}.\n",
        )
    )

    prompt_template = texts.t(
        "PLATEGA_TOPUP_PROMPT",
        (
            "💳 <b>Platega payment ({method_name})</b>\n\n"
            f"{default_prompt_body}"
            "Payment is processed via Platega."
        ),
    )

    keyboard = get_back_keyboard(db_user.language)

    if settings.YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED and not settings.DISABLE_TOPUP_BUTTONS:
        from .main import get_quick_amount_buttons

        quick_amount_buttons = get_quick_amount_buttons(db_user.language, db_user)
        if quick_amount_buttons:
            keyboard.inline_keyboard = quick_amount_buttons + keyboard.inline_keyboard

    await message.edit_text(
        prompt_template.format(
            method_name=method_name,
            min_amount=min_amount_label,
            max_amount=max_amount_label,
        ),
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    await state.set_state(BalanceStates.waiting_for_amount)
    await state.update_data(
        platega_prompt_message_id=message.message_id,
        platega_prompt_chat_id=message.chat.id,
    )


@error_handler
async def start_platega_payment(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
):
    texts = get_texts(db_user.language)

    if not settings.is_platega_enabled():
        await callback.answer(
            texts.t(
                "PLATEGA_TEMPORARILY_UNAVAILABLE",
                "❌ Platega payments are temporarily unavailable",
            ),
            show_alert=True,
        )
        return

    active_methods = _get_active_methods()
    if not active_methods:
        await callback.answer(
            texts.t(
                "PLATEGA_METHODS_NOT_CONFIGURED",
                "⚠️ No Platega payment methods are available",
            ),
            show_alert=True,
        )
        return

    await state.update_data(payment_method="platega")
    data = await state.get_data()
    has_pending_amount = bool(int(data.get("platega_pending_amount") or 0))

    if len(active_methods) == 1:
        await _prompt_amount(callback.message, db_user, state, active_methods[0])
        await callback.answer()
        return

    method_buttons: list[list[types.InlineKeyboardButton]] = []
    for method_code in active_methods:
        label = settings.get_platega_method_display_title(method_code)
        method_buttons.append(
            [
                types.InlineKeyboardButton(
                    text=label,
                    callback_data=f"platega_method_{method_code}",
                )
            ]
        )

    method_buttons.append(
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")]
    )

    await callback.message.edit_text(
        texts.t(
            "PLATEGA_SELECT_PAYMENT_METHOD",
            "Choose a Platega payment method:",
        ),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=method_buttons),
    )
    if not has_pending_amount:
        await state.set_state(BalanceStates.waiting_for_platega_method)
    await callback.answer()


@error_handler
async def handle_platega_method_selection(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
):
    try:
        method_code = int(callback.data.rsplit("_", 1)[-1])
    except ValueError:
        await callback.answer(
            texts.t(
                "PLATEGA_INVALID_METHOD",
                "❌ Invalid payment method",
            ),
            show_alert=True,
        )
        return

    if method_code not in _get_active_methods():
        await callback.answer(
            texts.t(
                "PLATEGA_METHOD_UNAVAILABLE",
                "⚠️ This method is currently unavailable",
            ),
            show_alert=True,
        )
        return

    await _prompt_amount(callback.message, db_user, state, method_code)
    await callback.answer()


@error_handler
async def process_platega_payment_amount(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    state: FSMContext,
):
    texts = get_texts(db_user.language)

    if not settings.is_platega_enabled():
        await message.answer(
            texts.t(
                "PLATEGA_TEMPORARILY_UNAVAILABLE",
                "❌ Platega payments are temporarily unavailable",
            )
        )
        return

    data = await state.get_data()
    method_code = int(data.get("platega_method", 0))
    if method_code not in _get_active_methods():
        await message.answer(
            texts.t(
                "PLATEGA_METHOD_SELECTION_REQUIRED",
                "⚠️ Choose a Platega method before entering an amount",
            )
        )
        await state.set_state(BalanceStates.waiting_for_platega_method)
        return

    if amount_kopeks < settings.PLATEGA_MIN_AMOUNT_KOPEKS:
        await message.answer(
            texts.t(
                "PLATEGA_AMOUNT_TOO_LOW",
                "Minimum Platega amount: {amount}",
            ).format(amount=settings.format_price(settings.PLATEGA_MIN_AMOUNT_KOPEKS))
        )
        return

    if amount_kopeks > settings.PLATEGA_MAX_AMOUNT_KOPEKS:
        await message.answer(
            texts.t(
                "PLATEGA_AMOUNT_TOO_HIGH",
                "Maximum Platega amount: {amount}",
            ).format(amount=settings.format_price(settings.PLATEGA_MAX_AMOUNT_KOPEKS))
        )
        return

    try:
        payment_service = PaymentService(message.bot)
        payment_result = await payment_service.create_platega_payment(
            db=db,
            user_id=db_user.id,
            amount_kopeks=amount_kopeks,
            description=settings.get_balance_payment_description(amount_kopeks),
            language=db_user.language,
            payment_method_code=method_code,
        )
    except Exception as error:
        logger.exception("Platega payment creation failed: %s", error)
        payment_result = None

    if not payment_result or not payment_result.get("redirect_url"):
        await message.answer(
            texts.t(
                "PLATEGA_PAYMENT_ERROR",
                "❌ Could not create Platega payment. Try again later or contact support.",
            )
        )
        await state.clear()
        return

    redirect_url = payment_result.get("redirect_url")
    local_payment_id = payment_result.get("local_payment_id")
    transaction_id = payment_result.get("transaction_id")
    method_title = settings.get_platega_method_display_title(method_code)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        "PLATEGA_PAY_BUTTON",
                        "💳 Pay with {method}",
                    ).format(method=method_title),
                    url=redirect_url,
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                    callback_data=f"check_platega_{local_payment_id}",
                )
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")],
        ]
    )

    instructions_template = texts.t(
        "PLATEGA_PAYMENT_INSTRUCTIONS",
        (
            "💳 <b>Platega payment ({method})</b>\n\n"
            "💰 Amount: {amount}\n"
            "🆔 Transaction ID: {transaction}\n\n"
            "📱 <b>Instructions:</b>\n"
            "1. Tap Pay\n"
            "2. Follow the payment system prompts\n"
            "3. Confirm the transfer\n"
            "4. Funds will be credited automatically\n\n"
            "❓ If you have issues, contact {support}"
        ),
    )

    state_data = await state.get_data()
    prompt_message_id = state_data.get("platega_prompt_message_id")
    prompt_chat_id = state_data.get("platega_prompt_chat_id", message.chat.id)

    try:
        await message.delete()
    except Exception as delete_error:  # pragma: no cover - depends on bot rights
        logger.warning("Failed to delete Platega amount message: %s", delete_error)

    if prompt_message_id:
        try:
            await message.bot.delete_message(prompt_chat_id, prompt_message_id)
        except Exception as delete_error:  # pragma: no cover - diagnostic log
            logger.warning(
                "Failed to delete Platega amount prompt message: %s",
                delete_error,
            )

    invoice_message = await message.answer(
        instructions_template.format(
            method=method_title,
            amount=settings.format_price(amount_kopeks),
            transaction=transaction_id or local_payment_id,
            support=settings.get_support_contact_display_html(),
        ),
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    try:
        from app.services import payment_service as payment_module

        payment = await payment_module.get_platega_payment_by_id(db, local_payment_id)
        if payment:
            payment_metadata = dict(getattr(payment, "metadata_json", {}) or {})
            payment_metadata["invoice_message"] = {
                "chat_id": invoice_message.chat.id,
                "message_id": invoice_message.message_id,
            }
            await payment_module.update_platega_payment(
                db,
                payment=payment,
                metadata=payment_metadata,
            )
    except Exception as error:  # pragma: no cover - diagnostic log
        logger.warning("Failed to persist Platega invoice message data: %s", error)

    await state.update_data(
        platega_invoice_message_id=invoice_message.message_id,
        platega_invoice_chat_id=invoice_message.chat.id,
    )

    await state.clear()


@error_handler
async def check_platega_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession,
):
    try:
        local_payment_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer(
            texts.t(
                "PLATEGA_INVALID_PAYMENT_ID",
                "❌ Invalid payment identifier",
            ),
            show_alert=True,
        )
        return

    payment_service = PaymentService(callback.bot)

    try:
        status_info = await payment_service.get_platega_payment_status(db, local_payment_id)
    except Exception as error:
        logger.exception("Platega status check failed: %s", error)
        await callback.answer(
            texts.t(
                "PLATEGA_STATUS_CHECK_ERROR",
                "⚠️ Failed to check payment status",
            ),
            show_alert=True,
        )
        return

    if not status_info:
        await callback.answer(
            texts.t(
                "PLATEGA_PAYMENT_NOT_FOUND",
                "⚠️ Payment not found",
            ),
            show_alert=True,
        )
        return

    payment = status_info.get("payment")
    status = status_info.get("status")
    is_paid = status_info.get("is_paid")

    language = "ru"
    user = getattr(payment, "user", None)
    if user and getattr(user, "language", None):
        language = user.language

    texts = get_texts(language)

    if is_paid:
        await callback.answer(
            texts.t(
                "PLATEGA_PAYMENT_ALREADY_CONFIRMED",
                "✅ Payment already credited",
            ),
            show_alert=True,
        )
    else:
        await callback.answer(
            texts.t(
                "PLATEGA_PAYMENT_STATUS",
                "Current payment status: {status}",
            ).format(status=status),
            show_alert=True,
        )
