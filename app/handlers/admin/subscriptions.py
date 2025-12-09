import logging
from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.states import AdminStates
from app.database.models import User
from app.keyboards.admin import get_admin_subscriptions_keyboard
from app.localization.texts import get_texts
from app.database.crud.subscription import (
    get_expiring_subscriptions, get_subscriptions_statistics, get_expired_subscriptions,
    get_all_subscriptions
)
from app.services.subscription_service import SubscriptionService
from app.utils.decorators import admin_required, error_handler
from app.utils.formatters import format_datetime, format_time_ago


def get_country_flag(country_name: str) -> str:
    flags = {
        'USA': '🇺🇸', 'United States': '🇺🇸', 'US': '🇺🇸',
        'Germany': '🇩🇪', 'DE': '🇩🇪', 'Deutschland': '🇩🇪',
        'Netherlands': '🇳🇱', 'NL': '🇳🇱', 'Holland': '🇳🇱',
        'United Kingdom': '🇬🇧', 'UK': '🇬🇧', 'GB': '🇬🇧',
        'Japan': '🇯🇵', 'JP': '🇯🇵',
        'France': '🇫🇷', 'FR': '🇫🇷',
        'Canada': '🇨🇦', 'CA': '🇨🇦',
        'Russia': '🇷🇺', 'RU': '🇷🇺',
        'Singapore': '🇸🇬', 'SG': '🇸🇬',
    }
    return flags.get(country_name, '🌍')


logger = logging.getLogger(__name__)


async def get_users_by_countries(db: AsyncSession) -> dict:
    try:
        result = await db.execute(
            select(User.preferred_location, func.count(User.id))
            .where(User.preferred_location.isnot(None))
            .group_by(User.preferred_location)
        )
        
        stats = {}
        for location, count in result.fetchall():
            if location:
                stats[location] = count
        
        return stats
    except Exception as e:
        logger.error(f"Error getting country statistics: {e}")
        return {}


@admin_required
@error_handler
async def show_subscriptions_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    stats = await get_subscriptions_statistics(db)
    
    text = f"""
{texts.t("ADMIN_SUBS_MENU_TITLE", "📱 <b>Subscription Management</b>")}

{texts.t("ADMIN_SUBS_STATS_TITLE", "📊 <b>Statistics:</b>")}
- {texts.t("ADMIN_SUBS_TOTAL", "Total")}: {stats['total_subscriptions']}
- {texts.t("ADMIN_SUBS_ACTIVE", "Active")}: {stats['active_subscriptions']}
- {texts.t("ADMIN_SUBS_PAID", "Paid")}: {stats['paid_subscriptions']}
- {texts.t("ADMIN_SUBS_TRIAL", "Trial")}: {stats['trial_subscriptions']}

{texts.t("ADMIN_SUBS_SALES_TITLE", "📈 <b>Sales:</b>")}
- {texts.t("ADMIN_SUBS_TODAY", "Today")}: {stats['purchased_today']}
- {texts.t("ADMIN_SUBS_WEEK", "This week")}: {stats['purchased_week']}
- {texts.t("ADMIN_SUBS_MONTH", "This month")}: {stats['purchased_month']}

{texts.t("ADMIN_SUBS_SELECT_ACTION", "Select an action:")}
"""
    
    keyboard = [
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_SUBS_BUTTON_LIST", "📋 Subscription list"), callback_data="admin_subs_list"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_SUBS_BUTTON_EXPIRING", "⏰ Expiring"), callback_data="admin_subs_expiring")
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_SUBS_BUTTON_STATS", "📊 Statistics"), callback_data="admin_subs_stats"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_SUBS_BUTTON_GEOGRAPHY", "🌍 Geography"), callback_data="admin_subs_countries")
        ],
        [
            types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")
        ]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_subscriptions_list(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    page: int = 1
):
    texts = get_texts(db_user.language)
    subscriptions, total_count = await get_all_subscriptions(db, page=page, limit=10)
    total_pages = (total_count + 9) // 10 
    
    if not subscriptions:
        text = f"{texts.t('ADMIN_SUBS_LIST_TITLE', '📱 <b>Subscription List</b>')}\n\n{texts.t('ADMIN_SUBS_NOT_FOUND', '❌ No subscriptions found.')}"
    else:
        text = f"{texts.t('ADMIN_SUBS_LIST_TITLE', '📱 <b>Subscription List</b>')}\n\n"
        text += f"📊 {texts.t('ADMIN_SUBS_TOTAL', 'Total')}: {total_count} | {texts.t('ADMIN_SUBS_PAGE', 'Page')}: {page}/{total_pages}\n\n"
        
        for i, sub in enumerate(subscriptions, 1 + (page - 1) * 10):
            user_info = f"ID{sub.user.telegram_id}" if sub.user else texts.t("ADMIN_SUBS_UNKNOWN", "Unknown")
            sub_type = "🎁" if sub.is_trial else "💎"
            status = texts.t("ADMIN_SUBS_STATUS_ACTIVE", "✅ Active") if sub.is_active else texts.t("ADMIN_SUBS_STATUS_INACTIVE", "❌ Inactive")
            
            text += f"{i}. {sub_type} {user_info}\n"
            text += f"   {status} | {texts.t('ADMIN_SUBS_UNTIL', 'Until')}: {format_datetime(sub.end_date)}\n"
            if sub.device_limit > 0:
                text += f"   📱 {texts.t('ADMIN_SUBS_DEVICES', 'Devices')}: {sub.device_limit}\n"
            text += "\n"
    
    keyboard = []
    
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(types.InlineKeyboardButton(
                text="⬅️", callback_data=f"admin_subs_list_page_{page-1}"
            ))
        
        nav_row.append(types.InlineKeyboardButton(
            text=f"{page}/{total_pages}", callback_data="current_page"
        ))
        
        if page < total_pages:
            nav_row.append(types.InlineKeyboardButton(
                text="➡️", callback_data=f"admin_subs_list_page_{page+1}"
            ))
        
        keyboard.append(nav_row)
    
    keyboard.extend([
        [types.InlineKeyboardButton(text=texts.t("ADMIN_SUBS_BUTTON_REFRESH", "🔄 Refresh"), callback_data="admin_subs_list")],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_subscriptions")]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_expiring_subscriptions(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    expiring_3d = await get_expiring_subscriptions(db, 3)
    expiring_1d = await get_expiring_subscriptions(db, 1)
    expired = await get_expired_subscriptions(db)
    
    text = f"""
{texts.t("ADMIN_SUBS_EXPIRING_TITLE", "⏰ <b>Expiring Subscriptions</b>")}

{texts.t("ADMIN_SUBS_STATS_TITLE", "📊 <b>Statistics:</b>")}
- {texts.t("ADMIN_SUBS_EXPIRING_IN_3_DAYS", "Expiring in 3 days")}: {len(expiring_3d)}
- {texts.t("ADMIN_SUBS_EXPIRING_TOMORROW", "Expiring tomorrow")}: {len(expiring_1d)}
- {texts.t("ADMIN_SUBS_EXPIRED", "Already expired")}: {len(expired)}

<b>{texts.t("ADMIN_SUBS_EXPIRING_IN_3_DAYS", "Expiring in 3 days")}:</b>
"""
    
    for sub in expiring_3d[:5]:
        user_info = f"ID{sub.user.telegram_id}" if sub.user else texts.t("ADMIN_SUBS_UNKNOWN", "Unknown")
        sub_type = "🎁" if sub.is_trial else "💎"
        text += f"{sub_type} {user_info} - {format_datetime(sub.end_date)}\n"
    
    if len(expiring_3d) > 5:
        text += f"... {texts.t('ADMIN_SUBS_AND_MORE', 'and {count} more').format(count=len(expiring_3d) - 5)}\n"
    
    text += f"\n<b>{texts.t('ADMIN_SUBS_EXPIRING_TOMORROW', 'Expiring tomorrow')}:</b>\n"
    for sub in expiring_1d[:5]:
        user_info = f"ID{sub.user.telegram_id}" if sub.user else texts.t("ADMIN_SUBS_UNKNOWN", "Unknown")
        sub_type = "🎁" if sub.is_trial else "💎"
        text += f"{sub_type} {user_info} - {format_datetime(sub.end_date)}\n"
    
    if len(expiring_1d) > 5:
        text += f"... {texts.t('ADMIN_SUBS_AND_MORE', 'and {count} more').format(count=len(expiring_1d) - 5)}\n"
    
    keyboard = [
        [types.InlineKeyboardButton(text=texts.t("ADMIN_SUBS_BUTTON_SEND_REMINDERS", "📨 Send reminders"), callback_data="admin_send_expiry_reminders")],
        [types.InlineKeyboardButton(text=texts.t("ADMIN_SUBS_BUTTON_REFRESH", "🔄 Refresh"), callback_data="admin_subs_expiring")],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_subscriptions")]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_subscriptions_stats(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    stats = await get_subscriptions_statistics(db)
    
    expiring_3d = await get_expiring_subscriptions(db, 3)
    expiring_7d = await get_expiring_subscriptions(db, 7)
    expired = await get_expired_subscriptions(db)
    
    text = f"""
{texts.t("ADMIN_SUBS_DETAILED_STATS_TITLE", "📊 <b>Detailed Subscription Statistics</b>")}

<b>{texts.t("ADMIN_SUBS_GENERAL_INFO", "📱 General Information:")}</b>
• {texts.t("ADMIN_SUBS_TOTAL_SUBS", "Total subscriptions")}: {stats['total_subscriptions']}
• {texts.t("ADMIN_SUBS_ACTIVE", "Active")}: {stats['active_subscriptions']}
• {texts.t("ADMIN_SUBS_INACTIVE", "Inactive")}: {stats['total_subscriptions'] - stats['active_subscriptions']}

<b>{texts.t("ADMIN_SUBS_BY_TYPE", "💎 By Type:")}</b>
• {texts.t("ADMIN_SUBS_PAID", "Paid")}: {stats['paid_subscriptions']}
• {texts.t("ADMIN_SUBS_TRIAL", "Trial")}: {stats['trial_subscriptions']}

<b>{texts.t("ADMIN_SUBS_SALES_TITLE", "📈 Sales:")}</b>
• {texts.t("ADMIN_SUBS_TODAY", "Today")}: {stats['purchased_today']}
• {texts.t("ADMIN_SUBS_WEEK", "This week")}: {stats['purchased_week']}  
• {texts.t("ADMIN_SUBS_MONTH", "This month")}: {stats['purchased_month']}

<b>{texts.t("ADMIN_SUBS_EXPIRATION", "⏰ Expiration:")}</b>
• {texts.t("ADMIN_SUBS_EXPIRING_IN_3_DAYS", "Expiring in 3 days")}: {len(expiring_3d)}
• {texts.t("ADMIN_SUBS_EXPIRING_IN_7_DAYS", "Expiring in 7 days")}: {len(expiring_7d)}
• {texts.t("ADMIN_SUBS_EXPIRED", "Already expired")}: {len(expired)}

<b>{texts.t("ADMIN_SUBS_CONVERSION", "💰 Conversion:")}</b>
• {texts.t("ADMIN_SUBS_TRIAL_TO_PAID", "Trial to paid")}: {stats.get('trial_to_paid_conversion', 0)}%
• {texts.t("ADMIN_SUBS_RENEWALS", "Renewals")}: {stats.get('renewals_count', 0)}
"""
    
    keyboard = [
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_subscriptions")]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_countries_management(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    try:
        from app.services.remnawave_service import RemnaWaveService
        remnawave_service = RemnaWaveService()
        
        nodes_data = await remnawave_service.get_all_nodes()
        squads_data = await remnawave_service.get_all_squads() 
        
        text = f"{texts.t('ADMIN_SUBS_COUNTRIES_TITLE', '🌍 <b>Country Management</b>')}\n\n"
        
        if nodes_data:
            text += f"<b>{texts.t('ADMIN_SUBS_AVAILABLE_SERVERS', 'Available Servers:')}</b>\n"
            countries = {}
            
            for node in nodes_data:
                country_code = node.get('country_code', 'XX')  
                country_name = country_code
                
                if country_name not in countries:
                    countries[country_name] = []
                countries[country_name].append(node)
            
            for country, nodes in countries.items():
                active_nodes = len([n for n in nodes if n.get('is_connected') and n.get('is_node_online')])
                total_nodes = len(nodes)
                
                country_flag = get_country_flag(country)
                text += f"{country_flag} {country}: {active_nodes}/{total_nodes} {texts.t('ADMIN_SUBS_SERVERS', 'servers')}\n"
                
                total_users_online = sum(n.get('users_online', 0) or 0 for n in nodes)
                if total_users_online > 0:
                    text += f"   👥 {texts.t('ADMIN_SUBS_USERS_ONLINE', 'Users online')}: {total_users_online}\n"
        else:
            text += f"❌ {texts.t('ADMIN_SUBS_FAILED_LOAD_SERVERS', 'Failed to load server data')}\n"
        
        if squads_data:
            text += f"\n<b>{texts.t('ADMIN_SUBS_TOTAL_SQUADS', 'Total squads')}:</b> {len(squads_data)}\n"
            
            total_members = sum(squad.get('members_count', 0) for squad in squads_data)
            text += f"<b>{texts.t('ADMIN_SUBS_SQUAD_MEMBERS', 'Members in squads')}:</b> {total_members}\n"
            
            text += f"\n<b>{texts.t('ADMIN_SUBS_SQUADS', 'Squads')}:</b>\n"
            for squad in squads_data[:5]: 
                name = squad.get('name', texts.t("ADMIN_SUBS_UNKNOWN", "Unknown"))
                members = squad.get('members_count', 0)
                inbounds = squad.get('inbounds_count', 0)
                text += f"• {name}: {members} {texts.t('ADMIN_SUBS_MEMBERS', 'members')}, {inbounds} inbound(s)\n"
            
            if len(squads_data) > 5:
                text += f"... {texts.t('ADMIN_SUBS_AND_MORE', 'and {count} more').format(count=len(squads_data) - 5)} {texts.t('ADMIN_SUBS_SQUADS', 'squads')}\n"
        
        user_stats = await get_users_by_countries(db)
        if user_stats:
            text += f"\n<b>{texts.t('ADMIN_SUBS_USERS_BY_REGION', 'Users by Region:')}</b>\n"
            for country, count in user_stats.items():
                country_flag = get_country_flag(country)
                text += f"{country_flag} {country}: {count} {texts.t('ADMIN_SUBS_USERS', 'users')}\n"
        
    except Exception as e:
        logger.error(f"Error getting country data: {e}")
        text = f"""
{texts.t('ADMIN_SUBS_COUNTRIES_TITLE', '🌍 <b>Country Management</b>')}

❌ <b>{texts.t('ADMIN_SUBS_LOAD_ERROR', 'Data Loading Error')}</b>
{texts.t('ADMIN_SUBS_FAILED_GET_SERVER_INFO', 'Failed to retrieve server information.')}

{texts.t('ADMIN_SUBS_CHECK_REMNAWAVE', 'Check connection to RemnaWave API.')}

<b>{texts.t('ADMIN_SUBS_ERROR_DETAILS', 'Error details')}:</b> {str(e)}
"""
    
    keyboard = [
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_SUBS_BUTTON_REFRESH", "🔄 Refresh"), callback_data="admin_subs_countries")
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_SUBS_BUTTON_NODE_STATS", "📊 Node statistics"), callback_data="admin_rw_nodes"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_SUBS_BUTTON_SQUADS", "🔧 Squads"), callback_data="admin_rw_squads")
        ],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_subscriptions")]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def send_expiry_reminders(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        f"{texts.t('ADMIN_SUBS_SENDING_REMINDERS', '📨 Sending reminders...')}\n\n{texts.t('ADMIN_SUBS_WAIT_MESSAGE', 'Please wait, this may take some time.')}",
        reply_markup=None
    )
    
    expiring_subs = await get_expiring_subscriptions(db, 1)
    sent_count = 0
    
    for subscription in expiring_subs:
        if subscription.user:
            try:
                user = subscription.user
                user_texts = get_texts(user.language)
                days_left = max(1, subscription.days_left)
                
                reminder_text = f"""
⚠️ <b>{user_texts.t('ADMIN_SUBS_REMINDER_TITLE', 'Subscription Expiring!')}</b>

{user_texts.t('ADMIN_SUBS_REMINDER_MESSAGE', 'Your subscription expires in {days} day(s).').format(days=days_left)}

{user_texts.t('ADMIN_SUBS_REMINDER_HINT', 'Don\'t forget to renew your subscription to avoid losing access to servers.')}

💎 {user_texts.t('ADMIN_SUBS_RENEW_HINT', 'You can renew your subscription in the main menu.')}
"""
                
                await callback.bot.send_message(
                    chat_id=user.telegram_id,
                    text=reminder_text
                )
                sent_count += 1
                
            except Exception as e:
                logger.error(f"Error sending reminder to user {subscription.user_id}: {e}")
    
    await callback.message.edit_text(
        texts.t("ADMIN_SUBS_REMINDERS_SENT", "✅ Reminders sent: {sent} of {total}").format(sent=sent_count, total=len(expiring_subs)),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_subs_expiring")]
        ])
    )
    await callback.answer()


@admin_required
@error_handler  
async def handle_subscriptions_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    page = int(callback.data.split('_')[-1])
    await show_subscriptions_list(callback, db_user, db, page)


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_subscriptions_menu, F.data == "admin_subscriptions")
    dp.callback_query.register(show_subscriptions_list, F.data == "admin_subs_list")
    dp.callback_query.register(show_expiring_subscriptions, F.data == "admin_subs_expiring")
    dp.callback_query.register(show_subscriptions_stats, F.data == "admin_subs_stats")
    dp.callback_query.register(show_countries_management, F.data == "admin_subs_countries")
    dp.callback_query.register(send_expiry_reminders, F.data == "admin_send_expiry_reminders")
    
    dp.callback_query.register(
        handle_subscriptions_pagination, 
        F.data.startswith("admin_subs_list_page_")
    )
