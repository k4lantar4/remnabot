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
                text=texts.t("ADMIN_TENANT_BOTS_UPDATE_WEBHOOKS", "🔄 Update All Webhooks"),
                callback_data="admin_tenant_bots_update_webhooks"
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
• Wallet: {wallet}  Toman
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
                text=texts.t("ADMIN_TENANT_BOT_TEST", "🧪 Test Bot Status"),
                callback_data=f"admin_tenant_bot_test:{bot_id}"
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
        
        # Initialize and start the new bot immediately
        try:
            from app.bot import initialize_single_bot, start_bot_polling, setup_bot_webhook
            from app.database.crud.bot import get_bot_by_id
            
            # Get fresh bot config from database
            bot_config = await get_bot_by_id(db, bot.id)
            if bot_config:
                # Initialize the bot
                result = await initialize_single_bot(bot_config)
                if result:
                    bot_instance, dp_instance = result
                    
                    # Start polling if enabled
                    await start_bot_polling(bot.id, bot_instance, dp_instance)
                    
                    # Setup webhook if enabled
                    await setup_bot_webhook(bot.id, bot_instance)
                    
                    logger.info(f"✅ Bot {bot.id} ({bot.name}) initialized and started successfully")
                else:
                    logger.warning(f"⚠️ Bot {bot.id} created but initialization failed")
            else:
                logger.error(f"❌ Bot {bot.id} not found in database after creation")
        except Exception as e:
            logger.error(f"❌ Error initializing new bot {bot.id}: {e}", exc_info=True)
            # Continue - bot is created in DB, can be initialized on restart
        
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
        await callback.answer(texts.t("BOT_ACTIVATED"), show_alert=True)
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
        await callback.answer(texts.t("BOT_DEACTIVATED"), show_alert=True)
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


@admin_required
@error_handler
async def test_bot_status(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Test bot status and connectivity."""
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
    
    await callback.answer(texts.t("TESTING_BOT"), show_alert=True)
    
    from app.bot import active_bots, active_dispatchers, polling_tasks
    from app.config import settings
    from app.webserver import telegram
    
    status_lines = []
    status_lines.append(f"🤖 <b>Bot Status Test</b>\n")
    status_lines.append(f"<b>Name:</b> {bot.name}")
    status_lines.append(f"<b>ID:</b> {bot.id}")
    status_lines.append(f"<b>Token:</b> {bot.telegram_bot_token[:20]}...\n")
    
    # Check if initialized
    is_initialized = bot_id in active_bots
    
    # Try to initialize if not initialized
    if not is_initialized:
        status_lines.append(f"<b>Initialized:</b> ❌ No")
        status_lines.append("\n🔄 <b>Attempting to initialize bot...</b>")
        
        try:
            from app.bot import initialize_single_bot, start_bot_polling, setup_bot_webhook
            
            # Get fresh bot config (get_bot_by_id is already imported at top of file)
            bot_config = await get_bot_by_id(db, bot_id)
            if bot_config and bot_config.is_active:
                result = await initialize_single_bot(bot_config)
                if result:
                    bot_instance, dp_instance = result
                    status_lines.append("✅ <b>Bot initialized successfully!</b>\n")
                    
                    # Start polling if enabled
                    bot_run_mode = settings.get_bot_run_mode()
                    polling_enabled = bot_run_mode in {"polling", "both"}
                    if polling_enabled:
                        await start_bot_polling(bot_id, bot_instance, dp_instance)
                        status_lines.append("✅ <b>Polling started</b>\n")
                    
                    # Setup webhook if enabled
                    telegram_webhook_enabled = bot_run_mode in {"webhook", "both"}
                    if telegram_webhook_enabled:
                        await setup_bot_webhook(bot_id, bot_instance)
                        status_lines.append("✅ <b>Webhook configured</b>\n")
                    
                    is_initialized = True
                else:
                    status_lines.append("❌ <b>Failed to initialize bot</b>\n")
                    status_lines.append("Please check logs for details.\n")
            elif not bot_config:
                status_lines.append("❌ <b>Bot not found in database</b>\n")
            elif not bot_config.is_active:
                status_lines.append("❌ <b>Bot is not active</b>\n")
                status_lines.append("Activate the bot first.\n")
        except Exception as e:
            status_lines.append(f"❌ <b>Error during initialization: {str(e)[:100]}</b>\n")
            logger.error(f"Error initializing bot {bot_id} in test handler: {e}", exc_info=True)
    
    if is_initialized:
        status_lines.append(f"<b>Initialized:</b> ✅ Yes\n")
        bot_instance = active_bots[bot_id]
        dp_instance = active_dispatchers.get(bot_id)
        
        # Test bot connectivity
        try:
            bot_info = await bot_instance.get_me()
            status_lines.append(f"<b>Bot Username:</b> @{bot_info.username}")
            status_lines.append(f"<b>Bot Name:</b> {bot_info.first_name}")
            status_lines.append(f"<b>Connectivity:</b> ✅ Connected")
        except Exception as e:
            status_lines.append(f"<b>Connectivity:</b> ❌ Error: {str(e)[:50]}")
        
        # Check polling
        bot_run_mode = settings.get_bot_run_mode()
        polling_enabled = bot_run_mode in {"polling", "both"}
        if polling_enabled:
            is_polling = bot_id in polling_tasks and not polling_tasks[bot_id].done()
            status_lines.append(f"<b>Polling:</b> {'✅ Running' if is_polling else '❌ Not running'}")
        else:
            status_lines.append(f"<b>Polling:</b> ⏸️ Disabled (mode: {bot_run_mode})")
        
        # Check webhook
        telegram_webhook_enabled = bot_run_mode in {"webhook", "both"}
        if telegram_webhook_enabled:
            try:
                webhook_info = await bot_instance.get_webhook_info()
                if webhook_info.url:
                    status_lines.append(f"<b>Webhook:</b> ✅ Set")
                    status_lines.append(f"<b>Webhook URL:</b> {webhook_info.url}")
                    status_lines.append(f"<b>Pending Updates:</b> {webhook_info.pending_update_count}")
                else:
                    status_lines.append(f"<b>Webhook:</b> ❌ Not set")
            except Exception as e:
                status_lines.append(f"<b>Webhook:</b> ❌ Error: {str(e)[:50]}")
        else:
            status_lines.append(f"<b>Webhook:</b> ⏸️ Disabled (mode: {bot_run_mode})")
        
        # Check webhook registry
        if bot_id in telegram._bot_registry:
            status_lines.append(f"<b>Webhook Registry:</b> ✅ Registered")
        else:
            status_lines.append(f"<b>Webhook Registry:</b> ⚠️ Not registered (may use fallback)")
        
        # Check dispatcher
        if dp_instance:
            status_lines.append(f"<b>Dispatcher:</b> ✅ Available")
        else:
            status_lines.append(f"<b>Dispatcher:</b> ❌ Missing")
        
        # Final status
        status_lines.append("\n" + "="*30)
        status_lines.append("✅ <b>Bot is ready and operational!</b>")
        status_lines.append("="*30)
    else:
        status_lines.append("\n⚠️ <b>Bot initialization failed!</b>")
        status_lines.append("The bot needs to be initialized to work.")
        status_lines.append("Try:")
        status_lines.append("• Restarting the server")
        status_lines.append("• Using 'Update All Webhooks' button")
        status_lines.append("• Checking bot is active in database")
    
    result_text = "\n".join(status_lines)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_VIEW", "👁️ View Bot"),
                callback_data=f"admin_tenant_bot_detail:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_MENU", "🏠 Bots Menu"),
                callback_data="admin_tenant_bots_menu"
            )
        ]
    ])
    
    await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def update_all_webhooks(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Update webhooks for all active bots."""
    texts = get_texts(db_user.language)
    
    from app.bot import active_bots, active_dispatchers
    from app.config import settings
    from urllib.parse import urljoin
    
    # Check if webhook mode is enabled
    bot_run_mode = settings.get_bot_run_mode()
    telegram_webhook_enabled = bot_run_mode in {"webhook", "both"}
    
    if not telegram_webhook_enabled:
        await callback.answer(
            texts.t(
                "ADMIN_TENANT_BOTS_WEBHOOK_DISABLED",
                "❌ Webhook mode is disabled. Set BOT_RUN_MODE=webhook or both"
            ),
            show_alert=True
        )
        return
    
    base_webhook_url = settings.get_telegram_webhook_url()
    if not base_webhook_url:
        await callback.answer(
            texts.t(
                "ADMIN_TENANT_BOTS_WEBHOOK_URL_NOT_SET",
                "❌ WEBHOOK_URL is not set in configuration"
            ),
            show_alert=True
        )
        return
    
    await callback.answer(texts.t("UPDATING_WEBHOOKS"), show_alert=True)
    
    # Get active bots from database
    from app.database.crud.bot import get_active_bots
    active_bot_configs = await get_active_bots(db)
    
    if not active_bot_configs:
        await callback.message.edit_text(
            texts.t(
                "ADMIN_TENANT_BOTS_NO_ACTIVE_BOTS",
                "❌ No active bots found"
            ),
            parse_mode="HTML"
        )
        return
    
    # Get dispatcher to resolve allowed updates
    if active_dispatchers:
        first_dp = list(active_dispatchers.values())[0]
        allowed_updates = first_dp.resolve_used_update_types()
    else:
        allowed_updates = None
    
    results = []
    success_count = 0
    error_count = 0
    
    for bot_config in active_bot_configs:
        bot_id = bot_config.id
        
        # Get bot instance from active_bots registry
        if bot_id not in active_bots:
            results.append(f"❌ Bot {bot_id} ({bot_config.name}): Not initialized")
            error_count += 1
            continue
        
        bot_instance = active_bots[bot_id]
        
        # Construct bot-specific webhook URL
        bot_webhook_url = urljoin(base_webhook_url.rstrip('/') + '/', f'webhook/{bot_id}')
        
        try:
            await bot_instance.set_webhook(
                url=bot_webhook_url,
                secret_token=settings.WEBHOOK_SECRET_TOKEN,
                drop_pending_updates=settings.WEBHOOK_DROP_PENDING_UPDATES,
                allowed_updates=allowed_updates,
            )
            results.append(f"✅ Bot {bot_id} ({bot_config.name}): {bot_webhook_url}")
            success_count += 1
            logger.info(f"✅ Webhook updated for bot {bot_id} ({bot_config.name}): {bot_webhook_url}")
        except Exception as e:
            error_msg = str(e)[:100]  # Limit error message length
            results.append(f"❌ Bot {bot_id} ({bot_config.name}): {error_msg}")
            error_count += 1
            logger.error(f"❌ Failed to update webhook for bot {bot_id} ({bot_config.name}): {e}", exc_info=True)
    
    # Build result message
    result_text = texts.t(
        "ADMIN_TENANT_BOTS_WEBHOOK_UPDATE_RESULT",
        """🔄 <b>Webhook Update Results</b>

✅ Success: {success}
❌ Errors: {errors}

<b>Details:</b>
{details}

<a href="admin_tenant_bots_menu">🔙 Back to Menu</a>"""
    ).format(
        success=success_count,
        errors=error_count,
        details="\n".join(results[:20])  # Limit to 20 results
    )
    
    if len(results) > 20:
        result_text += f"\n\n... and {len(results) - 20} more"
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_MENU", "🔙 Back to Menu"),
                callback_data="admin_tenant_bots_menu"
            )
        ]
    ])
    
    await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode="HTML")
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
    
    dp.callback_query.register(
        update_all_webhooks,
        F.data == "admin_tenant_bots_update_webhooks"
    )
    
    dp.callback_query.register(
        test_bot_status,
        F.data.startswith("admin_tenant_bot_test:")
    )
    
    logger.info("✅ Tenant bots admin handlers registered")



