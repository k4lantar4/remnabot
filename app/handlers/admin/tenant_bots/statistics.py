"""Statistics handlers for tenant bots."""

from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sql_text

from app.database.models import User
from app.database.crud.bot import get_bot_by_id
from app.localization.texts import get_texts
from app.utils.decorators import error_handler
from app.utils.permissions import admin_required
from .common import logger


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
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
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
• Traffic Sold: {traffic_sold} GB""",
    ).format(
        name=bot.name,
        new_users_30d=new_users_30d,
        active_users=active_users,
        new_subs_30d=new_subs_30d,
        revenue_30d=f"{revenue_30d / 100:,.0f}".replace(",", " "),
        traffic_sold=f"{bot.traffic_sold_bytes / (1024**3):.2f}",
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

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_STATS_DETAILED", "📊 Detailed Stats"),
                    callback_data=f"admin_tenant_bot_stats_detailed:{bot_id}",
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_STATS_REVENUE_CHART", "📈 Revenue Chart"),
                    callback_data=f"admin_tenant_bot_stats_revenue:{bot_id}",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_STATS_USERS_LIST", "👥 Users List"),
                    callback_data=f"admin_tenant_bot_stats_users:{bot_id}",
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_STATS_SUBSCRIPTIONS", "📦 Subscriptions"),
                    callback_data=f"admin_tenant_bot_stats_subs:{bot_id}",
                ),
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data=f"admin_tenant_bot_detail:{bot_id}")],
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
