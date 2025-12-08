import logging
from datetime import datetime, timedelta
from aiogram import Dispatcher, types, F
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.keyboards.admin import get_admin_statistics_keyboard, get_period_selection_keyboard
from app.localization.texts import get_texts
from app.services.user_service import UserService
from app.database.crud.subscription import get_subscriptions_statistics
from app.database.crud.transaction import get_transactions_statistics, get_revenue_by_period
from app.database.crud.referral import get_referral_statistics
from app.utils.decorators import admin_required, error_handler
from app.utils.formatters import format_datetime, format_percentage

logger = logging.getLogger(__name__)


@admin_required
@error_handler
async def show_statistics_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    text = texts.t("ADMIN_STATISTICS_MENU_TITLE", "📊 <b>System statistics</b>") + "\n\n"
    text += texts.t("ADMIN_STATISTICS_MENU_HINT", "Select a section to view statistics:")
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_statistics_keyboard(db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_users_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_service = UserService()
    stats = await user_service.get_user_statistics(db)
    
    total_users = stats['total_users']
    active_rate = format_percentage(stats['active_users'] / total_users * 100 if total_users > 0 else 0)
    texts = get_texts(db_user.language)
    current_time = format_datetime(datetime.utcnow())
    
    text = texts.t("ADMIN_STATS_USERS_TITLE", "👥 <b>User statistics</b>") + "\n\n"
    text += texts.t("ADMIN_STATS_USERS_GENERAL", "<b>General metrics:</b>") + "\n"
    text += texts.t("ADMIN_STATS_USERS_TOTAL", "- Total registered: {count}").format(count=stats['total_users']) + "\n"
    text += texts.t("ADMIN_STATS_USERS_ACTIVE", "- Active: {count} ({rate})").format(count=stats['active_users'], rate=active_rate) + "\n"
    text += texts.t("ADMIN_STATS_USERS_BLOCKED", "- Blocked: {count}").format(count=stats['blocked_users']) + "\n\n"
    text += texts.t("ADMIN_STATS_USERS_REGISTRATIONS", "<b>New registrations:</b>") + "\n"
    text += texts.t("ADMIN_STATS_USERS_TODAY", "- Today: {count}").format(count=stats['new_today']) + "\n"
    text += texts.t("ADMIN_STATS_USERS_WEEK", "- This week: {count}").format(count=stats['new_week']) + "\n"
    text += texts.t("ADMIN_STATS_USERS_MONTH", "- This month: {count}").format(count=stats['new_month']) + "\n\n"
    text += texts.t("ADMIN_STATS_USERS_ACTIVITY", "<b>Activity:</b>") + "\n"
    text += texts.t("ADMIN_STATS_USERS_ACTIVITY_RATE", "- Activity rate: {rate}").format(rate=active_rate) + "\n"
    text += texts.t("ADMIN_STATS_USERS_GROWTH", "- Monthly growth: +{count} ({rate})").format(
        count=stats['new_month'], rate=format_percentage(stats['new_month'] / total_users * 100 if total_users > 0 else 0)
    ) + "\n\n"
    text += texts.t("ADMIN_STATS_UPDATED_AT", "<b>Updated:</b> {time}").format(time=current_time)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=texts.t("ADMIN_STATS_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_stats_users")],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_statistics")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.answer(texts.t("ADMIN_STATS_DATA_CURRENT", "📊 Data is current"), show_alert=False)
        else:
            logger.error(f"Error updating user statistics: {e}")
            await callback.answer(texts.t("ADMIN_STATS_ERROR_UPDATE", "❌ Data update error"), show_alert=True)
            return
    
    await callback.answer(texts.t("ADMIN_STATS_REFRESHED", "✅ Statistics refreshed"))



@admin_required
@error_handler
async def show_subscriptions_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    stats = await get_subscriptions_statistics(db)
    texts = get_texts(db_user.language)
    
    total_subs = stats['total_subscriptions']
    conversion_rate = format_percentage(stats['paid_subscriptions'] / total_subs * 100 if total_subs > 0 else 0)
    current_time = format_datetime(datetime.utcnow())
    
    text = texts.t("ADMIN_STATS_SUBS_TITLE", "📱 <b>Subscription statistics</b>") + "\n\n"
    text += texts.t("ADMIN_STATS_SUBS_GENERAL", "<b>General metrics:</b>") + "\n"
    text += texts.t("ADMIN_STATS_SUBS_TOTAL", "- Total subscriptions: {count}").format(count=stats['total_subscriptions']) + "\n"
    text += texts.t("ADMIN_STATS_SUBS_ACTIVE", "- Active: {count}").format(count=stats['active_subscriptions']) + "\n"
    text += texts.t("ADMIN_STATS_SUBS_PAID", "- Paid: {count}").format(count=stats['paid_subscriptions']) + "\n"
    text += texts.t("ADMIN_STATS_SUBS_TRIAL", "- Trial: {count}").format(count=stats['trial_subscriptions']) + "\n\n"
    text += texts.t("ADMIN_STATS_SUBS_CONVERSION", "<b>Conversion:</b>") + "\n"
    text += texts.t("ADMIN_STATS_SUBS_TRIAL_TO_PAID", "- Trial to paid: {rate}").format(rate=conversion_rate) + "\n"
    text += texts.t("ADMIN_STATS_SUBS_ACTIVE_PAID", "- Active paid: {count}").format(count=stats['paid_subscriptions']) + "\n\n"
    text += texts.t("ADMIN_STATS_SUBS_SALES", "<b>Sales:</b>") + "\n"
    text += texts.t("ADMIN_STATS_SUBS_SALES_TODAY", "- Today: {count}").format(count=stats['purchased_today']) + "\n"
    text += texts.t("ADMIN_STATS_SUBS_SALES_WEEK", "- This week: {count}").format(count=stats['purchased_week']) + "\n"
    text += texts.t("ADMIN_STATS_SUBS_SALES_MONTH", "- This month: {count}").format(count=stats['purchased_month']) + "\n\n"
    text += texts.t("ADMIN_STATS_UPDATED_AT", "<b>Updated:</b> {time}").format(time=current_time)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=texts.t("ADMIN_STATS_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_stats_subs")],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_statistics")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer(texts.t("ADMIN_STATS_REFRESHED", "✅ Statistics refreshed"))
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.answer(texts.t("ADMIN_STATS_DATA_CURRENT", "📊 Data is current"), show_alert=False)
        else:
            logger.error(f"Error updating subscription statistics: {e}")
            await callback.answer(texts.t("ADMIN_STATS_ERROR_UPDATE", "❌ Data update error"), show_alert=True)


@admin_required
@error_handler
async def show_revenue_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    texts = get_texts(db_user.language)
    
    month_stats = await get_transactions_statistics(db, month_start, now)
    all_time_stats = await get_transactions_statistics(db)
    current_time = format_datetime(datetime.utcnow())
    
    text = texts.t("ADMIN_STATS_REVENUE_TITLE", "💰 <b>Revenue statistics</b>") + "\n\n"
    text += texts.t("ADMIN_STATS_REVENUE_MONTH", "<b>Current month:</b>") + "\n"
    text += texts.t("ADMIN_STATS_REVENUE_INCOME", "- Revenue: {amount}").format(amount=settings.format_price(month_stats['totals']['income_kopeks'])) + "\n"
    text += texts.t("ADMIN_STATS_REVENUE_EXPENSES", "- Expenses: {amount}").format(amount=settings.format_price(month_stats['totals']['expenses_kopeks'])) + "\n"
    text += texts.t("ADMIN_STATS_REVENUE_PROFIT", "- Profit: {amount}").format(amount=settings.format_price(month_stats['totals']['profit_kopeks'])) + "\n"
    text += texts.t("ADMIN_STATS_REVENUE_SUBS_INCOME", "- From subscriptions: {amount}").format(amount=settings.format_price(month_stats['totals']['subscription_income_kopeks'])) + "\n\n"
    text += texts.t("ADMIN_STATS_REVENUE_TODAY", "<b>Today:</b>") + "\n"
    text += texts.t("ADMIN_STATS_REVENUE_TODAY_TXS", "- Transactions: {count}").format(count=month_stats['today']['transactions_count']) + "\n"
    text += texts.t("ADMIN_STATS_REVENUE_TODAY_INCOME", "- Revenue: {amount}").format(amount=settings.format_price(month_stats['today']['income_kopeks'])) + "\n\n"
    text += texts.t("ADMIN_STATS_REVENUE_ALL_TIME", "<b>All time:</b>") + "\n"
    text += texts.t("ADMIN_STATS_REVENUE_TOTAL_INCOME", "- Total revenue: {amount}").format(amount=settings.format_price(all_time_stats['totals']['income_kopeks'])) + "\n"
    text += texts.t("ADMIN_STATS_REVENUE_TOTAL_PROFIT", "- Total profit: {amount}").format(amount=settings.format_price(all_time_stats['totals']['profit_kopeks'])) + "\n\n"
    text += texts.t("ADMIN_STATS_REVENUE_PAYMENT_METHODS", "<b>Payment methods:</b>") + "\n"
    
    for method, data in month_stats['by_payment_method'].items():
        if method and data['count'] > 0:
            text += f"• {method}: {data['count']} ({settings.format_price(data['amount'])})\n"
    
    text += "\n" + texts.t("ADMIN_STATS_UPDATED_AT", "<b>Updated:</b> {time}").format(time=current_time)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
      # [types.InlineKeyboardButton(text=texts.t("ADMIN_STATS_BTN_PERIOD", "📈 Period"), callback_data="admin_revenue_period")],
        [types.InlineKeyboardButton(text=texts.t("ADMIN_STATS_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_stats_revenue")],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_statistics")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer(texts.t("ADMIN_STATS_REFRESHED", "✅ Statistics refreshed"))
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.answer(texts.t("ADMIN_STATS_DATA_CURRENT", "📊 Data is current"), show_alert=False)
        else:
            logger.error(f"Error updating revenue statistics: {e}")
            await callback.answer(texts.t("ADMIN_STATS_ERROR_UPDATE", "❌ Data update error"), show_alert=True)


@admin_required
@error_handler
async def show_referral_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    stats = await get_referral_statistics(db)
    texts = get_texts(db_user.language)
    current_time = format_datetime(datetime.utcnow())
    
    avg_per_referrer = 0
    if stats['active_referrers'] > 0:
        avg_per_referrer = stats['total_paid_kopeks'] / stats['active_referrers']
    
    text = texts.t("ADMIN_STATS_REF_TITLE", "🤝 <b>Referral statistics</b>") + "\n\n"
    text += texts.t("ADMIN_STATS_REF_GENERAL", "<b>General metrics:</b>") + "\n"
    text += texts.t("ADMIN_STATS_REF_USERS_WITH_REFS", "- Users with referrals: {count}").format(count=stats['users_with_referrals']) + "\n"
    text += texts.t("ADMIN_STATS_REF_ACTIVE_REFERRERS", "- Active referrers: {count}").format(count=stats['active_referrers']) + "\n"
    text += texts.t("ADMIN_STATS_REF_TOTAL_PAID", "- Total paid: {amount}").format(amount=settings.format_price(stats['total_paid_kopeks'])) + "\n\n"
    text += texts.t("ADMIN_STATS_REF_PERIOD", "<b>Period earnings:</b>") + "\n"
    text += texts.t("ADMIN_STATS_REF_TODAY", "- Today: {amount}").format(amount=settings.format_price(stats['today_earnings_kopeks'])) + "\n"
    text += texts.t("ADMIN_STATS_REF_WEEK", "- This week: {amount}").format(amount=settings.format_price(stats['week_earnings_kopeks'])) + "\n"
    text += texts.t("ADMIN_STATS_REF_MONTH", "- This month: {amount}").format(amount=settings.format_price(stats['month_earnings_kopeks'])) + "\n\n"
    text += texts.t("ADMIN_STATS_REF_AVERAGES", "<b>Averages:</b>") + "\n"
    text += texts.t("ADMIN_STATS_REF_PER_REFERRER", "- Per referrer: {amount}").format(amount=settings.format_price(int(avg_per_referrer))) + "\n\n"
    text += texts.t("ADMIN_STATS_REF_TOP_TITLE", "<b>Top referrers:</b>") + "\n"
    
    if stats['top_referrers']:
        for i, referrer in enumerate(stats['top_referrers'][:5], 1):
            name = referrer['display_name']
            earned = settings.format_price(referrer['total_earned_kopeks'])
            count = referrer['referrals_count']
            text += texts.t("ADMIN_STATS_REF_TOP_ITEM", "{i}. {name}: {amount} ({count} ref.)").format(
                i=i, name=name, amount=earned, count=count
            ) + "\n"
    else:
        text += texts.t("ADMIN_STATS_REF_NO_ACTIVE", "No active referrers yet")
    
    text += "\n" + texts.t("ADMIN_STATS_UPDATED_AT", "<b>Updated:</b> {time}").format(time=current_time)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=texts.t("ADMIN_STATS_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_stats_referrals")],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_statistics")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer(texts.t("ADMIN_STATS_REFRESHED", "✅ Statistics refreshed"))
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.answer(texts.t("ADMIN_STATS_DATA_CURRENT", "📊 Data is current"), show_alert=False)
        else:
            logger.error(f"Error updating referral statistics: {e}")
            await callback.answer(texts.t("ADMIN_STATS_ERROR_UPDATE", "❌ Data update error"), show_alert=True)


@admin_required
@error_handler
async def show_summary_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_service = UserService()
    user_stats = await user_service.get_user_statistics(db)
    sub_stats = await get_subscriptions_statistics(db)
    
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue_stats = await get_transactions_statistics(db, month_start, now)
    texts = get_texts(db_user.language)
    current_time = format_datetime(datetime.utcnow())
    
    conversion_rate = 0
    if user_stats['total_users'] > 0:
        conversion_rate = sub_stats['paid_subscriptions'] / user_stats['total_users'] * 100
    
    arpu = 0
    if user_stats['active_users'] > 0:
        arpu = revenue_stats['totals']['income_kopeks'] / user_stats['active_users']
    
    text = texts.t("ADMIN_STATS_SUMMARY_TITLE", "📊 <b>System summary</b>") + "\n\n"
    text += texts.t("ADMIN_STATS_SUMMARY_USERS", "<b>Users:</b>") + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_USERS_TOTAL", "- Total: {count}").format(count=user_stats['total_users']) + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_USERS_ACTIVE", "- Active: {count}").format(count=user_stats['active_users']) + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_USERS_NEW_MONTH", "- New this month: {count}").format(count=user_stats['new_month']) + "\n\n"
    text += texts.t("ADMIN_STATS_SUMMARY_SUBS", "<b>Subscriptions:</b>") + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_SUBS_ACTIVE", "- Active: {count}").format(count=sub_stats['active_subscriptions']) + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_SUBS_PAID", "- Paid: {count}").format(count=sub_stats['paid_subscriptions']) + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_SUBS_CONVERSION", "- Conversion: {rate}").format(rate=format_percentage(conversion_rate)) + "\n\n"
    text += texts.t("ADMIN_STATS_SUMMARY_FINANCE", "<b>Finances (month):</b>") + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_FINANCE_INCOME", "- Revenue: {amount}").format(amount=settings.format_price(revenue_stats['totals']['income_kopeks'])) + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_FINANCE_ARPU", "- ARPU: {amount}").format(amount=settings.format_price(int(arpu))) + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_FINANCE_TXS", "- Transactions: {count}").format(count=sum(data['count'] for data in revenue_stats['by_type'].values())) + "\n\n"
    text += texts.t("ADMIN_STATS_SUMMARY_GROWTH", "<b>Growth:</b>") + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_GROWTH_USERS", "- Users: +{count} this month").format(count=user_stats['new_month']) + "\n"
    text += texts.t("ADMIN_STATS_SUMMARY_GROWTH_SALES", "- Sales: +{count} this month").format(count=sub_stats['purchased_month']) + "\n\n"
    text += texts.t("ADMIN_STATS_UPDATED_AT", "<b>Updated:</b> {time}").format(time=current_time)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=texts.t("ADMIN_STATS_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_stats_summary")],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_statistics")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer(texts.t("ADMIN_STATS_REFRESHED", "✅ Statistics refreshed"))
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.answer(texts.t("ADMIN_STATS_DATA_CURRENT", "📊 Data is current"), show_alert=False)
        else:
            logger.error(f"Error updating summary statistics: {e}")
            await callback.answer(texts.t("ADMIN_STATS_ERROR_UPDATE", "❌ Data update error"), show_alert=True)

@admin_required
@error_handler
async def show_revenue_by_period(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    period = callback.data.split('_')[-1]
    
    period_map = {
        "today": 1,
        "yesterday": 1,
        "week": 7,
        "month": 30,
        "all": 365
    }
    
    days = period_map.get(period, 30)
    revenue_data = await get_revenue_by_period(db, days)
    
    if period == "yesterday":
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        revenue_data = [r for r in revenue_data if r['date'] == yesterday]
    elif period == "today":
        today = datetime.utcnow().date()
        revenue_data = [r for r in revenue_data if r['date'] == today]
    
    total_revenue = sum(r['amount_kopeks'] for r in revenue_data)
    avg_daily = total_revenue / len(revenue_data) if revenue_data else 0
    texts = get_texts(db_user.language)
    
    text = texts.t("ADMIN_STATS_PERIOD_TITLE", "📈 <b>Revenue for period: {period}</b>").format(period=period) + "\n\n"
    text += texts.t("ADMIN_STATS_PERIOD_SUMMARY", "<b>Summary:</b>") + "\n"
    text += texts.t("ADMIN_STATS_PERIOD_TOTAL", "- Total revenue: {amount}").format(amount=settings.format_price(total_revenue)) + "\n"
    text += texts.t("ADMIN_STATS_PERIOD_DAYS", "- Days with data: {count}").format(count=len(revenue_data)) + "\n"
    text += texts.t("ADMIN_STATS_PERIOD_DAILY_AVG", "- Average daily revenue: {amount}").format(amount=settings.format_price(int(avg_daily))) + "\n\n"
    text += texts.t("ADMIN_STATS_PERIOD_BY_DAYS", "<b>By days:</b>") + "\n"
    
    for revenue in revenue_data[-10:]:
        text += f"• {revenue['date'].strftime('%d.%m')}: {settings.format_price(revenue['amount_kopeks'])}\n"
    
    if len(revenue_data) > 10:
        text += texts.t("ADMIN_STATS_PERIOD_MORE_DAYS", "... and {count} more days").format(count=len(revenue_data) - 10)
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_STATS_BTN_OTHER_PERIOD", "📊 Other period"), callback_data="admin_revenue_period")],
            [types.InlineKeyboardButton(text=texts.t("ADMIN_STATS_BTN_TO_REVENUE", "⬅️ To revenue"), callback_data="admin_stats_revenue")]
        ])
    )
    await callback.answer()


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_statistics_menu, F.data == "admin_statistics")
    dp.callback_query.register(show_users_statistics, F.data == "admin_stats_users")
    dp.callback_query.register(show_subscriptions_statistics, F.data == "admin_stats_subs")
    dp.callback_query.register(show_revenue_statistics, F.data == "admin_stats_revenue")
    dp.callback_query.register(show_referral_statistics, F.data == "admin_stats_referrals")
    dp.callback_query.register(show_summary_statistics, F.data == "admin_stats_summary")
    dp.callback_query.register(show_revenue_by_period, F.data.startswith("period_"))
    
    periods = ["today", "yesterday", "week", "month", "all"]
    for period in periods:
        dp.callback_query.register(
            show_revenue_by_period,
            F.data == f"period_{period}"
        )
