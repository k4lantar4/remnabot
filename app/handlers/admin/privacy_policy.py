import html
import logging
from datetime import datetime

from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.localization.texts import get_texts
from app.services.privacy_policy_service import PrivacyPolicyService
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
    policy = await PrivacyPolicyService.get_policy(
        db,
        db_user.language,
        fallback=False,
    )

    normalized_language = PrivacyPolicyService.normalize_language(db_user.language)
    has_content = bool(policy and policy.content and policy.content.strip())

    description = texts.t(
        "ADMIN_PRIVACY_POLICY_DESCRIPTION",
        "Privacy policy is shown in the \"Info\" section.",
    )

    status_text = texts.t(
        "ADMIN_PRIVACY_POLICY_STATUS_DISABLED",
        "⚠️ Policy display is turned off or text is missing.",
    )
    if policy and policy.is_enabled and has_content:
        status_text = texts.t(
            "ADMIN_PRIVACY_POLICY_STATUS_ENABLED",
            "✅ Policy is active and shown to users.",
        )
    elif policy and policy.is_enabled:
        status_text = texts.t(
            "ADMIN_PRIVACY_POLICY_STATUS_ENABLED_EMPTY",
            "⚠️ Policy is enabled but text is empty — users won't see it.",
        )

    updated_at = _format_timestamp(getattr(policy, "updated_at", None))
    updated_block = ""
    if updated_at:
        updated_block = texts.t(
            "ADMIN_PRIVACY_POLICY_UPDATED_AT",
            "Last updated: {timestamp}",
        ).format(timestamp=updated_at)

    preview_block = texts.t(
        "ADMIN_PRIVACY_POLICY_PREVIEW_EMPTY",
        "Text has not been provided yet.",
    )
    if has_content:
        preview_title = texts.t(
            "ADMIN_PRIVACY_POLICY_PREVIEW_TITLE",
            "<b>Text preview:</b>",
        )
        preview_raw = policy.content.strip()
        preview_trimmed = preview_raw[:400]
        if len(preview_raw) > 400:
            preview_trimmed += "..."
        preview_block = (
            f"{preview_title}\n"
            f"<code>{html.escape(preview_trimmed)}</code>"
        )

    language_block = texts.t(
        "ADMIN_PRIVACY_POLICY_LANGUAGE",
        "Language: <code>{lang}</code>",
    ).format(lang=normalized_language)

    header = texts.t(
        "ADMIN_PRIVACY_POLICY_HEADER",
        "🛡️ <b>Privacy policy</b>",
    )
    actions_prompt = texts.t(
        "ADMIN_PRIVACY_POLICY_ACTION_PROMPT",
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
                "ADMIN_PRIVACY_POLICY_EDIT_BUTTON",
                "✏️ Edit text",
            ),
            callback_data="admin_privacy_policy_edit",
        )
    ])

    if has_content:
        buttons.append([
            types.InlineKeyboardButton(
                text=texts.t(
                    "ADMIN_PRIVACY_POLICY_VIEW_BUTTON",
                    "👀 View current text",
                ),
                callback_data="admin_privacy_policy_view",
            )
        ])

    toggle_text = texts.t(
        "ADMIN_PRIVACY_POLICY_ENABLE_BUTTON",
        "✅ Enable display",
    )
    if policy and policy.is_enabled:
        toggle_text = texts.t(
            "ADMIN_PRIVACY_POLICY_DISABLE_BUTTON",
            "🚫 Disable display",
        )

    buttons.append([
        types.InlineKeyboardButton(
            text=toggle_text,
            callback_data="admin_privacy_policy_toggle",
        )
    ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t(
                "ADMIN_PRIVACY_POLICY_HTML_HELP",
                "ℹ️ HTML help",
            ),
            callback_data="admin_privacy_policy_help",
        )
    ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data="admin_submenu_settings",
        )
    ])

    return overview_text, types.InlineKeyboardMarkup(inline_keyboard=buttons), policy


@admin_required
@error_handler
async def show_privacy_policy_management(
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
async def toggle_privacy_policy(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    updated_policy = await PrivacyPolicyService.toggle_enabled(db, db_user.language)
    logger.info(
        "Admin %s toggled privacy policy display: %s",
        db_user.telegram_id,
        "enabled" if updated_policy.is_enabled else "disabled",
    )
    status_message = (
        texts.t("ADMIN_PRIVACY_POLICY_ENABLED", "✅ Policy enabled")
        if updated_policy.is_enabled
        else texts.t("ADMIN_PRIVACY_POLICY_DISABLED", "🚫 Policy disabled")
    )

    overview_text, markup, _ = await _build_overview(db_user, db)
    await callback.message.edit_text(
        overview_text,
        reply_markup=markup,
    )
    await callback.answer(status_message)


@admin_required
@error_handler
async def start_edit_privacy_policy(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    policy = await PrivacyPolicyService.get_policy(
        db,
        db_user.language,
        fallback=False,
    )

    current_preview = ""
    if policy and policy.content:
        preview = policy.content.strip()[:400]
        if len(policy.content.strip()) > 400:
            preview += "..."
        current_preview = (
            texts.t(
                "ADMIN_PRIVACY_POLICY_CURRENT_PREVIEW",
                "Current text (preview):",
            )
            + f"\n<code>{html.escape(preview)}</code>\n\n"
        )

    prompt = texts.t(
        "ADMIN_PRIVACY_POLICY_EDIT_PROMPT",
        "Send the new privacy policy text. HTML markup is allowed.",
    )

    hint = texts.t(
        "ADMIN_PRIVACY_POLICY_EDIT_HINT",
        "Use /html_help for tag reference.",
    )

    message_text = (
        f"📝 <b>{texts.t('ADMIN_PRIVACY_POLICY_EDIT_TITLE', 'Editing policy')}</b>\n\n"
        f"{current_preview}{prompt}\n\n{hint}"
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_PRIVACY_POLICY_HTML_HELP",
                        "ℹ️ HTML помощь",
                    ),
                    callback_data="admin_privacy_policy_help",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_PRIVACY_POLICY_CANCEL", "❌ Cancel"),
                    callback_data="admin_privacy_policy_cancel",
                )
            ],
        ]
    )

    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await state.set_state(AdminStates.editing_privacy_policy)
    await callback.answer()


@admin_required
@error_handler
async def cancel_edit_privacy_policy(
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
    await callback.answer()


@admin_required
@error_handler
async def process_privacy_policy_edit(
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
                "ADMIN_PRIVACY_POLICY_TOO_LONG",
                "❌ Policy text is too long. Maximum 4000 characters.",
            )
        )
        return

    is_valid, error_message = validate_html_tags(new_text)
    if not is_valid:
        await message.answer(
            texts.t(
                "ADMIN_PRIVACY_POLICY_HTML_ERROR",
                "❌ HTML error: {error}",
            ).format(error=error_message)
        )
        return

    await PrivacyPolicyService.save_policy(db, db_user.language, new_text)
    logger.info(
        "Admin %s updated privacy policy text (%d characters)",
        db_user.telegram_id,
        len(new_text),
    )
    await state.clear()

    success_text = texts.t(
        "ADMIN_PRIVACY_POLICY_SAVED",
        "✅ Privacy policy updated.",
    )

    reply_markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_PRIVACY_POLICY_BACK_BUTTON",
                        "⬅️ Back to policy settings",
                    ),
                    callback_data="admin_privacy_policy",
                )
            ]
        ]
    )

    await message.answer(success_text, reply_markup=reply_markup)


@admin_required
@error_handler
async def view_privacy_policy(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    policy = await PrivacyPolicyService.get_policy(
        db,
        db_user.language,
        fallback=False,
    )

    if not policy or not policy.content or not policy.content.strip():
        await callback.answer(
            texts.t(
                "ADMIN_PRIVACY_POLICY_PREVIEW_EMPTY_ALERT",
                "Policy text has not been provided yet.",
            ),
            show_alert=True,
        )
        return

    content = policy.content.strip()
    truncated = False
    max_length = 3800
    if len(content) > max_length:
        content = content[: max_length - 3] + "..."
        truncated = True

    header = texts.t(
        "ADMIN_PRIVACY_POLICY_VIEW_TITLE",
        "👀 <b>Current policy text</b>",
    )

    note = ""
    if truncated:
        note = texts.t(
            "ADMIN_PRIVACY_POLICY_VIEW_TRUNCATED",
            "\n\n⚠️ Text is truncated for display. Users will see the full version in the menu.",
        )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_PRIVACY_POLICY_BACK_BUTTON",
                        "⬅️ Back to policy settings",
                    ),
                    callback_data="admin_privacy_policy",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_PRIVACY_POLICY_EDIT_BUTTON",
                        "✏️ Edit text",
                    ),
                    callback_data="admin_privacy_policy_edit",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        f"{header}\n\n{content}{note}",
        reply_markup=keyboard,
    )
    await callback.answer()


@admin_required
@error_handler
async def show_privacy_policy_html_help(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    help_text = get_html_help_text()

    current_state = await state.get_state()

    buttons: list[list[types.InlineKeyboardButton]] = []

    if current_state == AdminStates.editing_privacy_policy.state:
        buttons.append([
            types.InlineKeyboardButton(
                text=texts.t(
                    "ADMIN_PRIVACY_POLICY_RETURN_TO_EDIT",
                    "⬅️ Back to editing",
                ),
                callback_data="admin_privacy_policy_edit",
            )
        ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t(
                "ADMIN_PRIVACY_POLICY_BACK_BUTTON",
                "⬅️ К настройкам политики",
            ),
            callback_data="admin_privacy_policy",
        )
    ])

    await callback.message.edit_text(
        help_text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


def register_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(
        show_privacy_policy_management,
        F.data == "admin_privacy_policy",
    )
    dp.callback_query.register(
        toggle_privacy_policy,
        F.data == "admin_privacy_policy_toggle",
    )
    dp.callback_query.register(
        start_edit_privacy_policy,
        F.data == "admin_privacy_policy_edit",
    )
    dp.callback_query.register(
        cancel_edit_privacy_policy,
        F.data == "admin_privacy_policy_cancel",
    )
    dp.callback_query.register(
        view_privacy_policy,
        F.data == "admin_privacy_policy_view",
    )
    dp.callback_query.register(
        show_privacy_policy_html_help,
        F.data == "admin_privacy_policy_help",
    )

    dp.message.register(
        process_privacy_policy_edit,
        AdminStates.editing_privacy_policy,
    )
