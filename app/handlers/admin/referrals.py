import logging
from aiogram import Dispatcher, types, F
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from app.config import settings
from app.database.models import User
from app.localization.texts import get_texts
from app.database.crud.referral import get_referral_statistics, get_user_referral_stats
from app.database.crud.user import get_user_by_id
from app.utils.decorators import admin_required, error_handler

logger = logging.getLogger(__name__)


@admin_required
@error_handler
async def show_referral_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    try:
        stats = await get_referral_statistics(db)
        
        avg_per_referrer = 0
        if stats.get('active_referrers', 0) > 0:
            avg_per_referrer = stats.get('total_paid_kopeks', 0) / stats['active_referrers']
        
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        texts = get_texts(db_user.language)
        
        text = texts.t("ADMIN_REFERRAL_TITLE", "🤝 <b>Referral statistics</b>") + "\n\n"
        text += texts.t("ADMIN_REFERRAL_GENERAL_METRICS", "<b>General metrics:</b>") + "\n"
        text += texts.t("ADMIN_REFERRAL_USERS_WITH_REFERRALS", "- Users with referrals: {count}").format(count=stats.get('users_with_referrals', 0)) + "\n"
        text += texts.t("ADMIN_REFERRAL_ACTIVE_REFERRERS", "- Active referrers: {count}").format(count=stats.get('active_referrers', 0)) + "\n"
        text += texts.t("ADMIN_REFERRAL_TOTAL_PAID", "- Total paid: {amount}").format(amount=settings.format_price(stats.get('total_paid_kopeks', 0))) + "\n\n"
        text += texts.t("ADMIN_REFERRAL_PERIOD_TITLE", "<b>Period earnings:</b>") + "\n"
        text += texts.t("ADMIN_REFERRAL_TODAY", "- Today: {amount}").format(amount=settings.format_price(stats.get('today_earnings_kopeks', 0))) + "\n"
        text += texts.t("ADMIN_REFERRAL_WEEK", "- This week: {amount}").format(amount=settings.format_price(stats.get('week_earnings_kopeks', 0))) + "\n"
        text += texts.t("ADMIN_REFERRAL_MONTH", "- This month: {amount}").format(amount=settings.format_price(stats.get('month_earnings_kopeks', 0))) + "\n\n"
        text += texts.t("ADMIN_REFERRAL_AVERAGES", "<b>Averages:</b>") + "\n"
        text += texts.t("ADMIN_REFERRAL_PER_REFERRER", "- Per referrer: {amount}").format(amount=settings.format_price(int(avg_per_referrer))) + "\n\n"
        text += texts.t("ADMIN_REFERRAL_TOP_5", "<b>Top 5 referrers:</b>") + "\n"
        
        top_referrers = stats.get('top_referrers', [])
        if top_referrers:
            for i, referrer in enumerate(top_referrers[:5], 1):
                earned = referrer.get('total_earned_kopeks', 0)
                count = referrer.get('referrals_count', 0)
                user_id = referrer.get('user_id', 'N/A')
                
                if count > 0:
                    text += texts.t("ADMIN_REFERRAL_TOP_ITEM", "{i}. ID {user_id}: {amount} ({count} ref.)").format(
                        i=i, user_id=user_id, amount=settings.format_price(earned), count=count
                    ) + "\n"
                else:
                    logger.warning(f"Referrer {user_id} has {count} referrals but is in top")
        else:
            text += texts.t("ADMIN_REFERRAL_NO_DATA", "No data") + "\n"
        
        text += "\n" + texts.t("ADMIN_REFERRAL_SETTINGS_TITLE", "<b>Referral system settings:</b>") + "\n"
        text += texts.t("ADMIN_REFERRAL_MIN_TOPUP", "- Minimum top-up: {amount}").format(amount=settings.format_price(settings.REFERRAL_MINIMUM_TOPUP_KOPEKS)) + "\n"
        text += texts.t("ADMIN_REFERRAL_FIRST_TOPUP_BONUS", "- First top-up bonus: {amount}").format(amount=settings.format_price(settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS)) + "\n"
        text += texts.t("ADMIN_REFERRAL_INVITER_BONUS", "- Inviter bonus: {amount}").format(amount=settings.format_price(settings.REFERRAL_INVITER_BONUS_KOPEKS)) + "\n"
        text += texts.t("ADMIN_REFERRAL_COMMISSION", "- Purchase commission: {percent}%").format(percent=settings.REFERRAL_COMMISSION_PERCENT) + "\n"
        notifications_status = texts.t("ADMIN_REFERRAL_NOTIFICATIONS_ENABLED", "✅ Enabled") if settings.REFERRAL_NOTIFICATIONS_ENABLED else texts.t("ADMIN_REFERRAL_NOTIFICATIONS_DISABLED", "❌ Disabled")
        text += texts.t("ADMIN_REFERRAL_NOTIFICATIONS", "- Notifications: {status}").format(status=notifications_status) + "\n\n"
        text += texts.t("ADMIN_REFERRAL_UPDATED_AT", "<i>🕐 Updated: {time}</i>").format(time=current_time)
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_REFERRAL_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_referrals")],
            [types.InlineKeyboardButton(text=texts.t("ADMIN_REFERRAL_BTN_TOP", "👥 Top referrers"), callback_data="admin_referrals_top")],
            [types.InlineKeyboardButton(text=texts.t("ADMIN_REFERRAL_BTN_SETTINGS", "⚙️ Settings"), callback_data="admin_referrals_settings")],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")]
        ])
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(texts.t("ADMIN_REFERRAL_REFRESHED", "Refreshed"))
        except Exception as edit_error:
            if "message is not modified" in str(edit_error):
                await callback.answer(texts.t("ADMIN_REFERRAL_DATA_CURRENT", "Data is current"))
            else:
                logger.error(f"Error editing message: {edit_error}")
                await callback.answer(texts.t("ADMIN_REFERRAL_ERROR_UPDATE", "Update error"))
        
    except Exception as e:
        logger.error(f"Error in show_referral_statistics: {e}", exc_info=True)
        texts = get_texts(db_user.language)
        
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        text = texts.t("ADMIN_REFERRAL_TITLE", "🤝 <b>Referral statistics</b>") + "\n\n"
        text += texts.t("ADMIN_REFERRAL_ERROR_TITLE", "❌ <b>Data loading error</b>") + "\n\n"
        text += texts.t("ADMIN_REFERRAL_CURRENT_SETTINGS", "<b>Current settings:</b>") + "\n"
        text += texts.t("ADMIN_REFERRAL_MIN_TOPUP", "- Minimum top-up: {amount}").format(amount=settings.format_price(settings.REFERRAL_MINIMUM_TOPUP_KOPEKS)) + "\n"
        text += texts.t("ADMIN_REFERRAL_FIRST_TOPUP_BONUS", "- First top-up bonus: {amount}").format(amount=settings.format_price(settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS)) + "\n"
        text += texts.t("ADMIN_REFERRAL_INVITER_BONUS", "- Inviter bonus: {amount}").format(amount=settings.format_price(settings.REFERRAL_INVITER_BONUS_KOPEKS)) + "\n"
        text += texts.t("ADMIN_REFERRAL_COMMISSION", "- Purchase commission: {percent}%").format(percent=settings.REFERRAL_COMMISSION_PERCENT) + "\n\n"
        text += texts.t("ADMIN_REFERRAL_UPDATED_AT", "<i>🕐 Updated: {time}</i>").format(time=current_time)
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_REFERRAL_BTN_RETRY", "🔄 Retry"), callback_data="admin_referrals")],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")]
        ])
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except:
            pass
        await callback.answer(texts.t("ADMIN_REFERRAL_ERROR_OCCURRED", "Error loading statistics"))


@admin_required
@error_handler
async def show_top_referrers(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    try:
        stats = await get_referral_statistics(db)
        top_referrers = stats.get('top_referrers', [])
        texts = get_texts(db_user.language)
        
        text = texts.t("ADMIN_REFERRAL_TOP_TITLE", "🏆 <b>Top referrers</b>") + "\n\n"
        
        if top_referrers:
            for i, referrer in enumerate(top_referrers[:20], 1): 
                earned = referrer.get('total_earned_kopeks', 0)
                count = referrer.get('referrals_count', 0)
                display_name = referrer.get('display_name', 'N/A')
                username = referrer.get('username', '')
                telegram_id = referrer.get('telegram_id', 'N/A')
                
                if username:
                    display_text = f"@{username} (ID{telegram_id})"
                elif display_name and display_name != f"ID{telegram_id}":
                    display_text = f"{display_name} (ID{telegram_id})"
                else:
                    display_text = f"ID{telegram_id}"
                
                emoji = ""
                if i == 1:
                    emoji = "🥇 "
                elif i == 2:
                    emoji = "🥈 "
                elif i == 3:
                    emoji = "🥉 "
                
                text += texts.t("ADMIN_REFERRAL_TOP_ITEM_FULL", "{emoji}{i}. {display}\n   💰 {amount} | 👥 {count} ref.").format(
                    emoji=emoji, i=i, display=display_text, amount=settings.format_price(earned), count=count
                ) + "\n\n"
        else:
            text += texts.t("ADMIN_REFERRAL_NO_REFERRERS", "No referrer data") + "\n"
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_REFERRAL_BTN_TO_STATS", "⬅️ To statistics"), callback_data="admin_referrals")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in show_top_referrers: {e}", exc_info=True)
        texts = get_texts(db_user.language)
        await callback.answer(texts.t("ADMIN_REFERRAL_ERROR_TOP", "Error loading top referrers"))


@admin_required
@error_handler
async def show_referral_settings(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    text = texts.t("ADMIN_REFERRAL_SETTINGS_HEADER", "⚙️ <b>Referral system settings</b>") + "\n\n"
    text += texts.t("ADMIN_REFERRAL_BONUSES_TITLE", "<b>Bonuses and rewards:</b>") + "\n"
    text += texts.t("ADMIN_REFERRAL_BONUSES_MIN_TOPUP", "• Minimum top-up for participation: {amount}").format(amount=settings.format_price(settings.REFERRAL_MINIMUM_TOPUP_KOPEKS)) + "\n"
    text += texts.t("ADMIN_REFERRAL_BONUSES_FIRST_TOPUP", "• Referral first top-up bonus: {amount}").format(amount=settings.format_price(settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS)) + "\n"
    text += texts.t("ADMIN_REFERRAL_BONUSES_INVITER", "• Inviter bonus for first top-up: {amount}").format(amount=settings.format_price(settings.REFERRAL_INVITER_BONUS_KOPEKS)) + "\n\n"
    text += texts.t("ADMIN_REFERRAL_COMMISSIONS_TITLE", "<b>Commissions:</b>") + "\n"
    text += texts.t("ADMIN_REFERRAL_COMMISSIONS_PERCENT", "• Percent from each referral purchase: {percent}%").format(percent=settings.REFERRAL_COMMISSION_PERCENT) + "\n\n"
    text += texts.t("ADMIN_REFERRAL_NOTIFICATIONS_TITLE", "<b>Notifications:</b>") + "\n"
    notifications_status = texts.t("ADMIN_REFERRAL_NOTIFICATIONS_ENABLED", "✅ Enabled") if settings.REFERRAL_NOTIFICATIONS_ENABLED else texts.t("ADMIN_REFERRAL_NOTIFICATIONS_DISABLED", "❌ Disabled")
    text += texts.t("ADMIN_REFERRAL_NOTIFICATIONS_STATUS", "• Status: {status}").format(status=notifications_status) + "\n"
    text += texts.t("ADMIN_REFERRAL_NOTIFICATIONS_ATTEMPTS", "• Send attempts: {attempts}").format(attempts=getattr(settings, 'REFERRAL_NOTIFICATION_RETRY_ATTEMPTS', 3)) + "\n\n"
    text += texts.t("ADMIN_REFERRAL_SETTINGS_HINT", "<i>💡 To change settings, edit the .env file and restart the bot</i>")
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=texts.t("ADMIN_REFERRAL_BTN_TO_STATS", "⬅️ To statistics"), callback_data="admin_referrals")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_referral_statistics, F.data == "admin_referrals")
    dp.callback_query.register(show_top_referrers, F.data == "admin_referrals_top")
    dp.callback_query.register(show_referral_settings, F.data == "admin_referrals_settings")
