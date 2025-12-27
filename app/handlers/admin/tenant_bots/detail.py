"""Bot detail view handler."""
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy import text as sql_text

from app.database.models import User, Subscription, SubscriptionStatus
from app.database.crud.bot import get_bot_by_id
from app.localization.texts import get_texts
from app.utils.decorators import error_handler, admin_required
from app.services.bot_config_service import BotConfigService
from .common import logger


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

