"""Configuration management handlers for tenant bots (AC9)."""

import json
from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.crud.bot import get_bot_by_id
from app.localization.texts import get_texts
from app.utils.decorators import error_handler
from app.utils.permissions import admin_required
from app.services.bot_config_service import BotConfigService
from app.states import AdminStates
from .common import logger


# Configuration categories as per AC9
CONFIG_CATEGORIES = {
    "basic": {
        "name": "Basic Settings",
        "icon": "⚙️",
        "keys": [
            "DEFAULT_LANGUAGE",
            "AVAILABLE_LANGUAGES",
            "LANGUAGE_SELECTION_ENABLED",
            "TZ",
            "SKIP_RULES_ACCEPT",
            "SKIP_REFERRAL_CODE",
        ],
    },
    "support": {
        "name": "Support Settings",
        "icon": "💬",
        "keys": [
            "SUPPORT_USERNAME",
            "SUPPORT_MENU_ENABLED",
            "SUPPORT_MODE",
            "TICKET_SLA_HOURS",
        ],
    },
    "notifications": {
        "name": "Notifications",
        "icon": "🔔",
        "keys": [
            "ADMIN_NOTIFICATIONS_ENABLED",
            "ADMIN_NOTIFICATIONS_CHAT_ID",
            "ADMIN_NOTIFICATIONS_TOPIC_ID",
            "REPORTS_ENABLED",
            "REPORTS_CHAT_ID",
            "REPORTS_TOPIC_ID",
            "REPORTS_SEND_TIME",
            "USER_NOTIFICATIONS_ENABLED",
            "TRIAL_WARNING_ENABLED",
            "RETRY_ATTEMPTS",
        ],
    },
    "subscription": {
        "name": "Subscription Settings",
        "icon": "📦",
        "keys": [
            "TRIAL_DURATION_DAYS",
            "TRIAL_TRAFFIC_LIMIT_GB",
            "TRIAL_DEVICE_LIMIT",
            "TRIAL_PAYMENT_ENABLED",
            "DEFAULT_DEVICE_LIMIT",
            "MAX_DEVICES_LIMIT",
            "DEFAULT_TRAFFIC_LIMIT_GB",
            "DEFAULT_TRAFFIC_RESET_STRATEGY",
            "AVAILABLE_SUBSCRIPTION_PERIODS",
        ],
    },
    "pricing": {
        "name": "Pricing Settings",
        "icon": "💰",
        "keys": [
            "PRICE_14_DAYS",
            "PRICE_30_DAYS",
            "PRICE_60_DAYS",
            "PRICE_90_DAYS",
            "PRICE_180_DAYS",
            "PRICE_360_DAYS",
            "TRAFFIC_PACKAGES_CONFIG",
            "PRICE_PER_DEVICE",
        ],
    },
    "ui": {
        "name": "UI/UX Settings",
        "icon": "🎨",
        "keys": [
            "ENABLE_LOGO_MODE",
            "LOGO_FILE",
            "MAIN_MENU_MODE",
            "HIDE_SUBSCRIPTION_LINK",
            "CONNECT_BUTTON_MODE",
            "MINIAPP_CUSTOM_URL",
        ],
    },
    "integrations": {
        "name": "Integrations",
        "icon": "🔌",
        "keys": [
            "SERVER_STATUS_ENABLED",
            "MONITORING_ENABLED",
            "MAINTENANCE_MODE",
        ],
    },
    "advanced": {
        "name": "Advanced Settings",
        "icon": "🔧",
        "keys": [
            "AUTOPAY_ENABLED",
            "REFERRAL_PROGRAM_ENABLED",
            "PROMO_GROUPS_ENABLED",
            "CONTEST_ENABLED",
        ],
    },
}


@admin_required
@error_handler
async def show_bot_configuration_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show configuration management menu with categories (AC9)."""
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

    text = texts.t(
        "ADMIN_TENANT_BOT_CONFIG",
        """🔧 <b>Configuration: {name}</b>

Select a category to manage configurations.""",
    ).format(name=bot.name)

    # Build keyboard with category buttons
    keyboard_buttons = []
    row = []
    for category_key, category_info in CONFIG_CATEGORIES.items():
        button = types.InlineKeyboardButton(
            text=f"{category_info['icon']} {category_info['name']}",
            callback_data=f"admin_tenant_bot_config_{category_key}:{bot_id}",
        )
        row.append(button)
        if len(row) == 2:
            keyboard_buttons.append(row)
            row = []
    if row:
        keyboard_buttons.append(row)

    # Back button
    keyboard_buttons.append(
        [types.InlineKeyboardButton(text=texts.BACK, callback_data=f"admin_tenant_bot_detail:{bot_id}")]
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def show_config_category(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show configuration values for a specific category (AC9)."""
    texts = get_texts(db_user.language)

    try:
        # Parse callback: admin_tenant_bot_config_{category}:{bot_id}
        parts = callback.data.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid callback format")

        category_key = parts[0].replace("admin_tenant_bot_config_", "")
        bot_id = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    if category_key not in CONFIG_CATEGORIES:
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid category"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    category_info = CONFIG_CATEGORIES[category_key]

    # Fetch all config values for this category
    config_values = {}
    for config_key in category_info["keys"]:
        value = await BotConfigService.get_config(db, bot_id, config_key)
        config_values[config_key] = value

    # Build display text
    lines = [
        f"{category_info['icon']} <b>{category_info['name']}: {bot.name}</b>",
        "",
    ]

    for config_key in category_info["keys"]:
        value = config_values.get(config_key)
        display_value = str(value) if value is not None else "Not set"
        if isinstance(value, bool):
            display_value = "✅ Enabled" if value else "❌ Disabled"
        elif isinstance(value, (dict, list)):
            display_value = f"[Complex: {type(value).__name__}]"

        lines.append(f"<b>{config_key}:</b> {display_value}")

    text = "\n".join(lines)

    # Build keyboard with edit buttons
    # Use shorter callback format to avoid Telegram's 64-byte limit
    keyboard_buttons = []
    for config_key in category_info["keys"]:
        # Shortened format: cfg_edit:{bot_id}:{category}:{key}
        # This saves ~22 chars compared to admin_tenant_bot_config_edit:
        callback_data = f"cfg_edit:{bot_id}:{category_key}:{config_key}"

        # Telegram limit is 64 bytes - verify we're under
        callback_bytes = len(callback_data.encode("utf-8"))
        if callback_bytes > 64:
            # This shouldn't happen with current config keys, but handle gracefully
            logger.error(
                f"Callback data too long ({callback_bytes} bytes) for config_key '{config_key}' "
                f"in category '{category_key}'. Telegram limit is 64 bytes. "
                f"Consider using a shorter config_key or index-based approach."
            )
            # Don't truncate - it would break parsing. Instead, skip this button
            # or use an alternative approach. For now, we'll skip to avoid invalid callback_data
            continue

        keyboard_buttons.append([types.InlineKeyboardButton(text=f"✏️ Edit {config_key}", callback_data=callback_data)])

    # Back button
    keyboard_buttons.append(
        [types.InlineKeyboardButton(text=texts.BACK, callback_data=f"admin_tenant_bot_config:{bot_id}")]
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def start_edit_config(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Start editing a configuration value (AC9)."""
    texts = get_texts(db_user.language)

    try:
        # Parse: cfg_edit:{bot_id}:{category}:{config_key}
        # Support both old and new format for backward compatibility
        if callback.data.startswith("admin_tenant_bot_config_edit:"):
            # Old format
            parts = callback.data.replace("admin_tenant_bot_config_edit:", "").split(":")
        elif callback.data.startswith("cfg_edit:"):
            # New shortened format
            parts = callback.data.replace("cfg_edit:", "").split(":")
        else:
            raise ValueError("Invalid callback format")

        if len(parts) != 3:
            raise ValueError("Invalid callback format")

        bot_id = int(parts[0])
        category_key = parts[1]
        config_key = parts[2]
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    if category_key not in CONFIG_CATEGORIES:
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid category"), show_alert=True)
        return

    if config_key not in CONFIG_CATEGORIES[category_key]["keys"]:
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid config key"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    # Get current value
    current_value = await BotConfigService.get_config(db, bot_id, config_key)

    # Store in FSM state
    await state.update_data(
        bot_id=bot_id,
        category_key=category_key,
        config_key=config_key,
    )
    await state.set_state(AdminStates.editing_tenant_config_value)

    # Request new value
    current_display = str(current_value) if current_value is not None else "Not set"
    text = texts.t(
        "ADMIN_TENANT_BOT_CONFIG_EDIT",
        """✏️ <b>Edit Configuration</b>

<b>Bot:</b> {name}
<b>Key:</b> {key}
<b>Current Value:</b> {current}

Please send the new value for this configuration.

For boolean values, send: true or false
For JSON objects, send valid JSON.""",
    ).format(
        name=bot.name,
        key=config_key,
        current=current_display,
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                    callback_data=f"admin_tenant_bot_config_{category_key}:{bot_id}",
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def save_config_value(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Save configuration value from FSM (AC9)."""
    texts = get_texts(db_user.language)

    data = await state.get_data()
    bot_id = data.get("bot_id")
    category_key = data.get("category_key")
    config_key = data.get("config_key")

    if not all([bot_id, category_key, config_key]):
        await message.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request. Please start over."))
        await state.clear()
        return

    # Parse the new value
    new_value_str = message.text.strip()

    # Try to parse as different types
    new_value = None
    try:
        # Try boolean
        if new_value_str.lower() in ("true", "1", "yes", "enabled"):
            new_value = True
        elif new_value_str.lower() in ("false", "0", "no", "disabled"):
            new_value = False
        # Try integer
        elif new_value_str.isdigit() or (new_value_str.startswith("-") and new_value_str[1:].isdigit()):
            new_value = int(new_value_str)
        # Try float
        elif "." in new_value_str and new_value_str.replace(".", "").replace("-", "").isdigit():
            new_value = float(new_value_str)
        # Try JSON
        elif new_value_str.startswith("{") or new_value_str.startswith("["):
            new_value = json.loads(new_value_str)
        # Default to string
        else:
            new_value = new_value_str
    except (ValueError, json.JSONDecodeError):
        new_value = new_value_str  # Fallback to string

    # Save using BotConfigService
    try:
        await BotConfigService.set_config(db, bot_id, config_key, new_value, commit=True)

        # Clear FSM state
        await state.clear()

        # Show success message and return to category view
        bot = await get_bot_by_id(db, bot_id)
        success_text = texts.t(
            "ADMIN_TENANT_BOT_CONFIG_SAVED",
            """✅ <b>Configuration Updated</b>

<b>Key:</b> {key}
<b>New Value:</b> {value}

Returning to category view...""",
        ).format(
            key=config_key,
            value=str(new_value),
        )

        # Send success message with button to view updated category
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_VIEW_CATEGORY", "👁️ View Category"),
                        callback_data=f"admin_tenant_bot_config_{category_key}:{bot_id}",
                    )
                ]
            ]
        )

        await message.answer(success_text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error saving config {config_key} for bot {bot_id}: {e}", exc_info=True)
        await message.answer(texts.t("ADMIN_ERROR", f"❌ Error saving configuration: {str(e)}"))
        await state.clear()
