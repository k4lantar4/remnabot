import html
import logging
from datetime import datetime

from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.localization.texts import get_texts
from app.services.public_offer_service import PublicOfferService
from app.states import AdminStates
from app.utils.decorators import admin_required, error_handler
from app.utils.validators import validate_html_tags, get_html_help_text

logger = logging.getLogger(__name__)


def _format_timestamp(value: datetime | None) -> str:
    if not value:
        return ""
    try:
        return value.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return ""


async def _build_overview(
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    offer = await PublicOfferService.get_offer(
        db,
        db_user.language,
        fallback=False,
    )

    normalized_language = PublicOfferService.normalize_language(db_user.language)
    has_content = bool(offer and offer.content and offer.content.strip())

    description = texts.t(
        "ADMIN_PUBLIC_OFFER_DESCRIPTION",
        "Public offer is shown in the \"Info\" section.",
    )

    status_text = texts.t(
        "ADMIN_PUBLIC_OFFER_STATUS_DISABLED",
        "⚠️ Offer display is turned off or text is missing.",
    )
    if offer and offer.is_enabled and has_content:
        status_text = texts.t(
            "ADMIN_PUBLIC_OFFER_STATUS_ENABLED",
            "✅ Offer is active and shown to users.",
        )
    elif offer and offer.is_enabled:
        status_text = texts.t(
            "ADMIN_PUBLIC_OFFER_STATUS_ENABLED_EMPTY",
            "⚠️ Offer is enabled but text is empty — users won't see it.",
        )

    updated_at = _format_timestamp(getattr(offer, "updated_at", None))
    updated_block = ""
    if updated_at:
        updated_block = texts.t(
            "ADMIN_PUBLIC_OFFER_UPDATED_AT",
            "Last updated: {timestamp}",
        ).format(timestamp=updated_at)

    preview_block = texts.t(
        "ADMIN_PUBLIC_OFFER_PREVIEW_EMPTY",
        "Text has not been provided yet.",
    )
    if has_content:
        preview_title = texts.t(
            "ADMIN_PUBLIC_OFFER_PREVIEW_TITLE",
            "<b>Text preview:</b>",
        )
        preview_raw = offer.content.strip()
        preview_trimmed = preview_raw[:400]
        if len(preview_raw) > 400:
            preview_trimmed += "..."
        preview_block = (
            f"{preview_title}\n"
            f"<code>{html.escape(preview_trimmed)}</code>"
        )

    language_block = texts.t(
        "ADMIN_PUBLIC_OFFER_LANGUAGE",
        "Language: <code>{lang}</code>",
    ).format(lang=normalized_language)

    header = texts.t(
        "ADMIN_PUBLIC_OFFER_HEADER",
        "📄 <b>Public offer</b>",
    )
    actions_prompt = texts.t(
        "ADMIN_PUBLIC_OFFER_ACTION_PROMPT",
        "Choose an action:",
    )

    message_parts = [
        header,
        description,
        language_block,
        status_text,
    ]

    if updated_block:
        message_parts.append(updated_block)

    message_parts.append(preview_block)
    message_parts.append(actions_prompt)

    overview_text = "\n\n".join(part for part in message_parts if part)

    buttons: list[list[types.InlineKeyboardButton]] = []

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t(
                "ADMIN_PUBLIC_OFFER_EDIT_BUTTON",
                "✏️ Edit text",
            ),
            callback_data="admin_public_offer_edit",
        )
    ])

    if has_content:
        buttons.append([
            types.InlineKeyboardButton(
                text=texts.t(
                    "ADMIN_PUBLIC_OFFER_VIEW_BUTTON",
                    "👀 View current text",
                ),
                callback_data="admin_public_offer_view",
            )
        ])

    toggle_text = texts.t(
        "ADMIN_PUBLIC_OFFER_ENABLE_BUTTON",
        "✅ Enable display",
    )
    if offer and offer.is_enabled:
        toggle_text = texts.t(
            "ADMIN_PUBLIC_OFFER_DISABLE_BUTTON",
            "🚫 Disable display",
        )

    buttons.append([
        types.InlineKeyboardButton(
            text=toggle_text,
            callback_data="admin_public_offer_toggle",
        )
    ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t(
                "ADMIN_PUBLIC_OFFER_HTML_HELP",
                "ℹ️ HTML help",
            ),
            callback_data="admin_public_offer_help",
        )
    ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data="admin_submenu_settings",
        )
    ])

    return overview_text, types.InlineKeyboardMarkup(inline_keyboard=buttons), offer


@admin_required
@error_handler
async def show_public_offer_management(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    overview_text, markup, _ = await _build_overview(db_user, db)

    await callback.message.edit_text(
        overview_text,
        reply_markup=markup,
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_public_offer(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    updated_offer = await PublicOfferService.toggle_enabled(db, db_user.language)
    logger.info(
        "Admin %s toggled public offer display: %s",
        db_user.telegram_id,
        "enabled" if updated_offer.is_enabled else "disabled",
    )
    status_message = (
        texts.t("ADMIN_PUBLIC_OFFER_ENABLED", "✅ Offer enabled")
        if updated_offer.is_enabled
        else texts.t("ADMIN_PUBLIC_OFFER_DISABLED", "🚫 Offer disabled")
    )

    overview_text, markup, _ = await _build_overview(db_user, db)
    await callback.message.edit_text(
        overview_text,
        reply_markup=markup,
    )
    await callback.answer(status_message)


@admin_required
@error_handler
async def start_edit_public_offer(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    offer = await PublicOfferService.get_offer(
        db,
        db_user.language,
        fallback=False,
    )

    current_preview = ""
    if offer and offer.content:
        preview = offer.content.strip()[:400]
        if len(offer.content.strip()) > 400:
            preview += "..."
        current_preview = (
            texts.t(
                "ADMIN_PUBLIC_OFFER_CURRENT_PREVIEW",
                "Current text (preview):",
            )
            + f"\n<code>{html.escape(preview)}</code>\n\n"
        )

    prompt = texts.t(
        "ADMIN_PUBLIC_OFFER_EDIT_PROMPT",
        "Send the new public offer text. HTML markup is allowed.",
    )

    hint = texts.t(
        "ADMIN_PUBLIC_OFFER_EDIT_HINT",
        "Use /html_help for tag reference.",
    )

    message_text = (
        f"📝 <b>{texts.t('ADMIN_PUBLIC_OFFER_EDIT_TITLE', 'Editing offer')}</b>\n\n"
        f"{current_preview}{prompt}\n\n{hint}"
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_PUBLIC_OFFER_HTML_HELP",
                        "ℹ️ HTML help",
                    ),
                    callback_data="admin_public_offer_help",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_PUBLIC_OFFER_CANCEL", "❌ Cancel"),
                    callback_data="admin_public_offer_cancel",
                )
            ],
        ]
    )

    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await state.set_state(AdminStates.editing_public_offer)
    await callback.answer()


@admin_required
@error_handler
async def cancel_edit_public_offer(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    await state.clear()
    overview_text, markup, _ = await _build_overview(db_user, db)
    await callback.message.edit_text(
        overview_text,
        reply_markup=markup,
    )
    await callback.answer(
        get_texts(db_user.language).t(
            "ADMIN_PUBLIC_OFFER_EDIT_CANCELLED",
            "Offer editing cancelled.",
        )
    )


@admin_required
@error_handler
async def process_public_offer_edit(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    new_text = message.text or ""

    if len(new_text) > 4000:
        await message.answer(
            texts.t(
                "ADMIN_PUBLIC_OFFER_TOO_LONG",
                "❌ Offer text is too long. Maximum 4000 characters.",
            )
        )
        return

    is_valid, error_message = validate_html_tags(new_text)
    if not is_valid:
        await message.answer(
            texts.t(
                "ADMIN_PUBLIC_OFFER_HTML_ERROR",
                "❌ HTML error: {error}",
            ).format(error=error_message)
        )
        return

    await PublicOfferService.save_offer(db, db_user.language, new_text)
    logger.info(
        "Admin %s updated public offer text (%d characters)",
        db_user.telegram_id,
        len(new_text),
    )
    await state.clear()

    success_text = texts.t(
        "ADMIN_PUBLIC_OFFER_SAVED",
        "✅ Public offer updated.",
    )

    reply_markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_PUBLIC_OFFER_BACK_BUTTON",
                        "⬅️ Back to offer settings",
                    ),
                    callback_data="admin_public_offer",
                )
            ]
        ]
    )

    await message.answer(success_text, reply_markup=reply_markup)


@admin_required
@error_handler
async def view_public_offer(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    offer = await PublicOfferService.get_offer(
        db,
        db_user.language,
        fallback=False,
    )

    if not offer or not offer.content or not offer.content.strip():
        await callback.answer(
            texts.t(
                "ADMIN_PUBLIC_OFFER_PREVIEW_EMPTY_ALERT",
                "Offer text has not been provided yet.",
            ),
            show_alert=True,
        )
        return

    content = offer.content.strip()
    max_length = 3800
    pages = PublicOfferService.split_content_into_pages(
        content,
        max_length=max_length,
    )

    if not pages:
        await callback.answer(
            texts.t(
                "ADMIN_PUBLIC_OFFER_PREVIEW_EMPTY_ALERT",
                "Offer text has not been provided yet.",
            ),
            show_alert=True,
        )
        return

    preview = pages[0]
    truncated = len(pages) > 1

    header = texts.t(
        "ADMIN_PUBLIC_OFFER_VIEW_TITLE",
        "👀 <b>Current offer text</b>",
    )

    note = ""
    if truncated:
        note = texts.t(
            "ADMIN_PUBLIC_OFFER_VIEW_TRUNCATED",
            "\n\n⚠️ Text is truncated for display. Users will see the full version in the menu.",
        )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_PUBLIC_OFFER_BACK_BUTTON",
                        "⬅️ Back to offer settings",
                    ),
                    callback_data="admin_public_offer",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_PUBLIC_OFFER_EDIT_BUTTON",
                        "✏️ Edit text",
                    ),
                    callback_data="admin_public_offer_edit",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        f"{header}\n\n{preview}{note}",
        reply_markup=keyboard,
    )
    await callback.answer()


@admin_required
@error_handler
async def show_public_offer_html_help(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    help_text = get_html_help_text()

    current_state = await state.get_state()

    buttons: list[list[types.InlineKeyboardButton]] = []

    if current_state == AdminStates.editing_public_offer.state:
        buttons.append([
            types.InlineKeyboardButton(
                text=texts.t(
                    "ADMIN_PUBLIC_OFFER_RETURN_TO_EDIT",
                    "⬅️ Back to editing",
                ),
                callback_data="admin_public_offer_edit",
            )
        ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t(
                "ADMIN_PUBLIC_OFFER_BACK_BUTTON",
                "⬅️ Back to offer settings",
            ),
            callback_data="admin_public_offer",
        )
    ])

    await callback.message.edit_text(
        help_text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


def register_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(
        show_public_offer_management,
        F.data == "admin_public_offer",
    )
    dp.callback_query.register(
        toggle_public_offer,
        F.data == "admin_public_offer_toggle",
    )
    dp.callback_query.register(
        start_edit_public_offer,
        F.data == "admin_public_offer_edit",
    )
    dp.callback_query.register(
        cancel_edit_public_offer,
        F.data == "admin_public_offer_cancel",
    )
    dp.callback_query.register(
        view_public_offer,
        F.data == "admin_public_offer_view",
    )
    dp.callback_query.register(
        show_public_offer_html_help,
        F.data == "admin_public_offer_help",
    )

    dp.message.register(
        process_public_offer_edit,
        AdminStates.editing_public_offer,
    )
