"""Menu and list handlers for tenant bots."""

from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy import text as sql_text

from app.database.models import User, Bot, Transaction, TransactionType
from app.database.crud.bot import get_bot_by_id
from app.localization.texts import get_texts
from app.utils.decorators import error_handler, admin_required
from app.keyboards.admin import get_admin_pagination_keyboard
from .common import logger


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

Select action:""",
    ).format(
        total=total_bots,
        active=active_bots,
        inactive=inactive_bots,
        users=total_users,
        revenue=f"{total_revenue / 100:,.0f}".replace(",", " "),
    )

    # AC1: Navigation buttons - List Bots, Create Bot, Statistics, Settings
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOTS_LIST", "📋 List Bots"), callback_data="admin_tenant_bots_list"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOTS_CREATE", "➕ Create Bot"), callback_data="admin_tenant_bots_create"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOTS_STATISTICS", "📊 Statistics"),
                    callback_data="admin_tenant_bots_stats",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOTS_SETTINGS", "⚙️ Settings"), callback_data="admin_tenant_bots_settings"
                )
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")],
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def list_tenant_bots(callback: types.CallbackQuery, db_user: User, db: AsyncSession, page: int = 1):
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
                func.count(func.distinct(User.id)).label("user_count"),
                func.coalesce(func.sum(Transaction.amount_toman), 0).label("revenue"),
            )
            .select_from(Bot)
            .outerjoin(User, User.bot_id == Bot.id)
            .outerjoin(
                Transaction,
                and_(
                    Transaction.bot_id == Bot.id,
                    Transaction.type == TransactionType.DEPOSIT.value,
                    Transaction.is_completed == True,
                ),
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
    text = (
        texts.t("ADMIN_TENANT_BOTS_LIST_TITLE", "🤖 <b>Tenant Bots</b> (page {page}/{total})").format(
            page=page, total=total_pages
        )
        + "\n\n"
    )

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

            keyboard.append(
                [types.InlineKeyboardButton(text=button_text, callback_data=f"admin_tenant_bot_detail:{bot.id}")]
            )

    # Use standard pagination keyboard (matches other handlers)
    pagination_keyboard = get_admin_pagination_keyboard(
        current_page=page,
        total_pages=total_pages,
        callback_prefix="admin_tenant_bots_list",
        back_callback="admin_tenant_bots_menu",
        language=user_language,
    )

    # Combine keyboard with pagination
    final_keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard + pagination_keyboard.inline_keyboard)

    await callback.message.edit_text(text, reply_markup=final_keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def handle_tenant_bots_list_pagination(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    """Handle pagination for tenant bots list."""
    try:
        page = int(callback.data.split("_page_")[1])
        await list_tenant_bots(callback, db_user, db, page=page)
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing page number: {e}")
        await list_tenant_bots(callback, db_user, db, page=1)


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

<b>Note:</b> Detailed statistics for individual bots are available from the bot detail menu.""",
    ).format(
        total=total_bots,
        active=active_bots,
        inactive=inactive_bots,
        users=total_users,
        revenue=f"{total_revenue / 100:,.0f}".replace(",", " "),
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_tenant_bots_menu")]]
    )

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

<b>Note:</b> Individual bot settings are available from the bot detail menu.""",
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_tenant_bots_menu")]]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
