import html
import logging
from datetime import datetime
from typing import Any, Optional

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.database import AsyncSessionLocal
from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.services.payment_service import PaymentService
from app.utils.decorators import error_handler
from app.states import BalanceStates

logger = logging.getLogger(__name__)


def _get_available_pal24_methods() -> list[str]:
    methods: list[str] = []
    if settings.is_pal24_sbp_button_visible():
        methods.append("sbp")
    if settings.is_pal24_card_button_visible():
        methods.append("card")
    if not methods:
        methods.append("sbp")
    return methods


async def _send_pal24_payment_message(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    payment_method: str,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)

    try:
        payment_service = PaymentService(message.bot)
        payment_result = await payment_service.create_pal24_payment(
            db=db,
            user_id=db_user.id,
            amount_kopeks=amount_kopeks,
            description=settings.get_balance_payment_description(amount_kopeks),
            language=db_user.language,
            payment_method=payment_method,
        )

        if not payment_result:
            await message.answer(
                texts.t(
                    "PAL24_PAYMENT_ERROR",
                    "❌ Error creating PayPalych payment. Try again later or contact support.",
                )
            )
            await state.clear()
            return

        sbp_url = (
            payment_result.get("sbp_url")
            or payment_result.get("transfer_url")
        )
        card_url = payment_result.get("card_url")
        fallback_url = (
            payment_result.get("link_page_url")
            or payment_result.get("link_url")
        )

        if not (sbp_url or card_url or fallback_url):
            await message.answer(
                texts.t(
                    "PAL24_PAYMENT_ERROR",
                    "❌ Error creating PayPalych payment. Try again later or contact support.",
                )
            )
            await state.clear()
            return

        if not sbp_url:
            sbp_url = fallback_url

        bill_id = payment_result.get("bill_id")
        local_payment_id = payment_result.get("local_payment_id")

        pay_buttons: list[list[types.InlineKeyboardButton]] = []
        steps: list[str] = []
        step_counter = 1

        default_sbp_text = texts.t(
            "PAL24_SBP_PAY_BUTTON",
            "🏦 Pay via PayPalych (SBP)",
        )
        sbp_button_text = settings.get_pal24_sbp_button_text(default_sbp_text)

        if sbp_url and settings.is_pal24_sbp_button_visible():
            pay_buttons.append(
                [
                    types.InlineKeyboardButton(
                        text=sbp_button_text,
                        url=sbp_url,
                    )
                ]
            )
            steps.append(
                texts.t(
                    "PAL24_INSTRUCTION_BUTTON",
                    "{step}. Tap the “{button}” button",
                ).format(step=step_counter, button=html.escape(sbp_button_text))
            )
            step_counter += 1

        default_card_text = texts.t(
            "PAL24_CARD_PAY_BUTTON",
            "💳 Pay by bank card (PayPalych)",
        )
        card_button_text = settings.get_pal24_card_button_text(default_card_text)

        if card_url and card_url != sbp_url and settings.is_pal24_card_button_visible():
            pay_buttons.append(
                [
                    types.InlineKeyboardButton(
                        text=card_button_text,
                        url=card_url,
                    )
                ]
            )
            steps.append(
                texts.t(
                    "PAL24_INSTRUCTION_BUTTON",
                    "{step}. Tap the “{button}” button",
                ).format(step=step_counter, button=html.escape(card_button_text))
            )
            step_counter += 1

        if not pay_buttons and fallback_url and settings.is_pal24_sbp_button_visible():
            pay_buttons.append(
                [
                    types.InlineKeyboardButton(
                        text=sbp_button_text,
                        url=fallback_url,
                    )
                ]
            )
            steps.append(
                texts.t(
                    "PAL24_INSTRUCTION_BUTTON",
                    "{step}. Tap the “{button}” button",
                ).format(step=step_counter, button=html.escape(sbp_button_text))
            )
            step_counter += 1

        follow_template = texts.t(
            "PAL24_INSTRUCTION_FOLLOW",
            "{step}. Follow the payment system prompts",
        )
        steps.append(follow_template.format(step=step_counter))
        step_counter += 1

        confirm_template = texts.t(
            "PAL24_INSTRUCTION_CONFIRM",
            "{step}. Confirm the transfer",
        )
        steps.append(confirm_template.format(step=step_counter))
        step_counter += 1

        success_template = texts.t(
            "PAL24_INSTRUCTION_COMPLETE",
            "{step}. Funds will be credited automatically",
        )
        steps.append(success_template.format(step=step_counter))

        message_template = texts.t(
            "PAL24_PAYMENT_INSTRUCTIONS",
            (
                "🏦 <b>PayPalych payment</b>\n\n"
                "💰 Amount: {amount}\n"
                "🆔 Invoice ID: {bill_id}\n\n"
                "📱 <b>Instructions:</b>\n{steps}\n\n"
                "❓ If you have issues, contact {support}"
            ),
        )

        keyboard_rows = pay_buttons + [
            [
                types.InlineKeyboardButton(
                    text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                    callback_data=f"check_pal24_{local_payment_id}",
                )
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")],
        ]

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        message_text = message_template.format(
            amount=settings.format_price(amount_kopeks),
            bill_id=bill_id,
            steps="\n".join(steps),
            support=settings.get_support_contact_display_html(),
        )

        invoice_message = await message.answer(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        try:
            from app.services import payment_service as payment_module

            payment = await payment_module.get_pal24_payment_by_id(db, local_payment_id)
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
            logger.warning("Could not save PayPalych invoice message: %s", error)

        await state.update_data(
            pal24_invoice_message_id=invoice_message.message_id,
            pal24_invoice_chat_id=invoice_message.chat.id,
        )

        await state.clear()

        logger.info(
            "Created PayPalych invoice for user %s: %s₽, ID: %s, method: %s",
            db_user.telegram_id,
            amount_kopeks / 100,
            bill_id,
            payment_method,
        )

    except Exception as error:
        logger.error(f"Error creating PayPalych payment: {error}")
        await message.answer(
            texts.t(
                "PAL24_PAYMENT_ERROR",
                "❌ Error creating PayPalych payment. Try again later or contact support.",
            )
        )
        await state.clear()

@error_handler
async def start_pal24_payment(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
):
    texts = get_texts(db_user.language)

    if not settings.is_pal24_enabled():
        await callback.answer(
            texts.t(
                "PAL24_UNAVAILABLE",
                "❌ PayPalych payments are temporarily unavailable",
            ),
            show_alert=True,
        )
        return

    # Build message text based on available payment methods
    if settings.is_pal24_sbp_button_visible() and settings.is_pal24_card_button_visible():
        payment_methods_text = texts.t(
            "PAL24_METHODS_SBP_AND_CARD",
            "SBP and bank card",
        )
    elif settings.is_pal24_sbp_button_visible():
        payment_methods_text = texts.t("PAL24_METHODS_SBP", "SBP")
    elif settings.is_pal24_card_button_visible():
        payment_methods_text = texts.t("PAL24_METHODS_CARD", "bank card")
    else:
        # Если обе кнопки отключены, используем общий текст
        payment_methods_text = texts.t("PAL24_METHODS_GENERIC", "available methods")

    message_text = texts.t(
        "PAL24_TOPUP_PROMPT",
        (
            f"🏦 <b>PayPalych payment ({payment_methods_text})</b>\n\n"
            "Enter a top-up amount from 100 to 1,000,000 ₽.\n"
            f"Payment is processed via PayPalych ({payment_methods_text})."
        ),
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
        payment_method="pal24",
        pal24_prompt_message_id=callback.message.message_id,
        pal24_prompt_chat_id=callback.message.chat.id,
    )
    await callback.answer()


@error_handler
async def process_pal24_payment_amount(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    state: FSMContext,
):
    texts = get_texts(db_user.language)

    if not settings.is_pal24_enabled():
        await message.answer(
            texts.t(
                "PAL24_UNAVAILABLE",
                "❌ PayPalych payments are temporarily unavailable",
            )
        )
        return

    if amount_kopeks < settings.PAL24_MIN_AMOUNT_KOPEKS:
        min_rubles = settings.PAL24_MIN_AMOUNT_KOPEKS / 100
        await message.answer(
            texts.t(
                "PAL24_MIN_AMOUNT",
                "❌ Minimum amount for PayPalych payment: {amount:.0f} ₽",
            ).format(amount=min_rubles)
        )
        return

    if amount_kopeks > settings.PAL24_MAX_AMOUNT_KOPEKS:
        max_rubles = settings.PAL24_MAX_AMOUNT_KOPEKS / 100
        await message.answer(
            texts.t(
                "PAL24_MAX_AMOUNT",
                "❌ Maximum amount for PayPalych payment: {amount:,.0f} ₽",
            ).format(amount=max_rubles).replace(',', ' ')
        )
        return

    available_methods = _get_available_pal24_methods()

    state_data = await state.get_data()
    prompt_message_id = state_data.get("pal24_prompt_message_id")
    prompt_chat_id = state_data.get("pal24_prompt_chat_id", message.chat.id)

    try:
        await message.delete()
    except Exception as delete_error:  # pragma: no cover - depends on bot rights
        logger.warning(
            "Failed to delete PayPalych amount message: %s",
            delete_error,
        )

    if prompt_message_id:
        try:
            await message.bot.delete_message(prompt_chat_id, prompt_message_id)
        except Exception as delete_error:  # pragma: no cover - diagnostic
            logger.warning(
                "Failed to delete PayPalych prompt message: %s",
                delete_error,
            )

    if len(available_methods) == 1:
        await _send_pal24_payment_message(
            message,
            db_user,
            db,
            amount_kopeks,
            available_methods[0],
            state,
        )
        return

    await state.update_data(pal24_amount_kopeks=amount_kopeks)
    await state.set_state(BalanceStates.waiting_for_pal24_method)

    method_buttons: list[list[types.InlineKeyboardButton]] = []
    if "sbp" in available_methods:
        method_buttons.append(
            [
                types.InlineKeyboardButton(
                    text=settings.get_pal24_sbp_button_text(
                        texts.t("PAL24_SBP_PAY_BUTTON", "🏦 Pay via PayPalych (SBP)")
                    ),
                    callback_data="pal24_method_sbp",
                )
            ]
        )
    if "card" in available_methods:
        method_buttons.append(
            [
                types.InlineKeyboardButton(
                    text=settings.get_pal24_card_button_text(
                        texts.t("PAL24_CARD_PAY_BUTTON", "💳 Pay by bank card (PayPalych)")
                    ),
                    callback_data="pal24_method_card",
                )
            ]
        )

    method_buttons.append([types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")])

    await message.answer(
        texts.t(
            "PAL24_SELECT_PAYMENT_METHOD",
            "Select a PayPalych payment method:",
        ),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=method_buttons),
    )


@error_handler
async def handle_pal24_method_selection(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
):
    data = await state.get_data()
    amount_kopeks = data.get("pal24_amount_kopeks")
    if not amount_kopeks:
        texts = get_texts(db_user.language)
        await callback.answer(
            texts.t(
                "PAL24_PAYMENT_ERROR",
                "❌ Error creating PayPalych payment. Try again later or contact support.",
            ),
            show_alert=True,
        )
        await state.clear()
        return

    method = "sbp" if callback.data.endswith("_sbp") else "card"

    await callback.answer()

    async with AsyncSessionLocal() as db:
        await _send_pal24_payment_message(
            callback.message,
            db_user,
            db,
            int(amount_kopeks),
            method,
            state,
        )


@error_handler
async def check_pal24_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession,
):
    try:
        local_payment_id = int(callback.data.split('_')[-1])
        payment_service = PaymentService(callback.bot)
        status_info = await payment_service.get_pal24_payment_status(db, local_payment_id)

        if not status_info:
            texts = get_texts(settings.DEFAULT_LANGUAGE)
            await callback.answer(
                texts.t("PAL24_PAYMENT_NOT_FOUND", "❌ Payment not found"),
                show_alert=True,
            )
            return

        payment = status_info["payment"]

        status_labels = {
            "NEW": ("⏳", "PAL24_STATUS_NEW"),
            "PROCESS": ("⌛", "PAL24_STATUS_PROCESS"),
            "SUCCESS": ("✅", "PAL24_STATUS_SUCCESS"),
            "FAIL": ("❌", "PAL24_STATUS_FAIL"),
            "UNDERPAID": ("⚠️", "PAL24_STATUS_UNDERPAID"),
            "OVERPAID": ("⚠️", "PAL24_STATUS_OVERPAID"),
        }

        emoji, status_key = status_labels.get(payment.status, ("❓", "PAL24_STATUS_UNKNOWN"))
        db_user = getattr(callback, "db_user", None)
        texts = get_texts(db_user.language if db_user else settings.DEFAULT_LANGUAGE)
        status_text = texts.t(
            status_key,
            {
                "PAL24_STATUS_NEW": "Awaiting payment",
                "PAL24_STATUS_PROCESS": "Processing",
                "PAL24_STATUS_SUCCESS": "Paid",
                "PAL24_STATUS_FAIL": "Canceled",
                "PAL24_STATUS_UNDERPAID": "Underpaid",
                "PAL24_STATUS_OVERPAID": "Overpaid",
                "PAL24_STATUS_UNKNOWN": "Unknown",
            }.get(status_key, "Unknown"),
        )

        metadata = payment.metadata_json or {}
        links_meta = metadata.get("links") if isinstance(metadata, dict) else None
        if not isinstance(links_meta, dict):
            links_meta = {}

        links_info = status_info.get("links") or {}

        def _extract_link(source: Any, keys: tuple[str, ...]) -> Optional[str]:
            stack: list[Any] = [source]
            while stack:
                current = stack.pop()
                if isinstance(current, dict):
                    for key in keys:
                        value = current.get(key)
                        if value:
                            return str(value)
                    stack.extend(current.values())
                elif isinstance(current, list):
                    stack.extend(current)
            return None

        raw_response = metadata.get("raw_response") if isinstance(metadata, dict) else None
        remote_data = status_info.get("remote_data")
        transfer_keys = (
            "transfer_url",
            "transferUrl",
            "transfer_link",
            "transferLink",
            "transfer",
            "sbp_url",
            "sbpUrl",
            "sbp_link",
            "sbpLink",
        )
        card_keys = (
            "link_url",
            "linkUrl",
            "link",
            "card_url",
            "cardUrl",
            "card_link",
            "cardLink",
            "payment_url",
            "paymentUrl",
            "url",
        )

        extra_sbp_link = (
            _extract_link(raw_response, transfer_keys)
            if raw_response
            else None
        )
        if not extra_sbp_link and remote_data:
            extra_sbp_link = _extract_link(remote_data, transfer_keys)

        extra_card_link = (
            _extract_link(raw_response, card_keys)
            if raw_response
            else None
        )
        if not extra_card_link and remote_data:
            extra_card_link = _extract_link(remote_data, card_keys)

        sbp_link = (
            links_info.get("sbp")
            or links_meta.get("sbp")
            or status_info.get("sbp_url")
            or extra_sbp_link
            or payment.link_url
        )
        card_link = (
            links_info.get("card")
            or links_meta.get("card")
            or status_info.get("card_url")
            or extra_card_link
        )

        if not card_link and payment.link_page_url and payment.link_page_url != sbp_link:
            card_link = payment.link_page_url

        message_lines = [
            texts.t("PAL24_STATUS_TITLE", "🏦 PayPalych payment status:"),
            "",
            texts.t("PAL24_STATUS_BILL_ID", "🆔 Invoice ID: {bill_id}").format(
                bill_id=payment.bill_id
            ),
            texts.t("PAL24_STATUS_AMOUNT", "💰 Amount: {amount}").format(
                amount=settings.format_price(payment.amount_kopeks)
            ),
            texts.t("PAL24_STATUS_STATE", "📊 Status: {emoji} {status}").format(
                emoji=emoji, status=status_text
            ),
            texts.t("PAL24_STATUS_CREATED_AT", "📅 Created: {date}").format(
                date=payment.created_at.strftime('%d.%m.%Y %H:%M')
            ),
        ]

        if payment.is_paid:
            message_lines.append("")
            message_lines.append(
                texts.t(
                    "PAL24_STATUS_PAID",
                    "✅ Payment completed successfully! Funds are on the balance.",
                )
            )
        elif payment.status in {"NEW", "PROCESS"}:
            message_lines.append("")
            message_lines.append(
                texts.t(
                    "PAL24_STATUS_PENDING",
                    "⏳ Payment is not finished yet. Pay the invoice and check status later.",
                )
            )
            if sbp_link:
                message_lines.append("")
                message_lines.append(
                    texts.t("PAL24_STATUS_SBP_LINK", "🏦 SBP: {link}").format(link=sbp_link)
                )
            if card_link and card_link != sbp_link:
                message_lines.append(
                    texts.t("PAL24_STATUS_CARD_LINK", "💳 Bank card: {link}").format(
                        link=card_link
                    )
                )
        elif payment.status in {"FAIL", "UNDERPAID", "OVERPAID"}:
            message_lines.append("")
            message_lines.append(
                texts.t(
                    "PAL24_STATUS_FAILED",
                    "❌ Payment not completed correctly. Contact {support}",
                ).format(support=settings.get_support_contact_display())
            )

        pay_rows: list[list[types.InlineKeyboardButton]] = []

        if not payment.is_paid and payment.status in {"NEW", "PROCESS"}:
            default_sbp_text = texts.t(
                "PAL24_SBP_PAY_BUTTON",
                "🏦 Pay via PayPalych (SBP)",
            )
            sbp_button_text = settings.get_pal24_sbp_button_text(default_sbp_text)

            if sbp_link and settings.is_pal24_sbp_button_visible():
                pay_rows.append(
                    [
                        types.InlineKeyboardButton(
                            text=sbp_button_text,
                            url=sbp_link,
                        )
                    ]
                )

            default_card_text = texts.t(
                "PAL24_CARD_PAY_BUTTON",
                "💳 Pay by bank card (PayPalych)",
            )
            card_button_text = settings.get_pal24_card_button_text(default_card_text)

            if card_link and settings.is_pal24_card_button_visible():
                if not pay_rows or pay_rows[-1][0].url != card_link:
                    pay_rows.append(
                        [
                            types.InlineKeyboardButton(
                                text=card_button_text,
                                url=card_link,
                            )
                        ]
                    )

        keyboard_rows = pay_rows + [
            [
                types.InlineKeyboardButton(
                    text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                    callback_data=f"check_pal24_{local_payment_id}",
                )
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="balance_topup")],
        ]

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        await callback.answer()
        try:
            await callback.message.edit_text(
                "\n".join(message_lines),
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except TelegramBadRequest as error:
            if "message is not modified" in str(error).lower():
                await callback.answer(
                    texts.t("CHECK_STATUS_NO_CHANGES", "Status has not changed")
                )
            else:
                raise

    except Exception as e:
        logger.error(f"Error checking PayPalych status: {e}")
        texts = get_texts(settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("PAL24_STATUS_ERROR", "❌ Error checking status"),
            show_alert=True,
        )