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
from app.utils.decorators import error_handler
from app.utils.permissions import admin_required
from app.keyboards.inline import get_back_keyboard
from app.states import AdminStates
from app.services.bot_config_service import BotConfigService
from app.database.models import Transaction, TransactionType, User, Subscription, SubscriptionStatus, Bot
from sqlalchemy import select, func, and_
from sqlalchemy import text as sql_text
from app.keyboards.admin import get_admin_pagination_keyboard

logger = logging.getLogger(__name__)


@admin_required
@error_handler
async def show_tenant_bots_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show tenant bots management menu with overview statistics."""
    texts = get_texts(db_user.language)
    
    # Query matches AC1 specification exactly
    # Using FILTER for efficient aggregation
    stats_query = sql_text("""
        SELECT 
            COUNT(*) FILTER (WHERE is_master = FALSE) as total_bots,
            COUNT(*) FILTER (WHERE is_master = FALSE AND is_active = TRUE) as active_bots,
            COUNT(*) FILTER (WHERE is_master = FALSE AND is_active = FALSE) as inactive_bots,
            (SELECT COUNT(*) FROM users WHERE bot_id IN (SELECT id FROM bots WHERE is_master = FALSE)) as total_users,
            (SELECT COALESCE(SUM(amount_toman), 0) FROM transactions WHERE bot_id IN (SELECT id FROM bots WHERE is_master = FALSE) AND type = 'deposit' AND is_completed = TRUE) as total_revenue
        FROM bots
    """)
    
    stats_result = await db.execute(stats_query)
    stats_row = stats_result.fetchone()
    
    if stats_row:
        total_bots = stats_row[0] or 0
        active_bots = stats_row[1] or 0
        inactive_bots = stats_row[2] or 0
        total_users = stats_row[3] or 0
        total_revenue = stats_row[4] or 0
    else:
        total_bots = 0
        active_bots = 0
        inactive_bots = 0
        total_users = 0
        total_revenue = 0
    
    text = texts.t(
        "ADMIN_TENANT_BOTS_MENU",
        """🤖 <b>Tenant Bots Management</b>

📊 <b>Statistics:</b>
• Total bots: {total}
• Active: {active}
• Inactive: {inactive}
• Total users: {users}
• Total revenue: {revenue} Toman

Select action:"""
    ).format(
        total=total_bots,
        active=active_bots,
        inactive=inactive_bots,
        users=total_users,
        revenue=f"{total_revenue / 100:,.0f}".replace(',', ' ')
    )
    
    # AC1: Navigation buttons - List Bots, Create Bot, Statistics, Settings
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_LIST", "📋 List Bots"),
                callback_data="admin_tenant_bots_list"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_CREATE", "➕ Create Bot"),
                callback_data="admin_tenant_bots_create"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_STATISTICS", "📊 Statistics"),
                callback_data="admin_tenant_bots_stats"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_SETTINGS", "⚙️ Settings"),
                callback_data="admin_tenant_bots_settings"
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
    page: int = 1
):
    """List all tenant bots with pagination, showing user count, revenue, and plan."""
    # Cache language value before any potential rollback to avoid lazy loading issues
    user_language = db_user.language
    texts = get_texts(user_language)
    
    # Parse page from callback if not provided
    if page == 1 and ":" in callback.data:
        try:
            page = int(callback.data.split(":")[1]) + 1  # Convert 0-based to 1-based
        except (ValueError, IndexError):
            page = 1
    elif page == 1 and "_page_" in callback.data:
        # Support standard pagination pattern: admin_tenant_bots_list_page_{page}
        try:
            page = int(callback.data.split("_page_")[1])
        except (ValueError, IndexError):
            page = 1
    
    # Ensure page is valid
    if page < 1:
        page = 1
    
    page_size = 5
    offset = (page - 1) * page_size
    
    # Optimized query with JOINs (matches story spec exactly)
    # Use raw SQL with sql_text() for tenant_subscriptions since models don't exist yet
    try:
        # Query matches story specification: AC2 Database Query
        # Note: b.* in spec is represented by selecting needed Bot columns
        # GROUP BY matches spec: b.id, ts.plan_tier_id, tsp.display_name
        query_text = sql_text("""
            SELECT 
                b.id, b.name, b.is_active, b.created_at,
                COUNT(DISTINCT u.id) as user_count,
                COALESCE(SUM(t.amount_toman), 0) as revenue,
                ts.plan_tier_id,
                tsp.display_name as plan_name
            FROM bots b
            LEFT JOIN users u ON u.bot_id = b.id
            LEFT JOIN transactions t ON t.bot_id = b.id 
                AND t.type = 'deposit' 
                AND t.is_completed = TRUE
            LEFT JOIN tenant_subscriptions ts ON ts.bot_id = b.id 
                AND ts.status = 'active'
            LEFT JOIN tenant_subscription_plans tsp ON tsp.id = ts.plan_tier_id
            WHERE b.is_master = FALSE
            GROUP BY b.id, ts.plan_tier_id, tsp.display_name
            ORDER BY b.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        
        result = await db.execute(query_text, {"limit": page_size, "offset": offset})
        raw_rows = result.fetchall()
        
        # Convert to Bot objects and format
        # Row structure: (b.id, b.name, b.is_active, b.created_at, user_count, revenue, plan_tier_id, plan_name)
        rows = []
        for row in raw_rows:
            bot = await get_bot_by_id(db, row[0])
            if bot:
                rows.append((bot, row[4] or 0, row[5] or 0, row[7] or None))
        
    except Exception as e:
        # Fallback: if tables don't exist, use simplified query
        # Rollback the failed transaction before trying fallback
        await db.rollback()
        logger.warning(f"Failed to use optimized query with tenant_subscriptions: {e}. Using fallback.")
        query = (
            select(
                Bot,
                func.count(func.distinct(User.id)).label('user_count'),
                func.coalesce(func.sum(Transaction.amount_toman), 0).label('revenue')
            )
            .select_from(Bot)
            .outerjoin(User, User.bot_id == Bot.id)
            .outerjoin(
                Transaction,
                and_(
                    Transaction.bot_id == Bot.id,
                    Transaction.type == TransactionType.DEPOSIT.value,
                    Transaction.is_completed == True
                )
            )
            .where(Bot.is_master == False)
            .group_by(Bot.id)
            .order_by(Bot.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        
        result = await db.execute(query)
        query_rows = result.all()
        # Add None for plan_name
        rows = [(row[0], row[1], row[2], None) for row in query_rows]
    
    # Get total count for pagination
    count_query = select(func.count(Bot.id)).where(Bot.is_master == False)
    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar() or 0
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    
    # Format text (match other admin lists pattern)
    text = texts.t(
        "ADMIN_TENANT_BOTS_LIST_TITLE",
        "🤖 <b>Tenant Bots</b> (page {page}/{total})"
    ).format(page=page, total=total_pages) + "\n\n"
    
    # Initialize keyboard to avoid UnboundLocalError when rows is empty
    keyboard = []
    
    if not rows:
        text += texts.t("ADMIN_TENANT_BOTS_EMPTY", "No tenant bots found.")
    else:
        text += texts.t("ADMIN_TENANT_BOTS_LIST_HINT", "Click on a bot to manage:") + "\n\n"
        for row in rows:
            bot = row[0]  # Bot object
            user_count = row[1] or 0
            revenue = (row[2] or 0) / 100  # Convert from kopeks to toman
            plan_name = row[3] if len(row) > 3 and row[3] else "N/A"  # plan_name from query
            
            status_icon = "✅" if bot.is_active else "⏸️"
            
            # Format bot info (match users list pattern)
            button_text = f"{status_icon} {bot.name} (ID: {bot.id})"
            if len(button_text) > 50:
                button_text = f"{status_icon} {bot.name[:20]}... (ID: {bot.id})"
            
            # Add stats to text (not button - matches users pattern)
            text += f"{status_icon} <b>{bot.name}</b> (ID: {bot.id})\n"
            text += f"   • Users: {user_count} | Revenue: {revenue:,.0f} Toman | Plan: {plan_name}\n\n"
            
            keyboard.append([
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"admin_tenant_bot_detail:{bot.id}"
                )
            ])
    
    # Use standard pagination keyboard (matches other handlers)
    pagination_keyboard = get_admin_pagination_keyboard(
        current_page=page,
        total_pages=total_pages,
        callback_prefix="admin_tenant_bots_list",
        back_callback="admin_tenant_bots_menu",
        language=user_language
    )
    
    # Combine keyboard with pagination
    final_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=keyboard + pagination_keyboard.inline_keyboard
    )
    
    await callback.message.edit_text(text, reply_markup=final_keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def handle_tenant_bots_list_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Handle pagination for tenant bots list."""
    try:
        page = int(callback.data.split("_page_")[1])
        await list_tenant_bots(callback, db_user, db, page=page)
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing page number: {e}")
        await list_tenant_bots(callback, db_user, db, page=1)


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
    
    # Fetch configs using BotConfigService
    card_to_card_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'card_to_card')
    zarinpal_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'zarinpal')
    default_language = await BotConfigService.get_config(db, bot_id, 'DEFAULT_LANGUAGE', 'fa')
    support_username = await BotConfigService.get_config(db, bot_id, 'SUPPORT_USERNAME')
    
    # Calculate statistics
    # User count
    user_count_result = await db.execute(
        select(func.count(User.id))
        .where(User.bot_id == bot_id)
    )
    user_count = user_count_result.scalar() or 0
    
    # Active subscriptions count
    active_subs_result = await db.execute(
        select(func.count(Subscription.id))
        .where(
            and_(
                Subscription.bot_id == bot_id,
                Subscription.status == SubscriptionStatus.ACTIVE.value
            )
        )
    )
    active_subscriptions = active_subs_result.scalar() or 0
    
    # Monthly revenue (current month) - matches AC3 spec: date_trunc('month', CURRENT_DATE)
    monthly_revenue_query = sql_text("""
        SELECT COALESCE(SUM(amount_toman), 0) 
        FROM transactions 
        WHERE bot_id = :bot_id 
          AND type = 'deposit' 
          AND is_completed = TRUE
          AND created_at >= date_trunc('month', CURRENT_DATE)
    """)
    monthly_revenue_result = await db.execute(monthly_revenue_query, {"bot_id": bot_id})
    monthly_revenue = monthly_revenue_result.scalar() or 0
    
    text = texts.t(
        "ADMIN_TENANT_BOT_DETAIL",
        """🤖 <b>Bot Details</b>

<b>Name:</b> {name}
<b>ID:</b> {id}
<b>Status:</b> {status}
{master}

<b>Quick Stats:</b>
• Users: {user_count}
• Active Subscriptions: {active_subs}
• Monthly Revenue: {monthly_revenue} Toman
• Traffic Sold: {traffic_sold} GB

<b>Current Settings:</b>
• Card-to-Card: {card_enabled}
• Zarinpal: {zarinpal_enabled}
• Language: {language}
• Support: {support}

<b>Wallet & Traffic:</b>
• Wallet: {wallet} Toman
• Traffic Consumed: {traffic_consumed} GB"""
    ).format(
        name=bot.name,
        id=bot.id,
        status=status_text,
        master=master_text,
        user_count=user_count,
        active_subs=active_subscriptions,
        monthly_revenue=f"{monthly_revenue / 100:,.0f}".replace(',', ' '),
        traffic_sold=f"{bot.traffic_sold_bytes / (1024**3):.2f}",
        card_enabled="✅ Enabled" if card_to_card_enabled else "❌ Disabled",
        zarinpal_enabled="✅ Enabled" if zarinpal_enabled else "❌ Disabled",
        language=default_language,
        support=support_username or "N/A",
        wallet=f"{bot.wallet_balance_toman / 100:,.2f}".replace(',', ' '),
        traffic_consumed=f"{bot.traffic_consumed_bytes / (1024**3):.2f}",
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
    
    # Add all sub-menu navigation options (AC3)
    keyboard_buttons.extend([
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_STATISTICS", "📊 Statistics"),
                callback_data=f"admin_tenant_bot_stats:{bot_id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_SETTINGS", "⚙️ General Settings"),
                callback_data=f"admin_tenant_bot_settings:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_FEATURES", "🎛️ Feature Flags"),
                callback_data=f"admin_tenant_bot_features:{bot_id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_PAYMENTS", "💳 Payment Methods"),
                callback_data=f"admin_tenant_bot_payments:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_PLANS", "📦 Subscription Plans"),
                callback_data=f"admin_tenant_bot_plans:{bot_id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_CONFIG", "🔧 Configuration"),
                callback_data=f"admin_tenant_bot_config:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_ANALYTICS", "📈 Analytics"),
                callback_data=f"admin_tenant_bot_analytics:{bot_id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_TEST", "🧪 Test Bot"),
                callback_data=f"admin_tenant_bot_test:{bot_id}"
            )
        ]
    ])
    
    # Delete bot button (only for tenant bots)
    if not bot.is_master:
        keyboard_buttons.append([
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_DELETE", "🗑️ Delete Bot"),
                callback_data=f"admin_tenant_bot_delete:{bot_id}"
            )
        ])
    
    # Back button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data="admin_tenant_bots_list"
        )
    ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def start_create_bot(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
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
    await state.set_state(AdminStates.creating_tenant_bot_name)
    await callback.answer()


@admin_required
@error_handler
async def process_bot_name(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
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
    await state.set_state(AdminStates.creating_tenant_bot_token)


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
    
    # Fetch configs using BotConfigService
    card_to_card_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'card_to_card')
    zarinpal_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'zarinpal')
    default_language = await BotConfigService.get_config(db, bot_id, 'DEFAULT_LANGUAGE', 'fa')
    support_username = await BotConfigService.get_config(db, bot_id, 'SUPPORT_USERNAME')
    admin_notifications_chat_id = await BotConfigService.get_config(db, bot_id, 'ADMIN_NOTIFICATIONS_CHAT_ID')
    
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

Select setting to edit:"""
    ).format(
        name=bot.name,
        id=bot.id,
        token_preview=f"{bot.telegram_bot_token[:20]}..." if bot.telegram_bot_token else "Not set",
        language=default_language,
        support=support_username or "Not set",
        notifications=notifications_display,
        card_status="✅ Enabled" if card_to_card_enabled else "❌ Disabled",
        zarinpal_status="✅ Enabled" if zarinpal_enabled else "❌ Disabled"
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_EDIT_NAME", "✏️ Edit Name"),
                callback_data=f"admin_tenant_bot_edit_name:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_EDIT_LANGUAGE", "🌐 Edit Language"),
                callback_data=f"admin_tenant_bot_edit_language:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_EDIT_SUPPORT", "💬 Edit Support"),
                callback_data=f"admin_tenant_bot_edit_support:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_EDIT_NOTIFICATIONS", "🔔 Edit Notifications"),
                callback_data=f"admin_tenant_bot_edit_notifications:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_TOGGLE_CARD", "💳 Toggle Card-to-Card"),
                callback_data=f"admin_tenant_bot_toggle_card:{bot_id}"
            ),
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
    
    # Get current value and toggle using BotConfigService
    current_value = await BotConfigService.is_feature_enabled(db, bot_id, 'card_to_card')
    new_value = not current_value
    await BotConfigService.set_feature_enabled(db, bot_id, 'card_to_card', new_value)
    
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
    
    # Get current value and toggle using BotConfigService
    current_value = await BotConfigService.is_feature_enabled(db, bot_id, 'zarinpal')
    new_value = not current_value
    await BotConfigService.set_feature_enabled(db, bot_id, 'zarinpal', new_value)
    
    status_text = "enabled" if new_value else "disabled"
    await callback.answer(f"✅ Zarinpal {status_text}")
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
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(AdminStates.editing_tenant_bot_name)
    
    text = texts.t(
        "ADMIN_TENANT_BOT_EDIT_NAME_PROMPT",
        """✏️ <b>Edit Bot Name</b>

Current name: <b>{current_name}</b>

Please enter the new bot name:
(Maximum 255 characters)

To cancel, send /cancel"""
    ).format(current_name=bot.name)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                callback_data=f"admin_tenant_bot_settings:{bot_id}"
            )
        ]
    ])
    
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
            reply_markup=get_back_keyboard(db_user.language)
        )
        await state.clear()
        return
    
    bot_name = message.text.strip()
    if not bot_name or len(bot_name) > 255:
        await message.answer(
            texts.t(
                "ADMIN_TENANT_BOT_NAME_INVALID",
                "❌ Invalid bot name. Please enter a name (max 255 characters)."
            )
        )
        return
    
    # Update bot name
    success = await update_bot(db, bot_id, name=bot_name)
    if success:
        await db.commit()
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_NAME_UPDATED", "✅ Bot name updated successfully!")
        )
    else:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_UPDATE_ERROR", "❌ Failed to update bot name.")
        )
    
    await state.clear()
    
    # Send success message with button to return to settings
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_VIEW_SETTINGS", "⚙️ View Settings"),
                callback_data=f"admin_tenant_bot_settings:{bot_id}"
            )
        ]
    ])
    await message.answer(
        texts.t("ADMIN_TENANT_BOT_RETURN_TO_SETTINGS", "Click below to return to settings:"),
        reply_markup=keyboard
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
    
    current_language = await BotConfigService.get_config(db, bot_id, 'DEFAULT_LANGUAGE', 'fa')
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(AdminStates.editing_tenant_bot_language)
    
    text = texts.t(
        "ADMIN_TENANT_BOT_EDIT_LANGUAGE_PROMPT",
        """🌐 <b>Edit Default Language</b>

Current language: <b>{current_language}</b>

Please enter the new language code (e.g., 'fa', 'en', 'ru'):
(Common codes: fa, en, ru, ar)

To cancel, send /cancel"""
    ).format(current_language=current_language)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                callback_data=f"admin_tenant_bot_settings:{bot_id}"
            )
        ]
    ])
    
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
            reply_markup=get_back_keyboard(db_user.language)
        )
        await state.clear()
        return
    
    language = message.text.strip().lower()
    if not language or len(language) > 5:
        await message.answer(
            texts.t(
                "ADMIN_TENANT_BOT_LANGUAGE_INVALID",
                "❌ Invalid language code. Please enter a valid language code (e.g., 'fa', 'en', 'ru')."
            )
        )
        return
    
    # Update language using BotConfigService
    await BotConfigService.set_config(db, bot_id, 'DEFAULT_LANGUAGE', language)
    await db.commit()
    
    await message.answer(
        texts.t("ADMIN_TENANT_BOT_LANGUAGE_UPDATED", "✅ Default language updated successfully!")
    )
    await state.clear()
    
    # Send success message with button to return to settings
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_VIEW_SETTINGS", "⚙️ View Settings"),
                callback_data=f"admin_tenant_bot_settings:{bot_id}"
            )
        ]
    ])
    await message.answer(
        texts.t("ADMIN_TENANT_BOT_RETURN_TO_SETTINGS", "Click below to return to settings:"),
        reply_markup=keyboard
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
    
    current_support = await BotConfigService.get_config(db, bot_id, 'SUPPORT_USERNAME')
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(AdminStates.editing_tenant_bot_support)
    
    text = texts.t(
        "ADMIN_TENANT_BOT_EDIT_SUPPORT_PROMPT",
        """💬 <b>Edit Support Username</b>

Current support: <b>{current_support}</b>

Please enter the new support username (without @):
(Leave empty to remove support username)

To cancel, send /cancel"""
    ).format(current_support=current_support or "Not set")
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                callback_data=f"admin_tenant_bot_settings:{bot_id}"
            )
        ]
    ])
    
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
            reply_markup=get_back_keyboard(db_user.language)
        )
        await state.clear()
        return
    
    support_username = message.text.strip()
    # Remove @ if present
    if support_username.startswith('@'):
        support_username = support_username[1:]
    
    # If empty, set to None to remove
    if not support_username:
        support_username = None
    
    # Update support username using BotConfigService
    await BotConfigService.set_config(db, bot_id, 'SUPPORT_USERNAME', support_username)
    await db.commit()
    
    if support_username:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_SUPPORT_UPDATED", "✅ Support username updated successfully!")
        )
    else:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_SUPPORT_REMOVED", "✅ Support username removed.")
        )
    
    await state.clear()
    
    # Send success message with button to return to settings
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_VIEW_SETTINGS", "⚙️ View Settings"),
                callback_data=f"admin_tenant_bot_settings:{bot_id}"
            )
        ]
    ])
    await message.answer(
        texts.t("ADMIN_TENANT_BOT_RETURN_TO_SETTINGS", "Click below to return to settings:"),
        reply_markup=keyboard
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
    
    current_chat_id = await BotConfigService.get_config(db, bot_id, 'ADMIN_NOTIFICATIONS_CHAT_ID')
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(AdminStates.editing_tenant_bot_notifications)
    
    text = texts.t(
        "ADMIN_TENANT_BOT_EDIT_NOTIFICATIONS_PROMPT",
        """🔔 <b>Edit Notifications Chat ID</b>

Current chat ID: <b>{current_chat_id}</b>

Please enter the new Telegram chat ID for admin notifications:
(Enter a negative number for groups, positive for channels)

To remove, send 'none' or '0'
To cancel, send /cancel"""
    ).format(current_chat_id=current_chat_id or "Not set")
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                callback_data=f"admin_tenant_bot_settings:{bot_id}"
            )
        ]
    ])
    
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
            reply_markup=get_back_keyboard(db_user.language)
        )
        await state.clear()
        return
    
    chat_id_input = message.text.strip().lower()
    
    # Handle removal
    if chat_id_input in ('none', '0', ''):
        chat_id = None
    else:
        try:
            chat_id = int(chat_id_input)
        except ValueError:
            await message.answer(
                texts.t(
                    "ADMIN_TENANT_BOT_NOTIFICATIONS_INVALID",
                    "❌ Invalid chat ID. Please enter a valid number, or 'none' to remove."
                )
            )
            return
    
    # Update notifications chat ID using BotConfigService
    await BotConfigService.set_config(db, bot_id, 'ADMIN_NOTIFICATIONS_CHAT_ID', chat_id)
    await db.commit()
    
    if chat_id:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_NOTIFICATIONS_UPDATED", "✅ Notifications chat ID updated successfully!")
        )
    else:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_NOTIFICATIONS_REMOVED", "✅ Notifications chat ID removed.")
        )
    
    await state.clear()
    
    # Send success message with button to return to settings
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_VIEW_SETTINGS", "⚙️ View Settings"),
                callback_data=f"admin_tenant_bot_settings:{bot_id}"
            )
        ]
    ])
    await message.answer(
        texts.t("ADMIN_TENANT_BOT_RETURN_TO_SETTINGS", "Click below to return to settings:"),
        reply_markup=keyboard
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


@admin_required
@error_handler
async def show_bot_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show comprehensive statistics for a bot."""
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
    
    # AC4: Use SQL queries matching spec exactly
    # New users (30 days) - matches AC4 spec
    new_users_30d_query = sql_text("""
        SELECT COUNT(*) FROM users 
        WHERE bot_id = :bot_id 
          AND created_at >= CURRENT_DATE - INTERVAL '30 days'
    """)
    new_users_30d_result = await db.execute(new_users_30d_query, {"bot_id": bot_id})
    new_users_30d = new_users_30d_result.scalar() or 0
    
    # Active users - matches AC4 spec
    active_users_query = sql_text("""
        SELECT COUNT(DISTINCT user_id) FROM subscriptions
        WHERE bot_id = :bot_id AND status = 'active'
    """)
    active_users_result = await db.execute(active_users_query, {"bot_id": bot_id})
    active_users = active_users_result.scalar() or 0
    
    # New subscriptions (30 days)
    new_subs_30d_query = sql_text("""
        SELECT COUNT(*) FROM subscriptions
        WHERE bot_id = :bot_id 
          AND created_at >= CURRENT_DATE - INTERVAL '30 days'
    """)
    new_subs_30d_result = await db.execute(new_subs_30d_query, {"bot_id": bot_id})
    new_subs_30d = new_subs_30d_result.scalar() or 0
    
    # Revenue (30 days)
    revenue_30d_query = sql_text("""
        SELECT COALESCE(SUM(amount_toman), 0) 
        FROM transactions 
        WHERE bot_id = :bot_id 
          AND type = 'deposit' 
          AND is_completed = TRUE
          AND created_at >= CURRENT_DATE - INTERVAL '30 days'
    """)
    revenue_30d_result = await db.execute(revenue_30d_query, {"bot_id": bot_id})
    revenue_30d = revenue_30d_result.scalar() or 0
    
    # Revenue breakdown by payment method (30 days) - matches AC4 spec
    revenue_by_method_query = sql_text("""
        SELECT payment_method, SUM(amount_toman) as total
        FROM transactions
        WHERE bot_id = :bot_id 
          AND type = 'deposit'
          AND is_completed = TRUE
          AND created_at >= CURRENT_DATE - INTERVAL '30 days'
          AND payment_method IS NOT NULL
        GROUP BY payment_method
    """)
    revenue_by_method_result = await db.execute(revenue_by_method_query, {"bot_id": bot_id})
    revenue_by_method = {row[0]: row[1] for row in revenue_by_method_result.fetchall()}
    
    # User growth metrics
    # Today
    new_users_today_query = sql_text("""
        SELECT COUNT(*) FROM users 
        WHERE bot_id = :bot_id 
          AND created_at >= date_trunc('day', CURRENT_DATE)
    """)
    new_users_today_result = await db.execute(new_users_today_query, {"bot_id": bot_id})
    new_users_today = new_users_today_result.scalar() or 0
    
    # This week
    new_users_week_query = sql_text("""
        SELECT COUNT(*) FROM users 
        WHERE bot_id = :bot_id 
          AND created_at >= date_trunc('week', CURRENT_DATE)
    """)
    new_users_week_result = await db.execute(new_users_week_query, {"bot_id": bot_id})
    new_users_week = new_users_week_result.scalar() or 0
    
    # This month
    new_users_month_query = sql_text("""
        SELECT COUNT(*) FROM users 
        WHERE bot_id = :bot_id 
          AND created_at >= date_trunc('month', CURRENT_DATE)
    """)
    new_users_month_result = await db.execute(new_users_month_query, {"bot_id": bot_id})
    new_users_month = new_users_month_result.scalar() or 0
    
    # Build statistics text
    text = texts.t(
        "ADMIN_TENANT_BOT_STATISTICS",
        """📊 <b>Bot Statistics: {name}</b>

📈 <b>Overview (Last 30 days):</b>
• New Users: {new_users_30d}
• Active Users: {active_users}
• New Subscriptions: {new_subs_30d}
• Revenue: {revenue_30d} Toman
• Traffic Sold: {traffic_sold} GB"""
    ).format(
        name=bot.name,
        new_users_30d=new_users_30d,
        active_users=active_users,
        new_subs_30d=new_subs_30d,
        revenue_30d=f"{revenue_30d / 100:,.0f}".replace(',', ' '),
        traffic_sold=f"{bot.traffic_sold_bytes / (1024**3):.2f}"
    )
    
    # Revenue breakdown
    if revenue_by_method:
        text += "\n\n💰 <b>Revenue Breakdown:</b>\n"
        total_revenue = sum(revenue_by_method.values())
        for method, amount in revenue_by_method.items():
            percentage = (amount / total_revenue * 100) if total_revenue > 0 else 0
            text += f"• {method}: {amount / 100:,.0f} Toman ({percentage:.0f}%)\n"
    
    # User growth
    text += "\n👥 <b>User Growth:</b>\n"
    text += f"• Today: +{new_users_today}\n"
    text += f"• This Week: +{new_users_week}\n"
    text += f"• This Month: +{new_users_month}\n"
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_STATS_DETAILED", "📊 Detailed Stats"),
                callback_data=f"admin_tenant_bot_stats_detailed:{bot_id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_STATS_REVENUE_CHART", "📈 Revenue Chart"),
                callback_data=f"admin_tenant_bot_stats_revenue:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_STATS_USERS_LIST", "👥 Users List"),
                callback_data=f"admin_tenant_bot_stats_users:{bot_id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOT_STATS_SUBSCRIPTIONS", "📦 Subscriptions"),
                callback_data=f"admin_tenant_bot_stats_subs:{bot_id}"
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
async def show_bot_feature_flags(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show feature flags management for a bot (AC6)."""
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
    
    # Define feature categories as per AC6
    feature_categories = {
        "Payment Gateways": [
            ("yookassa", "YooKassa"),
            ("cryptobot", "CryptoBot"),
            ("pal24", "Pal24"),
            ("card_to_card", "Card-to-Card"),
            ("zarinpal", "Zarinpal"),
            ("telegram_stars", "Telegram Stars"),
            ("heleket", "Heleket"),
            ("mulenpay", "MulenPay"),
            ("wata", "WATA"),
            ("tribute", "Tribute"),
        ],
        "Subscription Features": [
            ("trial", "Trial"),
            ("auto_renewal", "Auto Renewal"),
            ("simple_purchase", "Simple Purchase"),
        ],
        "Marketing Features": [
            ("referral_program", "Referral Program"),
            ("polls", "Polls"),
        ],
        "Support Features": [
            ("support_tickets", "Support Tickets"),
        ],
        "Integrations": [
            ("server_status", "Server Status"),
            ("monitoring", "Monitoring"),
        ],
    }
    
    # Get current plan info (if tenant_subscriptions table exists)
    plan_name = None
    try:
        plan_result = await db.execute(
            sql_text("""
                SELECT tsp.display_name
                FROM tenant_subscriptions ts
                LEFT JOIN tenant_subscription_plans tsp ON tsp.id = ts.plan_tier_id
                WHERE ts.bot_id = :bot_id AND ts.status = 'active'
                LIMIT 1
            """),
            {"bot_id": bot_id}
        )
        plan_row = plan_result.fetchone()
        if plan_row and plan_row[0]:
            plan_name = plan_row[0]
    except Exception:
        # Table doesn't exist yet, skip plan check
        pass
    
    # Build feature flags display
    text = texts.t(
        "ADMIN_TENANT_BOT_FEATURES",
        """🎛️ <b>Feature Flags: {name}</b>

<b>Current Plan:</b> {plan_name}

Select a category to view features:"""
    ).format(
        name=bot.name,
        plan_name=plan_name or "Not assigned"
    )
    
    keyboard_buttons = []
    
    # Add category buttons
    for category_name, features in feature_categories.items():
        # Count enabled features in this category
        enabled_count = 0
        for feature_key, _ in features:
            is_enabled = await BotConfigService.is_feature_enabled(db, bot_id, feature_key)
            if is_enabled:
                enabled_count += 1
        
        keyboard_buttons.append([
            types.InlineKeyboardButton(
                text=f"{category_name} ({enabled_count}/{len(features)})",
                callback_data=f"admin_tenant_bot_features_category:{bot_id}:{category_name}"
            )
        ])
    
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
async def show_bot_feature_flags_category(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show feature flags for a specific category."""
    texts = get_texts(db_user.language)
    
    try:
        parts = callback.data.split(":")
        bot_id = int(parts[1])
        category_name = ":".join(parts[2:])  # Handle category names with colons
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
    
    # Define feature categories
    feature_categories = {
        "Payment Gateways": [
            ("yookassa", "YooKassa"),
            ("cryptobot", "CryptoBot"),
            ("pal24", "Pal24"),
            ("card_to_card", "Card-to-Card"),
            ("zarinpal", "Zarinpal"),
            ("telegram_stars", "Telegram Stars"),
            ("heleket", "Heleket"),
            ("mulenpay", "MulenPay"),
            ("wata", "WATA"),
            ("tribute", "Tribute"),
        ],
        "Subscription Features": [
            ("trial", "Trial"),
            ("auto_renewal", "Auto Renewal"),
            ("simple_purchase", "Simple Purchase"),
        ],
        "Marketing Features": [
            ("referral_program", "Referral Program"),
            ("polls", "Polls"),
        ],
        "Support Features": [
            ("support_tickets", "Support Tickets"),
        ],
        "Integrations": [
            ("server_status", "Server Status"),
            ("monitoring", "Monitoring"),
        ],
    }
    
    features = feature_categories.get(category_name, [])
    if not features:
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid category"),
            show_alert=True
        )
        return
    
    # Get current plan and check restrictions
    plan_name = None
    plan_restrictions = {}  # feature_key -> required_plan
    try:
        plan_result = await db.execute(
            sql_text("""
                SELECT tsp.id, tsp.name, tsp.display_name
                FROM tenant_subscriptions ts
                LEFT JOIN tenant_subscription_plans tsp ON tsp.id = ts.plan_tier_id
                WHERE ts.bot_id = :bot_id AND ts.status = 'active'
                LIMIT 1
            """),
            {"bot_id": bot_id}
        )
        plan_row = plan_result.fetchone()
        if plan_row and plan_row[0]:
            plan_id, plan_key, plan_name = plan_row
            
            # Check which features are granted by this plan
            grants_result = await db.execute(
                sql_text("""
                    SELECT feature_key, enabled
                    FROM plan_feature_grants
                    WHERE plan_tier_id = :plan_id
                """),
                {"plan_id": plan_id}
            )
            for row in grants_result.fetchall():
                feature_key, enabled = row
                if not enabled:
                    plan_restrictions[feature_key] = plan_name or "Higher Plan"
    except Exception:
        # Tables don't exist yet, skip plan restrictions
        pass
    
    # Build feature list
    text = texts.t(
        "ADMIN_TENANT_BOT_FEATURES_CATEGORY",
        """🎛️ <b>{category}: {name}</b>

<b>Current Plan:</b> {plan_name}

<b>Features:</b>"""
    ).format(
        category=category_name,
        name=bot.name,
        plan_name=plan_name or "Not assigned"
    )
    
    keyboard_buttons = []
    
    for feature_key, feature_display in features:
        is_enabled = await BotConfigService.is_feature_enabled(db, bot_id, feature_key)
        status_icon = "✅" if is_enabled else "❌"
        
        # Check if feature requires a higher plan
        requires_plan = plan_restrictions.get(feature_key)
        restriction_text = ""
        if requires_plan and not is_enabled:
            restriction_text = f" (Requires {requires_plan})"
        
        text += f"\n{status_icon} <b>{feature_display}</b>{restriction_text}"
        
        # Add toggle button (master admin can always override)
        keyboard_buttons.append([
            types.InlineKeyboardButton(
                text=f"{'🔴 Disable' if is_enabled else '🟢 Enable'} {feature_display}",
                callback_data=f"admin_tenant_bot_toggle_feature:{bot_id}:{feature_key}"
            )
        ])
    
    # Back button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data=f"admin_tenant_bot_features:{bot_id}"
        )
    ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def toggle_feature_flag(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Toggle a feature flag for a bot (AC6)."""
    texts = get_texts(db_user.language)
    
    try:
        parts = callback.data.split(":")
        bot_id = int(parts[1])
        feature_key = parts[2]
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
    
    # Check plan restrictions (master admin can override)
    plan_name = None
    feature_allowed = True
    try:
        plan_result = await db.execute(
            sql_text("""
                SELECT tsp.id, tsp.name, tsp.display_name
                FROM tenant_subscriptions ts
                LEFT JOIN tenant_subscription_plans tsp ON tsp.id = ts.plan_tier_id
                WHERE ts.bot_id = :bot_id AND ts.status = 'active'
                LIMIT 1
            """),
            {"bot_id": bot_id}
        )
        plan_row = plan_result.fetchone()
        if plan_row and plan_row[0]:
            plan_id, plan_key, plan_name = plan_row
            
            # Check if feature is granted by plan
            grant_result = await db.execute(
                sql_text("""
                    SELECT enabled
                    FROM plan_feature_grants
                    WHERE plan_tier_id = :plan_id AND feature_key = :feature_key
                """),
                {"plan_id": plan_id, "feature_key": feature_key}
            )
            grant_row = grant_result.fetchone()
            if grant_row:
                feature_allowed = grant_row[0]
            # If no grant record exists, feature is not allowed by plan
            # But master admin can override
    except Exception:
        # Tables don't exist, allow toggle (master admin override)
        feature_allowed = True
    
    # Get current value
    current_value = await BotConfigService.is_feature_enabled(db, bot_id, feature_key)
    new_value = not current_value
    
    # If enabling and plan doesn't allow it, warn but allow (master admin override)
    if new_value and not feature_allowed and plan_name:
        # Master admin can override, but show warning
        await callback.answer(
            texts.t(
                "ADMIN_TENANT_BOT_FEATURE_PLAN_RESTRICTION",
                f"⚠️ This feature requires a higher plan. Overriding as master admin."
            ),
            show_alert=True
        )
    
    # Toggle feature using BotConfigService
    await BotConfigService.set_feature_enabled(db, bot_id, feature_key, new_value)
    await db.commit()
    
    status_text = "enabled" if new_value else "disabled"
    await callback.answer(f"✅ Feature {status_text}")
    
    # Refresh the category view
    # Find which category this feature belongs to
    feature_categories = {
        "Payment Gateways": [
            ("yookassa", "YooKassa"),
            ("cryptobot", "CryptoBot"),
            ("pal24", "Pal24"),
            ("card_to_card", "Card-to-Card"),
            ("zarinpal", "Zarinpal"),
            ("telegram_stars", "Telegram Stars"),
            ("heleket", "Heleket"),
            ("mulenpay", "MulenPay"),
            ("wata", "WATA"),
            ("tribute", "Tribute"),
        ],
        "Subscription Features": [
            ("trial", "Trial"),
            ("auto_renewal", "Auto Renewal"),
            ("simple_purchase", "Simple Purchase"),
        ],
        "Marketing Features": [
            ("referral_program", "Referral Program"),
            ("polls", "Polls"),
        ],
        "Support Features": [
            ("support_tickets", "Support Tickets"),
        ],
        "Integrations": [
            ("server_status", "Server Status"),
            ("monitoring", "Monitoring"),
        ],
    }
    
    # Find category for this feature
    category_name = None
    for cat_name, features in feature_categories.items():
        if any(fk == feature_key for fk, _ in features):
            category_name = cat_name
            break
    
    if category_name:
        # Update callback data to show category
        callback.data = f"admin_tenant_bot_features_category:{bot_id}:{category_name}"
        await show_bot_feature_flags_category(callback, db_user, db)
    else:
        # Fallback to main features view
        await show_bot_feature_flags(callback, db_user, db)


@admin_required
@error_handler
async def show_bot_payment_methods(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show payment methods management for a bot (AC7 placeholder)."""
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
        "ADMIN_TENANT_BOT_PAYMENTS",
        """💳 <b>Payment Methods: {name}</b>

Payment methods management will be implemented in AC7.

[Placeholder - To be implemented]"""
    ).format(name=bot.name)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
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
async def show_bot_plans(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show subscription plans management for a bot (AC8 placeholder)."""
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
        "ADMIN_TENANT_BOT_PLANS",
        """📦 <b>Subscription Plans: {name}</b>

Subscription plans management will be implemented in AC8.

[Placeholder - To be implemented]"""
    ).format(name=bot.name)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
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
async def show_bot_configuration_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show configuration management menu for a bot (AC9 placeholder)."""
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
        "ADMIN_TENANT_BOT_CONFIG",
        """🔧 <b>Configuration: {name}</b>

Configuration management will be implemented in AC9.

[Placeholder - To be implemented]"""
    ).format(name=bot.name)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
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
async def show_bot_analytics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show analytics for a bot (AC10 placeholder)."""
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
        "ADMIN_TENANT_BOT_ANALYTICS",
        """📈 <b>Analytics: {name}</b>

Analytics view will be implemented in AC10.

[Placeholder - To be implemented]"""
    ).format(name=bot.name)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
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
async def start_delete_bot(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Start bot deletion flow with confirmation (AC12 placeholder)."""
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
            texts.t("ADMIN_TENANT_BOT_CANNOT_DELETE_MASTER", "❌ Cannot delete master bot"),
            show_alert=True
        )
        return
    
    text = texts.t(
        "ADMIN_TENANT_BOT_DELETE_CONFIRM",
        """🗑️ <b>Delete Bot: {name}</b>

⚠️ <b>WARNING:</b> This action cannot be undone!

This will delete:
• All users associated with this bot
• All subscriptions
• All transactions
• All configurations and feature flags

Are you sure you want to delete this bot?"""
    ).format(name=bot.name)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_DELETE_CONFIRM", "✅ Yes, Delete"),
                callback_data=f"admin_tenant_bot_delete_confirm:{bot_id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                callback_data=f"admin_tenant_bot_detail:{bot_id}"
            )
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def show_tenant_bots_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show aggregate statistics for all tenant bots (AC1 - Statistics button)."""
    texts = get_texts(db_user.language)
    
    # Use same query as main menu for consistency
    stats_query = sql_text("""
        SELECT 
            COUNT(*) FILTER (WHERE is_master = FALSE) as total_bots,
            COUNT(*) FILTER (WHERE is_master = FALSE AND is_active = TRUE) as active_bots,
            COUNT(*) FILTER (WHERE is_master = FALSE AND is_active = FALSE) as inactive_bots,
            (SELECT COUNT(*) FROM users WHERE bot_id IN (SELECT id FROM bots WHERE is_master = FALSE)) as total_users,
            (SELECT COALESCE(SUM(amount_toman), 0) FROM transactions WHERE bot_id IN (SELECT id FROM bots WHERE is_master = FALSE) AND type = 'deposit' AND is_completed = TRUE) as total_revenue
        FROM bots
    """)
    
    stats_result = await db.execute(stats_query)
    stats_row = stats_result.fetchone()
    
    if stats_row:
        total_bots = stats_row[0] or 0
        active_bots = stats_row[1] or 0
        inactive_bots = stats_row[2] or 0
        total_users = stats_row[3] or 0
        total_revenue = stats_row[4] or 0
    else:
        total_bots = 0
        active_bots = 0
        inactive_bots = 0
        total_users = 0
        total_revenue = 0
    
    text = texts.t(
        "ADMIN_TENANT_BOTS_STATISTICS",
        """📊 <b>Tenant Bots Statistics</b>

<b>Overview:</b>
• Total bots: {total}
• Active: {active}
• Inactive: {inactive}
• Total users: {users}
• Total revenue: {revenue} Toman

<b>Note:</b> Detailed statistics for individual bots are available from the bot detail menu."""
    ).format(
        total=total_bots,
        active=active_bots,
        inactive=inactive_bots,
        users=total_users,
        revenue=f"{total_revenue / 100:,.0f}".replace(',', ' ')
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.BACK,
                callback_data="admin_tenant_bots_menu"
            )
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def show_tenant_bots_settings(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show tenant bots settings menu (AC1 - Settings button)."""
    texts = get_texts(db_user.language)
    
    text = texts.t(
        "ADMIN_TENANT_BOTS_SETTINGS",
        """⚙️ <b>Tenant Bots Settings</b>

<b>Global Settings:</b>
• Default configurations
• Feature flags defaults
• Payment methods defaults

<b>Note:</b> Individual bot settings are available from the bot detail menu."""
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.BACK,
                callback_data="admin_tenant_bots_menu"
            )
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


def register_handlers(dp: Dispatcher) -> None:
    """Register tenant bots handlers."""
    dp.callback_query.register(
        show_tenant_bots_menu,
        F.data == "admin_tenant_bots_menu"
    )
    
    # Main list handler (page 1 or no page specified)
    dp.callback_query.register(
        list_tenant_bots,
        F.data == "admin_tenant_bots_list"
    )
    
    # Old pattern support (backward compatible): admin_tenant_bots_list:{page}
    dp.callback_query.register(
        list_tenant_bots,
        F.data.startswith("admin_tenant_bots_list:") & ~F.data.contains("_page_")
    )
    
    # Pagination handler (standard pattern)
    dp.callback_query.register(
        handle_tenant_bots_list_pagination,
        F.data.startswith("admin_tenant_bots_list_page_")
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
        StateFilter(AdminStates.creating_tenant_bot_name)
    )
    
    dp.message.register(
        process_bot_token,
        StateFilter(AdminStates.creating_tenant_bot_token)
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
    
    # Settings edit handlers
    dp.callback_query.register(
        start_edit_bot_name,
        F.data.startswith("admin_tenant_bot_edit_name:")
    )
    
    dp.callback_query.register(
        start_edit_bot_language,
        F.data.startswith("admin_tenant_bot_edit_language:")
    )
    
    dp.callback_query.register(
        start_edit_bot_support,
        F.data.startswith("admin_tenant_bot_edit_support:")
    )
    
    dp.callback_query.register(
        start_edit_bot_notifications,
        F.data.startswith("admin_tenant_bot_edit_notifications:")
    )
    
    # FSM handlers for settings editing
    dp.message.register(
        process_edit_bot_name,
        StateFilter(AdminStates.editing_tenant_bot_name)
    )
    
    dp.message.register(
        process_edit_bot_language,
        StateFilter(AdminStates.editing_tenant_bot_language)
    )
    
    dp.message.register(
        process_edit_bot_support,
        StateFilter(AdminStates.editing_tenant_bot_support)
    )
    
    dp.message.register(
        process_edit_bot_notifications,
        StateFilter(AdminStates.editing_tenant_bot_notifications)
    )
    
    dp.callback_query.register(
        update_all_webhooks,
        F.data == "admin_tenant_bots_update_webhooks"
    )
    
    # AC1: Statistics and Settings buttons
    dp.callback_query.register(
        show_tenant_bots_statistics,
        F.data == "admin_tenant_bots_stats"
    )
    
    dp.callback_query.register(
        show_tenant_bots_settings,
        F.data == "admin_tenant_bots_settings"
    )
    
    dp.callback_query.register(
        test_bot_status,
        F.data.startswith("admin_tenant_bot_test:")
    )
    
    # Statistics
    dp.callback_query.register(
        show_bot_statistics,
        F.data.startswith("admin_tenant_bot_stats:")
    )
    
    # Feature flags - register specific handlers first (more specific patterns)
    dp.callback_query.register(
        toggle_feature_flag,
        F.data.startswith("admin_tenant_bot_toggle_feature:")
    )
    
    dp.callback_query.register(
        show_bot_feature_flags_category,
        F.data.startswith("admin_tenant_bot_features_category:")
    )
    
    # Main feature flags handler (less specific, must be last)
    dp.callback_query.register(
        show_bot_feature_flags,
        F.data.startswith("admin_tenant_bot_features:")
    )
    
    # Payment methods
    dp.callback_query.register(
        show_bot_payment_methods,
        F.data.startswith("admin_tenant_bot_payments:")
    )
    
    # Subscription plans
    dp.callback_query.register(
        show_bot_plans,
        F.data.startswith("admin_tenant_bot_plans:")
    )
    
    # Configuration
    dp.callback_query.register(
        show_bot_configuration_menu,
        F.data.startswith("admin_tenant_bot_config:")
    )
    
    # Analytics
    dp.callback_query.register(
        show_bot_analytics,
        F.data.startswith("admin_tenant_bot_analytics:")
    )
    
    # Delete bot
    dp.callback_query.register(
        start_delete_bot,
        F.data.startswith("admin_tenant_bot_delete:")
    )
    
    logger.info("✅ Tenant bots admin handlers registered")



