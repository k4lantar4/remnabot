"""Settings management handlers for tenant bots."""

from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.crud.bot import get_bot_by_id, update_bot
from app.localization.texts import get_texts
from app.utils.decorators import error_handler, admin_required
from app.keyboards.inline import get_back_keyboard
from app.states import AdminStates
from app.services.bot_config_service import BotConfigService
from .common import logger


@admin_required
@error_handler
async def show_bot_settings(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show bot settings management."""
    texts = get_texts(db_user.language)

    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    # Fetch configs using BotConfigService
    card_to_card_enabled = await BotConfigService.is_feature_enabled(db, bot_id, "card_to_card")
    zarinpal_enabled = await BotConfigService.is_feature_enabled(db, bot_id, "zarinpal")
    default_language = await BotConfigService.get_config(db, bot_id, "DEFAULT_LANGUAGE", "fa")
    support_username = await BotConfigService.get_config(db, bot_id, "SUPPORT_USERNAME")
    admin_notifications_chat_id = await BotConfigService.get_config(db, bot_id, "ADMIN_NOTIFICATIONS_CHAT_ID")

    # Format notifications display
    notifications_display = "✅ Configured" if admin_notifications_chat_id else "❌ Not set"

    text = texts.t(
        "ADMIN_TENANT_BOT_SETTINGS",
        """⚙️ <b>Bot Settings</b>

Bot: <b>{name}</b> (ID: {id})

<b>Current Settings:</b>
• Name: {name}
• Bot Token: {token_preview}
• Default Language: {language}
• Support Username: {support}
• Notifications: {notifications}

<b>Feature Flags:</b>
• Card-to-Card: {card_status}
• Zarinpal: {zarinpal_status}

Select setting to edit:""",
    ).format(
        name=bot.name,
        id=bot.id,
        token_preview=f"{bot.telegram_bot_token[:20]}..." if bot.telegram_bot_token else "Not set",
        language=default_language,
        support=support_username or "Not set",
        notifications=notifications_display,
        card_status="✅ Enabled" if card_to_card_enabled else "❌ Disabled",
        zarinpal_status="✅ Enabled" if zarinpal_enabled else "❌ Disabled",
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_EDIT_NAME", "✏️ Edit Name"),
                    callback_data=f"admin_tenant_bot_edit_name:{bot_id}",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_EDIT_LANGUAGE", "🌐 Edit Language"),
                    callback_data=f"admin_tenant_bot_edit_language:{bot_id}",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_EDIT_SUPPORT", "💬 Edit Support"),
                    callback_data=f"admin_tenant_bot_edit_support:{bot_id}",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_EDIT_NOTIFICATIONS", "🔔 Edit Notifications"),
                    callback_data=f"admin_tenant_bot_edit_notifications:{bot_id}",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_TOGGLE_CARD", "💳 Toggle Card-to-Card"),
                    callback_data=f"admin_tenant_bot_toggle_card:{bot_id}",
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_TOGGLE_ZARINPAL", "💳 Toggle Zarinpal"),
                    callback_data=f"admin_tenant_bot_toggle_zarinpal:{bot_id}",
                ),
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data=f"admin_tenant_bot_detail:{bot_id}")],
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def toggle_card_to_card(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Toggle card-to-card payment for a bot."""
    texts = get_texts(db_user.language)

    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    # Get current value and toggle using BotConfigService
    current_value = await BotConfigService.is_feature_enabled(db, bot_id, "card_to_card")
    new_value = not current_value
    await BotConfigService.set_feature_enabled(db, bot_id, "card_to_card", new_value)

    status_text = "enabled" if new_value else "disabled"
    await callback.answer(f"✅ Card-to-card {status_text}")
    await show_bot_settings(callback, db_user, db)


@admin_required
@error_handler
async def toggle_zarinpal(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Toggle Zarinpal payment for a bot."""
    texts = get_texts(db_user.language)

    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    # Get current value and toggle using BotConfigService
    current_value = await BotConfigService.is_feature_enabled(db, bot_id, "zarinpal")
    new_value = not current_value
    await BotConfigService.set_feature_enabled(db, bot_id, "zarinpal", new_value)

    status_text = "enabled" if new_value else "disabled"
    await callback.answer(f"✅ Zarinpal {status_text}")

    # Refresh settings view
    await show_bot_settings(callback, db_user, db)


@admin_required
@error_handler
async def start_edit_bot_name(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Start editing bot name."""
    texts = get_texts(db_user.language)

    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    await state.update_data(bot_id=bot_id)
    await state.set_state(AdminStates.editing_tenant_bot_name)

    text = texts.t(
        "ADMIN_TENANT_BOT_EDIT_NAME_PROMPT",
        """✏️ <b>Edit Bot Name</b>

Current name: <b>{current_name}</b>

Please enter the new bot name:
(Maximum 255 characters)

To cancel, send /cancel""",
    ).format(current_name=bot.name)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"), callback_data=f"admin_tenant_bot_settings:{bot_id}"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def process_edit_bot_name(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Process bot name edit."""
    texts = get_texts(db_user.language)

    data = await state.get_data()
    bot_id = data.get("bot_id")

    if not bot_id:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_ERROR", "❌ Error: Bot ID not found. Please start over."),
            reply_markup=get_back_keyboard(db_user.language),
        )
        await state.clear()
        return

    bot_name = message.text.strip()
    if not bot_name or len(bot_name) > 255:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_NAME_INVALID", "❌ Invalid bot name. Please enter a name (max 255 characters).")
        )
        return

    # Update bot name (auto-commits with default commit=True)
    updated_bot = await update_bot(db, bot_id, name=bot_name)
    if updated_bot:
        await message.answer(texts.t("ADMIN_TENANT_BOT_NAME_UPDATED", "✅ Bot name updated successfully!"))
    else:
        await message.answer(texts.t("ADMIN_TENANT_BOT_UPDATE_ERROR", "❌ Failed to update bot name."))

    await state.clear()

    # Send success message with button to return to settings
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_VIEW_SETTINGS", "⚙️ View Settings"),
                    callback_data=f"admin_tenant_bot_settings:{bot_id}",
                )
            ]
        ]
    )
    await message.answer(
        texts.t("ADMIN_TENANT_BOT_RETURN_TO_SETTINGS", "Click below to return to settings:"), reply_markup=keyboard
    )


@admin_required
@error_handler
async def start_edit_bot_language(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Start editing bot default language."""
    texts = get_texts(db_user.language)

    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    current_language = await BotConfigService.get_config(db, bot_id, "DEFAULT_LANGUAGE", "fa")

    await state.update_data(bot_id=bot_id)
    await state.set_state(AdminStates.editing_tenant_bot_language)

    text = texts.t(
        "ADMIN_TENANT_BOT_EDIT_LANGUAGE_PROMPT",
        """🌐 <b>Edit Default Language</b>

Current language: <b>{current_language}</b>

Please enter the new language code (e.g., 'fa', 'en', 'ru'):
(Common codes: fa, en, ru, ar)

To cancel, send /cancel""",
    ).format(current_language=current_language)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"), callback_data=f"admin_tenant_bot_settings:{bot_id}"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def process_edit_bot_language(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Process bot language edit."""
    texts = get_texts(db_user.language)

    data = await state.get_data()
    bot_id = data.get("bot_id")

    if not bot_id:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_ERROR", "❌ Error: Bot ID not found. Please start over."),
            reply_markup=get_back_keyboard(db_user.language),
        )
        await state.clear()
        return

    language = message.text.strip().lower()
    if not language or len(language) > 5:
        await message.answer(
            texts.t(
                "ADMIN_TENANT_BOT_LANGUAGE_INVALID",
                "❌ Invalid language code. Please enter a valid language code (e.g., 'fa', 'en', 'ru').",
            )
        )
        return

    # Update language using BotConfigService (auto-commits with default commit=True)
    await BotConfigService.set_config(db, bot_id, "DEFAULT_LANGUAGE", language)

    await message.answer(texts.t("ADMIN_TENANT_BOT_LANGUAGE_UPDATED", "✅ Default language updated successfully!"))
    await state.clear()

    # Send success message with button to return to settings
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_VIEW_SETTINGS", "⚙️ View Settings"),
                    callback_data=f"admin_tenant_bot_settings:{bot_id}",
                )
            ]
        ]
    )
    await message.answer(
        texts.t("ADMIN_TENANT_BOT_RETURN_TO_SETTINGS", "Click below to return to settings:"), reply_markup=keyboard
    )


@admin_required
@error_handler
async def start_edit_bot_support(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Start editing bot support username."""
    texts = get_texts(db_user.language)

    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    current_support = await BotConfigService.get_config(db, bot_id, "SUPPORT_USERNAME")

    await state.update_data(bot_id=bot_id)
    await state.set_state(AdminStates.editing_tenant_bot_support)

    text = texts.t(
        "ADMIN_TENANT_BOT_EDIT_SUPPORT_PROMPT",
        """💬 <b>Edit Support Username</b>

Current support: <b>{current_support}</b>

Please enter the new support username (without @):
(Leave empty to remove support username)

To cancel, send /cancel""",
    ).format(current_support=current_support or "Not set")

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"), callback_data=f"admin_tenant_bot_settings:{bot_id}"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def process_edit_bot_support(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Process bot support username edit."""
    texts = get_texts(db_user.language)

    data = await state.get_data()
    bot_id = data.get("bot_id")

    if not bot_id:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_ERROR", "❌ Error: Bot ID not found. Please start over."),
            reply_markup=get_back_keyboard(db_user.language),
        )
        await state.clear()
        return

    support_username = message.text.strip()
    # Remove @ if present
    if support_username.startswith("@"):
        support_username = support_username[1:]

    # If empty, set to None to remove
    if not support_username:
        support_username = None

    # Update support username using BotConfigService (auto-commits with default commit=True)
    await BotConfigService.set_config(db, bot_id, "SUPPORT_USERNAME", support_username)

    if support_username:
        await message.answer(texts.t("ADMIN_TENANT_BOT_SUPPORT_UPDATED", "✅ Support username updated successfully!"))
    else:
        await message.answer(texts.t("ADMIN_TENANT_BOT_SUPPORT_REMOVED", "✅ Support username removed."))

    await state.clear()

    # Send success message with button to return to settings
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_VIEW_SETTINGS", "⚙️ View Settings"),
                    callback_data=f"admin_tenant_bot_settings:{bot_id}",
                )
            ]
        ]
    )
    await message.answer(
        texts.t("ADMIN_TENANT_BOT_RETURN_TO_SETTINGS", "Click below to return to settings:"), reply_markup=keyboard
    )


@admin_required
@error_handler
async def start_edit_bot_notifications(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Start editing bot notifications chat ID."""
    texts = get_texts(db_user.language)

    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    current_chat_id = await BotConfigService.get_config(db, bot_id, "ADMIN_NOTIFICATIONS_CHAT_ID")

    await state.update_data(bot_id=bot_id)
    await state.set_state(AdminStates.editing_tenant_bot_notifications)

    text = texts.t(
        "ADMIN_TENANT_BOT_EDIT_NOTIFICATIONS_PROMPT",
        """🔔 <b>Edit Notifications Chat ID</b>

Current chat ID: <b>{current_chat_id}</b>

Please enter the new Telegram chat ID for admin notifications:
(Enter a negative number for groups, positive for channels)

To remove, send 'none' or '0'
To cancel, send /cancel""",
    ).format(current_chat_id=current_chat_id or "Not set")

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"), callback_data=f"admin_tenant_bot_settings:{bot_id}"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def process_edit_bot_notifications(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Process bot notifications chat ID edit."""
    texts = get_texts(db_user.language)

    data = await state.get_data()
    bot_id = data.get("bot_id")

    if not bot_id:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_ERROR", "❌ Error: Bot ID not found. Please start over."),
            reply_markup=get_back_keyboard(db_user.language),
        )
        await state.clear()
        return

    chat_id_input = message.text.strip().lower()

    # Handle removal
    if chat_id_input in ("none", "0", ""):
        chat_id = None
    else:
        try:
            chat_id = int(chat_id_input)
        except ValueError:
            await message.answer(
                texts.t(
                    "ADMIN_TENANT_BOT_NOTIFICATIONS_INVALID",
                    "❌ Invalid chat ID. Please enter a valid number, or 'none' to remove.",
                )
            )
            return

    # Update notifications chat ID using BotConfigService (auto-commits with default commit=True)
    await BotConfigService.set_config(db, bot_id, "ADMIN_NOTIFICATIONS_CHAT_ID", chat_id)

    if chat_id:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_NOTIFICATIONS_UPDATED", "✅ Notifications chat ID updated successfully!")
        )
    else:
        await message.answer(texts.t("ADMIN_TENANT_BOT_NOTIFICATIONS_REMOVED", "✅ Notifications chat ID removed."))

    await state.clear()

    # Send success message with button to return to settings
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_VIEW_SETTINGS", "⚙️ View Settings"),
                    callback_data=f"admin_tenant_bot_settings:{bot_id}",
                )
            ]
        ]
    )
    await message.answer(
        texts.t("ADMIN_TENANT_BOT_RETURN_TO_SETTINGS", "Click below to return to settings:"), reply_markup=keyboard
    )
