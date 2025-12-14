import logging
from typing import Optional
from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.database.crud.bot import (
    get_all_bots,
    get_bot_by_id,
    create_bot,
    update_bot,
    activate_bot,
    deactivate_bot,
)
from app.database.crud.tenant_payment_card import (
    get_payment_cards,
    create_payment_card,
    get_payment_card,
    update_payment_card,
    activate_card,
    deactivate_card,
    get_card_statistics,
)
from app.localization.texts import get_texts
from app.utils.decorators import admin_required, error_handler
from app.keyboards.inline import get_back_keyboard
from app.states import AdminStates

logger = logging.getLogger(__name__)


@admin_required
@error_handler
async def show_tenant_bots_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show tenant bots management menu."""
    texts = get_texts(db_user.language)
    
    # Get all bots
    bots = await get_all_bots(db)
    active_count = sum(1 for b in bots if b.is_active)
    
    text = texts.t(
        "ADMIN_TENANT_BOTS_MENU",
        """🤖 <b>Tenant Bots Management</b>

📊 <b>Statistics:</b>
• Total bots: {total}
• Active: {active}
• Inactive: {inactive}

Select action:"""
    ).format(
        total=len(bots),
        active=active_count,
        inactive=len(bots) - active_count
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_LIST", "📋 List Bots"),
                callback_data="admin_tenant_bots_list"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_CREATE", "➕ Create New Bot"),
                callback_data="admin_tenant_bots_create"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.BACK,
                callback_data="admin_panel"
            )
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def list_tenant_bots(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    page: int = 0,
):
    """List all tenant bots with pagination."""
    texts = get_texts(db_user.language)
    
    bots = await get_all_bots(db)
    page_size = 5
    total_pages = (len(bots) + page_size - 1) // page_size
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_bots = bots[start_idx:end_idx]
    
    text = texts.t(
        "ADMIN_TENANT_BOTS_LIST_TITLE",
        """🤖 <b>Tenant Bots</b>

Page {page} of {total_pages}
"""
    ).format(page=page + 1, total_pages=max(1, total_pages))
    
    if not page_bots:
        text += texts.t("ADMIN_TENANT_BOTS_EMPTY", "No bots found.")
    else:
        for bot in page_bots:
            status_icon = "✅" if bot.is_active else "⏸️"
            master_icon = "👑" if bot.is_master else ""
            text += f"\n{status_icon} {master_icon} <b>{bot.name}</b> (ID: {bot.id})\n"
            text += f"   • Card-to-Card: {'✅' if bot.card_to_card_enabled else '❌'}\n"
            text += f"   • Zarinpal: {'✅' if bot.zarinpal_enabled else '❌'}\n"
    
    keyboard_buttons = []
    
    # Bot buttons
    for bot in page_bots:
        keyboard_buttons.append([
            types.InlineKeyboardButton(
                text=f"{'✅' if bot.is_active else '⏸️'} {bot.name}",
                callback_data=f"admin_tenant_bot_detail:{bot.id}"
            )
        ])
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.InlineKeyboardButton(
                text="⬅️ Previous",
                callback_data=f"admin_tenant_bots_list:{page - 1}"
            )
        )
    if end_idx < len(bots):
        nav_buttons.append(
            types.InlineKeyboardButton(
                text="Next ➡️",
                callback_data=f"admin_tenant_bots_list:{page + 1}"
            )
        )
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    
    # Back button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data="admin_tenant_bots_menu"
        )
    ])
    
    # Back button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data="admin_tenant_bots_menu"
        )
    ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def show_bot_detail(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show bot details and management options."""
    texts = get_texts(db_user.language)
    
    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    status_text = "✅ Active" if bot.is_active else "⏸️ Inactive"
    master_text = "👑 Master Bot" if bot.is_master else ""
    
    text = texts.t(
        "ADMIN_TENANT_BOT_DETAIL",
        """🤖 <b>Bot Details</b>

<b>Name:</b> {name}
<b>ID:</b> {id}
<b>Status:</b> {status}
{master}

<b>Settings:</b>
• Card-to-Card: {card_enabled}
• Zarinpal: {zarinpal_enabled}
• Language: {language}
• Support: {support}

<b>Statistics:</b>
• Wallet: {wallet} ₽
• Traffic Consumed: {traffic_consumed} GB
• Traffic Sold: {traffic_sold} GB"""
    ).format(
        name=bot.name,
        id=bot.id,
        status=status_text,
        master=master_text,
        card_enabled="✅ Enabled" if bot.card_to_card_enabled else "❌ Disabled",
        zarinpal_enabled="✅ Enabled" if bot.zarinpal_enabled else "❌ Disabled",
        language=bot.default_language,
        support=bot.support_username or "N/A",
        wallet=f"{bot.wallet_balance_kopeks / 100:,.2f}".replace(',', ' '),
        traffic_consumed=f"{bot.traffic_consumed_bytes / (1024**3):.2f}",
        traffic_sold=f"{bot.traffic_sold_bytes / (1024**3):.2f}",
    )
    
    keyboard_buttons = []
    
    # Action buttons
    if not bot.is_master:
        if bot.is_active:
            keyboard_buttons.append([
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_DEACTIVATE", "⏸️ Deactivate"),
                    callback_data=f"admin_tenant_bot_deactivate:{bot_id}"
                )
            ])
        else:
            keyboard_buttons.append([
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_ACTIVATE", "✅ Activate"),
                    callback_data=f"admin_tenant_bot_activate:{bot_id}"
                )
            ])
    
    keyboard_buttons.extend([
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_SETTINGS", "⚙️ Settings"),
                callback_data=f"admin_tenant_bot_settings:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_PAYMENT_CARDS", "💳 Payment Cards"),
                callback_data=f"admin_tenant_bot_cards:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.BACK,
                callback_data="admin_tenant_bots_list:0"
            )
        ]
    ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def start_create_bot(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
):
    """Start bot creation flow."""
    texts = get_texts(db_user.language)
    
    text = texts.t(
        "ADMIN_TENANT_BOT_CREATE_START",
        """🤖 <b>Create New Tenant Bot</b>

Please enter the bot name:
(Maximum 255 characters)"""
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                callback_data="admin_tenant_bots_menu"
            )
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_bot_name)
    await callback.answer()


@admin_required
@error_handler
async def process_bot_name(
    message: types.Message,
    db_user: User,
    state: FSMContext,
):
    """Process bot name input."""
    texts = get_texts(db_user.language)
    
    bot_name = message.text.strip()
    if not bot_name or len(bot_name) > 255:
        await message.answer(
            texts.t(
                "ADMIN_TENANT_BOT_NAME_INVALID",
                "❌ Invalid bot name. Please enter a name (max 255 characters)."
            )
        )
        return
    
    await state.update_data(bot_name=bot_name)
    
    text = texts.t(
        "ADMIN_TENANT_BOT_CREATE_TOKEN",
        """✅ Bot name: <b>{name}</b>

Now please enter the Telegram Bot Token:
(Get it from @BotFather)"""
    ).format(name=bot_name)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                callback_data="admin_tenant_bots_menu"
            )
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_bot_token)


@admin_required
@error_handler
async def process_bot_token(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Process bot token and create bot."""
    texts = get_texts(db_user.language)
    
    token = message.text.strip()
    if not token or ":" not in token:
        await message.answer(
            texts.t(
                "ADMIN_TENANT_BOT_TOKEN_INVALID",
                "❌ Invalid token format. Please enter a valid Telegram Bot Token."
            )
        )
        return
    
    data = await state.get_data()
    bot_name = data.get("bot_name")
    
    if not bot_name:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_ERROR", "❌ Error: Bot name not found. Please start over."),
            reply_markup=get_back_keyboard(db_user.language)
        )
        await state.clear()
        return
    
    try:
        # Check if token already exists
        from app.database.crud.bot import get_bot_by_token
        existing = await get_bot_by_token(db, token)
        if existing:
            await message.answer(
                texts.t(
                    "ADMIN_TENANT_BOT_TOKEN_EXISTS",
                    "❌ A bot with this token already exists."
                ),
                reply_markup=get_back_keyboard(db_user.language)
            )
            await state.clear()
            return
        
        # Create bot
        bot, api_token = await create_bot(
            db=db,
            name=bot_name,
            telegram_bot_token=token,
            is_master=False,
            is_active=True,
            created_by=db_user.id
        )
        
        text = texts.t(
            "ADMIN_TENANT_BOT_CREATED",
            """✅ <b>Bot Created Successfully!</b>

<b>Name:</b> {name}
<b>ID:</b> {id}
<b>Status:</b> ✅ Active

<b>API Token:</b>
<code>{api_token}</code>

⚠️ <b>IMPORTANT:</b> Save this API token! It will not be shown again."""
        ).format(
            name=bot.name,
            id=bot.id,
            api_token=api_token
        )
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_VIEW", "👁️ View Bot"),
                    callback_data=f"admin_tenant_bot_detail:{bot.id}"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOTS_MENU", "🏠 Bots Menu"),
                    callback_data="admin_tenant_bots_menu"
                )
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error creating bot: {e}", exc_info=True)
        await message.answer(
            texts.t(
                "ADMIN_TENANT_BOT_CREATE_ERROR",
                "❌ Error creating bot. Please try again."
            ),
            reply_markup=get_back_keyboard(db_user.language)
        )
        await state.clear()


@admin_required
@error_handler
async def activate_tenant_bot(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Activate a tenant bot."""
    texts = get_texts(db_user.language)
    
    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    if bot.is_active:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_ALREADY_ACTIVE", "Bot is already active"),
            show_alert=True
        )
        return
    
    success = await activate_bot(db, bot_id)
    if success:
        await callback.answer("✅ Bot activated")
        # Refresh detail view
        await show_bot_detail(callback, db_user, db)
    else:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_ACTIVATE_ERROR", "❌ Failed to activate bot"),
            show_alert=True
        )


@admin_required
@error_handler
async def deactivate_tenant_bot(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Deactivate a tenant bot."""
    texts = get_texts(db_user.language)
    
    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    if bot.is_master:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_CANNOT_DEACTIVATE_MASTER", "❌ Cannot deactivate master bot"),
            show_alert=True
        )
        return
    
    if not bot.is_active:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_ALREADY_INACTIVE", "Bot is already inactive"),
            show_alert=True
        )
        return
    
    success = await deactivate_bot(db, bot_id)
    if success:
        await callback.answer("⏸️ Bot deactivated")
        # Refresh detail view
        await show_bot_detail(callback, db_user, db)
    else:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_DEACTIVATE_ERROR", "❌ Failed to deactivate bot"),
            show_alert=True
        )


@admin_required
@error_handler
async def show_bot_payment_cards(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show payment cards for a bot."""
    texts = get_texts(db_user.language)
    
    try:
        parts = callback.data.split(":")
        bot_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    cards = await get_payment_cards(db, bot_id, active_only=False)
    page_size = 5
    total_pages = (len(cards) + page_size - 1) // page_size
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_cards = cards[start_idx:end_idx]
    
    text = texts.t(
        "ADMIN_TENANT_BOT_CARDS_TITLE",
        """💳 <b>Payment Cards</b>
Bot: <b>{bot_name}</b>

Page {page} of {total_pages}
"""
    ).format(
        bot_name=bot.name,
        page=page + 1,
        total_pages=max(1, total_pages)
    )
    
    if not page_cards:
        text += texts.t("ADMIN_TENANT_BOT_CARDS_EMPTY", "No payment cards found.")
    else:
        for card in page_cards:
            status_icon = "✅" if card.is_active else "❌"
            masked_number = f"****{card.card_number[-4:]}" if len(card.card_number) > 4 else "****"
            text += f"\n{status_icon} <b>{masked_number}</b>\n"
            text += f"   • Holder: {card.card_holder_name}\n"
            text += f"   • Strategy: {card.rotation_strategy}\n"
            text += f"   • Uses: {card.success_count + card.failure_count}\n"
    
    keyboard_buttons = []
    
    # Add card button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_TENANT_BOT_CARDS_ADD", "➕ Add Card"),
            callback_data=f"admin_tenant_bot_card_add:{bot_id}"
        )
    ])
    
    # Card buttons
    for card in page_cards:
        keyboard_buttons.append([
            types.InlineKeyboardButton(
                text=f"{'✅' if card.is_active else '❌'} Card {card.id}",
                callback_data=f"admin_tenant_bot_card_detail:{card.id}"
            )
        ])
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.InlineKeyboardButton(
                text="⬅️ Previous",
                callback_data=f"admin_tenant_bot_cards:{bot_id}:{page - 1}"
            )
        )
    if end_idx < len(cards):
        nav_buttons.append(
            types.InlineKeyboardButton(
                text="Next ➡️",
                callback_data=f"admin_tenant_bot_cards:{bot_id}:{page + 1}"
            )
        )
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    
    # Back button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data=f"admin_tenant_bot_detail:{bot_id}"
        )
    ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


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
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    text = texts.t(
        "ADMIN_TENANT_BOT_SETTINGS",
        """⚙️ <b>Bot Settings</b>

Bot: <b>{name}</b> (ID: {id})

<b>Current Settings:</b>
• Card-to-Card: {card_status}
• Zarinpal: {zarinpal_status}
• Default Language: {language}
• Support: {support}

Select setting to change:"""
    ).format(
        name=bot.name,
        id=bot.id,
        card_status="✅ Enabled" if bot.card_to_card_enabled else "❌ Disabled",
        zarinpal_status="✅ Enabled" if bot.zarinpal_enabled else "❌ Disabled",
        language=bot.default_language,
        support=bot.support_username or "Not set"
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_TOGGLE_CARD", "💳 Toggle Card-to-Card"),
                callback_data=f"admin_tenant_bot_toggle_card:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_TOGGLE_ZARINPAL", "💳 Toggle Zarinpal"),
                callback_data=f"admin_tenant_bot_toggle_zarinpal:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.BACK,
                callback_data=f"admin_tenant_bot_detail:{bot_id}"
            )
        ]
    ])
    
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
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    new_value = not bot.card_to_card_enabled
    updated_bot = await update_bot(db, bot_id, card_to_card_enabled=new_value)
    
    if updated_bot:
        status_text = "enabled" if new_value else "disabled"
        await callback.answer(f"✅ Card-to-card {status_text}")
        await show_bot_settings(callback, db_user, db)
    else:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_UPDATE_ERROR", "❌ Failed to update"),
            show_alert=True
        )


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
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    new_value = not bot.zarinpal_enabled
    updated_bot = await update_bot(db, bot_id, zarinpal_enabled=new_value)
    
    if updated_bot:
        status_text = "enabled" if new_value else "disabled"
        await callback.answer(f"✅ Zarinpal {status_text}")
        await show_bot_settings(callback, db_user, db)
    else:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_UPDATE_ERROR", "❌ Failed to update"),
            show_alert=True
        )
    
    # Back button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data=f"admin_tenant_bot_detail:{bot_id}"
        )
    ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


def register_handlers(dp: Dispatcher) -> None:
    """Register tenant bots handlers."""
    dp.callback_query.register(
        show_tenant_bots_menu,
        F.data == "admin_tenant_bots_menu"
    )
    
    dp.callback_query.register(
        list_tenant_bots,
        F.data.startswith("admin_tenant_bots_list")
    )
    
    dp.callback_query.register(
        show_bot_detail,
        F.data.startswith("admin_tenant_bot_detail:")
    )
    
    dp.callback_query.register(
        start_create_bot,
        F.data == "admin_tenant_bots_create"
    )
    
    dp.message.register(
        process_bot_name,
        StateFilter(AdminStates.waiting_for_bot_name)
    )
    
    dp.message.register(
        process_bot_token,
        StateFilter(AdminStates.waiting_for_bot_token)
    )
    
    dp.callback_query.register(
        activate_tenant_bot,
        F.data.startswith("admin_tenant_bot_activate:")
    )
    
    dp.callback_query.register(
        deactivate_tenant_bot,
        F.data.startswith("admin_tenant_bot_deactivate:")
    )
    
    dp.callback_query.register(
        show_bot_payment_cards,
        F.data.startswith("admin_tenant_bot_cards:")
    )
    
    dp.callback_query.register(
        show_bot_settings,
        F.data.startswith("admin_tenant_bot_settings:")
    )
    
    dp.callback_query.register(
        toggle_card_to_card,
        F.data.startswith("admin_tenant_bot_toggle_card:")
    )
    
    dp.callback_query.register(
        toggle_zarinpal,
        F.data.startswith("admin_tenant_bot_toggle_zarinpal:")
    )
    
    logger.info("✅ Tenant bots admin handlers registered")



