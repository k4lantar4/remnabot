import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import InterfaceError
from sqlalchemy import select, func, and_, or_

from app.config import settings
from app.states import AdminStates
from app.database.models import (
    User,
    UserStatus,
    Subscription,
    SubscriptionStatus,
    BroadcastHistory,
)
from app.database.database import AsyncSessionLocal
from app.keyboards.admin import (
    get_admin_messages_keyboard, get_broadcast_target_keyboard,
    get_custom_criteria_keyboard, get_broadcast_history_keyboard,
    get_admin_pagination_keyboard, get_broadcast_media_keyboard,
    get_media_confirm_keyboard, get_updated_message_buttons_selector_keyboard_with_media,
    BROADCAST_BUTTON_ROWS, DEFAULT_BROADCAST_BUTTONS,
    get_broadcast_button_config, get_broadcast_button_labels
)
from app.localization.texts import get_texts
from app.database.crud.user import get_users_list
from app.database.crud.subscription import get_expiring_subscriptions
from app.utils.decorators import admin_required, error_handler
from app.utils.miniapp_buttons import build_miniapp_or_callback_button

logger = logging.getLogger(__name__)

BUTTON_ROWS = BROADCAST_BUTTON_ROWS
DEFAULT_SELECTED_BUTTONS = DEFAULT_BROADCAST_BUTTONS

TEXT_MENU_MINIAPP_BUTTON_KEYS = {
    "balance",
    "referrals",
    "promocode",
    "connect",
    "subscription",
}


def get_message_buttons_selector_keyboard(language: str = "ru") -> types.InlineKeyboardMarkup:
    return get_updated_message_buttons_selector_keyboard(list(DEFAULT_SELECTED_BUTTONS), language)


def get_updated_message_buttons_selector_keyboard(selected_buttons: list, language: str = "ru") -> types.InlineKeyboardMarkup:
    return get_updated_message_buttons_selector_keyboard_with_media(selected_buttons, False, language)


def create_broadcast_keyboard(selected_buttons: list, language: str = "ru") -> Optional[types.InlineKeyboardMarkup]:
    selected_buttons = selected_buttons or []
    keyboard: list[list[types.InlineKeyboardButton]] = []
    button_config_map = get_broadcast_button_config(language)

    for row in BUTTON_ROWS:
        row_buttons: list[types.InlineKeyboardButton] = []
        for button_key in row:
            if button_key not in selected_buttons:
                continue
            button_config = button_config_map[button_key]
            if settings.is_text_main_menu_mode() and button_key in TEXT_MENU_MINIAPP_BUTTON_KEYS:
                row_buttons.append(
                    build_miniapp_or_callback_button(
                        text=button_config["text"],
                        callback_data=button_config["callback"],
                    )
                )
            else:
                row_buttons.append(
                    types.InlineKeyboardButton(
                        text=button_config["text"],
                        callback_data=button_config["callback"]
                    )
                )
        if row_buttons:
            keyboard.append(row_buttons)

    if not keyboard:
        return None

    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


async def _persist_broadcast_result(
    db: AsyncSession,
    broadcast_history: BroadcastHistory,
    sent_count: int,
    failed_count: int,
    status: str,
) -> None:
    """Saves broadcast results with retry on connection loss."""

    broadcast_history.sent_count = sent_count
    broadcast_history.failed_count = failed_count
    broadcast_history.status = status
    broadcast_history.completed_at = datetime.utcnow()

    try:
        await db.commit()
        return
    except InterfaceError as error:
        logger.warning(
            "Database connection lost while saving broadcast results, retrying",
            exc_info=error,
        )
        await db.rollback()

    try:
        async with AsyncSessionLocal() as retry_session:
            retry_history = await retry_session.get(BroadcastHistory, broadcast_history.id)
            if not retry_history:
                logger.critical(
                    "Failed to find BroadcastHistory record #%s for retry",
                    broadcast_history.id,
                )
                return

            retry_history.sent_count = sent_count
            retry_history.failed_count = failed_count
            retry_history.status = status
            retry_history.completed_at = broadcast_history.completed_at
            await retry_session.commit()
            logger.info(
                "Broadcast results successfully saved after reconnection (id=%s)",
                broadcast_history.id,
            )
    except Exception as retry_error:
        logger.critical(
            "Failed to save broadcast results after reconnection",
            exc_info=retry_error,
        )


@admin_required
@error_handler
async def show_messages_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    text = texts.t(
        "ADMIN_MESSAGES_MENU_TITLE",
        "📨 <b>Broadcast management</b>"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_MENU_DESCRIPTION",
        "Choose broadcast type:"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_MENU_ALL_USERS",
        "- <b>All users</b> - broadcast to all active users"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_MENU_BY_SUBSCRIPTIONS",
        "- <b>By subscriptions</b> - filter by subscription type"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_MENU_BY_CRITERIA",
        "- <b>By criteria</b> - custom filters"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_MENU_HISTORY",
        "- <b>History</b> - view previous broadcasts"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_MENU_WARNING",
        "⚠️ Be careful with mass broadcasts!"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_messages_keyboard(db_user.language),
        parse_mode="HTML"  
    )
    await callback.answer()


@admin_required
@error_handler
async def show_broadcast_targets(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t(
            "ADMIN_MESSAGES_TARGET_SELECTION",
            "🎯 <b>Select target audience</b>\n\nChoose user category for broadcast:"
        ),
        reply_markup=get_broadcast_target_keyboard(db_user.language),
        parse_mode="HTML" 
    )
    await callback.answer()


@admin_required
@error_handler
async def show_messages_history(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    page = 1
    if '_page_' in callback.data:
        page = int(callback.data.split('_page_')[1])
    
    limit = 10
    offset = (page - 1) * limit
    
    stmt = select(BroadcastHistory).order_by(BroadcastHistory.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    broadcasts = result.scalars().all()
    
    count_stmt = select(func.count(BroadcastHistory.id))
    count_result = await db.execute(count_stmt)
    total_count = count_result.scalar() or 0
    total_pages = (total_count + limit - 1) // limit
    
    texts = get_texts(db_user.language)
    if not broadcasts:
        text = texts.t(
            "ADMIN_MESSAGES_HISTORY_EMPTY",
            "📋 <b>Broadcast history</b>\n\n❌ Broadcast history is empty.\nSend the first broadcast to see it here."
        )
        keyboard = [[types.InlineKeyboardButton(text=texts.t("ADMIN_MESSAGES_HISTORY_BACK", "⬅️ Back"), callback_data="admin_messages")]]
    else:
        text = texts.t(
            "ADMIN_MESSAGES_HISTORY_PAGE",
            "📋 <b>Broadcast history</b> (page {page}/{total_pages})\n\n"
        ).format(page=page, total_pages=total_pages)
        
        for broadcast in broadcasts:
            status_emoji = "✅" if broadcast.status == "completed" else "❌" if broadcast.status == "failed" else "⏳"
            success_rate = round((broadcast.sent_count / broadcast.total_count * 100), 1) if broadcast.total_count > 0 else 0
            
            message_preview = broadcast.message_text[:100] + "..." if len(broadcast.message_text) > 100 else broadcast.message_text
            
            import html
            message_preview = html.escape(message_preview) 
            
            target_name = get_target_name(broadcast.target_type)
            target_name = get_target_name(broadcast.target_type, db_user.language)
            text += texts.t(
                "ADMIN_MESSAGES_HISTORY_ITEM",
                "{status_emoji} <b>{date}</b>\n📊 Sent: {sent}/{total} ({success_rate}%)\n🎯 Audience: {target}\n👤 Admin: {admin}\n📝 Message: {preview}\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            ).format(
                status_emoji=status_emoji,
                date=broadcast.created_at.strftime('%d.%m.%Y %H:%M'),
                sent=broadcast.sent_count,
                total=broadcast.total_count,
                success_rate=success_rate,
                target=target_name,
                admin=broadcast.admin_name,
                preview=message_preview
            )
        
        keyboard = get_broadcast_history_keyboard(page, total_pages, db_user.language).inline_keyboard
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def show_custom_broadcast(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    stats = await get_users_statistics(db)
    
    text = texts.t(
        "ADMIN_MESSAGES_CUSTOM_TITLE",
        "📝 <b>Broadcast by criteria</b>"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_FILTERS",
        "📊 <b>Available filters:</b>"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_BY_REGISTRATION",
        "👥 <b>By registration:</b>"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_TODAY",
        "• Today: {count} users"
    ).format(count=stats['today']) + "\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_WEEK",
        "• Last week: {count} users"
    ).format(count=stats['week']) + "\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_MONTH",
        "• Last month: {count} users"
    ).format(count=stats['month']) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_BY_ACTIVITY",
        "💼 <b>By activity:</b>"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_ACTIVE_TODAY",
        "• Active today: {count} users"
    ).format(count=stats['active_today']) + "\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_INACTIVE_WEEK",
        "• Inactive 7+ days: {count} users"
    ).format(count=stats['inactive_week']) + "\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_INACTIVE_MONTH",
        "• Inactive 30+ days: {count} users"
    ).format(count=stats['inactive_month']) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_BY_SOURCE",
        "🔗 <b>By source:</b>"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_REFERRALS",
        "• Via referrals: {count} users"
    ).format(count=stats['referrals']) + "\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_DIRECT",
        "• Direct registration: {count} users"
    ).format(count=stats['direct']) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_CUSTOM_SELECT_CRITERIA",
        "Choose criteria for filtering:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_custom_criteria_keyboard(db_user.language),
        parse_mode="HTML" 
    )
    await callback.answer()


@admin_required
@error_handler
async def select_custom_criteria(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    criteria = callback.data.replace('criteria_', '')
    
    criteria_names = {
        "today": texts.t("ADMIN_MESSAGES_CRITERIA_TODAY", "Registered today"),
        "week": texts.t("ADMIN_MESSAGES_CRITERIA_WEEK", "Registered last week"),
        "month": texts.t("ADMIN_MESSAGES_CRITERIA_MONTH", "Registered last month"),
        "active_today": texts.t("ADMIN_MESSAGES_CRITERIA_ACTIVE_TODAY", "Active today"),
        "inactive_week": texts.t("ADMIN_MESSAGES_CRITERIA_INACTIVE_WEEK", "Inactive 7+ days"),
        "inactive_month": texts.t("ADMIN_MESSAGES_CRITERIA_INACTIVE_MONTH", "Inactive 30+ days"),
        "referrals": texts.t("ADMIN_MESSAGES_CRITERIA_REFERRALS", "Came via referrals"),
        "direct": texts.t("ADMIN_MESSAGES_CRITERIA_DIRECT", "Direct registration")
    }
    
    user_count = await get_custom_users_count(db, criteria)
    
    await state.update_data(broadcast_target=f"custom_{criteria}")
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_MESSAGES_CREATE_TITLE",
            "📨 <b>Create broadcast</b>\n\n"
        ) + texts.t(
            "ADMIN_MESSAGES_CREATE_CRITERIA",
            "🎯 <b>Criteria:</b> {criteria}\n"
        ).format(criteria=criteria_names.get(criteria, criteria)) + texts.t(
            "ADMIN_MESSAGES_CREATE_RECIPIENTS",
            "👥 <b>Recipients:</b> {count}\n\n"
        ).format(count=user_count) + texts.t(
            "ADMIN_MESSAGES_CREATE_PROMPT",
            "Enter message text for broadcast:\n\n"
        ) + texts.t(
            "ADMIN_MESSAGES_CREATE_HTML_HINT",
            "<i>HTML markup is supported</i>"
        ),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_MESSAGES_CREATE_CANCEL", "❌ Cancel"), callback_data="admin_messages")]
        ]),
        parse_mode="HTML" 
    )
    
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await callback.answer()


@admin_required
@error_handler
async def select_broadcast_target(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    raw_target = callback.data[len("broadcast_"):]
    target_aliases = {
        "no_sub": "no",
    }
    target = target_aliases.get(raw_target, raw_target)

    target_names = {
        "all": texts.t("ADMIN_MESSAGES_TARGET_ALL", "All users"),
        "active": texts.t("ADMIN_MESSAGES_TARGET_ACTIVE", "With active subscription"),
        "trial": texts.t("ADMIN_MESSAGES_TARGET_TRIAL", "With trial subscription"),
        "no": texts.t("ADMIN_MESSAGES_TARGET_NO", "Without subscription"),
        "expiring": texts.t("ADMIN_MESSAGES_TARGET_EXPIRING", "With expiring subscription"),
        "expired": texts.t("ADMIN_MESSAGES_TARGET_EXPIRED", "With expired subscription"),
        "active_zero": texts.t("ADMIN_MESSAGES_TARGET_ACTIVE_ZERO", "Active subscription, 0 GB traffic"),
        "trial_zero": texts.t("ADMIN_MESSAGES_TARGET_TRIAL_ZERO", "Trial subscription, 0 GB traffic"),
    }
    
    user_count = await get_target_users_count(db, target)
    
    await state.update_data(broadcast_target=target)
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_MESSAGES_CREATE_TITLE",
            "📨 <b>Create broadcast</b>\n\n"
        ) + texts.t(
            "ADMIN_MESSAGES_CREATE_AUDIENCE",
            "🎯 <b>Audience:</b> {audience}\n"
        ).format(audience=target_names.get(target, target)) + texts.t(
            "ADMIN_MESSAGES_CREATE_RECIPIENTS",
            "👥 <b>Recipients:</b> {count}\n\n"
        ).format(count=user_count) + texts.t(
            "ADMIN_MESSAGES_CREATE_PROMPT",
            "Enter message text for broadcast:\n\n"
        ) + texts.t(
            "ADMIN_MESSAGES_CREATE_HTML_HINT",
            "<i>HTML markup is supported</i>"
        ),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_MESSAGES_CREATE_CANCEL", "❌ Cancel"), callback_data="admin_messages")]
        ]),
        parse_mode="HTML" 
    )
    
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await callback.answer()


@admin_required
@error_handler
async def process_broadcast_message(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    broadcast_text = message.text
    
    if len(broadcast_text) > 4000:
        await message.answer(texts.t("ADMIN_MESSAGES_TOO_LONG", "❌ Message is too long (maximum 4000 characters)"))
        return
    
    await state.update_data(broadcast_message=broadcast_text)
    
    await message.answer(
        texts.t(
            "ADMIN_MESSAGES_ADD_MEDIA_TITLE",
            "🖼️ <b>Adding media file</b>\n\n"
        ) + texts.t(
            "ADMIN_MESSAGES_ADD_MEDIA_DESCRIPTION",
            "You can add a photo, video or document to the message.\nOr skip this step.\n\n"
        ) + texts.t(
            "ADMIN_MESSAGES_ADD_MEDIA_SELECT",
            "Choose media type:"
        ),
        reply_markup=get_broadcast_media_keyboard(db_user.language),
        parse_mode="HTML"
    )

@admin_required
@error_handler
async def handle_media_selection(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    if callback.data == "skip_media":
        await state.update_data(has_media=False)
        await show_button_selector_callback(callback, db_user, state)
        return
    
    texts = get_texts(db_user.language)
    media_type = callback.data.replace('add_media_', '')
    
    media_instructions = {
        "photo": texts.t("ADMIN_MESSAGES_MEDIA_PHOTO", "📷 Send a photo for broadcast:"),
        "video": texts.t("ADMIN_MESSAGES_MEDIA_VIDEO", "🎥 Send a video for broadcast:"),
        "document": texts.t("ADMIN_MESSAGES_MEDIA_DOCUMENT", "📄 Send a document for broadcast:")
    }
    
    await state.update_data(
        media_type=media_type,
        waiting_for_media=True
    )
    
    await callback.message.edit_text(
        f"{media_instructions.get(media_type, texts.t('ADMIN_MESSAGES_MEDIA_PHOTO', '📷 Send a photo for broadcast:'))}\n\n"
        f"{texts.t('ADMIN_MESSAGES_MEDIA_SIZE_LIMIT', '<i>File size must not exceed 50 MB</i>')}",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_MESSAGES_CREATE_CANCEL", "❌ Cancel"), callback_data="admin_messages")]
        ]),
        parse_mode="HTML"
    )
    
    await state.set_state(AdminStates.waiting_for_broadcast_media)
    await callback.answer()

@admin_required
@error_handler
async def process_broadcast_media(
    message: types.Message,
    db_user: User,
    state: FSMContext
):
    data = await state.get_data()
    expected_type = data.get('media_type')
    
    media_file_id = None
    media_type = None
    
    if message.photo and expected_type == "photo":
        media_file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video and expected_type == "video":
        media_file_id = message.video.file_id
        media_type = "video"
    elif message.document and expected_type == "document":
        media_file_id = message.document.file_id
        media_type = "document"
    else:
        texts = get_texts(db_user.language)
        media_type_names = {
            "photo": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_PHOTO", "Photo"),
            "video": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_VIDEO", "Video"),
            "document": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_DOCUMENT", "Document")
        }
        await message.answer(
            texts.t(
                "ADMIN_MESSAGES_MEDIA_WRONG_TYPE",
                "❌ Please send {type} as instructed."
            ).format(type=media_type_names.get(expected_type, expected_type))
        )
        return
    
    await state.update_data(
        has_media=True,
        media_file_id=media_file_id,
        media_type=media_type,
        media_caption=message.caption
    )
    
    await show_media_preview(message, db_user, state)

async def show_media_preview(
    message: types.Message,
    db_user: User,
    state: FSMContext
):
    data = await state.get_data()
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    
    texts = get_texts(db_user.language)
    media_type_names = {
        "photo": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_PHOTO", "Photo"),
        "video": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_VIDEO", "Video"),
        "document": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_DOCUMENT", "Document")
    }
    preview_text = texts.t(
        "ADMIN_MESSAGES_MEDIA_ADDED",
        "🖼️ <b>Media file added</b>\n\n"
    ) + texts.t(
        "ADMIN_MESSAGES_MEDIA_TYPE",
        "📎 <b>Type:</b> {type}\n"
    ).format(type=media_type_names.get(media_type, media_type)) + texts.t(
        "ADMIN_MESSAGES_MEDIA_SAVED",
        "✅ File saved and ready to send\n\n"
    ) + texts.t(
        "ADMIN_MESSAGES_MEDIA_NEXT",
        "What to do next?"
    )
    
    # For broadcast preview use original method without logo patching
    # to show exactly the uploaded photo
    from app.utils.message_patch import _original_answer
    
    if media_type == "photo" and media_file_id:
        # Show preview with uploaded photo
        await message.bot.send_photo(
            chat_id=message.chat.id,
            photo=media_file_id,
            caption=preview_text,
            reply_markup=get_media_confirm_keyboard(db_user.language),
            parse_mode="HTML"
        )
    else:
        # For other media types or if no photo, use regular message
        await _original_answer(message, preview_text, 
                             reply_markup=get_media_confirm_keyboard(db_user.language), 
                             parse_mode="HTML")

@admin_required
@error_handler
async def handle_media_confirmation(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    action = callback.data
    
    if action == "confirm_media":
        await show_button_selector_callback(callback, db_user, state)
    elif action == "replace_media":
        data = await state.get_data()
        media_type = data.get('media_type', 'photo')
        await handle_media_selection(callback, db_user, state)
    elif action == "skip_media":
        await state.update_data(
            has_media=False,
            media_file_id=None,
            media_type=None,
            media_caption=None
        )
        await show_button_selector_callback(callback, db_user, state)

@admin_required
@error_handler
async def handle_change_media(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t(
            "ADMIN_MESSAGES_CHANGE_MEDIA_TITLE",
            "🖼️ <b>Changing media file</b>\n\n"
        ) + texts.t(
            "ADMIN_MESSAGES_CHANGE_MEDIA_SELECT",
            "Choose new media type:"
        ),
        reply_markup=get_broadcast_media_keyboard(db_user.language),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_required
@error_handler
async def show_button_selector_callback(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    data = await state.get_data()
    has_media = data.get('has_media', False)
    selected_buttons = data.get('selected_buttons')

    if selected_buttons is None:
        selected_buttons = list(DEFAULT_SELECTED_BUTTONS)
        await state.update_data(selected_buttons=selected_buttons)
    
    texts = get_texts(db_user.language)
    media_info = ""
    if has_media:
        media_type = data.get('media_type', 'file')
        media_type_names = {
            "photo": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_PHOTO", "Photo"),
            "video": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_VIDEO", "Video"),
            "document": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_DOCUMENT", "Document")
        }
        media_info = "\n" + texts.t(
            "ADMIN_MESSAGES_PREVIEW_MEDIA",
            "\n🖼️ <b>Media file:</b> {media_type}"
        ).format(media_type=media_type_names.get(media_type, media_type)) + " " + texts.t("ADMIN_MESSAGES_MEDIA_SAVED", "✅ File saved and ready to send\n\n").split("\n")[0]
    
    text = texts.t(
        "ADMIN_MESSAGES_BUTTON_SELECTOR_TITLE",
        "📘 <b>Select additional buttons</b>"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_SELECTOR_DESCRIPTION",
        "Choose buttons that will be added to the broadcast message:"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_BALANCE_DESC",
        "💰 <b>Top up balance</b> — opens top-up methods"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_REFERRALS_DESC",
        "🤝 <b>Referrals</b> — opens referral program"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_PROMOCODE_DESC",
        "🎫 <b>Promo code</b> — opens promo code input form"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_CONNECT_DESC",
        "🔗 <b>Connect</b> — helps connect the app"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_SUBSCRIPTION_DESC",
        "📱 <b>Subscription</b> — shows subscription status"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_SUPPORT_DESC",
        "🛠️ <b>Support</b> — connects with support"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_HOME_DESC",
        "🏠 <b>Main menu button</b> is enabled by default, but you can disable it if needed."
    ) + media_info + "\n\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_SELECTOR_PROMPT",
        "Choose needed buttons and press \"Continue\":"
    )
    
    keyboard = get_updated_message_buttons_selector_keyboard_with_media(
        selected_buttons, has_media, db_user.language
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def show_button_selector(
    message: types.Message,
    db_user: User,
    state: FSMContext
):
    data = await state.get_data()
    selected_buttons = data.get('selected_buttons')
    if selected_buttons is None:
        selected_buttons = list(DEFAULT_SELECTED_BUTTONS)
        await state.update_data(selected_buttons=selected_buttons)

    has_media = data.get('has_media', False)

    texts = get_texts(db_user.language)
    text = texts.t(
        "ADMIN_MESSAGES_BUTTON_SELECTOR_TITLE",
        "📘 <b>Select additional buttons</b>"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_SELECTOR_DESCRIPTION",
        "Choose buttons that will be added to the broadcast message:"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_BALANCE_DESC",
        "💰 <b>Top up balance</b> — opens top-up methods"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_REFERRALS_DESC",
        "🤝 <b>Referrals</b> — opens referral program"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_PROMOCODE_DESC",
        "🎫 <b>Promo code</b> — opens promo code input form"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_CONNECT_DESC",
        "🔗 <b>Connect</b> — helps connect the app"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_SUBSCRIPTION_DESC",
        "📱 <b>Subscription</b> — shows subscription status"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_SUPPORT_DESC",
        "🛠️ <b>Support</b> — connects with support"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_HOME_DESC",
        "🏠 <b>Main menu button</b> is enabled by default, but you can disable it if needed."
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_BUTTON_SELECTOR_PROMPT",
        "Choose needed buttons and press \"Continue\":"
    )

    keyboard = get_updated_message_buttons_selector_keyboard_with_media(
        selected_buttons, has_media, db_user.language
    )

    await message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@admin_required
@error_handler
async def toggle_button_selection(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    button_type = callback.data.replace('btn_', '')
    data = await state.get_data()
    selected_buttons = data.get('selected_buttons')
    if selected_buttons is None:
        selected_buttons = list(DEFAULT_SELECTED_BUTTONS)
    else:
        selected_buttons = list(selected_buttons)

    if button_type in selected_buttons:
        selected_buttons.remove(button_type)
    else:
        selected_buttons.append(button_type)

    await state.update_data(selected_buttons=selected_buttons)

    has_media = data.get('has_media', False)
    keyboard = get_updated_message_buttons_selector_keyboard_with_media(
        selected_buttons, has_media, db_user.language
    )

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@admin_required
@error_handler
async def confirm_button_selection(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    data = await state.get_data()
    target = data.get('broadcast_target')
    message_text = data.get('broadcast_message')
    selected_buttons = data.get('selected_buttons')
    if selected_buttons is None:
        selected_buttons = list(DEFAULT_SELECTED_BUTTONS)
        await state.update_data(selected_buttons=selected_buttons)
    has_media = data.get('has_media', False)
    media_type = data.get('media_type')
    
    texts = get_texts(db_user.language)
    user_count = await get_target_users_count(db, target) if not target.startswith('custom_') else await get_custom_users_count(db, target.replace('custom_', ''))
    target_display = get_target_display_name(target, db_user.language)
    
    texts = get_texts(db_user.language)
    media_info = ""
    if has_media:
        media_type_names = {
            "photo": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_PHOTO", "Photo"),
            "video": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_VIDEO", "Video"),
            "document": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_DOCUMENT", "Document")
        }
        media_info = texts.t(
            "ADMIN_MESSAGES_PREVIEW_MEDIA",
            "\n🖼️ <b>Media file:</b> {media_type}"
        ).format(media_type=media_type_names.get(media_type, media_type))
    
    ordered_keys = [button_key for row in BUTTON_ROWS for button_key in row]
    button_labels = get_broadcast_button_labels(db_user.language)
    selected_names = [button_labels[key] for key in ordered_keys if key in selected_buttons]
    if selected_names:
        buttons_info = texts.t(
            "ADMIN_MESSAGES_PREVIEW_BUTTONS",
            "\n📘 <b>Buttons:</b> {buttons}"
        ).format(buttons=', '.join(selected_names))
    else:
        buttons_info = texts.t(
            "ADMIN_MESSAGES_PREVIEW_NO_BUTTONS",
            "\n📘 <b>Buttons:</b> none"
        )
    
    preview_text = texts.t(
        "ADMIN_MESSAGES_PREVIEW_TITLE",
        "📨 <b>Broadcast preview</b>"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_PREVIEW_AUDIENCE",
        "🎯 <b>Audience:</b> {audience}"
    ).format(audience=target_display) + "\n" + texts.t(
        "ADMIN_MESSAGES_PREVIEW_RECIPIENTS",
        "👥 <b>Recipients:</b> {count}"
    ).format(count=user_count) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_PREVIEW_MESSAGE",
        "📝 <b>Message:</b>\n{message}"
    ).format(message=message_text) + media_info + buttons_info + "\n\n" + texts.t(
        "ADMIN_MESSAGES_PREVIEW_CONFIRM",
        "Confirm sending?"
    )
    
    keyboard = [
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_MESSAGES_PREVIEW_SEND", "✅ Send"), callback_data="admin_confirm_broadcast"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_MESSAGES_PREVIEW_EDIT_BUTTONS", "📘 Edit buttons"), callback_data="edit_buttons")
        ]
    ]
    
    if has_media:
        keyboard.append([
            types.InlineKeyboardButton(text=texts.t("ADMIN_MESSAGES_PREVIEW_CHANGE_MEDIA", "🖼️ Change media"), callback_data="change_media")
        ])
    
    keyboard.append([
        types.InlineKeyboardButton(text=texts.t("ADMIN_MESSAGES_PREVIEW_CANCEL", "❌ Cancel"), callback_data="admin_messages")
    ])
    
    # If there is media, show it with uploaded photo, otherwise regular text message
    if has_media and media_type == "photo":
        media_file_id = data.get('media_file_id')
        if media_file_id:
            # Delete current message and send new one with photo
            await callback.message.delete()
            await callback.bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=media_file_id,
                caption=preview_text,
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )
        else:
            # If no file_id, use regular editing
            await callback.message.edit_text(
                preview_text,
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )
    else:
        # For text messages or other media types use regular editing
        await callback.message.edit_text(
            preview_text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode="HTML"
        )
    
    await callback.answer()
@admin_required
@error_handler
async def confirm_broadcast(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    data = await state.get_data()
    target = data.get('broadcast_target')
    message_text = data.get('broadcast_message')
    selected_buttons = data.get('selected_buttons')
    if selected_buttons is None:
        selected_buttons = list(DEFAULT_SELECTED_BUTTONS)
    has_media = data.get('has_media', False)
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    media_caption = data.get('media_caption')
    
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t(
            "ADMIN_MESSAGES_SENDING",
            "📨 Starting broadcast...\n\n"
        ) + texts.t(
            "ADMIN_MESSAGES_SENDING_WAIT",
            "⏳ This may take several minutes."
        ),
        reply_markup=None,
        parse_mode="HTML" 
    )
    
    if target.startswith('custom_'):
        users = await get_custom_users(db, target.replace('custom_', ''))
    else:
        users = await get_target_users(db, target)
    
    broadcast_history = BroadcastHistory(
        target_type=target,
        message_text=message_text,
        has_media=has_media,
        media_type=media_type,
        media_file_id=media_file_id,
        media_caption=media_caption,
        total_count=len(users),
        sent_count=0,
        failed_count=0,
        admin_id=db_user.id,
        admin_name=db_user.full_name,
        status="in_progress"
    )
    db.add(broadcast_history)
    await db.commit()
    await db.refresh(broadcast_history)
    
    sent_count = 0
    failed_count = 0
    
    broadcast_keyboard = create_broadcast_keyboard(selected_buttons, db_user.language)
    
    # Limit on concurrent sends and base delay between messages
    # to avoid bot overload and Telegram limits for large broadcasts
    max_concurrent_sends = 5
    per_message_delay = 0.05
    semaphore = asyncio.Semaphore(max_concurrent_sends)

    async def send_single_broadcast(user):
        """Sends a single broadcast message with semaphore limiting"""
        async with semaphore:
            for attempt in range(3):
                try:
                    if has_media and media_file_id:
                        if media_type == "photo":
                            await callback.bot.send_photo(
                                chat_id=user.telegram_id,
                                photo=media_file_id,
                                caption=message_text,
                                parse_mode="HTML",
                                reply_markup=broadcast_keyboard
                            )
                        elif media_type == "video":
                            await callback.bot.send_video(
                                chat_id=user.telegram_id,
                                video=media_file_id,
                                caption=message_text,
                                parse_mode="HTML",
                                reply_markup=broadcast_keyboard
                            )
                        elif media_type == "document":
                            await callback.bot.send_document(
                                chat_id=user.telegram_id,
                                document=media_file_id,
                                caption=message_text,
                                parse_mode="HTML",
                                reply_markup=broadcast_keyboard
                            )
                    else:
                        await callback.bot.send_message(
                            chat_id=user.telegram_id,
                            text=message_text,
                            parse_mode="HTML",
                            reply_markup=broadcast_keyboard
                        )

                    await asyncio.sleep(per_message_delay)
                    return True, user.telegram_id
                except TelegramRetryAfter as e:
                    retry_delay = min(e.retry_after + 1, 30)
                    logger.warning(
                        f"Telegram rate limit exceeded for {user.telegram_id}, waiting {retry_delay} sec."
                    )
                    await asyncio.sleep(retry_delay)
                except TelegramForbiddenError:
                    # User may have deleted the bot or blocked messages
                    logger.info(f"Broadcast unavailable for user {user.telegram_id}: Forbidden")
                    return False, user.telegram_id
                except TelegramBadRequest as e:
                    logger.error(
                        f"Invalid request when broadcasting to user {user.telegram_id}: {e}"
                    )
                    return False, user.telegram_id
                except Exception as e:
                    logger.error(
                        f"Error sending broadcast to user {user.telegram_id} (attempt {attempt + 1}/3): {e}"
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))

            return False, user.telegram_id

    # Send messages in batches for efficiency
    batch_size = 50
    for i in range(0, len(users), batch_size):
        batch = users[i:i + batch_size]
        tasks = [send_single_broadcast(user) for user in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, tuple):  # (success, telegram_id)
                success, _ = result
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            elif isinstance(result, Exception):
                failed_count += 1

        # Small delay between batches to reduce API load
        await asyncio.sleep(0.25)
    
    status = "completed" if failed_count == 0 else "partial"
    await _persist_broadcast_result(
        db=db,
        broadcast_history=broadcast_history,
        sent_count=sent_count,
        failed_count=failed_count,
        status=status,
    )
    
    texts = get_texts(db_user.language)
    media_info = ""
    if has_media:
        media_type_names = {
            "photo": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_PHOTO", "Photo"),
            "video": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_VIDEO", "Video"),
            "document": texts.t("ADMIN_MESSAGES_MEDIA_TYPE_DOCUMENT", "Document")
        }
        media_info = "\n" + texts.t(
            "ADMIN_MESSAGES_PREVIEW_MEDIA",
            "\n🖼️ <b>Media file:</b> {media_type}"
        ).format(media_type=media_type_names.get(media_type, media_type))
    
    success_rate = round(sent_count / len(users) * 100, 1) if users else 0
    result_text = texts.t(
        "ADMIN_MESSAGES_COMPLETED",
        "✅ <b>Broadcast completed!</b>"
    ) + "\n\n" + texts.t(
        "ADMIN_MESSAGES_RESULT",
        "📊 <b>Result:</b>"
    ) + "\n" + texts.t(
        "ADMIN_MESSAGES_RESULT_SENT",
        "- Sent: {sent}"
    ).format(sent=sent_count) + "\n" + texts.t(
        "ADMIN_MESSAGES_RESULT_FAILED",
        "- Failed: {failed}"
    ).format(failed=failed_count) + "\n" + texts.t(
        "ADMIN_MESSAGES_RESULT_TOTAL",
        "- Total users: {total}"
    ).format(total=len(users)) + "\n" + texts.t(
        "ADMIN_MESSAGES_RESULT_SUCCESS_RATE",
        "- Success rate: {rate}%"
    ).format(rate=success_rate) + media_info + "\n\n" + texts.t(
        "ADMIN_MESSAGES_RESULT_ADMIN",
        "<b>Administrator:</b> {admin}"
    ).format(admin=db_user.full_name)
    
    await callback.message.edit_text(
        result_text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_MESSAGES_BACK_TO_BROADCASTS", "📨 Back to broadcasts"), callback_data="admin_messages")]
        ]),
        parse_mode="HTML" 
    )
    
    await state.clear()
    logger.info(f"Broadcast completed by admin {db_user.telegram_id}: {sent_count}/{len(users)} (media: {has_media})")


async def get_target_users_count(db: AsyncSession, target: str) -> int:
    users = await get_target_users(db, target)
    return len(users)


async def get_target_users(db: AsyncSession, target: str) -> list:
    # Load all active users in batches to avoid 10k limit
    users: list[User] = []
    offset = 0
    batch_size = 5000

    while True:
        batch = await get_users_list(
            db,
            offset=offset,
            limit=batch_size,
            status=UserStatus.ACTIVE,
        )

        if not batch:
            break

        users.extend(batch)
        offset += batch_size

    if target == "all":
        return users

    if target == "active":
        return [
            user
            for user in users
            if user.subscription
            and user.subscription.is_active
            and not user.subscription.is_trial
        ]

    if target == "trial":
        return [
            user
            for user in users
            if user.subscription and user.subscription.is_trial
        ]

    if target == "no":
        return [
            user
            for user in users
            if not user.subscription or not user.subscription.is_active
        ]

    if target == "expiring":
        expiring_subs = await get_expiring_subscriptions(db, 3)
        return [sub.user for sub in expiring_subs if sub.user]

    if target == "expired":
        now = datetime.utcnow()
        expired_statuses = {
            SubscriptionStatus.EXPIRED.value,
            SubscriptionStatus.DISABLED.value,
        }
        expired_users = []
        for user in users:
            subscription = user.subscription
            if subscription:
                if subscription.status in expired_statuses:
                    expired_users.append(user)
                    continue
                if subscription.end_date <= now and not subscription.is_active:
                    expired_users.append(user)
                    continue
            elif user.has_had_paid_subscription:
                expired_users.append(user)
        return expired_users

    if target == "active_zero":
        return [
            user
            for user in users
            if user.subscription
            and not user.subscription.is_trial
            and user.subscription.is_active
            and (user.subscription.traffic_used_gb or 0) <= 0
        ]

    if target == "trial_zero":
        return [
            user
            for user in users
            if user.subscription
            and user.subscription.is_trial
            and user.subscription.is_active
            and (user.subscription.traffic_used_gb or 0) <= 0
        ]

    if target == "zero":
        return [
            user
            for user in users
            if user.subscription
            and user.subscription.is_active
            and (user.subscription.traffic_used_gb or 0) <= 0
        ]

    return []


async def get_custom_users_count(db: AsyncSession, criteria: str) -> int:
    users = await get_custom_users(db, criteria)
    return len(users)


async def get_custom_users(db: AsyncSession, criteria: str) -> list:
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    if criteria == "today":
        stmt = select(User).where(
            and_(User.status == "active", User.created_at >= today)
        )
    elif criteria == "week":
        stmt = select(User).where(
            and_(User.status == "active", User.created_at >= week_ago)
        )
    elif criteria == "month":
        stmt = select(User).where(
            and_(User.status == "active", User.created_at >= month_ago)
        )
    elif criteria == "active_today":
        stmt = select(User).where(
            and_(User.status == "active", User.last_activity >= today)
        )
    elif criteria == "inactive_week":
        stmt = select(User).where(
            and_(User.status == "active", User.last_activity < week_ago)
        )
    elif criteria == "inactive_month":
        stmt = select(User).where(
            and_(User.status == "active", User.last_activity < month_ago)
        )
    elif criteria == "referrals":
        stmt = select(User).where(
            and_(User.status == "active", User.referred_by_id.isnot(None))
        )
    elif criteria == "direct":
        stmt = select(User).where(
            and_(
                User.status == "active", 
                User.referred_by_id.is_(None)
            )
        )
    else:
        return []
    
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_users_statistics(db: AsyncSession) -> dict:
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    stats = {}
    
    stats['today'] = await db.scalar(
        select(func.count(User.id)).where(
            and_(User.status == "active", User.created_at >= today)
        )
    ) or 0
    
    stats['week'] = await db.scalar(
        select(func.count(User.id)).where(
            and_(User.status == "active", User.created_at >= week_ago)
        )
    ) or 0
    
    stats['month'] = await db.scalar(
        select(func.count(User.id)).where(
            and_(User.status == "active", User.created_at >= month_ago)
        )
    ) or 0
    
    stats['active_today'] = await db.scalar(
        select(func.count(User.id)).where(
            and_(User.status == "active", User.last_activity >= today)
        )
    ) or 0
    
    stats['inactive_week'] = await db.scalar(
        select(func.count(User.id)).where(
            and_(User.status == "active", User.last_activity < week_ago)
        )
    ) or 0
    
    stats['inactive_month'] = await db.scalar(
        select(func.count(User.id)).where(
            and_(User.status == "active", User.last_activity < month_ago)
        )
    ) or 0
    
    stats['referrals'] = await db.scalar(
        select(func.count(User.id)).where(
            and_(User.status == "active", User.referred_by_id.isnot(None))
        )
    ) or 0
    
    stats['direct'] = await db.scalar(
        select(func.count(User.id)).where(
            and_(
                User.status == "active", 
                User.referred_by_id.is_(None)
            )
        )
    ) or 0
    
    return stats


def get_target_name(target_type: str, language: str = "en") -> str:
    texts = get_texts(language)
    names = {
        "all": texts.t("ADMIN_MESSAGES_TARGET_ALL", "All users"),
        "active": texts.t("ADMIN_MESSAGES_TARGET_ACTIVE", "With active subscription"),
        "trial": texts.t("ADMIN_MESSAGES_TARGET_TRIAL", "With trial subscription"),
        "no": texts.t("ADMIN_MESSAGES_TARGET_NO", "Without subscription"),
        "sub": texts.t("ADMIN_MESSAGES_TARGET_NO", "Without subscription"),
        "expiring": texts.t("ADMIN_MESSAGES_TARGET_EXPIRING", "With expiring subscription"),
        "expired": texts.t("ADMIN_MESSAGES_TARGET_EXPIRED", "With expired subscription"),
        "active_zero": texts.t("ADMIN_MESSAGES_TARGET_ACTIVE_ZERO", "Active subscription, 0 GB traffic"),
        "trial_zero": texts.t("ADMIN_MESSAGES_TARGET_TRIAL_ZERO", "Trial subscription, 0 GB traffic"),
        "zero": texts.t("ADMIN_MESSAGES_TARGET_ACTIVE_ZERO", "Active subscription, 0 GB traffic"),
        "custom_today": texts.t("ADMIN_MESSAGES_TARGET_CUSTOM_TODAY", "Registered today"),
        "custom_week": texts.t("ADMIN_MESSAGES_TARGET_CUSTOM_WEEK", "Registered last week"),
        "custom_month": texts.t("ADMIN_MESSAGES_TARGET_CUSTOM_MONTH", "Registered last month"),
        "custom_active_today": texts.t("ADMIN_MESSAGES_TARGET_CUSTOM_ACTIVE_TODAY", "Active today"),
        "custom_inactive_week": texts.t("ADMIN_MESSAGES_TARGET_CUSTOM_INACTIVE_WEEK", "Inactive 7+ days"),
        "custom_inactive_month": texts.t("ADMIN_MESSAGES_TARGET_CUSTOM_INACTIVE_MONTH", "Inactive 30+ days"),
        "custom_referrals": texts.t("ADMIN_MESSAGES_TARGET_CUSTOM_REFERRALS", "Via referrals"),
        "custom_direct": texts.t("ADMIN_MESSAGES_TARGET_CUSTOM_DIRECT", "Direct registration")
    }
    return names.get(target_type, target_type)


def get_target_display_name(target: str, language: str = "en") -> str:
    return get_target_name(target, language)


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_messages_menu, F.data == "admin_messages")
    dp.callback_query.register(show_broadcast_targets, F.data.in_(["admin_msg_all", "admin_msg_by_sub"]))
    dp.callback_query.register(select_broadcast_target, F.data.startswith("broadcast_"))
    dp.callback_query.register(confirm_broadcast, F.data == "admin_confirm_broadcast")
    
    dp.callback_query.register(show_messages_history, F.data.startswith("admin_msg_history"))
    dp.callback_query.register(show_custom_broadcast, F.data == "admin_msg_custom")
    dp.callback_query.register(select_custom_criteria, F.data.startswith("criteria_"))
    
    dp.callback_query.register(toggle_button_selection, F.data.startswith("btn_"))
    dp.callback_query.register(confirm_button_selection, F.data == "buttons_confirm")
    dp.callback_query.register(show_button_selector_callback, F.data == "edit_buttons")
    dp.callback_query.register(handle_media_selection, F.data.startswith("add_media_"))
    dp.callback_query.register(handle_media_selection, F.data == "skip_media")
    dp.callback_query.register(handle_media_confirmation, F.data.in_(["confirm_media", "replace_media"]))
    dp.callback_query.register(handle_change_media, F.data == "change_media")
    dp.message.register(process_broadcast_message, AdminStates.waiting_for_broadcast_message)
    dp.message.register(process_broadcast_media, AdminStates.waiting_for_broadcast_media)
