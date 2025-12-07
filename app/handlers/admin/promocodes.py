import logging
from datetime import datetime, timedelta
from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.states import AdminStates
from app.database.models import PromoCode, PromoCodeUse, PromoCodeType, User
from app.keyboards.admin import (
    get_admin_promocodes_keyboard, get_promocode_type_keyboard,
    get_admin_pagination_keyboard, get_confirmation_keyboard
)
from app.localization.texts import get_texts
from app.database.crud.promocode import (
    get_promocodes_list, get_promocodes_count, create_promocode,
    get_promocode_statistics, get_promocode_by_code, update_promocode,
    delete_promocode, get_promocode_by_id
)
from app.database.crud.promo_group import get_promo_group_by_id, get_promo_groups_with_counts
from app.utils.decorators import admin_required, error_handler
from app.utils.formatters import format_datetime

logger = logging.getLogger(__name__)


@admin_required
@error_handler
async def show_promocodes_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    total_codes = await get_promocodes_count(db)
    active_codes = await get_promocodes_count(db, is_active=True)
    
    text = texts.t(
        "ADMIN_PROMOCODES_MENU",
        "🎫 <b>Promocode Management</b>\n\n"
        "📊 <b>Statistics:</b>\n"
        "- Total promocodes: {total}\n"
        "- Active: {active}\n"
        "- Inactive: {inactive}\n\n"
        "Select an action:"
    ).format(
        total=total_codes,
        active=active_codes,
        inactive=total_codes - active_codes
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_promocodes_keyboard(db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_promocodes_list(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    page: int = 1
):
    texts = get_texts(db_user.language)
    limit = 10
    offset = (page - 1) * limit
    
    promocodes = await get_promocodes_list(db, offset=offset, limit=limit)
    total_count = await get_promocodes_count(db)
    total_pages = (total_count + limit - 1) // limit
    
    if not promocodes:
        await callback.message.edit_text(
            texts.t("ADMIN_PROMOCODES_NOT_FOUND", "🎫 Promocodes not found"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_promocodes")]
            ])
        )
        await callback.answer()
        return
    
    text = texts.t(
        "ADMIN_PROMOCODES_LIST_HEADER",
        "🎫 <b>Promocode List</b> (page {page}/{total})"
    ).format(page=page, total=total_pages) + "\n\n"
    keyboard = []
    
    for promo in promocodes:
        status_emoji = "✅" if promo.is_active else "❌"
        type_emoji = {
            "balance": "💰",
            "subscription_days": "📅",
            "trial_subscription": "🎁",
            "promo_group": "🏷️"
        }.get(promo.type, "🎫")

        text += f"{status_emoji} {type_emoji} <code>{promo.code}</code>\n"
        text += texts.t("ADMIN_PROMOCODES_USES", "📊 Uses: {current}/{max}").format(
            current=promo.current_uses, max=promo.max_uses
        ) + "\n"

        if promo.type == PromoCodeType.BALANCE.value:
            text += texts.t("ADMIN_PROMOCODES_BONUS", "💰 Bonus: {amount}").format(
                amount=settings.format_price(promo.balance_bonus_kopeks)
            ) + "\n"
        elif promo.type == PromoCodeType.SUBSCRIPTION_DAYS.value:
            text += texts.t("ADMIN_PROMOCODES_DAYS", "📅 Days: {days}").format(
                days=promo.subscription_days
            ) + "\n"
        elif promo.type == PromoCodeType.PROMO_GROUP.value:
            if promo.promo_group:
                text += texts.t("ADMIN_PROMOCODES_PROMO_GROUP", "🏷️ Promo group: {name}").format(
                    name=promo.promo_group.name
                ) + "\n"

        if promo.valid_until:
            text += texts.t("ADMIN_PROMOCODES_VALID_UNTIL", "⏰ Until: {date}").format(
                date=format_datetime(promo.valid_until)
            ) + "\n"
        
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"🎫 {promo.code}", 
                callback_data=f"promo_manage_{promo.id}"
            )
        ])
        
        text += "\n" 
    
    if total_pages > 1:
        pagination_row = get_admin_pagination_keyboard(
            page, total_pages, "admin_promo_list", "admin_promocodes", db_user.language
        ).inline_keyboard[0]
        keyboard.append(pagination_row)
    
    keyboard.extend([
        [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CREATE", "➕ Create"), callback_data="admin_promo_create")],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_promocodes")]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_promocode_management(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    promo_id = int(callback.data.split('_')[-1])

    promo = await get_promocode_by_id(db, promo_id)
    if not promo:
        await callback.answer(texts.t("ADMIN_PROMOCODE_NOT_FOUND", "❌ Promocode not found"), show_alert=True)
        return
    
    status_emoji = "✅" if promo.is_active else "❌"
    type_emoji = {
        "balance": "💰",
        "subscription_days": "📅",
        "trial_subscription": "🎁",
        "promo_group": "🏷️"
    }.get(promo.type, "🎫")

    status_text = texts.t("ADMIN_STATUS_ACTIVE", "Active") if promo.is_active else texts.t("ADMIN_STATUS_INACTIVE", "Inactive")
    
    text = texts.t(
        "ADMIN_PROMOCODE_MANAGE_HEADER",
        "🎫 <b>Promocode Management</b>\n\n"
        "{type_emoji} <b>Code:</b> <code>{code}</code>\n"
        "{status_emoji} <b>Status:</b> {status}\n"
        "📊 <b>Uses:</b> {current}/{max}"
    ).format(
        type_emoji=type_emoji,
        code=promo.code,
        status_emoji=status_emoji,
        status=status_text,
        current=promo.current_uses,
        max=promo.max_uses
    ) + "\n"

    if promo.type == PromoCodeType.BALANCE.value:
        text += texts.t("ADMIN_PROMOCODE_BONUS_LABEL", "💰 <b>Bonus:</b> {amount}").format(
            amount=settings.format_price(promo.balance_bonus_kopeks)
        ) + "\n"
    elif promo.type == PromoCodeType.SUBSCRIPTION_DAYS.value:
        text += texts.t("ADMIN_PROMOCODE_DAYS_LABEL", "📅 <b>Days:</b> {days}").format(
            days=promo.subscription_days
        ) + "\n"
    elif promo.type == PromoCodeType.PROMO_GROUP.value:
        if promo.promo_group:
            text += texts.t("ADMIN_PROMOCODE_PROMO_GROUP_LABEL", "🏷️ <b>Promo group:</b> {name} (priority: {priority})").format(
                name=promo.promo_group.name, priority=promo.promo_group.priority
            ) + "\n"
        elif promo.promo_group_id:
            text += texts.t("ADMIN_PROMOCODE_PROMO_GROUP_ID_LABEL", "🏷️ <b>Promo group ID:</b> {id} (not found)").format(
                id=promo.promo_group_id
            ) + "\n"

    if promo.valid_until:
        text += texts.t("ADMIN_PROMOCODE_VALID_UNTIL_LABEL", "⏰ <b>Valid until:</b> {date}").format(
            date=format_datetime(promo.valid_until)
        ) + "\n"
    
    text += texts.t("ADMIN_PROMOCODE_CREATED_LABEL", "📅 <b>Created:</b> {date}").format(
        date=format_datetime(promo.created_at)
    ) + "\n"
    
    keyboard = [
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_EDIT", "✏️ Edit"), 
                callback_data=f"promo_edit_{promo.id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_TOGGLE_STATUS", "🔄 Toggle status"), 
                callback_data=f"promo_toggle_{promo.id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_STATISTICS", "📊 Statistics"), 
                callback_data=f"promo_stats_{promo.id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_DELETE", "🗑️ Delete"), 
                callback_data=f"promo_delete_{promo.id}"
            )
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_LIST", "⬅️ To list"), callback_data="admin_promo_list")
        ]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@admin_required
@error_handler
async def show_promocode_edit_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    try:
        promo_id = int(callback.data.split('_')[-1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_ERROR_PROMO_ID", "❌ Error getting promocode ID"), show_alert=True)
        return

    promo = await get_promocode_by_id(db, promo_id)
    if not promo:
        await callback.answer(texts.t("ADMIN_PROMOCODE_NOT_FOUND", "❌ Promocode not found"), show_alert=True)
        return
    
    text = texts.t(
        "ADMIN_PROMOCODE_EDIT_HEADER",
        "✏️ <b>Edit promocode</b> <code>{code}</code>\n\n💰 <b>Current parameters:</b>"
    ).format(code=promo.code) + "\n"
    
    if promo.type == PromoCodeType.BALANCE.value:
        text += texts.t("ADMIN_PROMOCODE_EDIT_BONUS", "• Bonus: {amount}").format(
            amount=settings.format_price(promo.balance_bonus_kopeks)
        ) + "\n"
    elif promo.type in [PromoCodeType.SUBSCRIPTION_DAYS.value, PromoCodeType.TRIAL_SUBSCRIPTION.value]:
        text += texts.t("ADMIN_PROMOCODE_EDIT_DAYS", "• Days: {days}").format(
            days=promo.subscription_days
        ) + "\n"
    
    text += texts.t("ADMIN_PROMOCODE_EDIT_USES", "• Uses: {current}/{max}").format(
        current=promo.current_uses, max=promo.max_uses
    ) + "\n"
    
    if promo.valid_until:
        text += texts.t("ADMIN_PROMOCODE_EDIT_UNTIL", "• Until: {date}").format(
            date=format_datetime(promo.valid_until)
        ) + "\n"
    else:
        text += texts.t("ADMIN_PROMOCODE_EDIT_UNLIMITED", "• Term: unlimited") + "\n"
    
    text += "\n" + texts.t("ADMIN_PROMOCODE_EDIT_SELECT", "Select parameter to change:")
    
    keyboard = [
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_EXPIRY_DATE", "📅 Expiry date"), 
                callback_data=f"promo_edit_date_{promo.id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_USES_COUNT", "📊 Uses count"), 
                callback_data=f"promo_edit_uses_{promo.id}"
            )
        ]
    ]
    
    if promo.type == PromoCodeType.BALANCE.value:
        keyboard.insert(1, [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_BONUS_AMOUNT", "💰 Bonus amount"), 
                callback_data=f"promo_edit_amount_{promo.id}"
            )
        ])
    elif promo.type in [PromoCodeType.SUBSCRIPTION_DAYS.value, PromoCodeType.TRIAL_SUBSCRIPTION.value]:
        keyboard.insert(1, [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_DAYS_COUNT", "📅 Days count"), 
                callback_data=f"promo_edit_days_{promo.id}"
            )
        ])
    
    keyboard.extend([
        [
            types.InlineKeyboardButton(
                text=texts.BACK, 
                callback_data=f"promo_manage_{promo.id}"
            )
        ]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def start_edit_promocode_date(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    try:
        promo_id = int(callback.data.split('_')[-1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_ERROR_PROMO_ID", "❌ Error getting promocode ID"), show_alert=True)
        return
    
    await state.update_data(
        editing_promo_id=promo_id,
        edit_action="date"
    )
    
    text = texts.t(
        "ADMIN_PROMOCODE_EDIT_DATE_PROMPT",
        "📅 <b>Change promocode expiry date</b>\n\n"
        "Enter the number of days until expiry (from now):\n"
        "• Enter <b>0</b> for unlimited promocode\n"
        "• Enter a positive number to set expiry\n\n"
        "<i>Example: 30 (promocode will be valid for 30 days)</i>\n\n"
        "Promocode ID: {promo_id}"
    ).format(promo_id=promo_id)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"promo_edit_{promo_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminStates.setting_promocode_expiry)
    await callback.answer()


@admin_required
@error_handler
async def start_edit_promocode_amount(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    try:
        promo_id = int(callback.data.split('_')[-1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_ERROR_PROMO_ID", "❌ Error getting promocode ID"), show_alert=True)
        return
    
    await state.update_data(
        editing_promo_id=promo_id,
        edit_action="amount"
    )
    
    text = texts.t(
        "ADMIN_PROMOCODE_EDIT_AMOUNT_PROMPT",
        "💰 <b>Change promocode bonus amount</b>\n\n"
        "Enter new amount in rubles:\n"
        "<i>Example: 500</i>\n\n"
        "Promocode ID: {promo_id}"
    ).format(promo_id=promo_id)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"promo_edit_{promo_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminStates.setting_promocode_value)
    await callback.answer()

@admin_required
@error_handler
async def start_edit_promocode_days(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    # FIX: take last element as ID
    try:
        promo_id = int(callback.data.split('_')[-1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_ERROR_PROMO_ID", "❌ Error getting promocode ID"), show_alert=True)
        return
    
    await state.update_data(
        editing_promo_id=promo_id,
        edit_action="days"
    )
    
    text = texts.t(
        "ADMIN_PROMOCODE_EDIT_DAYS_PROMPT",
        "📅 <b>Change subscription days count</b>\n\n"
        "Enter new number of days:\n"
        "<i>Example: 30</i>\n\n"
        "Promocode ID: {promo_id}"
    ).format(promo_id=promo_id)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"promo_edit_{promo_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminStates.setting_promocode_value)
    await callback.answer()


@admin_required
@error_handler
async def start_edit_promocode_uses(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    try:
        promo_id = int(callback.data.split('_')[-1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_ERROR_PROMO_ID", "❌ Error getting promocode ID"), show_alert=True)
        return
    
    await state.update_data(
        editing_promo_id=promo_id,
        edit_action="uses"
    )
    
    text = texts.t(
        "ADMIN_PROMOCODE_EDIT_USES_PROMPT",
        "📊 <b>Change maximum uses count</b>\n\n"
        "Enter new uses count:\n"
        "• Enter <b>0</b> for unlimited uses\n"
        "• Enter a positive number to limit\n\n"
        "<i>Example: 100</i>\n\n"
        "Promocode ID: {promo_id}"
    ).format(promo_id=promo_id)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"promo_edit_{promo_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminStates.setting_promocode_uses)
    await callback.answer()


@admin_required
@error_handler
async def start_promocode_creation(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t(
            "ADMIN_PROMOCODE_CREATE_HEADER",
            "🎫 <b>Create promocode</b>\n\nSelect promocode type:"
        ),
        reply_markup=get_promocode_type_keyboard(db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def select_promocode_type(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    promo_type = callback.data.split('_')[-1]

    type_names = {
        "balance": texts.t("ADMIN_PROMO_TYPE_BALANCE", "💰 Balance top-up"),
        "days": texts.t("ADMIN_PROMO_TYPE_DAYS", "📅 Subscription days"),
        "trial": texts.t("ADMIN_PROMO_TYPE_TRIAL", "🎁 Trial subscription"),
        "group": texts.t("ADMIN_PROMO_TYPE_GROUP", "🏷️ Promo group")
    }

    await state.update_data(promocode_type=promo_type)
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_PROMOCODE_CREATE_CODE_PROMPT",
            "🎫 <b>Create promocode</b>\n\n"
            "Type: {type_name}\n\n"
            "Enter promocode (only Latin letters and numbers):"
        ).format(type_name=type_names.get(promo_type, promo_type)),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data="admin_promocodes")]
        ])
    )
    
    await state.set_state(AdminStates.creating_promocode)
    await callback.answer()


@admin_required
@error_handler
async def process_promocode_code(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    code = message.text.strip().upper()
    
    if not code.isalnum() or len(code) < 3 or len(code) > 20:
        await message.answer(texts.t("ADMIN_PROMOCODE_INVALID_CODE", "❌ Code must contain only Latin letters and numbers (3-20 characters)"))
        return
    
    existing = await get_promocode_by_code(db, code)
    if existing:
        await message.answer(texts.t("ADMIN_PROMOCODE_EXISTS", "❌ Promocode with this code already exists"))
        return
    
    await state.update_data(promocode_code=code)
    
    data = await state.get_data()
    promo_type = data.get('promocode_type')
    
    if promo_type == "balance":
        await message.answer(
            texts.t(
                "ADMIN_PROMOCODE_ENTER_BALANCE",
                "💰 <b>Promocode:</b> <code>{code}</code>\n\nEnter balance top-up amount (in rubles):"
            ).format(code=code)
        )
        await state.set_state(AdminStates.setting_promocode_value)
    elif promo_type == "days":
        await message.answer(
            texts.t(
                "ADMIN_PROMOCODE_ENTER_DAYS",
                "📅 <b>Promocode:</b> <code>{code}</code>\n\nEnter number of subscription days:"
            ).format(code=code)
        )
        await state.set_state(AdminStates.setting_promocode_value)
    elif promo_type == "trial":
        await message.answer(
            texts.t(
                "ADMIN_PROMOCODE_ENTER_TRIAL_DAYS",
                "🎁 <b>Promocode:</b> <code>{code}</code>\n\nEnter number of trial subscription days:"
            ).format(code=code)
        )
        await state.set_state(AdminStates.setting_promocode_value)
    elif promo_type == "group":
        groups_with_counts = await get_promo_groups_with_counts(db, limit=50)

        if not groups_with_counts:
            await message.answer(
                texts.t("ADMIN_PROMOCODE_NO_GROUPS", "❌ Promo groups not found. Create at least one promo group."),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_promocodes")]
                ])
            )
            await state.clear()
            return

        keyboard = []
        text = texts.t(
            "ADMIN_PROMOCODE_SELECT_GROUP_HEADER",
            "🏷️ <b>Promocode:</b> <code>{code}</code>\n\nSelect promo group to assign:\n\n"
        ).format(code=code)

        for promo_group, user_count in groups_with_counts:
            text += texts.t(
                "ADMIN_PROMOCODE_GROUP_INFO",
                "• {name} (priority: {priority}, users: {users})"
            ).format(name=promo_group.name, priority=promo_group.priority, users=user_count) + "\n"
            keyboard.append([
                types.InlineKeyboardButton(
                    text=f"{promo_group.name} (↑{promo_group.priority})",
                    callback_data=f"promo_select_group_{promo_group.id}"
                )
            ])

        keyboard.append([
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data="admin_promocodes")
        ])

        await message.answer(
            text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await state.set_state(AdminStates.selecting_promo_group)


@admin_required
@error_handler
async def process_promo_group_selection(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    """Handle promo group selection for promocode"""
    texts = get_texts(db_user.language)
    try:
        promo_group_id = int(callback.data.split('_')[-1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_ERROR_PROMO_GROUP_ID", "❌ Error getting promo group ID"), show_alert=True)
        return

    promo_group = await get_promo_group_by_id(db, promo_group_id)
    if not promo_group:
        await callback.answer(texts.t("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"), show_alert=True)
        return

    await state.update_data(
        promo_group_id=promo_group_id,
        promo_group_name=promo_group.name
    )

    await callback.message.edit_text(
        texts.t(
            "ADMIN_PROMOCODE_GROUP_SELECTED",
            "🏷️ <b>Promocode for promo group</b>\n\n"
            "Promo group: {name}\n"
            "Priority: {priority}\n\n"
            "📊 Enter promocode uses count (or 0 for unlimited):"
        ).format(name=promo_group.name, priority=promo_group.priority)
    )

    await state.set_state(AdminStates.setting_promocode_uses)
    await callback.answer()


@admin_required
@error_handler
async def process_promocode_value(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    
    if data.get('editing_promo_id'):
        await handle_edit_value(message, db_user, state, db)
        return
    
    try:
        value = int(message.text.strip())
        
        promo_type = data.get('promocode_type')
        
        if promo_type == "balance" and (value < 1 or value > 10000):
            await message.answer(texts.t("ADMIN_PROMOCODE_INVALID_AMOUNT", "❌ Amount must be from 1 to 10,000 rubles"))
            return
        elif promo_type in ["days", "trial"] and (value < 1 or value > 3650):
            await message.answer(texts.t("ADMIN_PROMOCODE_INVALID_DAYS", "❌ Days count must be from 1 to 3650"))
            return
        
        await state.update_data(promocode_value=value)
        
        await message.answer(
            texts.t("ADMIN_PROMOCODE_ENTER_USES", "📊 Enter promocode uses count (or 0 for unlimited):")
        )
        await state.set_state(AdminStates.setting_promocode_uses)
        
    except ValueError:
        await message.answer(texts.t("ADMIN_ERROR_INVALID_NUMBER", "❌ Enter a valid number"))


async def handle_edit_value(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    promo_id = data.get('editing_promo_id')
    edit_action = data.get('edit_action')

    promo = await get_promocode_by_id(db, promo_id)
    if not promo:
        await message.answer(texts.t("ADMIN_PROMOCODE_NOT_FOUND", "❌ Promocode not found"))
        await state.clear()
        return
    
    try:
        value = int(message.text.strip())
        
        if edit_action == "amount":
            if value < 1 or value > 10000:
                await message.answer(texts.t("ADMIN_PROMOCODE_INVALID_AMOUNT", "❌ Amount must be from 1 to 10,000 rubles"))
                return
            
            await update_promocode(db, promo, balance_bonus_kopeks=value * 100)
            await message.answer(
                texts.t("ADMIN_PROMOCODE_AMOUNT_CHANGED", "✅ Bonus amount changed to {value}₽").format(value=value),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_PROMOCODE", "🎫 To promocode"), callback_data=f"promo_manage_{promo_id}")]
                ])
            )
            
        elif edit_action == "days":
            if value < 1 or value > 3650:
                await message.answer(texts.t("ADMIN_PROMOCODE_INVALID_DAYS", "❌ Days count must be from 1 to 3650"))
                return
            
            await update_promocode(db, promo, subscription_days=value)
            await message.answer(
                texts.t("ADMIN_PROMOCODE_DAYS_CHANGED", "✅ Days count changed to {value}").format(value=value),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_PROMOCODE", "🎫 To promocode"), callback_data=f"promo_manage_{promo_id}")]
                ])
            )
        
        await state.clear()
        logger.info(f"Promocode {promo.code} edited by admin {db_user.telegram_id}: {edit_action} = {value}")
        
    except ValueError:
        await message.answer(texts.t("ADMIN_ERROR_INVALID_NUMBER", "❌ Enter a valid number"))


@admin_required
@error_handler
async def process_promocode_uses(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    
    if data.get('editing_promo_id'):
        await handle_edit_uses(message, db_user, state, db)
        return
    
    try:
        max_uses = int(message.text.strip())
        
        if max_uses < 0 or max_uses > 100000:
            await message.answer(texts.t("ADMIN_PROMOCODE_INVALID_USES", "❌ Uses count must be from 0 to 100,000"))
            return
        
        if max_uses == 0:
            max_uses = 999999
        
        await state.update_data(promocode_max_uses=max_uses)
        
        await message.answer(
            texts.t("ADMIN_PROMOCODE_ENTER_EXPIRY", "⏰ Enter promocode validity in days (or 0 for unlimited):")
        )
        await state.set_state(AdminStates.setting_promocode_expiry)
        
    except ValueError:
        await message.answer(texts.t("ADMIN_ERROR_INVALID_NUMBER", "❌ Enter a valid number"))


async def handle_edit_uses(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    promo_id = data.get('editing_promo_id')

    promo = await get_promocode_by_id(db, promo_id)
    if not promo:
        await message.answer(texts.t("ADMIN_PROMOCODE_NOT_FOUND", "❌ Promocode not found"))
        await state.clear()
        return
    
    try:
        max_uses = int(message.text.strip())
        
        if max_uses < 0 or max_uses > 100000:
            await message.answer(texts.t("ADMIN_PROMOCODE_INVALID_USES", "❌ Uses count must be from 0 to 100,000"))
            return
        
        if max_uses == 0:
            max_uses = 999999
        
        if max_uses < promo.current_uses:
            await message.answer(
                texts.t(
                    "ADMIN_PROMOCODE_LIMIT_TOO_LOW",
                    "❌ New limit ({max_uses}) cannot be less than current uses ({current})"
                ).format(max_uses=max_uses, current=promo.current_uses)
            )
            return
        
        await update_promocode(db, promo, max_uses=max_uses)
        
        uses_text = texts.t("ADMIN_PROMOCODE_UNLIMITED", "unlimited") if max_uses == 999999 else str(max_uses)
        await message.answer(
            texts.t("ADMIN_PROMOCODE_USES_CHANGED", "✅ Maximum uses changed to {uses}").format(uses=uses_text),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_PROMOCODE", "🎫 To promocode"), callback_data=f"promo_manage_{promo_id}")]
            ])
        )
        
        await state.clear()
        logger.info(f"Promocode {promo.code} edited by admin {db_user.telegram_id}: max_uses = {max_uses}")
        
    except ValueError:
        await message.answer(texts.t("ADMIN_ERROR_INVALID_NUMBER", "❌ Enter a valid number"))


@admin_required
@error_handler
async def process_promocode_expiry(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    
    if data.get('editing_promo_id'):
        await handle_edit_expiry(message, db_user, state, db)
        return
    
    try:
        expiry_days = int(message.text.strip())
        
        if expiry_days < 0 or expiry_days > 3650:
            await message.answer(texts.t("ADMIN_PROMOCODE_INVALID_EXPIRY", "❌ Validity must be from 0 to 3650 days"))
            return
        
        code = data.get('promocode_code')
        promo_type = data.get('promocode_type')
        value = data.get('promocode_value', 0)
        max_uses = data.get('promocode_max_uses', 1)
        promo_group_id = data.get('promo_group_id')
        promo_group_name = data.get('promo_group_name')

        valid_until = None
        if expiry_days > 0:
            valid_until = datetime.utcnow() + timedelta(days=expiry_days)

        type_map = {
            "balance": PromoCodeType.BALANCE,
            "days": PromoCodeType.SUBSCRIPTION_DAYS,
            "trial": PromoCodeType.TRIAL_SUBSCRIPTION,
            "group": PromoCodeType.PROMO_GROUP
        }

        promocode = await create_promocode(
            db=db,
            code=code,
            type=type_map[promo_type],
            balance_bonus_kopeks=value * 100 if promo_type == "balance" else 0,
            subscription_days=value if promo_type in ["days", "trial"] else 0,
            max_uses=max_uses,
            valid_until=valid_until,
            created_by=db_user.id,
            promo_group_id=promo_group_id if promo_type == "group" else None
        )
        
        type_names = {
            "balance": texts.t("ADMIN_PROMO_TYPE_BALANCE_LABEL", "Balance top-up"),
            "days": texts.t("ADMIN_PROMO_TYPE_DAYS_LABEL", "Subscription days"),
            "trial": texts.t("ADMIN_PROMO_TYPE_TRIAL_LABEL", "Trial subscription"),
            "group": texts.t("ADMIN_PROMO_TYPE_GROUP_LABEL", "Promo group")
        }

        summary_text = texts.t(
            "ADMIN_PROMOCODE_CREATED_HEADER",
            "✅ <b>Promocode created!</b>\n\n"
            "🎫 <b>Code:</b> <code>{code}</code>\n"
            "📝 <b>Type:</b> {type_name}"
        ).format(code=promocode.code, type_name=type_names.get(promo_type)) + "\n"

        if promo_type == "balance":
            summary_text += texts.t("ADMIN_PROMOCODE_SUMMARY_AMOUNT", "💰 <b>Amount:</b> {amount}").format(
                amount=settings.format_price(promocode.balance_bonus_kopeks)
            ) + "\n"
        elif promo_type in ["days", "trial"]:
            summary_text += texts.t("ADMIN_PROMOCODE_SUMMARY_DAYS", "📅 <b>Days:</b> {days}").format(
                days=promocode.subscription_days
            ) + "\n"
        elif promo_type == "group" and promo_group_name:
            summary_text += texts.t("ADMIN_PROMOCODE_SUMMARY_GROUP", "🏷️ <b>Promo group:</b> {name}").format(
                name=promo_group_name
            ) + "\n"

        summary_text += texts.t("ADMIN_PROMOCODE_SUMMARY_USES", "📊 <b>Uses:</b> {uses}").format(
            uses=promocode.max_uses
        ) + "\n"
        
        if promocode.valid_until:
            summary_text += texts.t("ADMIN_PROMOCODE_SUMMARY_VALID_UNTIL", "⏰ <b>Valid until:</b> {date}").format(
                date=format_datetime(promocode.valid_until)
            ) + "\n"
        
        await message.answer(
            summary_text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_PROMOCODES", "🎫 To promocodes"), callback_data="admin_promocodes")]
            ])
        )
        
        await state.clear()
        logger.info(f"Promocode {code} created by admin {db_user.telegram_id}")
        
    except ValueError:
        await message.answer(texts.t("ADMIN_ERROR_INVALID_DAYS", "❌ Enter a valid number of days"))


async def handle_edit_expiry(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    promo_id = data.get('editing_promo_id')

    promo = await get_promocode_by_id(db, promo_id)
    if not promo:
        await message.answer(texts.t("ADMIN_PROMOCODE_NOT_FOUND", "❌ Promocode not found"))
        await state.clear()
        return
    
    try:
        expiry_days = int(message.text.strip())
        
        if expiry_days < 0 or expiry_days > 3650:
            await message.answer(texts.t("ADMIN_PROMOCODE_INVALID_EXPIRY", "❌ Validity must be from 0 to 3650 days"))
            return
        
        valid_until = None
        if expiry_days > 0:
            valid_until = datetime.utcnow() + timedelta(days=expiry_days)
        
        await update_promocode(db, promo, valid_until=valid_until)
        
        if valid_until:
            expiry_text = texts.t("ADMIN_PROMOCODE_EXPIRY_UNTIL", "until {date}").format(date=format_datetime(valid_until))
        else:
            expiry_text = texts.t("ADMIN_PROMOCODE_UNLIMITED", "unlimited")
            
        await message.answer(
            texts.t("ADMIN_PROMOCODE_EXPIRY_CHANGED", "✅ Promocode validity changed: {expiry}").format(expiry=expiry_text),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_PROMOCODE", "🎫 To promocode"), callback_data=f"promo_manage_{promo_id}")]
            ])
        )
        
        await state.clear()
        logger.info(f"Promocode {promo.code} edited by admin {db_user.telegram_id}: expiry = {expiry_days} days")
        
    except ValueError:
        await message.answer(texts.t("ADMIN_ERROR_INVALID_DAYS", "❌ Enter a valid number of days"))


@admin_required
@error_handler
async def toggle_promocode_status(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    promo_id = int(callback.data.split('_')[-1])

    promo = await get_promocode_by_id(db, promo_id)
    if not promo:
        await callback.answer(texts.t("ADMIN_PROMOCODE_NOT_FOUND", "❌ Promocode not found"), show_alert=True)
        return
    
    new_status = not promo.is_active
    await update_promocode(db, promo, is_active=new_status)
    
    status_text = texts.t("ADMIN_PROMOCODE_ACTIVATED", "activated") if new_status else texts.t("ADMIN_PROMOCODE_DEACTIVATED", "deactivated")
    await callback.answer(texts.t("ADMIN_PROMOCODE_STATUS_CHANGED", "✅ Promocode {status}").format(status=status_text), show_alert=True)
    
    await show_promocode_management(callback, db_user, db)


@admin_required
@error_handler
async def confirm_delete_promocode(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    try:
        promo_id = int(callback.data.split('_')[-1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_ERROR_PROMO_ID", "❌ Error getting promocode ID"), show_alert=True)
        return

    promo = await get_promocode_by_id(db, promo_id)
    if not promo:
        await callback.answer(texts.t("ADMIN_PROMOCODE_NOT_FOUND", "❌ Promocode not found"), show_alert=True)
        return
    
    status_text = texts.t("ADMIN_STATUS_ACTIVE", "Active") if promo.is_active else texts.t("ADMIN_STATUS_INACTIVE", "Inactive")
    
    text = texts.t(
        "ADMIN_PROMOCODE_DELETE_CONFIRM",
        "⚠️ <b>Delete confirmation</b>\n\n"
        "Are you sure you want to delete promocode <code>{code}</code>?\n\n"
        "📊 <b>Promocode info:</b>\n"
        "• Uses: {current}/{max}\n"
        "• Status: {status}\n\n"
        "<b>⚠️ Warning:</b> This action cannot be undone!\n\n"
        "ID: {promo_id}"
    ).format(
        code=promo.code,
        current=promo.current_uses,
        max=promo.max_uses,
        status=status_text,
        promo_id=promo_id
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_YES_DELETE", "✅ Yes, delete"), 
                callback_data=f"promo_delete_confirm_{promo.id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), 
                callback_data=f"promo_manage_{promo.id}"
            )
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@admin_required
@error_handler
async def delete_promocode_confirmed(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    try:
        promo_id = int(callback.data.split('_')[-1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_ERROR_PROMO_ID", "❌ Error getting promocode ID"), show_alert=True)
        return

    promo = await get_promocode_by_id(db, promo_id)
    if not promo:
        await callback.answer(texts.t("ADMIN_PROMOCODE_NOT_FOUND", "❌ Promocode not found"), show_alert=True)
        return
    
    code = promo.code
    success = await delete_promocode(db, promo)
    
    if success:
        await callback.answer(texts.t("ADMIN_PROMOCODE_DELETED", "✅ Promocode {code} deleted").format(code=code), show_alert=True)
        await show_promocodes_list(callback, db_user, db)
    else:
        await callback.answer(texts.t("ADMIN_PROMOCODE_DELETE_ERROR", "❌ Error deleting promocode"), show_alert=True)


@admin_required
@error_handler
async def show_promocode_stats(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    promo_id = int(callback.data.split('_')[-1])

    promo = await get_promocode_by_id(db, promo_id)
    if not promo:
        await callback.answer(texts.t("ADMIN_PROMOCODE_NOT_FOUND", "❌ Promocode not found"), show_alert=True)
        return
    
    stats = await get_promocode_statistics(db, promo_id)
    
    text = texts.t(
        "ADMIN_PROMOCODE_STATS_HEADER",
        "📊 <b>Promocode statistics</b> <code>{code}</code>\n\n"
        "📈 <b>General statistics:</b>\n"
        "- Total uses: {total}\n"
        "- Today uses: {today}\n"
        "- Remaining uses: {remaining}\n\n"
        "📅 <b>Recent uses:</b>"
    ).format(
        code=promo.code,
        total=stats['total_uses'],
        today=stats['today_uses'],
        remaining=promo.max_uses - promo.current_uses
    ) + "\n"
    
    if stats['recent_uses']:
        for use in stats['recent_uses'][:5]:
            use_date = format_datetime(use.used_at)
            
            if hasattr(use, 'user_username') and use.user_username:
                user_display = f"@{use.user_username}"
            elif hasattr(use, 'user_full_name') and use.user_full_name:
                user_display = use.user_full_name
            elif hasattr(use, 'user_telegram_id'):
                user_display = f"ID{use.user_telegram_id}"
            else:
                user_display = f"ID{use.user_id}"
            
            text += f"- {use_date} | {user_display}\n"
    else:
        text += texts.t("ADMIN_PROMOCODE_NO_USES", "- No uses yet") + "\n"
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.BACK, 
                callback_data=f"promo_manage_{promo.id}"
            )
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@admin_required
@error_handler
async def show_general_promocode_stats(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    total_codes = await get_promocodes_count(db)
    active_codes = await get_promocodes_count(db, is_active=True)
    
    text = texts.t(
        "ADMIN_PROMOCODES_GENERAL_STATS",
        "📊 <b>General promocode statistics</b>\n\n"
        "📈 <b>Key metrics:</b>\n"
        "- Total promocodes: {total}\n"
        "- Active: {active}\n"
        "- Inactive: {inactive}\n\n"
        "For detailed statistics, select a specific promocode from the list."
    ).format(
        total=total_codes,
        active=active_codes,
        inactive=total_codes - active_codes
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_TO_PROMOCODES", "🎫 To promocodes"), callback_data="admin_promo_list")
        ],
        [
            types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_promocodes")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_promocodes_menu, F.data == "admin_promocodes")
    dp.callback_query.register(show_promocodes_list, F.data == "admin_promo_list")
    dp.callback_query.register(start_promocode_creation, F.data == "admin_promo_create")
    dp.callback_query.register(select_promocode_type, F.data.startswith("promo_type_"))
    dp.callback_query.register(process_promo_group_selection, F.data.startswith("promo_select_group_"))
    
    dp.callback_query.register(show_promocode_management, F.data.startswith("promo_manage_"))
    dp.callback_query.register(toggle_promocode_status, F.data.startswith("promo_toggle_"))
    dp.callback_query.register(show_promocode_stats, F.data.startswith("promo_stats_"))
    
    dp.callback_query.register(start_edit_promocode_date, F.data.startswith("promo_edit_date_"))
    dp.callback_query.register(start_edit_promocode_amount, F.data.startswith("promo_edit_amount_"))
    dp.callback_query.register(start_edit_promocode_days, F.data.startswith("promo_edit_days_"))
    dp.callback_query.register(start_edit_promocode_uses, F.data.startswith("promo_edit_uses_"))
    dp.callback_query.register(show_general_promocode_stats, F.data == "admin_promo_general_stats")
    
    dp.callback_query.register(
        show_promocode_edit_menu, 
        F.data.regexp(r"^promo_edit_\d+$")
    )
    
    dp.callback_query.register(delete_promocode_confirmed, F.data.startswith("promo_delete_confirm_"))
    dp.callback_query.register(confirm_delete_promocode, F.data.startswith("promo_delete_"))
    
    dp.message.register(process_promocode_code, AdminStates.creating_promocode)
    dp.message.register(process_promocode_value, AdminStates.setting_promocode_value)
    dp.message.register(process_promocode_uses, AdminStates.setting_promocode_uses)
    dp.message.register(process_promocode_expiry, AdminStates.setting_promocode_expiry)
    
