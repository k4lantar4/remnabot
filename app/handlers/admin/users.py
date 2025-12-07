import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from aiogram import Dispatcher, types, F
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.states import AdminStates
from app.database.models import User, UserStatus, Subscription, SubscriptionStatus, TransactionType 
from app.database.crud.user import (
    get_user_by_id,
    get_user_by_telegram_id,
    get_user_by_username,
    get_referrals,
)
from app.database.crud.campaign import (
    get_campaign_registration_by_user,
    get_campaign_statistics,
)
from app.keyboards.admin import (
    get_admin_users_keyboard, get_user_management_keyboard,
    get_admin_pagination_keyboard, get_confirmation_keyboard,
    get_admin_users_filters_keyboard, get_user_promo_group_keyboard
)
from app.localization.texts import get_texts
from app.services.user_service import UserService
from app.services.admin_notification_service import AdminNotificationService
from app.database.crud.promo_group import get_promo_groups_with_counts
from app.utils.decorators import admin_required, error_handler
from app.utils.formatters import format_datetime, format_time_ago
from app.utils.user_utils import get_effective_referral_commission_percent
from app.services.remnawave_service import RemnaWaveService
from app.external.remnawave_api import TrafficLimitStrategy
from app.database.crud.server_squad import (
    get_all_server_squads,
    get_server_squad_by_uuid,
    get_server_squad_by_id,
    get_server_ids_by_uuids,
)
from app.services.subscription_service import SubscriptionService
from app.utils.subscription_utils import (
    resolve_hwid_device_limit_for_payload,
)

logger = logging.getLogger(__name__)


@admin_required
@error_handler
async def show_users_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    user_service = UserService()
    stats = await user_service.get_user_statistics(db)
    
    texts = get_texts(db_user.language)
    text = texts.t("ADMIN_USERS_MENU_TITLE", "👥 <b>User Management</b>") + "\n\n"
    text += texts.t("ADMIN_USERS_STATS_HEADER", "📊 <b>Statistics:</b>") + "\n"
    text += texts.t("ADMIN_USERS_TOTAL", "• Total: {count}").format(count=stats['total_users']) + "\n"
    text += texts.t("ADMIN_USERS_ACTIVE", "• Active: {count}").format(count=stats['active_users']) + "\n"
    text += texts.t("ADMIN_USERS_BLOCKED", "• Blocked: {count}").format(count=stats['blocked_users']) + "\n\n"
    text += texts.t("ADMIN_USERS_NEW_HEADER", "📈 <b>New Users:</b>") + "\n"
    text += texts.t("ADMIN_USERS_NEW_TODAY", "• Today: {count}").format(count=stats['new_today']) + "\n"
    text += texts.t("ADMIN_USERS_NEW_WEEK", "• This week: {count}").format(count=stats['new_week']) + "\n"
    text += texts.t("ADMIN_USERS_NEW_MONTH", "• This month: {count}").format(count=stats['new_month']) + "\n\n"
    text += texts.t("ADMIN_SELECT_ACTION", "Select action:") + "\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_users_keyboard(db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_users_filters(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    
    texts = get_texts(db_user.language)
    text = texts.t("ADMIN_USERS_FILTERS_TITLE", "⚙️ <b>User Filters</b>") + "\n\n"
    text += texts.t("ADMIN_USERS_FILTERS_SELECT", "Select filter to display users:") + "\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_users_filters_keyboard(db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_users_list(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    page: int = 1
):
    
    # Reset state since we're in regular list
    await state.set_state(None)
    
    texts = get_texts(db_user.language)
    user_service = UserService()
    users_data = await user_service.get_users_page(db, page=page, limit=10)
    
    if not users_data["users"]:
        await callback.message.edit_text(
            texts.t("ADMIN_USERS_NOT_FOUND", "👥 Users not found"),
            reply_markup=get_admin_users_keyboard(db_user.language)
        )
        await callback.answer()
        return
    
    text = texts.t("ADMIN_USERS_LIST_TITLE", "👥 <b>User List</b> (page {page}/{total})").format(page=page, total=users_data['total_pages']) + "\n\n"
    text += texts.t("ADMIN_USERS_LIST_HINT", "Click on a user to manage:")
    
    keyboard = []
    
    for user in users_data["users"]:
        if user.status == UserStatus.ACTIVE.value:
            status_emoji = "✅"
        elif user.status == UserStatus.BLOCKED.value:
            status_emoji = "🚫"
        else:
            status_emoji = "🗑️"
        
        subscription_emoji = ""
        if user.subscription:
            if user.subscription.is_trial:
                subscription_emoji = "🎁"
            elif user.subscription.is_active:
                subscription_emoji = "💎"
            else:
                subscription_emoji = "⏰"
        else:
            subscription_emoji = "❌"
        
        button_text = f"{status_emoji} {subscription_emoji} {user.full_name}"
        
        if user.balance_kopeks > 0:
            button_text += f" | 💰 {settings.format_price(user.balance_kopeks)}"
        
        button_text += f" | 📅 {format_time_ago(user.created_at, db_user.language)}"
        
        if len(button_text) > 60:
            short_name = user.full_name
            if len(short_name) > 20:
                short_name = short_name[:17] + "..."
            
            button_text = f"{status_emoji} {subscription_emoji} {short_name}"
            if user.balance_kopeks > 0:
                button_text += f" | 💰 {settings.format_price(user.balance_kopeks)}"
        
        keyboard.append([
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin_user_manage_{user.id}"
            )
        ])
    
    if users_data["total_pages"] > 1:
        pagination_row = get_admin_pagination_keyboard(
            users_data["current_page"],
            users_data["total_pages"],
            "admin_users_list",
            "admin_users",
            db_user.language
        ).inline_keyboard[0]
        keyboard.append(pagination_row)
    
    keyboard.extend([
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_SEARCH", "🔍 Search"), callback_data="admin_users_search"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_STATS", "📊 Statistics"), callback_data="admin_users_stats")
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")
        ]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_users_list_by_balance(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    page: int = 1
):
    
    # Set state to track where user came from
    await state.set_state(AdminStates.viewing_user_from_balance_list)
    
    texts = get_texts(db_user.language)
    user_service = UserService()
    users_data = await user_service.get_users_page(db, page=page, limit=10, order_by_balance=True)
    
    if not users_data["users"]:
        await callback.message.edit_text(
            texts.t("ADMIN_USERS_NOT_FOUND", "👥 Users not found"),
            reply_markup=get_admin_users_keyboard(db_user.language)
        )
        await callback.answer()
        return
    
    text = texts.t("ADMIN_USERS_LIST_BY_BALANCE_TITLE", "👥 <b>Users by Balance</b> (page {page}/{total})").format(page=page, total=users_data['total_pages']) + "\n\n"
    text += texts.t("ADMIN_USERS_LIST_HINT", "Click on a user to manage:")
    
    keyboard = []
    
    for user in users_data["users"]:
        if user.status == UserStatus.ACTIVE.value:
            status_emoji = "✅"
        elif user.status == UserStatus.BLOCKED.value:
            status_emoji = "🚫"
        else:
            status_emoji = "🗑️"
        
        subscription_emoji = ""
        if user.subscription:
            if user.subscription.is_trial:
                subscription_emoji = "🎁"
            elif user.subscription.is_active:
                subscription_emoji = "💎"
            else:
                subscription_emoji = "⏰"
        else:
            subscription_emoji = "❌"
        
        button_text = f"{status_emoji} {subscription_emoji} {user.full_name}"
        
        if user.balance_kopeks > 0:
            button_text += f" | 💰 {settings.format_price(user.balance_kopeks)}"
        
        # Add subscription end date if subscription exists
        if user.subscription and user.subscription.end_date:
            days_left = (user.subscription.end_date - datetime.utcnow()).days
            button_text += f" | 📅 {days_left}d"
        
        if len(button_text) > 60:
            short_name = user.full_name
            if len(short_name) > 20:
                short_name = short_name[:17] + "..."
            
            button_text = f"{status_emoji} {subscription_emoji} {short_name}"
            if user.balance_kopeks > 0:
                button_text += f" | 💰 {settings.format_price(user.balance_kopeks)}"
        
        keyboard.append([
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin_user_manage_{user.id}"
            )
        ])
    
    if users_data["total_pages"] > 1:
        pagination_row = get_admin_pagination_keyboard(
            users_data["current_page"],
            users_data["total_pages"],
            "admin_users_balance_list",
            "admin_users",
            db_user.language
        ).inline_keyboard[0]
        keyboard.append(pagination_row)
    
    keyboard.extend([
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_SEARCH", "🔍 Search"), callback_data="admin_users_search"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_STATS", "📊 Statistics"), callback_data="admin_users_stats")
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")
        ]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_users_list_by_traffic(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    page: int = 1
):
    
    await state.set_state(AdminStates.viewing_user_from_traffic_list)

    texts = get_texts(db_user.language)
    user_service = UserService()
    users_data = await user_service.get_users_page(
        db, page=page, limit=10, order_by_traffic=True
    )

    if not users_data["users"]:
        await callback.message.edit_text(
            texts.t("ADMIN_USERS_TRAFFIC_NOT_FOUND", "📶 No users with traffic found"),
            reply_markup=get_admin_users_keyboard(db_user.language)
        )
        await callback.answer()
        return

    text = texts.t("ADMIN_USERS_LIST_BY_TRAFFIC_TITLE", "👥 <b>Users by Traffic Used</b> (page {page}/{total})").format(page=page, total=users_data['total_pages']) + "\n\n"
    text += texts.t("ADMIN_USERS_LIST_HINT", "Click on a user to manage:")

    keyboard = []

    for user in users_data["users"]:
        if user.status == UserStatus.ACTIVE.value:
            status_emoji = "✅"
        elif user.status == UserStatus.BLOCKED.value:
            status_emoji = "🚫"
        else:
            status_emoji = "🗑️"

        if user.subscription:
            sub = user.subscription
            if sub.is_trial:
                subscription_emoji = "🎁"
            elif sub.is_active:
                subscription_emoji = "💎"
            else:
                subscription_emoji = "⏰"
            used = sub.traffic_used_gb or 0.0
            if sub.traffic_limit_gb and sub.traffic_limit_gb > 0:
                limit_display = f"{sub.traffic_limit_gb}"
            else:
                limit_display = "♾️"
            traffic_display = f"{used:.1f}/{limit_display} GB"
        else:
            subscription_emoji = "❌"
            traffic_display = texts.t("ADMIN_USERS_NO_SUBSCRIPTION_SHORT", "no subscription")

        button_text = f"{status_emoji} {subscription_emoji} {user.full_name}"
        button_text += f" | 📶 {traffic_display}"

        if user.balance_kopeks > 0:
            button_text += f" | 💰 {settings.format_price(user.balance_kopeks)}"

        if len(button_text) > 60:
            short_name = user.full_name
            if len(short_name) > 20:
                short_name = short_name[:17] + "..."
            button_text = f"{status_emoji} {subscription_emoji} {short_name}"
            button_text += f" | 📶 {traffic_display}"

        keyboard.append([
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin_user_manage_{user.id}"
            )
        ])

    if users_data["total_pages"] > 1:
        pagination_row = get_admin_pagination_keyboard(
            users_data["current_page"],
            users_data["total_pages"],
            "admin_users_traffic_list",
            "admin_users",
            db_user.language
        ).inline_keyboard[0]
        keyboard.append(pagination_row)

    keyboard.extend([
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_SEARCH", "🔍 Search"), callback_data="admin_users_search"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_STATS", "📊 Statistics"), callback_data="admin_users_stats")
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")
        ]
    ])

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_users_list_by_last_activity(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    page: int = 1
):
    
    await state.set_state(AdminStates.viewing_user_from_last_activity_list)

    texts = get_texts(db_user.language)
    user_service = UserService()
    users_data = await user_service.get_users_page(
        db,
        page=page,
        limit=10,
        order_by_last_activity=True,
    )

    if not users_data["users"]:
        await callback.message.edit_text(
            texts.t("ADMIN_USERS_ACTIVITY_NOT_FOUND", "🕒 No users with activity found"),
            reply_markup=get_admin_users_keyboard(db_user.language)
        )
        await callback.answer()
        return

    text = texts.t("ADMIN_USERS_LIST_BY_ACTIVITY_TITLE", "👥 <b>Users by Activity</b> (page {page}/{total})").format(page=page, total=users_data['total_pages']) + "\n\n"
    text += texts.t("ADMIN_USERS_LIST_HINT", "Click on a user to manage:")

    keyboard = []

    for user in users_data["users"]:
        if user.status == UserStatus.ACTIVE.value:
            status_emoji = "✅"
        elif user.status == UserStatus.BLOCKED.value:
            status_emoji = "🚫"
        else:
            status_emoji = "🗑️"

        activity_display = (
            format_time_ago(user.last_activity, db_user.language)
            if user.last_activity
            else texts.t("ADMIN_USERS_ACTIVITY_UNKNOWN", "unknown")
        )

        subscription_emoji = "❌"
        if user.subscription:
            if user.subscription.is_trial:
                subscription_emoji = "🎁"
            elif user.subscription.is_active:
                subscription_emoji = "💎"
            else:
                subscription_emoji = "⏰"

        button_text = f"{status_emoji} {subscription_emoji} {user.full_name}"
        button_text += f" | 🕒 {activity_display}"

        keyboard.append([
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin_user_manage_{user.id}"
            )
        ])

    if users_data["total_pages"] > 1:
        pagination_row = get_admin_pagination_keyboard(
            users_data["current_page"],
            users_data["total_pages"],
            "admin_users_activity_list",
            "admin_users",
            db_user.language
        ).inline_keyboard[0]
        keyboard.append(pagination_row)

    keyboard.extend([
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_SEARCH", "🔍 Search"), callback_data="admin_users_search"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_STATS", "📊 Statistics"), callback_data="admin_users_stats")
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")
        ]
    ])

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_users_list_by_spending(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    page: int = 1
):
    
    await state.set_state(AdminStates.viewing_user_from_spending_list)

    texts = get_texts(db_user.language)
    user_service = UserService()
    users_data = await user_service.get_users_page(
        db,
        page=page,
        limit=10,
        order_by_total_spent=True,
    )

    users = users_data["users"]
    if not users:
        await callback.message.edit_text(
            texts.t("ADMIN_USERS_SPENDING_NOT_FOUND", "💳 No users with spending found"),
            reply_markup=get_admin_users_keyboard(db_user.language)
        )
        await callback.answer()
        return

    spending_map = await user_service.get_user_spending_stats_map(
        db,
        [user.id for user in users],
    )

    text = texts.t("ADMIN_USERS_LIST_BY_SPENDING_TITLE", "👥 <b>Users by Total Spent</b> (page {page}/{total})").format(page=page, total=users_data['total_pages']) + "\n\n"
    text += texts.t("ADMIN_USERS_LIST_HINT", "Click on a user to manage:")

    keyboard = []

    for user in users:
        stats = spending_map.get(
            user.id,
            {"total_spent": 0, "purchase_count": 0},
        )
        total_spent = stats.get("total_spent", 0)
        purchases = stats.get("purchase_count", 0)

        status_emoji = "✅" if user.status == UserStatus.ACTIVE.value else "🚫" if user.status == UserStatus.BLOCKED.value else "🗑️"

        button_text = (
            f"{status_emoji} {user.full_name}"
            f" | 💳 {settings.format_price(total_spent)}"
            f" | 🛒 {purchases}"
        )

        keyboard.append([
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin_user_manage_{user.id}"
            )
        ])

    if users_data["total_pages"] > 1:
        pagination_row = get_admin_pagination_keyboard(
            users_data["current_page"],
            users_data["total_pages"],
            "admin_users_spending_list",
            "admin_users",
            db_user.language
        ).inline_keyboard[0]
        keyboard.append(pagination_row)

    keyboard.extend([
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_SEARCH", "🔍 Search"), callback_data="admin_users_search"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_STATS", "📊 Statistics"), callback_data="admin_users_stats")
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")
        ]
    ])

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_users_list_by_purchases(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    page: int = 1
):
    
    await state.set_state(AdminStates.viewing_user_from_purchases_list)

    texts = get_texts(db_user.language)
    user_service = UserService()
    users_data = await user_service.get_users_page(
        db,
        page=page,
        limit=10,
        order_by_purchase_count=True,
    )

    users = users_data["users"]
    if not users:
        await callback.message.edit_text(
            texts.t("ADMIN_USERS_PURCHASES_NOT_FOUND", "🛒 No users with purchases found"),
            reply_markup=get_admin_users_keyboard(db_user.language)
        )
        await callback.answer()
        return

    spending_map = await user_service.get_user_spending_stats_map(
        db,
        [user.id for user in users],
    )

    text = texts.t("ADMIN_USERS_LIST_BY_PURCHASES_TITLE", "👥 <b>Users by Purchase Count</b> (page {page}/{total})").format(page=page, total=users_data['total_pages']) + "\n\n"
    text += texts.t("ADMIN_USERS_LIST_HINT", "Click on a user to manage:")

    keyboard = []

    for user in users:
        stats = spending_map.get(
            user.id,
            {"total_spent": 0, "purchase_count": 0},
        )
        total_spent = stats.get("total_spent", 0)
        purchases = stats.get("purchase_count", 0)

        status_emoji = "✅" if user.status == UserStatus.ACTIVE.value else "🚫" if user.status == UserStatus.BLOCKED.value else "🗑️"

        button_text = (
            f"{status_emoji} {user.full_name}"
            f" | 🛒 {purchases}"
            f" | 💳 {settings.format_price(total_spent)}"
        )

        keyboard.append([
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin_user_manage_{user.id}"
            )
        ])

    if users_data["total_pages"] > 1:
        pagination_row = get_admin_pagination_keyboard(
            users_data["current_page"],
            users_data["total_pages"],
            "admin_users_purchases_list",
            "admin_users",
            db_user.language
        ).inline_keyboard[0]
        keyboard.append(pagination_row)

    keyboard.extend([
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_SEARCH", "🔍 Search"), callback_data="admin_users_search"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_STATS", "📊 Statistics"), callback_data="admin_users_stats")
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")
        ]
    ])

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_users_list_by_campaign(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    page: int = 1
):
    
    await state.set_state(AdminStates.viewing_user_from_campaign_list)

    texts = get_texts(db_user.language)
    user_service = UserService()
    users_data = await user_service.get_users_by_campaign_page(
        db,
        page=page,
        limit=10,
    )

    users = users_data.get("users", [])
    campaign_map = users_data.get("campaigns", {})

    if not users:
        await callback.message.edit_text(
            texts.t("ADMIN_USERS_CAMPAIGN_NOT_FOUND", "📢 No users with campaign found"),
            reply_markup=get_admin_users_keyboard(db_user.language)
        )
        await callback.answer()
        return

    text = texts.t("ADMIN_USERS_LIST_BY_CAMPAIGN_TITLE", "👥 <b>Users by Registration Campaign</b> (page {page}/{total})").format(page=page, total=users_data['total_pages']) + "\n\n"
    text += texts.t("ADMIN_USERS_LIST_HINT", "Click on a user to manage:")

    keyboard = []

    for user in users:
        info = campaign_map.get(user.id, {})
        campaign_name = info.get("campaign_name") or texts.t("ADMIN_USERS_NO_CAMPAIGN", "No campaign")
        registered_at = info.get("registered_at")
        registered_display = format_datetime(registered_at) if registered_at else texts.t("ADMIN_USERS_DATE_UNKNOWN", "unknown")

        status_emoji = "✅" if user.status == UserStatus.ACTIVE.value else "🚫" if user.status == UserStatus.BLOCKED.value else "🗑️"

        button_text = (
            f"{status_emoji} {user.full_name}"
            f" | 📢 {campaign_name}"
            f" | 📅 {registered_display}"
        )

        keyboard.append([
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin_user_manage_{user.id}"
            )
        ])

    if users_data["total_pages"] > 1:
        pagination_row = get_admin_pagination_keyboard(
            users_data["current_page"],
            users_data["total_pages"],
            "admin_users_campaign_list",
            "admin_users",
            db_user.language
        ).inline_keyboard[0]
        keyboard.append(pagination_row)

    keyboard.extend([
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_SEARCH", "🔍 Search"), callback_data="admin_users_search"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_USERS_BTN_STATS", "📊 Statistics"), callback_data="admin_users_stats")
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")
        ]
    ])

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()



@admin_required
@error_handler
async def handle_users_list_pagination_fixed(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    try:
        callback_parts = callback.data.split('_')
        page = int(callback_parts[-1]) 
        await show_users_list(callback, db_user, db, state, page)
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing page number: {e}")
        await show_users_list(callback, db_user, db, state, 1)


@admin_required
@error_handler
async def handle_users_balance_list_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    try:
        callback_parts = callback.data.split('_')
        page = int(callback_parts[-1]) 
        await show_users_list_by_balance(callback, db_user, db, state, page)
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing page number: {e}")
        await show_users_list_by_balance(callback, db_user, db, state, 1)


@admin_required
@error_handler
async def handle_users_traffic_list_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    try:
        callback_parts = callback.data.split('_')
        page = int(callback_parts[-1]) 
        await show_users_list_by_traffic(callback, db_user, db, state, page)
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing page number: {e}")
        await show_users_list_by_traffic(callback, db_user, db, state, 1)


@admin_required
@error_handler
async def handle_users_activity_list_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    try:
        callback_parts = callback.data.split('_')
        page = int(callback_parts[-1]) 
        await show_users_list_by_last_activity(callback, db_user, db, state, page)
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing page number: {e}")
        await show_users_list_by_last_activity(callback, db_user, db, state, 1)


@admin_required
@error_handler
async def handle_users_spending_list_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    try:
        callback_parts = callback.data.split('_')
        page = int(callback_parts[-1]) 
        await show_users_list_by_spending(callback, db_user, db, state, page)
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing page number: {e}")
        await show_users_list_by_spending(callback, db_user, db, state, 1)


@admin_required
@error_handler
async def handle_users_purchases_list_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    try:
        callback_parts = callback.data.split('_')
        page = int(callback_parts[-1]) 
        await show_users_list_by_purchases(callback, db_user, db, state, page)
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing page number: {e}")
        await show_users_list_by_purchases(callback, db_user, db, state, 1)


@admin_required
@error_handler
async def handle_users_campaign_list_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    try:
        callback_parts = callback.data.split('_')
        page = int(callback_parts[-1]) 
        await show_users_list_by_campaign(callback, db_user, db, state, page)
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing page number: {e}")
        await show_users_list_by_campaign(callback, db_user, db, state, 1)


@admin_required
@error_handler
async def start_user_search(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_USERS_SEARCH_PROMPT", "🔍 <b>User Search</b>\n\nEnter to search:\n• Telegram ID\n• Username (without @)\n• First or last name\n\nOr press /cancel to cancel"),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data="admin_users")]
        ])
    )
    
    await state.set_state(AdminStates.waiting_for_user_search)
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
    
    from sqlalchemy import select, func, or_

    current_time = datetime.utcnow()

    active_subscription_query = (
        select(func.count(Subscription.id))
        .join(User, Subscription.user_id == User.id)
        .where(
            User.status == UserStatus.ACTIVE.value,
            Subscription.status.in_(
                [
                    SubscriptionStatus.ACTIVE.value,
                    SubscriptionStatus.TRIAL.value,
                ]
            ),
            Subscription.end_date > current_time,
        )
    )
    users_with_subscription = (
        await db.execute(active_subscription_query)
    ).scalar() or 0

    trial_subscription_query = (
        select(func.count(Subscription.id))
        .join(User, Subscription.user_id == User.id)
        .where(
            User.status == UserStatus.ACTIVE.value,
            Subscription.end_date > current_time,
            or_(
                Subscription.status == SubscriptionStatus.TRIAL.value,
                Subscription.is_trial.is_(True),
            ),
        )
    )
    trial_users = (await db.execute(trial_subscription_query)).scalar() or 0

    users_without_subscription = max(
        stats["active_users"] - users_with_subscription,
        0,
    )
    
    avg_balance_result = await db.execute(
        select(func.avg(User.balance_kopeks))
        .where(User.status == UserStatus.ACTIVE.value)
    )
    avg_balance = avg_balance_result.scalar() or 0
    
    texts = get_texts(db_user.language)
    text = texts.t("ADMIN_USERS_DETAILED_STATS", """
📊 <b>Detailed User Statistics</b>

👥 <b>General:</b>
• Total: {total_users}
• Active: {active_users}
• Blocked: {blocked_users}

📱 <b>Subscriptions:</b>
• With active subscription: {with_subscription}
• On trial: {trial_users}
• Without subscription: {without_subscription}

💰 <b>Finances:</b>
• Average balance: {avg_balance}

📈 <b>Registrations:</b>
• Today: {new_today}
• This week: {new_week}
• This month: {new_month}

📊 <b>Activity:</b>
• Subscription conversion: {conversion}%
• Trial share: {trial_share}%
""").format(
        total_users=stats['total_users'],
        active_users=stats['active_users'],
        blocked_users=stats['blocked_users'],
        with_subscription=users_with_subscription,
        trial_users=trial_users,
        without_subscription=users_without_subscription,
        avg_balance=settings.format_price(int(avg_balance)),
        new_today=stats['new_today'],
        new_week=stats['new_week'],
        new_month=stats['new_month'],
        conversion=f"{(users_with_subscription / max(stats['active_users'], 1) * 100):.1f}",
        trial_share=f"{(trial_users / max(users_with_subscription, 1) * 100):.1f}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_users_stats")],
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")]
        ])
    )
    await callback.answer()


async def _render_user_subscription_overview(
    callback: types.CallbackQuery,
    db: AsyncSession,
    user_id: int,
    language: str = "en"
) -> bool:
    texts = get_texts(language)
    user_service = UserService()
    profile = await user_service.get_user_profile(db, user_id)

    if not profile:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return False

    user = profile["user"]
    subscription = profile["subscription"]

    text = texts.t("ADMIN_USER_SUBSCRIPTION_TITLE", "📱 <b>User Subscription & Settings</b>") + "\n\n"
    user_link = f'<a href="tg://user?id={user.telegram_id}">{user.full_name}</a>'
    text += f"👤 {user_link} (ID: <code>{user.telegram_id}</code>)\n\n"

    keyboard = []

    if subscription:
        status_emoji = "✅" if subscription.is_active else "❌"
        type_emoji = "🎁" if subscription.is_trial else "💎"

        traffic_display = f"{subscription.traffic_used_gb:.1f}/"
        if subscription.traffic_limit_gb == 0:
            traffic_display += "♾️ GB"
        else:
            traffic_display += f"{subscription.traffic_limit_gb} GB"

        status_text = texts.t("ADMIN_SUB_STATUS_ACTIVE", "Active") if subscription.is_active else texts.t("ADMIN_SUB_STATUS_INACTIVE", "Inactive")
        type_text = texts.t("ADMIN_SUB_TYPE_TRIAL", "Trial") if subscription.is_trial else texts.t("ADMIN_SUB_TYPE_PAID", "Paid")
        
        text += f"<b>{texts.t('ADMIN_SUB_FIELD_STATUS', 'Status')}:</b> {status_emoji} {status_text}\n"
        text += f"<b>{texts.t('ADMIN_SUB_FIELD_TYPE', 'Type')}:</b> {type_emoji} {type_text}\n"
        text += f"<b>{texts.t('ADMIN_SUB_FIELD_START', 'Start')}:</b> {format_datetime(subscription.start_date)}\n"
        text += f"<b>{texts.t('ADMIN_SUB_FIELD_END', 'End')}:</b> {format_datetime(subscription.end_date)}\n"
        text += f"<b>{texts.t('ADMIN_SUB_FIELD_TRAFFIC', 'Traffic')}:</b> {traffic_display}\n"
        text += f"<b>{texts.t('ADMIN_SUB_FIELD_DEVICES', 'Devices')}:</b> {subscription.device_limit}\n"

        if subscription.is_active:
            days_left = (subscription.end_date - datetime.utcnow()).days
            text += f"<b>{texts.t('ADMIN_SUB_FIELD_DAYS_LEFT', 'Days left')}:</b> {days_left}\n"

        current_squads = subscription.connected_squads or []
        if current_squads:
            text += f"\n<b>{texts.t('ADMIN_SUB_CONNECTED_SERVERS', 'Connected servers')}:</b>\n"
            for squad_uuid in current_squads:
                try:
                    server = await get_server_squad_by_uuid(db, squad_uuid)
                    if server:
                        text += f"• {server.display_name}\n"
                    else:
                        text += f"• {squad_uuid[:8]}... ({texts.t('ADMIN_SUB_SERVER_UNKNOWN', 'unknown')})\n"
                except Exception as e:
                    logger.error(f"Error getting server {squad_uuid}: {e}")
                    text += f"• {squad_uuid[:8]}... ({texts.t('ADMIN_SUB_SERVER_LOAD_ERROR', 'load error')})\n"
        else:
            text += f"\n<b>{texts.t('ADMIN_SUB_CONNECTED_SERVERS', 'Connected servers')}:</b> {texts.t('ADMIN_SUB_NO_SERVERS', 'none')}\n"

        keyboard = [
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_EXTEND", "⏰ Extend"),
                    callback_data=f"admin_sub_extend_{user_id}"
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_BUY", "💳 Buy subscription"),
                    callback_data=f"admin_sub_buy_{user_id}"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_CHANGE_TYPE", "🔄 Subscription type"),
                    callback_data=f"admin_sub_change_type_{user_id}"
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_ADD_TRAFFIC", "📊 Add traffic"),
                    callback_data=f"admin_sub_traffic_{user_id}"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_CHANGE_SERVER", "🌍 Change server"),
                    callback_data=f"admin_user_change_server_{user_id}"
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_DEVICES", "📱 Devices"),
                    callback_data=f"admin_user_devices_{user_id}"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_TRAFFIC_LIMIT", "🛠️ Traffic limit"),
                    callback_data=f"admin_user_traffic_{user_id}"
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_RESET_DEVICES", "🔄 Reset devices"),
                    callback_data=f"admin_user_reset_devices_{user_id}"
                )
            ]
        ]

        if subscription.is_active:
            keyboard.append([
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_DEACTIVATE", "🚫 Deactivate"),
                    callback_data=f"admin_sub_deactivate_{user_id}"
                )
            ])
        else:
            keyboard.append([
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_ACTIVATE", "✅ Activate"),
                    callback_data=f"admin_sub_activate_{user_id}"
                )
            ])
    else:
        text += texts.t("ADMIN_SUB_NO_SUBSCRIPTION", "❌ <b>No subscription</b>\n\nUser has not activated a subscription yet.")

        keyboard = [
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_GRANT_TRIAL", "🎁 Grant trial"),
                    callback_data=f"admin_sub_grant_trial_{user_id}"
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SUB_BTN_GRANT_PAID", "💎 Grant subscription"),
                    callback_data=f"admin_sub_grant_{user_id}"
                )
            ]
        ]

    keyboard.append([
        types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK_TO_USER", "⬅️ Back to user"), callback_data=f"admin_user_manage_{user_id}")
    ])

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    return True


@admin_required
@error_handler
async def show_user_subscription(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):

    user_id = int(callback.data.split('_')[-1])

    if await _render_user_subscription_overview(callback, db, user_id, db_user.language):
        await callback.answer()


@admin_required
@error_handler
async def show_user_transactions(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    user_id = int(callback.data.split('_')[-1])
    texts = get_texts(db_user.language)
    
    from app.database.crud.transaction import get_user_transactions
    
    user = await get_user_by_id(db, user_id)
    if not user:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return
    
    transactions = await get_user_transactions(db, user_id, limit=10)
    
    text = texts.t("ADMIN_USER_TRANSACTIONS_TITLE", "💳 <b>User Transactions</b>") + "\n\n"
    user_link = f'<a href="tg://user?id={user.telegram_id}">{user.full_name}</a>'
    text += f"👤 {user_link} (ID: <code>{user.telegram_id}</code>)\n"
    text += texts.t("ADMIN_USER_CURRENT_BALANCE", "💰 Current balance: {balance}").format(balance=settings.format_price(user.balance_kopeks)) + "\n\n"
    
    if transactions:
        text += texts.t("ADMIN_USER_RECENT_TRANSACTIONS", "<b>Recent transactions:</b>") + "\n\n"
        
        for transaction in transactions:
            type_emoji = "📈" if transaction.amount_kopeks > 0 else "📉"
            text += f"{type_emoji} {settings.format_price(abs(transaction.amount_kopeks))}\n"
            text += f"📋 {transaction.description}\n"
            text += f"📅 {format_datetime(transaction.created_at)}\n\n"
    else:
        text += texts.t("ADMIN_USER_NO_TRANSACTIONS", "📭 <b>No transactions</b>")
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK_TO_USER", "⬅️ Back to user"), callback_data=f"admin_user_manage_{user_id}")]
        ])
    )
    await callback.answer()


@admin_required
@error_handler
async def confirm_user_delete(
    callback: types.CallbackQuery,
    db_user: User
):
    
    user_id = int(callback.data.split('_')[-1])
    
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_USER_DELETE_CONFIRM", "🗑️ <b>Delete User</b>\n\n⚠️ <b>WARNING!</b>\nAre you sure you want to delete this user?\n\nThis action will:\n• Mark user as deleted\n• Deactivate their subscription\n• Block access to bot\n\nThis action is irreversible!"),
        reply_markup=get_confirmation_keyboard(
            f"admin_user_delete_confirm_{user_id}",
            f"admin_user_manage_{user_id}",
            db_user.language
        )
    )
    await callback.answer()


@admin_required
@error_handler
async def delete_user_account(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    user_id = int(callback.data.split('_')[-1])
    texts = get_texts(db_user.language)
    
    user_service = UserService()
    success = await user_service.delete_user_account(db, user_id, db_user.id)
    
    if success:
        await callback.message.edit_text(
            texts.t("ADMIN_USER_DELETE_SUCCESS", "✅ User successfully deleted"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_USER_LIST", "👥 To user list"), callback_data="admin_users_list")]
            ])
        )
    else:
        await callback.message.edit_text(
            texts.t("ADMIN_USER_DELETE_ERROR", "❌ Error deleting user"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK_TO_USER", "👤 Back to user"), callback_data=f"admin_user_manage_{user_id}")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def process_user_search(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    
    query = message.text.strip()
    texts = get_texts(db_user.language)
    
    if not query:
        await message.answer(texts.t("ADMIN_SEARCH_INVALID_QUERY", "❌ Enter a valid search query"))
        return
    
    user_service = UserService()
    search_results = await user_service.search_users(db, query, page=1, limit=10)
    
    if not search_results["users"]:
        await message.answer(
            texts.t("ADMIN_SEARCH_NOT_FOUND", "🔍 No results found for '<b>{query}</b>'").format(query=query),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")]
            ])
        )
        await state.clear()
        return
    
    text = texts.t("ADMIN_SEARCH_RESULTS", "🔍 <b>Search Results:</b> '{query}'").format(query=query) + "\n\n"
    text += texts.t("ADMIN_SEARCH_SELECT_USER", "Select a user:")
    
    keyboard = []
    
    for user in search_results["users"]:
        if user.status == UserStatus.ACTIVE.value:
            status_emoji = "✅"
        elif user.status == UserStatus.BLOCKED.value:
            status_emoji = "🚫"
        else:
            status_emoji = "🗑️"
        
        subscription_emoji = ""
        if user.subscription:
            if user.subscription.is_trial:
                subscription_emoji = "🎁"
            elif user.subscription.is_active:
                subscription_emoji = "💎"
            else:
                subscription_emoji = "⏰"
        else:
            subscription_emoji = "❌"
        
        button_text = f"{status_emoji} {subscription_emoji} {user.full_name}"
        
        button_text += f" | 🆔 {user.telegram_id}"
        
        if user.balance_kopeks > 0:
            button_text += f" | 💰 {settings.format_price(user.balance_kopeks)}"
        
        if len(button_text) > 60:
            short_name = user.full_name
            if len(short_name) > 15:
                short_name = short_name[:12] + "..."
            button_text = f"{status_emoji} {subscription_emoji} {short_name} | 🆔 {user.telegram_id}"
        
        keyboard.append([
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin_user_manage_{user.id}"
            )
        ])
    
    keyboard.append([
        types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")
    ])
    
    await message.answer(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.clear()


@admin_required
@error_handler
async def show_user_management(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    
    # Support transition from ticket: admin_user_manage_{userId}_from_ticket_{ticketId}
    parts = callback.data.split('_')
    try:
        user_id = int(parts[3])  # admin_user_manage_{userId}
    except Exception:
        user_id = int(callback.data.split('_')[-1])
    origin_ticket_id = None
    if "from" in parts and "ticket" in parts:
        try:
            origin_ticket_id = int(parts[-1])
        except Exception:
            origin_ticket_id = None
    # If came from ticket - remember in state to preserve back button
    try:
        if origin_ticket_id:
            await state.update_data(origin_ticket_id=origin_ticket_id, origin_ticket_user_id=user_id)
    except Exception:
        pass
    # If not in callback - try to get from state
    if origin_ticket_id is None:
        try:
            data_state = await state.get_data()
            if data_state.get("origin_ticket_user_id") == user_id:
                origin_ticket_id = data_state.get("origin_ticket_id")
        except Exception:
            pass
    
    # Check where user came from
    back_callback = "admin_users_list"
    
    # If callback_data contains info about coming from balance list
    # In practice it's hard to determine, so we use state
    
    user_service = UserService()
    profile = await user_service.get_user_profile(db, user_id)
    
    if not profile:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return
    
    user = profile["user"]
    subscription = profile["subscription"]

    texts = get_texts(db_user.language)

    status_map = {
        UserStatus.ACTIVE.value: texts.ADMIN_USER_STATUS_ACTIVE,
        UserStatus.BLOCKED.value: texts.ADMIN_USER_STATUS_BLOCKED,
        UserStatus.DELETED.value: texts.ADMIN_USER_STATUS_DELETED,
    }
    status_text = status_map.get(user.status, texts.ADMIN_USER_STATUS_UNKNOWN)

    username_display = (
        f"@{user.username}" if user.username else texts.ADMIN_USER_USERNAME_NOT_SET
    )
    last_activity = (
        format_time_ago(user.last_activity, db_user.language)
        if user.last_activity
        else texts.ADMIN_USER_LAST_ACTIVITY_UNKNOWN
    )

    sections = [
        texts.ADMIN_USER_MANAGEMENT_PROFILE.format(
            name=user.full_name,
            telegram_id=user.telegram_id,
            username=username_display,
            status=status_text,
            language=user.language,
            balance=settings.format_price(user.balance_kopeks),
            transactions=profile["transactions_count"],
            registration=format_datetime(user.created_at),
            last_activity=last_activity,
            registration_days=profile["registration_days"],
        )
    ]

    if subscription:
        subscription_type = (
            texts.ADMIN_USER_SUBSCRIPTION_TYPE_TRIAL
            if subscription.is_trial
            else texts.ADMIN_USER_SUBSCRIPTION_TYPE_PAID
        )
        subscription_status = (
            texts.ADMIN_USER_SUBSCRIPTION_STATUS_ACTIVE
            if subscription.is_active
            else texts.ADMIN_USER_SUBSCRIPTION_STATUS_INACTIVE
        )
        traffic_usage = texts.ADMIN_USER_TRAFFIC_USAGE.format(
            used=f"{subscription.traffic_used_gb:.1f}",
            limit=subscription.traffic_limit_gb,
        )
        sections.append(
            texts.ADMIN_USER_MANAGEMENT_SUBSCRIPTION.format(
                type=subscription_type,
                status=subscription_status,
                end_date=format_datetime(subscription.end_date),
                traffic=traffic_usage,
                devices=subscription.device_limit,
                countries=len(subscription.connected_squads),
            )
        )
    else:
        sections.append(texts.ADMIN_USER_MANAGEMENT_SUBSCRIPTION_NONE)

    # Display promo groups
    primary_group = user.get_primary_promo_group()
    if primary_group:
        sections.append(
            texts.t(
                "ADMIN_USER_PROMO_GROUPS_PRIMARY",
                "⭐ Основная: {name} (Priority: {priority})",
            ).format(name=primary_group.name, priority=getattr(primary_group, "priority", 0))
        )
        sections.append(
            texts.ADMIN_USER_MANAGEMENT_PROMO_GROUP.format(
                name=primary_group.name,
                server_discount=primary_group.server_discount_percent,
                traffic_discount=primary_group.traffic_discount_percent,
                device_discount=primary_group.device_discount_percent,
            )
        )

        # Show additional groups if any
        if user.user_promo_groups and len(user.user_promo_groups) > 1:
            additional_groups = [
                upg.promo_group for upg in user.user_promo_groups
                if upg.promo_group and upg.promo_group.id != primary_group.id
            ]
            if additional_groups:
                sections.append(
                    texts.t(
                        "ADMIN_USER_PROMO_GROUPS_ADDITIONAL",
                        "Дополнительные группы:",
                    )
                )
                for group in additional_groups:
                    sections.append(
                        f"  • {group.name} (Priority: {getattr(group, 'priority', 0)})"
                    )
    else:
        sections.append(texts.ADMIN_USER_MANAGEMENT_PROMO_GROUP_NONE)

    text = "\n\n".join(sections)

    # Check state to determine where user came from
    current_state = await state.get_state()
    if current_state == AdminStates.viewing_user_from_balance_list:
        back_callback = "admin_users_balance_filter"
    elif current_state == AdminStates.viewing_user_from_traffic_list:
        back_callback = "admin_users_traffic_filter"
    elif current_state == AdminStates.viewing_user_from_last_activity_list:
        back_callback = "admin_users_activity_filter"
    elif current_state == AdminStates.viewing_user_from_spending_list:
        back_callback = "admin_users_spending_filter"
    elif current_state == AdminStates.viewing_user_from_purchases_list:
        back_callback = "admin_users_purchases_filter"
    elif current_state == AdminStates.viewing_user_from_campaign_list:
        back_callback = "admin_users_campaign_filter"
    
    # Base profile keyboard
    kb = get_user_management_keyboard(user.id, user.status, db_user.language, back_callback)
    # If came from ticket - add back to ticket button at the beginning
    try:
        if origin_ticket_id:
            back_to_ticket_btn = types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_BACK_TO_TICKET", "🎫 Back to ticket"),
                callback_data=f"admin_view_ticket_{origin_ticket_id}"
            )
            kb.inline_keyboard.insert(0, [back_to_ticket_btn])
    except Exception:
        pass

    await callback.message.edit_text(
        text,
        reply_markup=kb
    )
    await callback.answer()


async def _build_user_referrals_view(
    db: AsyncSession,
    language: str,
    user_id: int,
    limit: int = 30,
) -> Optional[Tuple[str, InlineKeyboardMarkup]]:
    texts = get_texts(language)

    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    referrals = await get_referrals(db, user_id)

    effective_percent = get_effective_referral_commission_percent(user)
    default_percent = settings.REFERRAL_COMMISSION_PERCENT

    header = texts.t(
        "ADMIN_USER_REFERRALS_TITLE",
        "🤝 <b>User Referrals</b>",
    )
    summary = texts.t(
        "ADMIN_USER_REFERRALS_SUMMARY",
        "👤 {name} (ID: <code>{telegram_id}</code>)\n👥 Total referrals: {count}",
    ).format(
        name=user.full_name,
        telegram_id=user.telegram_id,
        count=len(referrals),
    )

    lines: List[str] = [header, summary]

    if user.referral_commission_percent is None:
        lines.append(
            texts.t(
                "ADMIN_USER_REFERRAL_COMMISSION_DEFAULT",
                "• Commission percent: {percent}% (default value)",
            ).format(percent=effective_percent)
        )
    else:
        lines.append(
            texts.t(
                "ADMIN_USER_REFERRAL_COMMISSION_CUSTOM",
                "• Custom percent: {percent}% (default: {default_percent}%)",
            ).format(
                percent=user.referral_commission_percent,
                default_percent=default_percent,
            )
        )

    if referrals:
        lines.append(
            texts.t(
                "ADMIN_USER_REFERRALS_LIST_HEADER",
                "<b>Referral list:</b>",
            )
        )
        items = []
        for referral in referrals[:limit]:
            username_part = (
                f", @{referral.username}"
                if referral.username
                else ""
            )
            referral_link = f'<a href="tg://user?id={referral.telegram_id}">{referral.full_name}</a>'
            items.append(
                texts.t(
                    "ADMIN_USER_REFERRALS_LIST_ITEM",
                    "• {name} (ID: <code>{telegram_id}</code>{username_part})",
                ).format(
                    name=referral_link,
                    telegram_id=referral.telegram_id,
                    username_part=username_part,
                )
            )

        lines.append("\n".join(items))

        if len(referrals) > limit:
            remaining = len(referrals) - limit
            lines.append(
                texts.t(
                    "ADMIN_USER_REFERRALS_LIST_TRUNCATED",
                    "• … and {count} more referrals",
                ).format(count=remaining)
            )
    else:
        lines.append(
            texts.t(
                "ADMIN_USER_REFERRALS_EMPTY",
                "No referrals yet.",
            )
        )

    lines.append(
        texts.t(
            "ADMIN_USER_REFERRALS_EDIT_HINT",
            "✏️ To edit the list, click «✏️ Edit» below.",
        )
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_USER_REFERRAL_COMMISSION_EDIT_BUTTON",
                        "📈 Change percent",
                    ),
                    callback_data=f"admin_user_referral_percent_{user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_USER_REFERRALS_EDIT_BUTTON",
                        "✏️ Edit",
                    ),
                    callback_data=f"admin_user_referrals_edit_{user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts.BACK,
                    callback_data=f"admin_user_manage_{user_id}",
                )
            ],
        ]
    )

    return "\n\n".join(lines), keyboard


@admin_required
@error_handler
async def show_user_referrals(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    user_id = int(callback.data.split('_')[-1])

    current_state = await state.get_state()
    if current_state in {AdminStates.editing_user_referrals, AdminStates.editing_user_referral_percent}:
        data = await state.get_data()
        preserved_data = {
            key: value
            for key, value in data.items()
            if key not in {"editing_referrals_user_id", "referrals_message_id", "editing_referral_percent_user_id"}
        }
        await state.clear()
        if preserved_data:
            await state.update_data(**preserved_data)

    view = await _build_user_referrals_view(db, db_user.language, user_id)
    if not view:
        texts = get_texts(db_user.language)
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return

    text, keyboard = view

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
    )
    await callback.answer()


@admin_required
@error_handler
async def start_edit_referral_percent(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    user_id = int(callback.data.split('_')[-1])

    texts = get_texts(db_user.language)
    user = await get_user_by_id(db, user_id)
    if not user:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return

    effective_percent = get_effective_referral_commission_percent(user)
    default_percent = settings.REFERRAL_COMMISSION_PERCENT

    prompt = texts.t(
        "ADMIN_USER_REFERRAL_COMMISSION_PROMPT",
        (
            "📈 <b>Custom Referral Commission Percent</b>\n\n"
            "Current value: {current}%\n"
            "Default value: {default}%\n\n"
            "Send a new value from 0 to 100 or 'standard' to reset."
        ),
    ).format(current=effective_percent, default=default_percent)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="5%",
                    callback_data=f"admin_user_referral_percent_set_{user_id}_5",
                ),
                InlineKeyboardButton(
                    text="10%",
                    callback_data=f"admin_user_referral_percent_set_{user_id}_10",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="15%",
                    callback_data=f"admin_user_referral_percent_set_{user_id}_15",
                ),
                InlineKeyboardButton(
                    text="20%",
                    callback_data=f"admin_user_referral_percent_set_{user_id}_20",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_USER_REFERRAL_COMMISSION_RESET_BUTTON",
                        "♻️ Reset to default",
                    ),
                    callback_data=f"admin_user_referral_percent_reset_{user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts.BACK,
                    callback_data=f"admin_user_referrals_{user_id}",
                )
            ],
        ]
    )

    await state.update_data(editing_referral_percent_user_id=user_id)
    await state.set_state(AdminStates.editing_user_referral_percent)

    await callback.message.edit_text(
        prompt,
        reply_markup=keyboard,
    )
    await callback.answer()


async def _update_referral_commission_percent(
    db: AsyncSession,
    user_id: int,
    percent: Optional[int],
    admin_id: int,
) -> Tuple[bool, Optional[int]]:
    try:
        user = await get_user_by_id(db, user_id)
        if not user:
            return False, None

        user.referral_commission_percent = percent
        user.updated_at = datetime.utcnow()

        await db.commit()

        effective = get_effective_referral_commission_percent(user)

        logger.info(
            "Admin %s updated referral percent for user %s: %s",
            admin_id,
            user_id,
            percent,
        )

        return True, effective
    except Exception as e:
        logger.error(
            "Error updating referral percent for user %s: %s",
            user_id,
            e,
        )
        try:
            await db.rollback()
        except Exception as rollback_error:
            logger.error("Error rolling back transaction: %s", rollback_error)
        return False, None


async def _render_referrals_after_update(
    callback: types.CallbackQuery,
    db: AsyncSession,
    db_user: User,
    user_id: int,
    success_message: str,
):
    view = await _build_user_referrals_view(db, db_user.language, user_id)
    if view:
        text, keyboard = view
        text = f"{success_message}\n\n" + text
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.message.edit_text(success_message)


@admin_required
@error_handler
async def set_referral_percent_button(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    parts = callback.data.split('_')

    if "reset" in parts:
        user_id = int(parts[-1])
        percent_value: Optional[int] = None
    else:
        user_id = int(parts[-2])
        percent_value = int(parts[-1])

    texts = get_texts(db_user.language)

    success, effective_percent = await _update_referral_commission_percent(
        db,
        user_id,
        percent_value,
        db_user.id,
    )

    if not success:
        await callback.answer(texts.t("ADMIN_REFERRAL_PERCENT_UPDATE_ERROR", "❌ Failed to update percent"), show_alert=True)
        return

    await state.clear()

    success_message = texts.t(
        "ADMIN_USER_REFERRAL_COMMISSION_UPDATED",
        "✅ Percent updated: {percent}%",
    ).format(percent=effective_percent)

    await _render_referrals_after_update(callback, db, db_user, user_id, success_message)
    await callback.answer()


@admin_required
@error_handler
async def process_referral_percent_input(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    user_id = data.get("editing_referral_percent_user_id")

    if not user_id:
        await message.answer(texts.t("ADMIN_USER_NOT_DETERMINED", "❌ Could not determine user"))
        return

    raw_text = message.text.strip()
    normalized = raw_text.lower()

    percent_value: Optional[int]

    if normalized in {"standard", "default"}:
        percent_value = None
    else:
        normalized_number = raw_text.replace(',', '.').strip()
        try:
            percent_float = float(normalized_number)
        except (TypeError, ValueError):
            await message.answer(
                texts.t(
                    "ADMIN_USER_REFERRAL_COMMISSION_INVALID",
                    "❌ Enter a number from 0 to 100 or 'standard'",
                )
            )
            return

        percent_value = int(round(percent_float))

        if percent_value < 0 or percent_value > 100:
            await message.answer(
                texts.t(
                    "ADMIN_USER_REFERRAL_COMMISSION_INVALID",
                    "❌ Enter a number from 0 to 100 or 'standard'",
                )
            )
            return

    success, effective_percent = await _update_referral_commission_percent(
        db,
        int(user_id),
        percent_value,
        db_user.id,
    )

    if not success:
        await message.answer(texts.t("ADMIN_REFERRAL_PERCENT_UPDATE_ERROR", "❌ Failed to update percent"))
        return

    await state.clear()

    success_message = texts.t(
        "ADMIN_USER_REFERRAL_COMMISSION_UPDATED",
        "✅ Percent updated: {percent}%",
    ).format(percent=effective_percent)

    view = await _build_user_referrals_view(db, db_user.language, int(user_id))
    if view:
        text, keyboard = view
        await message.answer(f"{success_message}\n\n{text}", reply_markup=keyboard)
    else:
        await message.answer(success_message)


@admin_required
@error_handler
async def start_edit_user_referrals(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    user_id = int(callback.data.split('_')[-1])

    texts = get_texts(db_user.language)
    user = await get_user_by_id(db, user_id)
    if not user:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return

    prompt = texts.t(
        "ADMIN_USER_REFERRALS_EDIT_PROMPT",
        (
            "✏️ <b>Edit Referrals</b>\n\n"
            "Send a list of referrals for user <b>{name}</b> (ID: <code>{telegram_id}</code>):\n"
            "• Use TG ID or @username\n"
            "• Values can be separated by comma, space, or newline\n"
            "• To clear the list, send 0 or 'none'\n\n"
            "Or press the button below to cancel."
        ),
    ).format(
        name=user.full_name,
        telegram_id=user.telegram_id,
    )

    await state.update_data(
        editing_referrals_user_id=user_id,
        referrals_message_id=callback.message.message_id,
    )

    await callback.message.edit_text(
        prompt,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=texts.BACK,
                        callback_data=f"admin_user_referrals_{user_id}",
                    )
                ]
            ]
        ),
    )

    await state.set_state(AdminStates.editing_user_referrals)
    await callback.answer()


@admin_required
@error_handler
async def process_edit_user_referrals(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()

    user_id = data.get("editing_referrals_user_id")
    if not user_id:
        await message.answer(
            texts.t(
                "ADMIN_USER_REFERRALS_STATE_LOST",
                "❌ Could not determine user. Please try again.",
            )
        )
        await state.clear()
        return

    raw_text = message.text.strip()
    lower_text = raw_text.lower()
    clear_keywords = {"0", "none", "empty", "clear"}
    clear_requested = lower_text in clear_keywords

    tokens: List[str] = []
    if not clear_requested:
        parts = re.split(r"[,\n]+", raw_text)
        for part in parts:
            for token in part.split():
                cleaned = token.strip()
                if cleaned and cleaned not in tokens:
                    tokens.append(cleaned)

    found_users: List[User] = []
    not_found: List[str] = []
    skipped_self: List[str] = []
    duplicate_tokens: List[str] = []

    seen_ids = set()

    for token in tokens:
        normalized = token.strip()
        if not normalized:
            continue

        if normalized.startswith("@"):
            normalized = normalized[1:]

        user = None
        if normalized.isdigit():
            try:
                user = await get_user_by_telegram_id(db, int(normalized))
            except ValueError:
                user = None
        else:
            user = await get_user_by_username(db, normalized)

        if not user:
            not_found.append(token)
            continue

        if user.id == user_id:
            skipped_self.append(token)
            continue

        if user.id in seen_ids:
            duplicate_tokens.append(token)
            continue

        seen_ids.add(user.id)
        found_users.append(user)

    if not found_users and not clear_requested:
        error_lines = [
            texts.t(
                "ADMIN_USER_REFERRALS_NO_VALID",
                "❌ Could not find any users from the provided data.",
            )
        ]
        if not_found:
            error_lines.append(
                texts.t(
                    "ADMIN_USER_REFERRALS_INVALID_ENTRIES",
                    "Not found: {values}",
                ).format(values=", ".join(not_found))
            )
        if skipped_self:
            error_lines.append(
                texts.t(
                    "ADMIN_USER_REFERRALS_SELF_SKIPPED",
                    "Skipped (same user): {values}",
                ).format(values=", ".join(skipped_self))
            )
        await message.answer("\n".join(error_lines))
        return

    user_service = UserService()

    new_referral_ids = [user.id for user in found_users] if not clear_requested else []

    success, details = await user_service.update_user_referrals(
        db,
        user_id,
        new_referral_ids,
        db_user.id,
    )

    if not success:
        await message.answer(
            texts.t(
                "ADMIN_USER_REFERRALS_UPDATE_ERROR",
                "❌ Failed to update referrals. Please try later.",
            )
        )
        return

    response_lines = [
        texts.t(
            "ADMIN_USER_REFERRALS_UPDATED",
            "✅ Referral list updated.",
        )
    ]

    total_referrals = details.get("total", len(new_referral_ids))
    added = details.get("added", 0)
    removed = details.get("removed", 0)

    response_lines.append(
        texts.t(
            "ADMIN_USER_REFERRALS_UPDATED_TOTAL",
            "• Current list: {total}",
        ).format(total=total_referrals)
    )

    if added > 0:
        response_lines.append(
            texts.t(
                "ADMIN_USER_REFERRALS_UPDATED_ADDED",
                "• Added: {count}",
            ).format(count=added)
        )

    if removed > 0:
        response_lines.append(
            texts.t(
                "ADMIN_USER_REFERRALS_UPDATED_REMOVED",
                "• Removed: {count}",
            ).format(count=removed)
        )

    if not_found:
        response_lines.append(
            texts.t(
                "ADMIN_USER_REFERRALS_INVALID_ENTRIES",
                "Not found: {values}",
            ).format(values=", ".join(not_found))
        )

    if skipped_self:
        response_lines.append(
            texts.t(
                "ADMIN_USER_REFERRALS_SELF_SKIPPED",
                "Skipped (same user): {values}",
            ).format(values=", ".join(skipped_self))
        )

    if duplicate_tokens:
        response_lines.append(
            texts.t(
                "ADMIN_USER_REFERRALS_DUPLICATES",
                "Ignored duplicates: {values}",
            ).format(values=", ".join(duplicate_tokens))
        )

    view = await _build_user_referrals_view(db, db_user.language, user_id)
    message_id = data.get("referrals_message_id")

    if view and message_id:
        try:
            await message.bot.edit_message_text(
                view[0],
                chat_id=message.chat.id,
                message_id=message_id,
                reply_markup=view[1],
            )
        except TelegramBadRequest:
            await message.answer(view[0], reply_markup=view[1])
    elif view:
        await message.answer(view[0], reply_markup=view[1])

    await message.answer("\n".join(response_lines))
    await state.clear()

async def _render_user_promo_group(
    message: types.Message,
    language: str,
    user: User,
    promo_groups: list
) -> None:
    texts = get_texts(language)

    # Get primary and all user groups
    primary_group = user.get_primary_promo_group()
    user_group_ids = [upg.promo_group_id for upg in user.user_promo_groups] if user.user_promo_groups else []

    # Build current groups section
    if primary_group:
        current_line = texts.t(
            "ADMIN_USER_PROMO_GROUPS_PRIMARY",
            "⭐ Primary: {name} (Priority: {priority})",
        ).format(name=primary_group.name, priority=getattr(primary_group, "priority", 0))

        discount_line = texts.ADMIN_USER_PROMO_GROUP_DISCOUNTS.format(
            servers=primary_group.server_discount_percent,
            traffic=primary_group.traffic_discount_percent,
            devices=primary_group.device_discount_percent,
        )

        # Show additional groups if any
        if len(user_group_ids) > 1:
            additional_groups = [
                upg.promo_group for upg in user.user_promo_groups
                if upg.promo_group and upg.promo_group.id != primary_group.id
            ]
            if additional_groups:
                additional_line = "\n" + texts.t(
                    "ADMIN_USER_PROMO_GROUPS_ADDITIONAL",
                    "Additional groups:",
                ) + "\n"
                for group in additional_groups:
                    additional_line += f"  • {group.name} (Priority: {getattr(group, 'priority', 0)})\n"
                discount_line += additional_line
    else:
        current_line = texts.t(
            "ADMIN_USER_PROMO_GROUPS_NONE",
            "User has no promo groups",
        )
        discount_line = ""

    text = (
        f"{texts.ADMIN_USER_PROMO_GROUP_TITLE}\n\n"
        f"{current_line}\n"
        f"{discount_line}\n\n"
        f"{texts.ADMIN_USER_PROMO_GROUP_SELECT}"
    )

    await message.edit_text(
        text,
        reply_markup=get_user_promo_group_keyboard(
            promo_groups,
            user.id,
            user_group_ids,  # Pass list of all group IDs
            language
        )
    )


@admin_required
@error_handler
async def show_user_promo_group(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):

    user_id = int(callback.data.split('_')[-1])

    texts = get_texts(db_user.language)
    user = await get_user_by_id(db, user_id)
    if not user:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return

    promo_groups = await get_promo_groups_with_counts(db)
    if not promo_groups:
        texts = get_texts(db_user.language)
        await callback.answer(texts.ADMIN_PROMO_GROUPS_EMPTY, show_alert=True)
        return

    await _render_user_promo_group(callback.message, db_user.language, user, promo_groups)
    await callback.answer()


@admin_required
@error_handler
async def set_user_promo_group(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    from app.database.crud.user_promo_group import (
        has_user_promo_group,
        add_user_to_promo_group,
        remove_user_from_promo_group,
        count_user_promo_groups
    )
    from app.database.crud.promo_group import get_promo_group_by_id

    parts = callback.data.split('_')
    user_id = int(parts[-2])
    group_id = int(parts[-1])

    texts = get_texts(db_user.language)

    user = await get_user_by_id(db, user_id)
    if not user:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return

    # Check if user already has this group
    has_group = await has_user_promo_group(db, user_id, group_id)

    if has_group:
        # Remove group
        # Check if it's the last group
        groups_count = await count_user_promo_groups(db, user_id)
        if groups_count <= 1:
            await callback.answer(
                texts.t(
                    "ADMIN_USER_PROMO_GROUP_CANNOT_REMOVE_LAST",
                    "❌ Cannot remove the last promo group",
                ),
                show_alert=True
            )
            return

        group = await get_promo_group_by_id(db, group_id)
        await remove_user_from_promo_group(db, user_id, group_id)
        await callback.answer(
            texts.t(
                "ADMIN_USER_PROMO_GROUP_REMOVED",
                "🗑 Group «{name}» removed",
            ).format(name=group.name if group else ""),
            show_alert=True
        )
    else:
        # Add group
        group = await get_promo_group_by_id(db, group_id)
        if not group:
            await callback.answer(texts.ADMIN_USER_PROMO_GROUP_ERROR, show_alert=True)
            return

        await add_user_to_promo_group(db, user_id, group_id, assigned_by="admin")
        await callback.answer(
            texts.t(
                "ADMIN_USER_PROMO_GROUP_ADDED",
                "✅ Group «{name}» added",
            ).format(name=group.name),
            show_alert=True
        )

    # Refresh user data and show updated list
    user = await get_user_by_id(db, user_id)
    promo_groups = await get_promo_groups_with_counts(db)
    await _render_user_promo_group(callback.message, db_user.language, user, promo_groups)



@admin_required
@error_handler
async def start_balance_edit(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    
    user_id = int(callback.data.split('_')[-1])
    
    await state.update_data(editing_user_id=user_id)
    
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_USER_BALANCE_EDIT_PROMPT", "💰 <b>Edit Balance</b>\n\nEnter the amount to change balance:\n• Positive number to add\n• Negative number to deduct\n• Examples: 100, -50, 25.5\n\nOr press /cancel to cancel"),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"admin_user_manage_{user_id}")]
        ])
    )
    
    await state.set_state(AdminStates.editing_user_balance)
    await callback.answer()


@admin_required
@error_handler
async def start_send_user_message(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    user_id = int(callback.data.split('_')[-1])

    texts = get_texts(db_user.language)
    target_user = await get_user_by_id(db, user_id)
    if not target_user:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return

    await state.update_data(direct_message_user_id=user_id)

    prompt = texts.t("ADMIN_USER_SEND_MESSAGE_PROMPT",
                 "✉️ <b>Send Message to User</b>\n\n"
                 "Enter the text that the bot will send to the user."
                 "\n\nYou can cancel with /cancel or the button below.")

    await callback.message.edit_text(
        prompt,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"admin_user_manage_{user_id}")]
            ]
        ),
        parse_mode="HTML",
    )

    await state.set_state(AdminStates.sending_user_message)
    await callback.answer()


@admin_required
@error_handler
async def process_send_user_message(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    user_id = data.get("direct_message_user_id")

    if not user_id:
        await message.answer(texts.t("ADMIN_USER_SEND_MESSAGE_ERROR_NOT_FOUND", "❌ User for sending message not found"))
        await state.clear()
        return

    target_user = await get_user_by_id(db, int(user_id))
    if not target_user:
        await message.answer(texts.t("ADMIN_USER_SEND_MESSAGE_ERROR_NOT_FOUND", "❌ User not found or was deleted"))
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(texts.t("ADMIN_USER_SEND_MESSAGE_EMPTY", "❌ Please enter a non-empty message"))
        return

    confirmation_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK_TO_USER", "👤 Back to user"), callback_data=f"admin_user_manage_{user_id}")]]
    )

    try:
        await message.bot.send_message(target_user.telegram_id, text)
        await message.answer(
            texts.t("ADMIN_USER_SEND_MESSAGE_SUCCESS", "✅ Message sent to user"),
            reply_markup=confirmation_keyboard,
        )
    except TelegramForbiddenError:
        await message.answer(
            texts.t("ADMIN_USER_SEND_MESSAGE_FORBIDDEN", "⚠️ User blocked the bot or cannot receive messages."),
            reply_markup=confirmation_keyboard,
        )
    except TelegramBadRequest as err:
        logger.error("Error sending message to user %s: %s", target_user.telegram_id, err)
        await message.answer(
            texts.t("ADMIN_USER_SEND_MESSAGE_BAD_REQUEST", "❌ Telegram rejected the message. Check the text and try again."),
            reply_markup=confirmation_keyboard,
        )
        return
    except Exception as err:
        logger.error("Unexpected error sending message to user %s: %s", target_user.telegram_id, err)
        await message.answer(
            texts.t("ADMIN_USER_SEND_MESSAGE_ERROR", "❌ Failed to send message. Please try later."),
            reply_markup=confirmation_keyboard,
        )
        await state.clear()
        return

    await state.clear()


@admin_required
@error_handler
async def process_balance_edit(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    
    texts = get_texts(db_user.language)
    data = await state.get_data()
    user_id = data.get("editing_user_id")
    
    if not user_id:
        await message.answer(texts.t("ADMIN_USER_NOT_FOUND_ERROR", "❌ Error: user not found"))
        await state.clear()
        return
    
    try:
        amount_rubles = float(message.text.replace(',', '.'))
        amount_kopeks = int(amount_rubles * 100)
        
        if abs(amount_kopeks) > 10000000: 
            await message.answer(texts.t("ADMIN_BALANCE_TOO_LARGE", "❌ Amount too large (maximum 100,000)"))
            return
        
        user_service = UserService()
        
        description = f"Balance change by admin {db_user.full_name}"
        if amount_kopeks > 0:
            description = f"Top-up by admin: +{int(amount_rubles)}"
        else:
            description = f"Deduction by admin: {int(amount_rubles)}"
        
        success = await user_service.update_user_balance(
            db, user_id, amount_kopeks, description, db_user.id,
            bot=message.bot, admin_name=db_user.full_name
        )
        
        if success:
            action = texts.t("ADMIN_BALANCE_TOPPED_UP", "topped up") if amount_kopeks > 0 else texts.t("ADMIN_BALANCE_DEDUCTED", "deducted")
            await message.answer(
                texts.t("ADMIN_BALANCE_CHANGED_SUCCESS", "✅ User balance {action} by {amount}").format(action=action, amount=settings.format_price(abs(amount_kopeks))),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK_TO_USER", "👤 Back to user"), callback_data=f"admin_user_manage_{user_id}")]
                ])
            )
        else:
            await message.answer(texts.t("ADMIN_BALANCE_CHANGE_ERROR", "❌ Error changing balance (possibly insufficient funds)"))
        
    except ValueError:
        await message.answer(texts.t("ADMIN_BALANCE_INVALID_AMOUNT", "❌ Enter a valid amount (e.g., 100 or -50)"))
        return
    
    await state.clear()


@admin_required
@error_handler
async def confirm_user_block(
    callback: types.CallbackQuery,
    db_user: User
):
    
    user_id = int(callback.data.split('_')[-1])
    
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_USER_BLOCK_CONFIRM", "🚫 <b>Block User</b>\n\nAre you sure you want to block this user?\nUser will lose access to the bot."),
        reply_markup=get_confirmation_keyboard(
            f"admin_user_block_confirm_{user_id}",
            f"admin_user_manage_{user_id}",
            db_user.language
        )
    )
    await callback.answer()


@admin_required
@error_handler
async def block_user(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    user_id = int(callback.data.split('_')[-1])
    texts = get_texts(db_user.language)
    
    user_service = UserService()
    success = await user_service.block_user(
        db, user_id, db_user.id, "Blocked by administrator"
    )
    
    if success:
        await callback.message.edit_text(
            texts.t("ADMIN_USER_BLOCKED_SUCCESS", "✅ User blocked"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK_TO_USER", "👤 Back to user"), callback_data=f"admin_user_manage_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            texts.t("ADMIN_USER_BLOCK_ERROR", "❌ Error blocking user"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK_TO_USER", "👤 Back to user"), callback_data=f"admin_user_manage_{user_id}")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def show_inactive_users(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    texts = get_texts(db_user.language)
    user_service = UserService()
    
    from app.database.crud.user import get_inactive_users
    inactive_users = await get_inactive_users(db, settings.INACTIVE_USER_DELETE_MONTHS)
    
    if not inactive_users:
        await callback.message.edit_text(
            texts.t("ADMIN_INACTIVE_USERS_NONE", "✅ No inactive users (over {months} months) found").format(months=settings.INACTIVE_USER_DELETE_MONTHS),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")]
            ])
        )
        await callback.answer()
        return
    
    text = texts.t("ADMIN_INACTIVE_USERS_TITLE", "🗑️ <b>Inactive Users</b>") + "\n"
    text += texts.t("ADMIN_INACTIVE_USERS_COUNT", "Inactive for over {months} months: {count}").format(months=settings.INACTIVE_USER_DELETE_MONTHS, count=len(inactive_users)) + "\n\n"

    for user in inactive_users[:10]:
        user_link = f'<a href="tg://user?id={user.telegram_id}">{user.full_name}</a>'
        text += f"👤 {user_link}\n"
        text += f"🆔 <code>{user.telegram_id}</code>\n"
        last_activity_display = (
            format_time_ago(user.last_activity, db_user.language)
            if user.last_activity
            else texts.t("ADMIN_ACTIVITY_NEVER", "Never")
        )
        text += f"📅 {last_activity_display}\n\n"
    
    if len(inactive_users) > 10:
        text += texts.t("ADMIN_INACTIVE_USERS_MORE", "... and {count} more users").format(count=len(inactive_users) - 10)
    
    keyboard = [
        [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CLEANUP_ALL", "🗑️ Clean up all"), callback_data="admin_cleanup_inactive")],
        [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data="admin_users")]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@admin_required
@error_handler
async def confirm_user_unblock(
    callback: types.CallbackQuery,
    db_user: User
):
    
    user_id = int(callback.data.split('_')[-1])
    
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_USER_UNBLOCK_CONFIRM", "✅ <b>Unblock User</b>\n\nAre you sure you want to unblock this user?\nUser will regain access to the bot."),
        reply_markup=get_confirmation_keyboard(
            f"admin_user_unblock_confirm_{user_id}",
            f"admin_user_manage_{user_id}",
            db_user.language
        )
    )
    await callback.answer()


@admin_required
@error_handler
async def unblock_user(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    user_id = int(callback.data.split('_')[-1])
    texts = get_texts(db_user.language)
    
    user_service = UserService()
    success = await user_service.unblock_user(db, user_id, db_user.id)
    
    if success:
        await callback.message.edit_text(
            texts.t("ADMIN_USER_UNBLOCKED_SUCCESS", "✅ User unblocked"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK_TO_USER", "👤 Back to user"), callback_data=f"admin_user_manage_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            texts.t("ADMIN_USER_UNBLOCK_ERROR", "❌ Error unblocking user"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK_TO_USER", "👤 Back to user"), callback_data=f"admin_user_manage_{user_id}")]
            ])
        )
    
    await callback.answer()

@admin_required
@error_handler
async def show_user_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    user_id = int(callback.data.split('_')[-1])
    
    user_service = UserService()
    profile = await user_service.get_user_profile(db, user_id)
    
    texts = get_texts(db_user.language)
    if not profile:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return
    
    user = profile["user"]
    subscription = profile["subscription"]
    
    referral_stats = await get_detailed_referral_stats(db, user.id)
    campaign_registration = await get_campaign_registration_by_user(db, user.id)
    campaign_stats = None
    if campaign_registration:
        campaign_stats = await get_campaign_statistics(db, campaign_registration.campaign_id)
    
    text = texts.t("ADMIN_USER_STATS_TITLE", "📊 <b>User Statistics</b>") + "\n\n"
    user_link = f'<a href="tg://user?id={user.telegram_id}">{user.full_name}</a>'
    text += f"👤 {user_link} (ID: <code>{user.telegram_id}</code>)\n\n"
    
    text += f"<b>{texts.t('ADMIN_USER_STATS_BASIC', 'Basic Information')}:</b>\n"
    text += f"• {texts.t('ADMIN_USER_STATS_DAYS', 'Days since registration')}: {profile['registration_days']}\n"
    text += f"• {texts.t('ADMIN_USER_STATS_BALANCE', 'Balance')}: {settings.format_price(user.balance_kopeks)}\n"
    text += f"• {texts.t('ADMIN_USER_STATS_TRANSACTIONS', 'Transactions')}: {profile['transactions_count']}\n"
    text += f"• {texts.t('ADMIN_USER_STATS_LANGUAGE', 'Language')}: {user.language}\n\n"
    
    text += f"<b>{texts.t('ADMIN_USER_STATS_SUBSCRIPTION', 'Subscription')}:</b>\n"
    if subscription:
        sub_status = texts.t("ADMIN_SUB_ACTIVE", "✅ Active") if subscription.is_active else texts.t("ADMIN_SUB_INACTIVE", "❌ Inactive")
        sub_type = f" ({texts.t('ADMIN_SUB_TRIAL', 'trial')})" if subscription.is_trial else f" ({texts.t('ADMIN_SUB_PAID', 'paid')})"
        text += f"• {texts.t('ADMIN_SUB_FIELD_STATUS', 'Status')}: {sub_status}{sub_type}\n"
        text += f"• {texts.t('ADMIN_SUB_FIELD_TRAFFIC', 'Traffic')}: {subscription.traffic_used_gb:.1f}/{subscription.traffic_limit_gb} GB\n"
        text += f"• {texts.t('ADMIN_SUB_FIELD_DEVICES', 'Devices')}: {subscription.device_limit}\n"
        text += f"• {texts.t('ADMIN_USER_STATS_COUNTRIES', 'Countries')}: {len(subscription.connected_squads)}\n"
    else:
        text += f"• {texts.t('ADMIN_USER_STATS_NO_SUB', 'None')}\n"
    
    text += f"\n<b>{texts.t('ADMIN_USER_STATS_REFERRAL', 'Referral Program')}:</b>\n"

    if user.referred_by_id:
        referrer = await get_user_by_id(db, user.referred_by_id)
        if referrer:
            text += f"• {texts.t('ADMIN_USER_STATS_REFERRED_BY', 'Referred by')} <b>{referrer.full_name}</b>\n"
        else:
            text += f"• {texts.t('ADMIN_USER_STATS_REFERRED_UNKNOWN', 'Referred by (referrer not found)')}\n"
        if campaign_registration and campaign_registration.campaign:
            text += f"• {texts.t('ADMIN_USER_STATS_ALSO_CAMPAIGN', 'Also registered via campaign')} <b>{campaign_registration.campaign.name}</b>\n"
    elif campaign_registration and campaign_registration.campaign:
        text += f"• {texts.t('ADMIN_USER_STATS_VIA_CAMPAIGN', 'Registered via campaign')} <b>{campaign_registration.campaign.name}</b>\n"
        if campaign_registration.created_at:
            text += f"• {texts.t('ADMIN_USER_STATS_CAMPAIGN_DATE', 'Campaign registration date')}: {campaign_registration.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    else:
        text += f"• {texts.t('ADMIN_USER_STATS_DIRECT', 'Direct registration')}\n"

    text += f"• {texts.t('ADMIN_USER_STATS_REF_CODE', 'Referral code')}: <code>{user.referral_code}</code>\n\n"

    if campaign_registration and campaign_registration.campaign and campaign_stats:
        text += f"<b>{texts.t('ADMIN_USER_STATS_CAMPAIGN', 'Campaign')}:</b>\n"
        text += f"• {texts.t('ADMIN_USER_STATS_NAME', 'Name')}: <b>{campaign_registration.campaign.name}</b>"
        if campaign_registration.campaign.start_parameter:
            text += f" ({texts.t('ADMIN_USER_STATS_PARAM', 'param')}: <code>{campaign_registration.campaign.start_parameter}</code>)"
        text += "\n"
        text += f"• {texts.t('ADMIN_USER_STATS_TOTAL_REG', 'Total registrations')}: {campaign_stats['registrations']}\n"
        text += f"• {texts.t('ADMIN_USER_STATS_TOTAL_REV', 'Total revenue')}: {settings.format_price(campaign_stats['total_revenue_kopeks'])}\n"
        text += f"• {texts.t('ADMIN_USER_STATS_TRIAL_USERS', 'Trial users')}: {campaign_stats['trial_users_count']} ({texts.t('ADMIN_USER_STATS_ACTIVE', 'active')}: {campaign_stats['active_trials_count']})\n"
        text += f"• {texts.t('ADMIN_USER_STATS_CONVERSIONS', 'Conversions')}: {campaign_stats['conversion_count']} ({texts.t('ADMIN_USER_STATS_PAID_USERS', 'paid users')}: {campaign_stats['paid_users_count']})\n"
        text += f"• {texts.t('ADMIN_USER_STATS_CONV_RATE', 'Conversion rate')}: {campaign_stats['conversion_rate']:.1f}%\n"
        text += f"• {texts.t('ADMIN_USER_STATS_TRIAL_CONV', 'Trial conversion')}: {campaign_stats['trial_conversion_rate']:.1f}%\n"
        text += f"• {texts.t('ADMIN_USER_STATS_AVG_REV', 'Avg revenue per user')}: {settings.format_price(campaign_stats['avg_revenue_per_user_kopeks'])}\n"
        text += f"• {texts.t('ADMIN_USER_STATS_AVG_FIRST', 'Avg first payment')}: {settings.format_price(campaign_stats['avg_first_payment_kopeks'])}\n"
        text += "\n"
    
    if referral_stats['invited_count'] > 0:
        text += f"<b>{texts.t('ADMIN_USER_STATS_REF_EARNINGS', 'Referral Earnings')}:</b>\n"
        text += f"• {texts.t('ADMIN_USER_STATS_INVITED', 'Total invited')}: {referral_stats['invited_count']}\n"
        text += f"• {texts.t('ADMIN_USER_STATS_ACTIVE_REFS', 'Active referrals')}: {referral_stats['active_referrals']}\n"
        text += f"• {texts.t('ADMIN_USER_STATS_TOTAL_EARNED', 'Total earned')}: {settings.format_price(referral_stats['total_earned_kopeks'])}\n"
        text += f"• {texts.t('ADMIN_USER_STATS_MONTH_EARNED', 'Month earned')}: {settings.format_price(referral_stats['month_earned_kopeks'])}\n"
        
        if referral_stats['referrals_detail']:
            text += f"\n<b>{texts.t('ADMIN_USER_STATS_REF_DETAILS', 'Referral Details')}:</b>\n"
            for detail in referral_stats['referrals_detail'][:5]: 
                referral_name = detail['referral_name']
                earned = settings.format_price(detail['total_earned_kopeks'])
                status = "🟢" if detail['is_active'] else "🔴"
                text += f"• {status} {referral_name}: {earned}\n"
            
            if len(referral_stats['referrals_detail']) > 5:
                text += f"• {texts.t('ADMIN_USER_STATS_MORE_REFS', '... and {count} more referrals').format(count=len(referral_stats['referrals_detail']) - 5)}\n"
    else:
        text += f"<b>{texts.t('ADMIN_USER_STATS_REFERRAL', 'Referral Program')}:</b>\n"
        text += f"• {texts.t('ADMIN_USER_STATS_NO_REFS', 'No referrals')}\n"
        text += f"• {texts.t('ADMIN_USER_STATS_NO_EARNINGS', 'No earnings')}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK_TO_USER", "⬅️ Back to user"), callback_data=f"admin_user_manage_{user_id}")]
        ])
    )
    await callback.answer()


async def get_detailed_referral_stats(db: AsyncSession, user_id: int) -> dict:
    from app.database.crud.referral import get_user_referral_stats, get_referral_earnings_by_user
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload
    
    base_stats = await get_user_referral_stats(db, user_id)
    
    referrals_query = select(User).options(
        selectinload(User.subscription)
    ).where(User.referred_by_id == user_id)
    
    referrals_result = await db.execute(referrals_query)
    referrals = referrals_result.scalars().all()
    
    earnings_by_referral = {}
    all_earnings = await get_referral_earnings_by_user(db, user_id)
    
    for earning in all_earnings:
        referral_id = earning.referral_id
        if referral_id not in earnings_by_referral:
            earnings_by_referral[referral_id] = 0
        earnings_by_referral[referral_id] += earning.amount_kopeks
    
    referrals_detail = []
    current_time = datetime.utcnow()
    
    for referral in referrals:
        earned = earnings_by_referral.get(referral.id, 0)
        
        is_active = False
        if referral.subscription:
            from app.database.models import SubscriptionStatus
            is_active = (
                referral.subscription.status == SubscriptionStatus.ACTIVE.value and 
                referral.subscription.end_date > current_time
            )
        
        referrals_detail.append({
            'referral_id': referral.id,
            'referral_name': referral.full_name,
            'referral_telegram_id': referral.telegram_id,
            'total_earned_kopeks': earned,
            'is_active': is_active,
            'registration_date': referral.created_at,
            'has_subscription': bool(referral.subscription)
        })
    
    referrals_detail.sort(key=lambda x: x['total_earned_kopeks'], reverse=True)
    
    return {
        'invited_count': base_stats['invited_count'],
        'active_referrals': base_stats['active_referrals'], 
        'total_earned_kopeks': base_stats['total_earned_kopeks'],
        'month_earned_kopeks': base_stats['month_earned_kopeks'],
        'referrals_detail': referrals_detail
    }
    
@admin_required
@error_handler
async def extend_user_subscription(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    user_id = int(callback.data.split('_')[-1])
    
    await state.update_data(extending_user_id=user_id)
    
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_SUB_EXTEND_PROMPT", "⏰ <b>Extend Subscription</b>\n\nEnter number of days to change:\n• Positive values extend subscription\n• Negative values reduce term\n• Range: -365 to 365 days (0 not allowed)\n\nOr press /cancel to cancel"),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="-7 days", callback_data=f"admin_sub_extend_days_{user_id}_-7"),
                types.InlineKeyboardButton(text="-30 days", callback_data=f"admin_sub_extend_days_{user_id}_-30")
            ],
            [
                types.InlineKeyboardButton(text="7 days", callback_data=f"admin_sub_extend_days_{user_id}_7"),
                types.InlineKeyboardButton(text="30 days", callback_data=f"admin_sub_extend_days_{user_id}_30")
            ],
            [
                types.InlineKeyboardButton(text="90 days", callback_data=f"admin_sub_extend_days_{user_id}_90"),
                types.InlineKeyboardButton(text="180 days", callback_data=f"admin_sub_extend_days_{user_id}_180")
            ],
            [
                types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"admin_user_subscription_{user_id}")
            ]
        ])
    )
    
    await state.set_state(AdminStates.extending_subscription)
    await callback.answer()


@admin_required
@error_handler
async def process_subscription_extension_days(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    parts = callback.data.split('_')
    user_id = int(parts[-2])
    days = int(parts[-1])
    
    texts = get_texts(db_user.language)
    if days == 0 or days < -365 or days > 365:
        await callback.answer(texts.t("ADMIN_SUB_EXTEND_DAYS_INVALID", "❌ Days must be from -365 to 365, excluding 0"), show_alert=True)
        return

    success = await _extend_subscription_by_days(db, user_id, days, db_user.id)

    if success:
        if days > 0:
            action_text = texts.t("ADMIN_SUB_EXTENDED_BY", "extended by {days} days").format(days=days)
        else:
            action_text = texts.t("ADMIN_SUB_REDUCED_BY", "reduced by {days} days").format(days=abs(days))
        await callback.message.edit_text(
            texts.t("ADMIN_SUB_CHANGE_SUCCESS", "✅ User subscription {action}").format(action=action_text),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_SUBSCRIPTION", "📱 To subscription"), callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            texts.t("ADMIN_SUB_EXTEND_ERROR", "❌ Error extending subscription"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_SUBSCRIPTION", "📱 To subscription"), callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def process_subscription_extension_text(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    user_id = data.get("extending_user_id")
    
    if not user_id:
        await message.answer(texts.t("ADMIN_USER_NOT_FOUND_ERROR", "❌ Error: user not found"))
        await state.clear()
        return
    
    try:
        days = int(message.text.strip())
        
        if days == 0 or days < -365 or days > 365:
            await message.answer(texts.t("ADMIN_SUB_EXTEND_DAYS_INVALID", "❌ Days must be from -365 to 365, excluding 0"))
            return

        success = await _extend_subscription_by_days(db, user_id, days, db_user.id)

        if success:
            if days > 0:
                action_text = texts.t("ADMIN_SUB_EXTENDED_BY", "extended by {days} days").format(days=days)
            else:
                action_text = texts.t("ADMIN_SUB_REDUCED_BY", "reduced by {days} days").format(days=abs(days))
            await message.answer(
                texts.t("ADMIN_SUB_CHANGE_SUCCESS", "✅ User subscription {action}").format(action=action_text),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_SUBSCRIPTION", "📱 To subscription"), callback_data=f"admin_user_subscription_{user_id}")]
                ])
            )
        else:
            await message.answer(texts.t("ADMIN_SUB_EXTEND_ERROR", "❌ Error extending subscription"))
        
    except ValueError:
        await message.answer(texts.t("ADMIN_SUB_DAYS_INVALID", "❌ Enter a valid number of days"))
        return
    
    await state.clear()


@admin_required
@error_handler
async def add_subscription_traffic(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    user_id = int(callback.data.split('_')[-1])
    
    await state.update_data(traffic_user_id=user_id)
    
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_SUB_ADD_TRAFFIC_PROMPT", "📊 <b>Add Traffic</b>\n\nEnter amount of GB to add:\n• Examples: 50, 100, 500\n• Maximum: 10000 GB\n\nOr press /cancel to cancel"),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="50 GB", callback_data=f"admin_sub_traffic_add_{user_id}_50"),
                types.InlineKeyboardButton(text="100 GB", callback_data=f"admin_sub_traffic_add_{user_id}_100")
            ],
            [
                types.InlineKeyboardButton(text="500 GB", callback_data=f"admin_sub_traffic_add_{user_id}_500"),
                types.InlineKeyboardButton(text="1000 GB", callback_data=f"admin_sub_traffic_add_{user_id}_1000")
            ],
            [
                types.InlineKeyboardButton(text=texts.t("ADMIN_SUB_UNLIMITED", "♾️ Unlimited"), callback_data=f"admin_sub_traffic_add_{user_id}_0"),
            ],
            [
                types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_user_subscription_{user_id}")
            ]
        ])
    )
    
    await state.set_state(AdminStates.adding_traffic)
    await callback.answer()


@admin_required
@error_handler
async def process_traffic_addition_button(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    parts = callback.data.split('_')
    user_id = int(parts[-2])
    gb = int(parts[-1])
    
    success = await _add_subscription_traffic(db, user_id, gb, db_user.id)
    
    texts = get_texts(db_user.language)
    if success:
        traffic_text = texts.t("ADMIN_SUB_UNLIMITED", "♾️ unlimited") if gb == 0 else f"{gb} GB"
        await callback.message.edit_text(
            texts.t("ADMIN_SUB_TRAFFIC_ADDED", "✅ Traffic added to subscription: {traffic}").format(traffic=traffic_text),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_SUBSCRIPTION", "📱 To subscription"), callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            texts.t("ADMIN_SUB_TRAFFIC_ADD_ERROR", "❌ Error adding traffic"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_SUBSCRIPTION", "📱 To subscription"), callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def process_traffic_addition_text(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    user_id = data.get("traffic_user_id")
    
    if not user_id:
        await message.answer(texts.t("ADMIN_USER_NOT_FOUND_ERROR", "❌ Error: user not found"))
        await state.clear()
        return
    
    try:
        gb = int(message.text.strip())
        
        if gb < 0 or gb > 10000:
            await message.answer(texts.t("ADMIN_SUB_TRAFFIC_GB_INVALID", "❌ GB must be from 0 to 10000 (0 = unlimited)"))
            return
        
        success = await _add_subscription_traffic(db, user_id, gb, db_user.id)
        
        if success:
            traffic_text = texts.t("ADMIN_SUB_UNLIMITED", "♾️ unlimited") if gb == 0 else f"{gb} GB"
            await message.answer(
                texts.t("ADMIN_SUB_TRAFFIC_ADDED", "✅ Traffic added to subscription: {traffic}").format(traffic=traffic_text),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_SUBSCRIPTION", "📱 To subscription"), callback_data=f"admin_user_subscription_{user_id}")]
                ])
            )
        else:
            await message.answer(texts.t("ADMIN_SUB_TRAFFIC_ADD_ERROR", "❌ Error adding traffic"))
        
    except ValueError:
        await message.answer(texts.t("ADMIN_SUB_TRAFFIC_INVALID_GB", "❌ Enter a valid number of GB"))
        return
    
    await state.clear()


@admin_required
@error_handler
async def deactivate_user_subscription(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_id = int(callback.data.split('_')[-1])
    
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_SUB_DEACTIVATE_CONFIRM", "🚫 <b>Deactivate Subscription</b>\n\nAre you sure you want to deactivate this user's subscription?\nUser will lose access to the service."),
        reply_markup=get_confirmation_keyboard(
            f"admin_sub_deactivate_confirm_{user_id}",
            f"admin_user_subscription_{user_id}",
            db_user.language
        )
    )
    await callback.answer()


@admin_required
@error_handler
async def confirm_subscription_deactivation(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_id = int(callback.data.split('_')[-1])
    texts = get_texts(db_user.language)
    
    success = await _deactivate_user_subscription(db, user_id, db_user.id)
    
    if success:
        await callback.message.edit_text(
            texts.t("ADMIN_SUB_DEACTIVATED", "✅ User subscription deactivated"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_SUBSCRIPTION", "📱 To subscription"), callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            texts.t("ADMIN_SUB_DEACTIVATE_ERROR", "❌ Error deactivating subscription"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_SUBSCRIPTION", "📱 To subscription"), callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def activate_user_subscription(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_id = int(callback.data.split('_')[-1])
    texts = get_texts(db_user.language)
    
    success = await _activate_user_subscription(db, user_id, db_user.id)
    
    if success:
        await callback.message.edit_text(
            texts.t("ADMIN_SUB_ACTIVATED", "✅ User subscription activated"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_SUBSCRIPTION", "📱 To subscription"), callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка активации подписки",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📱 К подписке", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def grant_trial_subscription(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_id = int(callback.data.split('_')[-1])
    
    success = await _grant_trial_subscription(db, user_id, db_user.id)
    
    if success:
        await callback.message.edit_text(
            "✅ Пользователю выдан триальный период",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📱 К подписке", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка выдачи триального периода",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📱 К подписке", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def grant_paid_subscription(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    user_id = int(callback.data.split('_')[-1])
    
    await state.update_data(granting_user_id=user_id)
    
    await callback.message.edit_text(
        "💎 <b>Выдача подписки</b>\n\n"
        "Введите количество дней подписки:\n"
        "• Например: 30, 90, 180, 365\n"
        "• Максимум: 730 дней\n\n"
        "Или нажмите /cancel для отмены",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="30 дней", callback_data=f"admin_sub_grant_days_{user_id}_30"),
                types.InlineKeyboardButton(text="90 дней", callback_data=f"admin_sub_grant_days_{user_id}_90")
            ],
            [
                types.InlineKeyboardButton(text="180 дней", callback_data=f"admin_sub_grant_days_{user_id}_180"),
                types.InlineKeyboardButton(text="365 дней", callback_data=f"admin_sub_grant_days_{user_id}_365")
            ],
            [
                types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_user_subscription_{user_id}")
            ]
        ])
    )
    
    await state.set_state(AdminStates.granting_subscription)
    await callback.answer()


@admin_required
@error_handler
async def process_subscription_grant_days(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    parts = callback.data.split('_')
    user_id = int(parts[-2])
    days = int(parts[-1])
    
    success = await _grant_paid_subscription(db, user_id, days, db_user.id)
    
    if success:
        await callback.message.edit_text(
            f"✅ Пользователю выдана подписка на {days} дней",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📱 К подписке", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка выдачи подписки",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📱 К подписке", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def process_subscription_grant_text(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    data = await state.get_data()
    user_id = data.get("granting_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    try:
        days = int(message.text.strip())
        
        if days <= 0 or days > 730:
            await message.answer("❌ Количество дней должно быть от 1 до 730")
            return
        
        success = await _grant_paid_subscription(db, user_id, days, db_user.id)
        
        if success:
            await message.answer(
                f"✅ Пользователю выдана подписка на {days} дней",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="📱 К подписке", callback_data=f"admin_user_subscription_{user_id}")]
                ])
            )
        else:
            await message.answer("❌ Ошибка выдачи подписки")
        
    except ValueError:
        await message.answer("❌ Введите корректное число дней")
        return
    
    await state.clear()

@admin_required
@error_handler
async def show_user_servers_management(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_id = int(callback.data.split('_')[-1])

    if await _render_user_subscription_overview(callback, db, user_id):
        await callback.answer()


@admin_required
@error_handler
async def show_server_selection(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_id = int(callback.data.split('_')[-1])
    await _show_servers_for_user(callback, user_id, db)
    await callback.answer()

async def _show_servers_for_user(
    callback: types.CallbackQuery,
    user_id: int,
    db: AsyncSession
):
    try:
        user = await get_user_by_id(db, user_id)
        current_squads = []
        if user and user.subscription:
            current_squads = user.subscription.connected_squads or []
        
        all_servers, _ = await get_all_server_squads(db, available_only=False)
        
        servers_to_show = []
        for server in all_servers:
            if server.is_available or server.squad_uuid in current_squads:
                servers_to_show.append(server)
        
        texts = get_texts(db_user.language)
        if not servers_to_show:
            await callback.message.edit_text(
                texts.t("ADMIN_SERVERS_NOT_FOUND", "❌ No available servers found"),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data=f"admin_user_subscription_{user_id}")]
                ])
            )
            return
        
        text = texts.t("ADMIN_SERVERS_MANAGE_TITLE", "🌍 <b>Server Management</b>") + "\n\n"
        text += texts.t("ADMIN_SERVERS_MANAGE_HINT", "Click on a server to add/remove:") + "\n"
        text += texts.t("ADMIN_SERVERS_SELECTED", "✅ - selected server") + "\n"
        text += texts.t("ADMIN_SERVERS_AVAILABLE", "⚪ - available server") + "\n"
        text += texts.t("ADMIN_SERVERS_INACTIVE", "🔒 - inactive (for already assigned only)") + "\n\n"
        
        keyboard = []
        selected_servers = [s for s in servers_to_show if s.squad_uuid in current_squads]
        available_servers = [s for s in servers_to_show if s.squad_uuid not in current_squads and s.is_available]
        inactive_servers = [s for s in servers_to_show if s.squad_uuid not in current_squads and not s.is_available]
        
        sorted_servers = selected_servers + available_servers + inactive_servers
        
        for server in sorted_servers[:20]: 
            is_selected = server.squad_uuid in current_squads
            
            if is_selected:
                emoji = "✅"
            elif server.is_available:
                emoji = "⚪"
            else:
                emoji = "🔒"
            
            display_name = server.display_name
            if not server.is_available and not is_selected:
                display_name += " (inactive)"
            
            keyboard.append([
                types.InlineKeyboardButton(
                    text=f"{emoji} {display_name}",
                    callback_data=f"admin_user_toggle_server_{user_id}_{server.id}"
                )
            ])
        
        if len(servers_to_show) > 20:
            text += f"\n📝 {texts.t('ADMIN_SERVERS_SHOWING', 'Showing first 20 of {count} servers').format(count=len(servers_to_show))}"
        
        keyboard.append([
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_DONE", "✅ Done"), callback_data=f"admin_user_subscription_{user_id}"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data=f"admin_user_subscription_{user_id}")
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error showing servers: {e}")

@admin_required
@error_handler
async def toggle_user_server(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    parts = callback.data.split('_')
    user_id = int(parts[4]) 
    server_id = int(parts[5])
    
    try:
        texts = get_texts(db_user.language)
        user = await get_user_by_id(db, user_id)
        if not user or not user.subscription:
            await callback.answer(texts.t("ADMIN_USER_OR_SUB_NOT_FOUND", "❌ User or subscription not found"), show_alert=True)
            return
        
        server = await get_server_squad_by_id(db, server_id)
        if not server:
            await callback.answer(texts.t("ADMIN_SERVER_NOT_FOUND", "❌ Server not found"), show_alert=True)
            return
        
        subscription = user.subscription
        current_squads = list(subscription.connected_squads or [])
        
        if server.squad_uuid in current_squads:
            current_squads.remove(server.squad_uuid)
            action_text = "removed"
        else:
            current_squads.append(server.squad_uuid)
            action_text = "added"
        
        subscription.connected_squads = current_squads
        subscription.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(subscription)
        
        if user.remnawave_uuid:
            try:
                remnawave_service = RemnaWaveService()
                async with remnawave_service.get_api_client() as api:
                    await api.update_user(
                        uuid=user.remnawave_uuid,
                        active_internal_squads=current_squads,
                        description=settings.format_remnawave_user_description(
                            full_name=user.full_name,
                            username=user.username,
                            telegram_id=user.telegram_id
                        )
                    )
                logger.info(f"✅ Updated servers in RemnaWave for user {user.telegram_id}")
            except Exception as rw_error:
                logger.error(f"❌ Error updating RemnaWave: {rw_error}")
        
        logger.info(f"Admin {db_user.id}: server {server.display_name} {action_text} for user {user_id}")
        
        await refresh_server_selection_screen(callback, user_id, db_user, db)
        
    except Exception as e:
        logger.error(f"Error toggling server: {e}")
        await callback.answer(texts.t("ADMIN_SERVER_CHANGE_ERROR", "❌ Error changing server"), show_alert=True)

async def refresh_server_selection_screen(
    callback: types.CallbackQuery,
    user_id: int,
    db_user: User,
    db: AsyncSession
):
    try:
        texts = get_texts(db_user.language)
        user = await get_user_by_id(db, user_id)
        current_squads = []
        if user and user.subscription:
            current_squads = user.subscription.connected_squads or []
        
        servers, _ = await get_all_server_squads(db, available_only=True)
        
        if not servers:
            await callback.message.edit_text(
                texts.t("ADMIN_SERVERS_NOT_FOUND", "❌ No available servers found"),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_BACK", "⬅️ Back"), callback_data=f"admin_user_subscription_{user_id}")]
                ])
            )
            return
        
        text = texts.t("ADMIN_SERVERS_MANAGE_TITLE", "🌍 <b>Server Management</b>") + "\n\n"
        text += texts.t("ADMIN_SERVERS_MANAGE_HINT", "Click on a server to add/remove:") + "\n\n"
        
        keyboard = []
        for server in servers[:15]:
            is_selected = server.squad_uuid in current_squads
            emoji = "✅" if is_selected else "⚪"
            
            keyboard.append([
                types.InlineKeyboardButton(
                    text=f"{emoji} {server.display_name}",
                    callback_data=f"admin_user_toggle_server_{user_id}_{server.id}"
                )
            ])
        
        if len(servers) > 15:
            text += f"\n📝 Показано первых 15 из {len(servers)} серверов"
        
        keyboard.append([
            types.InlineKeyboardButton(text="✅ Готово", callback_data=f"admin_user_subscription_{user_id}"),
            types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_user_subscription_{user_id}")
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error updating servers screen: {e}")


@admin_required
@error_handler
async def start_devices_edit(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    user_id = int(callback.data.split('_')[-1])
    
    await state.update_data(editing_devices_user_id=user_id)
    
    await callback.message.edit_text(
        "📱 <b>Изменение количества устройств</b>\n\n"
        "Введите новое количество устройств (от 1 до 10):\n"
        "• Текущее значение будет заменено\n"
        "• Примеры: 1, 2, 5, 10\n\n"
        "Или нажмите /cancel для отмены",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="1", callback_data=f"admin_user_devices_set_{user_id}_1"),
                types.InlineKeyboardButton(text="2", callback_data=f"admin_user_devices_set_{user_id}_2"),
                types.InlineKeyboardButton(text="3", callback_data=f"admin_user_devices_set_{user_id}_3")
            ],
            [
                types.InlineKeyboardButton(text="5", callback_data=f"admin_user_devices_set_{user_id}_5"),
                types.InlineKeyboardButton(text="10", callback_data=f"admin_user_devices_set_{user_id}_10")
            ],
            [
                types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_user_subscription_{user_id}")
            ]
        ])
    )
    
    await state.set_state(AdminStates.editing_user_devices)
    await callback.answer()


@admin_required
@error_handler
async def set_user_devices_button(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    parts = callback.data.split('_')
    user_id = int(parts[-2])
    devices = int(parts[-1])
    
    success = await _update_user_devices(db, user_id, devices, db_user.id)
    
    if success:
        await callback.message.edit_text(
            f"✅ Количество устройств изменено на: {devices}",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📱 Подписка и настройки", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка изменения количества устройств",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📱 Подписка и настройки", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def process_devices_edit_text(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    data = await state.get_data()
    user_id = data.get("editing_devices_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    try:
        devices = int(message.text.strip())
        
        if devices <= 0 or devices > 10:
            await message.answer("❌ Количество устройств должно быть от 1 до 10")
            return
        
        success = await _update_user_devices(db, user_id, devices, db_user.id)
        
        if success:
            await message.answer(
                f"✅ Количество устройств изменено на: {devices}",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="📱 Подписка и настройки", callback_data=f"admin_user_subscription_{user_id}")]
                ])
            )
        else:
            await message.answer("❌ Ошибка изменения количества устройств")
        
    except ValueError:
        await message.answer("❌ Введите корректное число устройств")
        return
    
    await state.clear()


@admin_required
@error_handler
async def start_traffic_edit(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    user_id = int(callback.data.split('_')[-1])
    
    await state.update_data(editing_traffic_user_id=user_id)
    
    await callback.message.edit_text(
        "📊 <b>Изменение лимита трафика</b>\n\n"
        "Введите новый лимит трафика в ГБ:\n"
        "• 0 - безлимитный трафик\n"
        "• Примеры: 50, 100, 500, 1000\n"
        "• Максимум: 10000 ГБ\n\n"
        "Или нажмите /cancel для отмены",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="50 ГБ", callback_data=f"admin_user_traffic_set_{user_id}_50"),
                types.InlineKeyboardButton(text="100 ГБ", callback_data=f"admin_user_traffic_set_{user_id}_100")
            ],
            [
                types.InlineKeyboardButton(text="500 ГБ", callback_data=f"admin_user_traffic_set_{user_id}_500"),
                types.InlineKeyboardButton(text="1000 ГБ", callback_data=f"admin_user_traffic_set_{user_id}_1000")
            ],
            [
                types.InlineKeyboardButton(text="♾️ Безлимит", callback_data=f"admin_user_traffic_set_{user_id}_0")
            ],
            [
                types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_user_subscription_{user_id}")
            ]
        ])
    )
    
    await state.set_state(AdminStates.editing_user_traffic)
    await callback.answer()


@admin_required
@error_handler
async def set_user_traffic_button(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    parts = callback.data.split('_')
    user_id = int(parts[-2])
    traffic_gb = int(parts[-1])
    
    success = await _update_user_traffic(db, user_id, traffic_gb, db_user.id)
    
    if success:
        traffic_text = "♾️ безлимитный" if traffic_gb == 0 else f"{traffic_gb} ГБ"
        await callback.message.edit_text(
            f"✅ Лимит трафика изменен на: {traffic_text}",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📱 Подписка и настройки", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка изменения лимита трафика",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📱 Подписка и настройки", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def process_traffic_edit_text(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    data = await state.get_data()
    user_id = data.get("editing_traffic_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    try:
        traffic_gb = int(message.text.strip())
        
        if traffic_gb < 0 or traffic_gb > 10000:
            await message.answer("❌ Лимит трафика должен быть от 0 до 10000 ГБ (0 = безлимит)")
            return
        
        success = await _update_user_traffic(db, user_id, traffic_gb, db_user.id)
        
        if success:
            traffic_text = "♾️ безлимитный" if traffic_gb == 0 else f"{traffic_gb} ГБ"
            await message.answer(
                f"✅ Лимит трафика изменен на: {traffic_text}",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="📱 Подписка и настройки", callback_data=f"admin_user_subscription_{user_id}")]
                ])
            )
        else:
            await message.answer("❌ Ошибка изменения лимита трафика")
        
    except ValueError:
        await message.answer("❌ Введите корректное число ГБ")
        return
    
    await state.clear()


@admin_required
@error_handler
async def confirm_reset_devices(
    callback: types.CallbackQuery,
    db_user: User
):
    user_id = int(callback.data.split('_')[-1])
    
    await callback.message.edit_text(
        "🔄 <b>Сброс устройств пользователя</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b>\n"
        "Вы уверены, что хотите сбросить все HWID устройства этого пользователя?\n\n"
        "Это действие:\n"
        "• Удалит все привязанные устройства\n"
        "• Пользователь сможет заново подключить устройства\n"
        "• Действие необратимо!\n\n"
        "Продолжить?",
        reply_markup=get_confirmation_keyboard(
            f"admin_user_reset_devices_confirm_{user_id}",
            f"admin_user_subscription_{user_id}",
            db_user.language
        )
    )
    await callback.answer()


@admin_required
@error_handler
async def reset_user_devices(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_id = int(callback.data.split('_')[-1])
    
    try:
        user = await get_user_by_id(db, user_id)
        if not user or not user.remnawave_uuid:
            await callback.answer("❌ Пользователь не найден или не связан с RemnaWave", show_alert=True)
            return
        
        remnawave_service = RemnaWaveService()
        async with remnawave_service.get_api_client() as api:
            success = await api.reset_user_devices(user.remnawave_uuid)
        
        if success:
            await callback.message.edit_text(
                "✅ Устройства пользователя успешно сброшены",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="📱 Подписка и настройки", callback_data=f"admin_user_subscription_{user_id}")]
                ])
            )
            logger.info(f"Admin {db_user.id} reset devices for user {user_id}")
        else:
            await callback.message.edit_text(
                "❌ Ошибка сброса устройств",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="📱 Подписка и настройки", callback_data=f"admin_user_subscription_{user_id}")]
                ])
            )
        
    except Exception as e:
        logger.error(f"Error resetting devices: {e}")
        await callback.answer("❌ Ошибка сброса устройств", show_alert=True)

async def _update_user_devices(db: AsyncSession, user_id: int, devices: int, admin_id: int) -> bool:
    try:
        user = await get_user_by_id(db, user_id)
        if not user or not user.subscription:
            logger.error(f"Пользователь {user_id} или подписка не найдены")
            return False
        
        subscription = user.subscription
        old_devices = subscription.device_limit
        subscription.device_limit = devices
        subscription.updated_at = datetime.utcnow()
        
        await db.commit()
        
        if user.remnawave_uuid:
            try:
                remnawave_service = RemnaWaveService()
                async with remnawave_service.get_api_client() as api:
                    await api.update_user(
                        uuid=user.remnawave_uuid,
                        hwid_device_limit=devices,
                        description=settings.format_remnawave_user_description(
                            full_name=user.full_name,
                            username=user.username,
                            telegram_id=user.telegram_id
                        )
                    )
                logger.info(f"✅ Обновлен лимит устройств в RemnaWave для пользователя {user.telegram_id}")
            except Exception as rw_error:
                logger.error(f"❌ Ошибка обновления лимита устройств в RemnaWave: {rw_error}")
        
        logger.info(f"Админ {admin_id} изменил лимит устройств пользователя {user_id}: {old_devices} -> {devices}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления лимита устройств: {e}")
        await db.rollback()
        return False


async def _update_user_traffic(db: AsyncSession, user_id: int, traffic_gb: int, admin_id: int) -> bool:
    try:
        user = await get_user_by_id(db, user_id)
        if not user or not user.subscription:
            logger.error(f"Пользователь {user_id} или подписка не найдены")
            return False
        
        subscription = user.subscription
        old_traffic = subscription.traffic_limit_gb
        subscription.traffic_limit_gb = traffic_gb
        subscription.updated_at = datetime.utcnow()
        
        await db.commit()
        
        if user.remnawave_uuid:
            try:
                from app.external.remnawave_api import TrafficLimitStrategy
                
                remnawave_service = RemnaWaveService()
                async with remnawave_service.get_api_client() as api:
                    await api.update_user(
                        uuid=user.remnawave_uuid,
                        traffic_limit_bytes=traffic_gb * (1024**3) if traffic_gb > 0 else 0,
                        traffic_limit_strategy=TrafficLimitStrategy.MONTH,
                        description=settings.format_remnawave_user_description(
                            full_name=user.full_name,
                            username=user.username,
                            telegram_id=user.telegram_id
                        )
                    )
                logger.info(f"✅ Обновлен лимит трафика в RemnaWave для пользователя {user.telegram_id}")
            except Exception as rw_error:
                logger.error(f"❌ Ошибка обновления лимита трафика в RemnaWave: {rw_error}")
        
        traffic_text_old = "безлимитный" if old_traffic == 0 else f"{old_traffic} ГБ"
        traffic_text_new = "безлимитный" if traffic_gb == 0 else f"{traffic_gb} ГБ"
        logger.info(f"Админ {admin_id} изменил лимит трафика пользователя {user_id}: {traffic_text_old} -> {traffic_text_new}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления лимита трафика: {e}")
        await db.rollback()
        return False


async def _extend_subscription_by_days(db: AsyncSession, user_id: int, days: int, admin_id: int) -> bool:
    try:
        from app.database.crud.subscription import get_subscription_by_user_id, extend_subscription
        from app.services.subscription_service import SubscriptionService
        
        subscription = await get_subscription_by_user_id(db, user_id)
        if not subscription:
            logger.error(f"Подписка не найдена для пользователя {user_id}")
            return False
        
        await extend_subscription(db, subscription, days)
        
        subscription_service = SubscriptionService()
        await subscription_service.update_remnawave_user(db, subscription)
        
        if days > 0:
            logger.info(f"Админ {admin_id} продлил подписку пользователя {user_id} на {days} дней")
        else:
            logger.info(f"Админ {admin_id} сократил подписку пользователя {user_id} на {abs(days)} дней")
        return True

    except Exception as e:
        logger.error(f"Ошибка продления подписки: {e}")
        return False


async def _add_subscription_traffic(db: AsyncSession, user_id: int, gb: int, admin_id: int) -> bool:
    try:
        from app.database.crud.subscription import get_subscription_by_user_id, add_subscription_traffic
        from app.services.subscription_service import SubscriptionService
        
        subscription = await get_subscription_by_user_id(db, user_id)
        if not subscription:
            logger.error(f"Подписка не найдена для пользователя {user_id}")
            return False
        
        if gb == 0:  
            subscription.traffic_limit_gb = 0
            await db.commit()
        else:
            await add_subscription_traffic(db, subscription, gb)
        
        subscription_service = SubscriptionService()
        await subscription_service.update_remnawave_user(db, subscription)
        
        traffic_text = "безлимитный" if gb == 0 else f"{gb} ГБ"
        logger.info(f"Админ {admin_id} добавил трафик {traffic_text} пользователю {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка добавления трафика: {e}")
        return False


async def _deactivate_user_subscription(db: AsyncSession, user_id: int, admin_id: int) -> bool:
    try:
        from app.database.crud.subscription import get_subscription_by_user_id, deactivate_subscription
        from app.services.subscription_service import SubscriptionService
        
        subscription = await get_subscription_by_user_id(db, user_id)
        if not subscription:
            logger.error(f"Подписка не найдена для пользователя {user_id}")
            return False
        
        await deactivate_subscription(db, subscription)
        
        user = await get_user_by_id(db, user_id)
        if user and user.remnawave_uuid:
            subscription_service = SubscriptionService()
            await subscription_service.disable_remnawave_user(user.remnawave_uuid)
        
        logger.info(f"Админ {admin_id} деактивировал подписку пользователя {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка деактивации подписки: {e}")
        return False


async def _activate_user_subscription(db: AsyncSession, user_id: int, admin_id: int) -> bool:
    try:
        from app.database.crud.subscription import get_subscription_by_user_id
        from app.services.subscription_service import SubscriptionService
        from app.database.models import SubscriptionStatus
        from datetime import datetime
        
        subscription = await get_subscription_by_user_id(db, user_id)
        if not subscription:
            logger.error(f"Подписка не найдена для пользователя {user_id}")
            return False
        
        subscription.status = SubscriptionStatus.ACTIVE.value
        if subscription.end_date <= datetime.utcnow():
            subscription.end_date = datetime.utcnow() + timedelta(days=1)
        
        await db.commit()
        await db.refresh(subscription)
        
        subscription_service = SubscriptionService()
        await subscription_service.update_remnawave_user(db, subscription)
        
        logger.info(f"Админ {admin_id} активировал подписку пользователя {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка активации подписки: {e}")
        return False


async def _grant_trial_subscription(db: AsyncSession, user_id: int, admin_id: int) -> bool:
    try:
        from app.database.crud.subscription import get_subscription_by_user_id, create_trial_subscription
        from app.services.subscription_service import SubscriptionService
        
        existing_subscription = await get_subscription_by_user_id(db, user_id)
        if existing_subscription:
            logger.error(f"У пользователя {user_id} уже есть подписка")
            return False
        
        forced_devices = None
        if not settings.is_devices_selection_enabled():
            forced_devices = settings.get_disabled_mode_device_limit()

        subscription = await create_trial_subscription(
            db,
            user_id,
            device_limit=forced_devices,
        )
        
        subscription_service = SubscriptionService()
        await subscription_service.create_remnawave_user(db, subscription)
        
        logger.info(f"Админ {admin_id} выдал триальную подписку пользователю {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка выдачи триальной подписки: {e}")
        return False


async def _grant_paid_subscription(db: AsyncSession, user_id: int, days: int, admin_id: int) -> bool:
    try:
        from app.database.crud.subscription import get_subscription_by_user_id, create_paid_subscription
        from app.services.subscription_service import SubscriptionService
        from app.config import settings
        
        existing_subscription = await get_subscription_by_user_id(db, user_id)
        if existing_subscription:
            logger.error(f"У пользователя {user_id} уже есть подписка")
            return False
        
        trial_squads: list[str] = []

        try:
            from app.database.crud.server_squad import get_random_trial_squad_uuid

            trial_uuid = await get_random_trial_squad_uuid(db)
            if trial_uuid:
                trial_squads = [trial_uuid]
        except Exception as error:
            logger.error(
                "Не удалось подобрать сквад при выдаче подписки админом %s: %s",
                admin_id,
                error,
            )

        forced_devices = None
        if not settings.is_devices_selection_enabled():
            forced_devices = settings.get_disabled_mode_device_limit()

        device_limit = settings.DEFAULT_DEVICE_LIMIT
        if forced_devices is not None:
            device_limit = forced_devices

        subscription = await create_paid_subscription(
            db=db,
            user_id=user_id,
            duration_days=days,
            traffic_limit_gb=settings.DEFAULT_TRAFFIC_LIMIT_GB,
            device_limit=device_limit,
            connected_squads=trial_squads,
            update_server_counters=True,
        )
        
        subscription_service = SubscriptionService()
        await subscription_service.create_remnawave_user(db, subscription)
        
        logger.info(f"Админ {admin_id} выдал платную подписку на {days} дней пользователю {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка выдачи платной подписки: {e}")
        return False


async def _calculate_subscription_period_price(
    db: AsyncSession,
    target_user: User,
    subscription: Subscription,
    period_days: int,
    subscription_service: Optional[SubscriptionService] = None,
) -> int:
    """Рассчитывает стоимость подписки для администратора с учётом всех параметров."""

    service = subscription_service or SubscriptionService()

    connected_squads = list(subscription.connected_squads or [])
    server_ids = []

    if connected_squads:
        try:
            server_ids = await get_server_ids_by_uuids(db, connected_squads)
            if len(server_ids) != len(connected_squads):
                logger.warning(
                    "Не удалось сопоставить все сервера подписки пользователя %s для расчёта цены",
                    target_user.telegram_id,
                )
        except Exception as e:
            logger.error(
                "Не удалось получить идентификаторы серверов для расчёта цены подписки пользователя %s: %s",
                target_user.telegram_id,
                e,
            )
            server_ids = []
    traffic_limit_gb = subscription.traffic_limit_gb
    if traffic_limit_gb is None:
        traffic_limit_gb = settings.DEFAULT_TRAFFIC_LIMIT_GB

    device_limit = subscription.device_limit
    if not device_limit or device_limit < 0:
        device_limit = settings.DEFAULT_DEVICE_LIMIT

    total_price, _ = await service.calculate_subscription_price(
        period_days=period_days,
        traffic_gb=traffic_limit_gb,
        server_squad_ids=server_ids,
        devices=device_limit,
        db=db,
        user=target_user,
        promo_group=target_user.promo_group,
    )

    return total_price

@admin_required
@error_handler
async def cleanup_inactive_users(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    user_service = UserService()
    deleted_count = await user_service.cleanup_inactive_users(db)
    
    await callback.message.edit_text(
        f"✅ Очистка завершена\n\n"
        f"Удалено неактивных пользователей: {deleted_count}",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_users")]
        ])
    )
    await callback.answer()

@admin_required
@error_handler
async def change_subscription_type(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_id = int(callback.data.split('_')[-1])
    
    user_service = UserService()
    profile = await user_service.get_user_profile(db, user_id)
    
    if not profile or not profile["subscription"]:
        await callback.answer("❌ Пользователь или подписка не найдены", show_alert=True)
        return
    
    subscription = profile["subscription"]
    current_type = "🎁 Триал" if subscription.is_trial else "💎 Платная"
    
    text = f"🔄 <b>Смена типа подписки</b>\n\n"
    text += f"👤 {profile['user'].full_name}\n"
    text += f"📱 Текущий тип: {current_type}\n\n"
    text += f"Выберите новый тип подписки:"
    
    keyboard = []
    
    if subscription.is_trial:
        keyboard.append([
            InlineKeyboardButton(
                text="💎 Сделать платной", 
                callback_data=f"admin_sub_type_paid_{user_id}"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text="🎁 Сделать триальной", 
                callback_data=f"admin_sub_type_trial_{user_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="⬅️ Назад", 
            callback_data=f"admin_user_subscription_{user_id}"
        )
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@admin_required
@error_handler
async def admin_buy_subscription(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    user_id = int(callback.data.split('_')[-1])
    
    user_service = UserService()
    profile = await user_service.get_user_profile(db, user_id)
    
    if not profile:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    target_user = profile["user"]
    subscription = profile["subscription"]
    
    if not subscription:
        await callback.answer("❌ У пользователя нет подписки", show_alert=True)
        return
    
    available_periods = settings.get_available_subscription_periods()

    subscription_service = SubscriptionService()
    period_buttons = []

    for period in available_periods:
        try:
            price_kopeks = await _calculate_subscription_period_price(
                db,
                target_user,
                subscription,
                period,
                subscription_service=subscription_service,
            )
        except Exception as e:
            logger.error(
                "Ошибка расчёта стоимости подписки для пользователя %s и периода %s дней: %s",
                target_user.telegram_id,
                period,
                e,
            )
            continue

        period_buttons.append([
            types.InlineKeyboardButton(
                text=f"{period} дней ({settings.format_price(price_kopeks)})",
                callback_data=f"admin_buy_sub_confirm_{user_id}_{period}_{price_kopeks}"
            )
        ])

    if not period_buttons:
        await callback.answer("❌ Не удалось рассчитать стоимость подписки", show_alert=True)
        return

    period_buttons.append([
        types.InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"admin_user_subscription_{user_id}"
        )
    ])

    text = f"💳 <b>Покупка подписки для пользователя</b>\n\n"
    target_user_link = f'<a href="tg://user?id={target_user.telegram_id}">{target_user.full_name}</a>'
    text += f"👤 {target_user_link} (ID: {target_user.telegram_id})\n"
    text += f"💰 Баланс пользователя: {settings.format_price(target_user.balance_kopeks)}\n\n"
    traffic_text = "Безлимит" if (subscription.traffic_limit_gb or 0) <= 0 else f"{subscription.traffic_limit_gb} ГБ"
    devices_limit = subscription.device_limit
    if devices_limit is None:
        devices_limit = settings.DEFAULT_DEVICE_LIMIT
    servers_count = len(subscription.connected_squads or [])
    text += f"📶 Трафик: {traffic_text}\n"
    text += f"📱 Устройства: {devices_limit}\n"
    text += f"🌐 Серверов: {servers_count}\n\n"
    text += "Выберите период подписки:\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=period_buttons)
    )
    await callback.answer()


@admin_required
@error_handler
async def admin_buy_subscription_confirm(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    parts = callback.data.split('_')
    user_id = int(parts[4])
    period_days = int(parts[5])
    price_kopeks_from_callback = int(parts[6]) if len(parts) > 6 else None
    
    user_service = UserService()
    profile = await user_service.get_user_profile(db, user_id)
    
    if not profile:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    target_user = profile["user"]
    subscription = profile["subscription"]

    if not subscription:
        await callback.answer("❌ У пользователя нет подписки", show_alert=True)
        return

    subscription_service = SubscriptionService()

    try:
        price_kopeks = await _calculate_subscription_period_price(
            db,
            target_user,
            subscription,
            period_days,
            subscription_service=subscription_service,
        )
    except Exception as e:
        logger.error(
            "Ошибка расчёта стоимости подписки при подтверждении админом для пользователя %s: %s",
            target_user.telegram_id,
            e,
        )
        await callback.answer("❌ Не удалось рассчитать стоимость подписки", show_alert=True)
        return

    if price_kopeks_from_callback is not None and price_kopeks_from_callback != price_kopeks:
        logger.info(
            "Стоимость подписки для пользователя %s изменилась с %s до %s при подтверждении",
            target_user.telegram_id,
            price_kopeks_from_callback,
            price_kopeks,
        )

    if target_user.balance_kopeks < price_kopeks:
        missing_kopeks = price_kopeks - target_user.balance_kopeks
        await callback.message.edit_text(
            f"❌ Недостаточно средств на балансе пользователя\n\n"
            f"💰 Баланс пользователя: {settings.format_price(target_user.balance_kopeks)}\n"
            f"💳 Стоимость подписки: {settings.format_price(price_kopeks)}\n"
            f"📉 Не хватает: {settings.format_price(missing_kopeks)}\n\n"
            f"Пополните баланс пользователя перед покупкой.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text="⬅️ Назад к подписке",
                    callback_data=f"admin_user_subscription_{user_id}"
                )]
            ])
        )
        await callback.answer()
        return
    
    text = f"💳 <b>Подтверждение покупки подписки</b>\n\n"
    target_user_link = f'<a href="tg://user?id={target_user.telegram_id}">{target_user.full_name}</a>'
    text += f"👤 {target_user_link} (ID: {target_user.telegram_id})\n"
    text += f"📅 Период подписки: {period_days} дней\n"
    text += f"💰 Стоимость: {settings.format_price(price_kopeks)}\n"
    text += f"💰 Баланс пользователя: {settings.format_price(target_user.balance_kopeks)}\n\n"
    traffic_text = "Безлимит" if (subscription.traffic_limit_gb or 0) <= 0 else f"{subscription.traffic_limit_gb} ГБ"
    devices_limit = subscription.device_limit
    if devices_limit is None:
        devices_limit = settings.DEFAULT_DEVICE_LIMIT
    servers_count = len(subscription.connected_squads or [])
    text += f"📶 Трафик: {traffic_text}\n"
    text += f"📱 Устройства: {devices_limit}\n"
    text += f"🌐 Серверов: {servers_count}\n\n"
    text += "Вы уверены, что хотите купить подписку для этого пользователя?"
    
    keyboard = [
        [
            types.InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=f"admin_buy_sub_execute_{user_id}_{period_days}_{price_kopeks}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=f"admin_sub_buy_{user_id}"
            )
        ]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def admin_buy_subscription_execute(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    parts = callback.data.split('_')
    user_id = int(parts[4])
    period_days = int(parts[5])
    price_kopeks_from_callback = int(parts[6]) if len(parts) > 6 else None
    
    user_service = UserService()
    profile = await user_service.get_user_profile(db, user_id)
    
    if not profile:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    target_user = profile["user"]
    subscription = profile["subscription"]

    if not subscription:
        await callback.answer("❌ У пользователя нет подписки", show_alert=True)
        return

    subscription_service = SubscriptionService()

    try:
        price_kopeks = await _calculate_subscription_period_price(
            db,
            target_user,
            subscription,
            period_days,
            subscription_service=subscription_service,
        )
    except Exception as e:
        logger.error(
            "Ошибка расчёта стоимости подписки при списании средств админом для пользователя %s: %s",
            target_user.telegram_id,
            e,
        )
        await callback.answer("❌ Не удалось рассчитать стоимость подписки", show_alert=True)
        return

    if price_kopeks_from_callback is not None and price_kopeks_from_callback != price_kopeks:
        logger.info(
            "Стоимость подписки для пользователя %s изменилась с %s до %s перед списанием",
            target_user.telegram_id,
            price_kopeks_from_callback,
            price_kopeks,
        )

    if target_user.balance_kopeks < price_kopeks:
        await callback.answer("❌ Недостаточно средств на балансе пользователя", show_alert=True)
        return
    
    try:
        from app.database.crud.user import subtract_user_balance
        success = await subtract_user_balance(
            db, target_user, price_kopeks,
            f"Покупка подписки на {period_days} дней (администратор)"
        )
        
        if not success:
            await callback.answer("❌ Ошибка списания средств", show_alert=True)
            return
        
        if subscription:
            current_time = datetime.utcnow()
            bonus_period = timedelta()

            if (
                subscription.is_trial
                and settings.TRIAL_ADD_REMAINING_DAYS_TO_PAID
                and subscription.end_date
            ):
                remaining_trial_delta = subscription.end_date - current_time
                if remaining_trial_delta.total_seconds() > 0:
                    bonus_period = remaining_trial_delta
                    logger.info(
                        "Админ продлевает подписку: добавляем оставшееся время триала (%s) пользователю %s",
                        bonus_period,
                        target_user.telegram_id,
                    )

            if subscription.end_date <= current_time:
                subscription.start_date = current_time

            subscription.end_date = current_time + timedelta(days=period_days) + bonus_period
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.updated_at = current_time

            if subscription.is_trial or not subscription.is_active:
                subscription.is_trial = False
                if subscription.traffic_limit_gb != 0: 
                    subscription.traffic_limit_gb = 0
                subscription.device_limit = settings.DEFAULT_DEVICE_LIMIT
                if subscription.is_trial:
                    subscription.traffic_used_gb = 0.0
            
            await db.commit()
            await db.refresh(subscription)
            
            from app.database.crud.transaction import create_transaction
            transaction = await create_transaction(
                db=db,
                user_id=target_user.id,
                type=TransactionType.SUBSCRIPTION_PAYMENT,
                amount_kopeks=price_kopeks,
                description=f"Продление подписки на {period_days} дней (администратор)"
            )
            
            try:
                from app.services.remnawave_service import RemnaWaveService
                from app.external.remnawave_api import UserStatus, TrafficLimitStrategy
                remnawave_service = RemnaWaveService()
                
                hwid_limit = resolve_hwid_device_limit_for_payload(subscription)

                if target_user.remnawave_uuid:
                    async with remnawave_service.get_api_client() as api:
                        update_kwargs = dict(
                            uuid=target_user.remnawave_uuid,
                            status=UserStatus.ACTIVE if subscription.is_active else UserStatus.EXPIRED,
                            expire_at=subscription.end_date,
                            traffic_limit_bytes=subscription.traffic_limit_gb * (1024**3) if subscription.traffic_limit_gb > 0 else 0,
                            traffic_limit_strategy=TrafficLimitStrategy.MONTH,
                            description=settings.format_remnawave_user_description(
                                full_name=target_user.full_name,
                                username=target_user.username,
                                telegram_id=target_user.telegram_id
                            ),
                            active_internal_squads=subscription.connected_squads,
                        )

                        if hwid_limit is not None:
                            update_kwargs['hwid_device_limit'] = hwid_limit

                        remnawave_user = await api.update_user(**update_kwargs)
                else:
                    username = settings.format_remnawave_username(
                        full_name=target_user.full_name,
                        username=target_user.username,
                        telegram_id=target_user.telegram_id,
                    )
                    async with remnawave_service.get_api_client() as api:
                        create_kwargs = dict(
                            username=username,
                            expire_at=subscription.end_date,
                            status=UserStatus.ACTIVE if subscription.is_active else UserStatus.EXPIRED,
                            traffic_limit_bytes=subscription.traffic_limit_gb * (1024**3) if subscription.traffic_limit_gb > 0 else 0,
                            traffic_limit_strategy=TrafficLimitStrategy.MONTH,
                            telegram_id=target_user.telegram_id,
                            description=settings.format_remnawave_user_description(
                                full_name=target_user.full_name,
                                username=target_user.username,
                                telegram_id=target_user.telegram_id
                            ),
                            active_internal_squads=subscription.connected_squads,
                        )

                        if hwid_limit is not None:
                            create_kwargs['hwid_device_limit'] = hwid_limit

                        remnawave_user = await api.create_user(**create_kwargs)
                    
                    if remnawave_user and hasattr(remnawave_user, 'uuid'):
                        target_user.remnawave_uuid = remnawave_user.uuid
                        await db.commit()
                
                if remnawave_user:
                    logger.info(f"Пользователь {target_user.telegram_id} успешно обновлен в RemnaWave")
                else:
                    logger.error(f"Ошибка обновления пользователя {target_user.telegram_id} в RemnaWave")
            except Exception as e:
                logger.error(f"Ошибка работы с RemnaWave для пользователя {target_user.telegram_id}: {e}")
            
            message = f"✅ Подписка пользователя продлена на {period_days} дней"
        else:
            message = "❌ Ошибка: у пользователя нет существующей подписки"
        
        target_user_link = f'<a href="tg://user?id={target_user.telegram_id}">{target_user.full_name}</a>'
        await callback.message.edit_text(
            f"{message}\n\n"
            f"👤 {target_user_link} (ID: {target_user.telegram_id})\n"
            f"💰 Списано: {settings.format_price(price_kopeks)}\n"
            f"📅 Подписка действительна до: {format_datetime(subscription.end_date)}",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text="⬅️ Назад к подписке",
                    callback_data=f"admin_user_subscription_{user_id}"
                )]
            ]),
            parse_mode="HTML"
        )
        
        try:
            if callback.bot:
                await callback.bot.send_message(
                    chat_id=target_user.telegram_id,
                    text=f"💳 <b>Администратор продлил вашу подписку</b>\n\n"
                         f"📅 Подписка продлена на {period_days} дней\n"
                         f"💰 Списано с баланса: {settings.format_price(price_kopeks)}\n"
                         f"📅 Подписка действительна до: {format_datetime(subscription.end_date)}",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {target_user.telegram_id}: {e}")
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка покупки подписки администратором: {e}")
        await callback.answer("❌ Ошибка при покупке подписки", show_alert=True)
        
        await db.rollback()


@admin_required
@error_handler
async def change_subscription_type_confirm(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    parts = callback.data.split('_')
    new_type = parts[-2]  # 'paid' или 'trial'
    user_id = int(parts[-1])
    
    success = await _change_subscription_type(db, user_id, new_type, db_user.id)
    
    if success:
        type_text = "платной" if new_type == "paid" else "триальной"
        await callback.message.edit_text(
            f"✅ Тип подписки успешно изменен на {type_text}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 К подписке", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка изменения типа подписки",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 К подписке", callback_data=f"admin_user_subscription_{user_id}")]
            ])
        )
    
    await callback.answer()


async def _change_subscription_type(db: AsyncSession, user_id: int, new_type: str, admin_id: int) -> bool:
    try:
        from app.database.crud.subscription import get_subscription_by_user_id
        from app.services.subscription_service import SubscriptionService
        
        subscription = await get_subscription_by_user_id(db, user_id)
        if not subscription:
            logger.error(f"Подписка не найдена для пользователя {user_id}")
            return False
        
        new_is_trial = (new_type == "trial")
        
        if subscription.is_trial == new_is_trial:
            logger.info(f"Тип подписки уже установлен корректно для пользователя {user_id}")
            return True
        
        old_type = "триальной" if subscription.is_trial else "платной"
        new_type_text = "триальной" if new_is_trial else "платной"
        
        subscription.is_trial = new_is_trial
        subscription.updated_at = datetime.utcnow()
        
        if not new_is_trial and subscription.is_trial:
            user = await get_user_by_id(db, user_id)
            if user:
                user.has_had_paid_subscription = True
        
        await db.commit()
        
        subscription_service = SubscriptionService()
        await subscription_service.update_remnawave_user(db, subscription)
        
        logger.info(f"Админ {admin_id} изменил тип подписки пользователя {user_id}: {old_type} -> {new_type_text}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка изменения типа подписки: {e}")
        await db.rollback()
        return False


def register_handlers(dp: Dispatcher):
    
    dp.callback_query.register(
        show_users_menu,
        F.data == "admin_users"
    )
    
    dp.callback_query.register(
        show_users_list,
        F.data == "admin_users_list"
    )
    
    dp.callback_query.register(
        show_users_statistics,
        F.data == "admin_users_stats"
    )
    
    dp.callback_query.register(
        show_user_subscription,
        F.data.startswith("admin_user_subscription_")
    )

    dp.callback_query.register(
        show_user_transactions,
        F.data.startswith("admin_user_transactions_")
    )

    dp.callback_query.register(
        show_user_statistics,
        F.data.startswith("admin_user_statistics_")
    )

    dp.callback_query.register(
        block_user,
        F.data.startswith("admin_user_block_confirm_")
    )

    dp.callback_query.register(
        delete_user_account,
        F.data.startswith("admin_user_delete_confirm_")
    )

    dp.callback_query.register(
        confirm_user_block,
        F.data.startswith("admin_user_block_") & ~F.data.contains("confirm")
    )

    dp.callback_query.register(
        unblock_user,
        F.data.startswith("admin_user_unblock_confirm_")
    )

    dp.callback_query.register(
        confirm_user_unblock,
        F.data.startswith("admin_user_unblock_") & ~F.data.contains("confirm")
    )

    dp.callback_query.register(
        confirm_user_delete,
        F.data.startswith("admin_user_delete_") & ~F.data.contains("confirm")
    )
    
    dp.callback_query.register(
        handle_users_list_pagination_fixed,
        F.data.startswith("admin_users_list_page_")
    )
    
    dp.callback_query.register(
        handle_users_balance_list_pagination,
        F.data.startswith("admin_users_balance_list_page_")
    )
    
    dp.callback_query.register(
        handle_users_traffic_list_pagination,
        F.data.startswith("admin_users_traffic_list_page_")
    )

    dp.callback_query.register(
        handle_users_activity_list_pagination,
        F.data.startswith("admin_users_activity_list_page_")
    )

    dp.callback_query.register(
        handle_users_spending_list_pagination,
        F.data.startswith("admin_users_spending_list_page_")
    )

    dp.callback_query.register(
        handle_users_purchases_list_pagination,
        F.data.startswith("admin_users_purchases_list_page_")
    )

    dp.callback_query.register(
        handle_users_campaign_list_pagination,
        F.data.startswith("admin_users_campaign_list_page_")
    )
    
    dp.callback_query.register(
        start_user_search,
        F.data == "admin_users_search"
    )
    
    dp.message.register(
        process_user_search,
        AdminStates.waiting_for_user_search
    )
    
    dp.callback_query.register(
        show_user_management,
        F.data.startswith("admin_user_manage_")
    )

    dp.callback_query.register(
        show_user_promo_group,
        F.data.startswith("admin_user_promo_group_") & ~F.data.contains("_set_") & ~F.data.contains("_toggle_")
    )

    dp.callback_query.register(
        set_user_promo_group,
        F.data.startswith("admin_user_promo_group_toggle_")
    )

    dp.callback_query.register(
        start_balance_edit,
        F.data.startswith("admin_user_balance_")
    )

    dp.message.register(
        process_balance_edit,
        AdminStates.editing_user_balance
    )

    dp.callback_query.register(
        show_user_referrals,
        F.data.startswith("admin_user_referrals_") & ~F.data.contains("_edit")
    )

    dp.callback_query.register(
        start_edit_referral_percent,
        F.data.startswith("admin_user_referral_percent_")
        & ~F.data.contains("_set_")
        & ~F.data.contains("_reset")
    )

    dp.callback_query.register(
        set_referral_percent_button,
        F.data.startswith("admin_user_referral_percent_set_")
        | F.data.startswith("admin_user_referral_percent_reset_")
    )

    dp.message.register(
        process_referral_percent_input,
        AdminStates.editing_user_referral_percent,
    )

    dp.callback_query.register(
        start_edit_user_referrals,
        F.data.startswith("admin_user_referrals_edit_")
    )

    dp.message.register(
        process_edit_user_referrals,
        AdminStates.editing_user_referrals
    )

    dp.callback_query.register(
        start_send_user_message,
        F.data.startswith("admin_user_send_message_")
    )

    dp.message.register(
        process_send_user_message,
        AdminStates.sending_user_message
    )
    
    dp.callback_query.register(
        show_inactive_users,
        F.data == "admin_users_inactive"
    )
    
    dp.callback_query.register(
        cleanup_inactive_users,
        F.data == "admin_cleanup_inactive"
    )

    
    dp.callback_query.register(
        extend_user_subscription,
        F.data.startswith("admin_sub_extend_") & ~F.data.contains("days") & ~F.data.contains("confirm")
    )
    
    dp.callback_query.register(
        process_subscription_extension_days,
        F.data.startswith("admin_sub_extend_days_")
    )
    
    dp.message.register(
        process_subscription_extension_text,
        AdminStates.extending_subscription
    )
    
    dp.callback_query.register(
        add_subscription_traffic,
        F.data.startswith("admin_sub_traffic_") & ~F.data.contains("add")
    )
    
    dp.callback_query.register(
        process_traffic_addition_button,
        F.data.startswith("admin_sub_traffic_add_")
    )
    
    dp.message.register(
        process_traffic_addition_text,
        AdminStates.adding_traffic
    )
    
    dp.callback_query.register(
        deactivate_user_subscription,
        F.data.startswith("admin_sub_deactivate_") & ~F.data.contains("confirm")
    )
    
    dp.callback_query.register(
        confirm_subscription_deactivation,
        F.data.startswith("admin_sub_deactivate_confirm_")
    )
    
    dp.callback_query.register(
        activate_user_subscription,
        F.data.startswith("admin_sub_activate_")
    )
    
    dp.callback_query.register(
        grant_trial_subscription,
        F.data.startswith("admin_sub_grant_trial_")
    )
    
    dp.callback_query.register(
        grant_paid_subscription,
        F.data.startswith("admin_sub_grant_") & ~F.data.contains("trial") & ~F.data.contains("days")
    )
    
    dp.callback_query.register(
        process_subscription_grant_days,
        F.data.startswith("admin_sub_grant_days_")
    )
    
    dp.message.register(
        process_subscription_grant_text,
        AdminStates.granting_subscription
    )

    dp.callback_query.register(
        show_user_servers_management,
        F.data.startswith("admin_user_servers_")
    )
    
    dp.callback_query.register(
        show_server_selection,
        F.data.startswith("admin_user_change_server_")
    )
    
    dp.callback_query.register(
        toggle_user_server,
        F.data.startswith("admin_user_toggle_server_") & ~F.data.endswith("_add") & ~F.data.endswith("_remove")
    )
    
    dp.callback_query.register(
        start_devices_edit,
        F.data.startswith("admin_user_devices_") & ~F.data.contains("set")
    )
    
    dp.callback_query.register(
        set_user_devices_button,
        F.data.startswith("admin_user_devices_set_")
    )
    
    dp.message.register(
        process_devices_edit_text,
        AdminStates.editing_user_devices
    )
    
    dp.callback_query.register(
        start_traffic_edit,
        F.data.startswith("admin_user_traffic_") & ~F.data.contains("set")
    )
    
    dp.callback_query.register(
        set_user_traffic_button,
        F.data.startswith("admin_user_traffic_set_")
    )
    
    dp.message.register(
        process_traffic_edit_text,
        AdminStates.editing_user_traffic
    )
    
    dp.callback_query.register(
        confirm_reset_devices,
        F.data.startswith("admin_user_reset_devices_") & ~F.data.contains("confirm")
    )
    
    dp.callback_query.register(
        reset_user_devices,
        F.data.startswith("admin_user_reset_devices_confirm_")
    )

    dp.callback_query.register(
        change_subscription_type,
        F.data.startswith("admin_sub_change_type_")
    )
    
    dp.callback_query.register(
        change_subscription_type_confirm,
        F.data.startswith("admin_sub_type_")
    )
    
    # Регистрация обработчика покупки подписки администратором
    dp.callback_query.register(
        admin_buy_subscription,
        F.data.startswith("admin_sub_buy_")
    )
    
    # Регистрация дополнительных обработчиков для покупки подписки
    dp.callback_query.register(
        admin_buy_subscription_confirm,
        F.data.startswith("admin_buy_sub_confirm_")
    )
    
    dp.callback_query.register(
        admin_buy_subscription_execute,
        F.data.startswith("admin_buy_sub_execute_")
    )
    
    # Регистрация обработчиков для фильтрации пользователей
    dp.callback_query.register(
        show_users_filters,
        F.data == "admin_users_filters"
    )
    
    dp.callback_query.register(
        show_users_list_by_balance,
        F.data == "admin_users_balance_filter"
    )
    
    dp.callback_query.register(
        show_users_list_by_traffic,
        F.data == "admin_users_traffic_filter"
    )

    dp.callback_query.register(
        show_users_list_by_last_activity,
        F.data == "admin_users_activity_filter"
    )

    dp.callback_query.register(
        show_users_list_by_spending,
        F.data == "admin_users_spending_filter"
    )

    dp.callback_query.register(
        show_users_list_by_purchases,
        F.data == "admin_users_purchases_filter"
    )

    dp.callback_query.register(
        show_users_list_by_campaign,
        F.data == "admin_users_campaign_filter"
    )
    
