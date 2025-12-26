import logging
from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.user_message import (
    create_user_message, get_all_user_messages, get_user_message_by_id,
    update_user_message, delete_user_message, toggle_user_message_status,
    get_user_messages_stats
)
from app.database.models import User
from app.keyboards.admin import get_admin_main_keyboard
from app.utils.validators import (
    get_html_help_text,
    sanitize_html,
    validate_html_tags,
)
from app.utils.decorators import admin_required, error_handler
from app.localization.texts import get_texts

logger = logging.getLogger(__name__)


class UserMessageStates(StatesGroup):
    waiting_for_message_text = State()
    waiting_for_edit_text = State()


def get_user_messages_keyboard(language: str = "ru"):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from app.localization.texts import get_texts
    texts = get_texts(language)
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_USER_MESSAGES_ADD", "📝 Add message"),
                callback_data="add_user_message"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_USER_MESSAGES_LIST", "📋 Message list"),
                callback_data="list_user_messages:0"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_USER_MESSAGES_STATS", "📊 Statistics"),
                callback_data="user_messages_stats"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_USER_MESSAGES_BACK", "🔙 Back to admin"),
                callback_data="admin_panel"
            )
        ]
    ])


def get_message_actions_keyboard(message_id: int, is_active: bool, language: str = "ru"):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from app.localization.texts import get_texts
    texts = get_texts(language)
    
    status_text = texts.t("ADMIN_USER_MESSAGES_DEACTIVATE", "🔴 Deactivate") if is_active else texts.t("ADMIN_USER_MESSAGES_ACTIVATE", "🟢 Activate")
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_USER_MESSAGES_EDIT", "✏️ Edit"),
                callback_data=f"edit_user_message:{message_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=status_text,
                callback_data=f"toggle_user_message:{message_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_USER_MESSAGES_DELETE", "🗑️ Delete"),
                callback_data=f"delete_user_message:{message_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_USER_MESSAGES_BACK_TO_LIST", "🔙 Back to list"),
                callback_data="list_user_messages:0"
            )
        ]
    ])


@admin_required
@error_handler
async def show_user_messages_panel(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    text = texts.t(
        "ADMIN_USER_MESSAGES_PANEL_DESCRIPTION",
        "📢 <b>Main menu message management</b>\n\n"
        "Here you can add messages that will be shown to users "
        "in the main menu between subscription information and action buttons.\n\n"
        "• Messages support HTML tags\n"
        "• You can create multiple messages\n"
        "• Active messages are shown randomly\n"
        "• Inactive messages are not shown"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_user_messages_keyboard(db_user.language),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def add_user_message_start(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t(
            "ADMIN_USER_MESSAGES_ADD_PROMPT",
            "📝 <b>Adding new message</b>\n\n"
            "Enter the message text that will be shown in the main menu.\n\n"
            "{html_help}\n\n"
            "Send /cancel to cancel."
        ).format(html_help=get_html_help_text()),
        parse_mode="HTML"
    )
    
    await state.set_state(UserMessageStates.waiting_for_message_text)
    await callback.answer()


@admin_required
@error_handler
async def process_new_message_text(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            texts.t("ADMIN_USER_MESSAGES_ADD_CANCELLED", "❌ Message addition cancelled."),
            reply_markup=get_user_messages_keyboard(db_user.language)
        )
        return
    
    message_text = message.text.strip()
    
    if len(message_text) > 4000:
        await message.answer(
            texts.t(
                "ADMIN_USER_MESSAGES_TOO_LONG",
                "❌ Message is too long. Maximum 4000 characters.\n"
                "Please try again or send /cancel to cancel."
            )
        )
        return
    
    is_valid, error_msg = validate_html_tags(message_text)
    if not is_valid:
        await message.answer(
            texts.t(
                "ADMIN_USER_MESSAGES_HTML_ERROR",
                "❌ HTML markup error: {error}\n\n"
                "Fix the error and try again, or send /cancel to cancel."
            ).format(error=error_msg),
            parse_mode=None 
        )
        return
    
    try:
        new_message = await create_user_message(
            db=db,
            message_text=message_text,
            created_by=db_user.id,
            is_active=True
        )
        
        await state.clear()
        
        active_status = texts.t("ADMIN_USER_MESSAGES_ACTIVE", "🟢 Active") if new_message.is_active else texts.t("ADMIN_USER_MESSAGES_INACTIVE", "🔴 Inactive")
        await message.answer(
            texts.t(
                "ADMIN_USER_MESSAGES_ADDED_SUCCESS",
                "✅ <b>Message added!</b>\n\n"
                "<b>ID:</b> {id}\n"
                "<b>Status:</b> {status}\n"
                "<b>Created:</b> {created}\n\n"
                "<b>Preview:</b>\n"
                "<blockquote>{preview}</blockquote>"
            ).format(
                id=new_message.id,
                status=active_status,
                created=new_message.created_at.strftime('%d.%m.%Y %H:%M'),
                preview=message_text
            ),
            reply_markup=get_user_messages_keyboard(db_user.language),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error creating message: {e}")
        await state.clear()
        await message.answer(
            texts.t("ADMIN_USER_MESSAGES_CREATE_ERROR", "❌ An error occurred while creating the message. Please try again."),
            reply_markup=get_user_messages_keyboard(db_user.language)
        )

@admin_required
@error_handler
async def list_user_messages(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    page = 0
    if ":" in callback.data:
        try:
            page = int(callback.data.split(":")[1])
        except (ValueError, IndexError):
            page = 0
    
    limit = 5
    offset = page * limit
    
    texts = get_texts(db_user.language)
    messages = await get_all_user_messages(db, offset=offset, limit=limit)
    
    if not messages:
        await callback.message.edit_text(
            texts.t(
                "ADMIN_USER_MESSAGES_LIST_EMPTY",
                "📋 <b>Message list</b>\n\n"
                "No messages yet. Add the first message!"
            ),
            reply_markup=get_user_messages_keyboard(db_user.language),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = texts.t("ADMIN_USER_MESSAGES_LIST_TITLE", "📋 <b>Message list</b>\n\n")
    
    for msg in messages:
        status_emoji = "🟢" if msg.is_active else "🔴"
        preview = msg.message_text[:100] + "..." if len(msg.message_text) > 100 else msg.message_text
        preview = preview.replace('<', '&lt;').replace('>', '&gt;')
        
        text += (
            f"{status_emoji} <b>ID {msg.id}</b>\n"
            f"{preview}\n"
            f"📅 {msg.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = []
    
    for msg in messages:
        status_emoji = "🟢" if msg.is_active else "🔴"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status_emoji} ID {msg.id}",
                callback_data=f"view_user_message:{msg.id}"
            )
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text=texts.t("ADMIN_USER_MESSAGES_NAV_BACK", "⬅️ Back"),
                callback_data=f"list_user_messages:{page-1}"
            )
        )
    
    nav_buttons.append(
        InlineKeyboardButton(
            text=texts.t("ADMIN_USER_MESSAGES_NAV_ADD", "➕ Add"),
            callback_data="add_user_message"
        )
    )
    
    if len(messages) == limit:  
        nav_buttons.append(
            InlineKeyboardButton(
                text=texts.t("ADMIN_USER_MESSAGES_NAV_NEXT", "Next ➡️"),
                callback_data=f"list_user_messages:{page+1}"
            )
        )
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(
            text=texts.t("ADMIN_USER_MESSAGES_NAV_BACK", "🔙 Back"),
            callback_data="user_messages_panel"
        )
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def view_user_message(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    try:
        message_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_USER_MESSAGES_INVALID_ID", "❌ Invalid message ID"), show_alert=True)
        return
    
    message = await get_user_message_by_id(db, message_id)

    if not message:
        await callback.answer(texts.t("ADMIN_USER_MESSAGES_NOT_FOUND", "❌ Message not found"), show_alert=True)
        return

    safe_content = sanitize_html(message.message_text)

    status_text = texts.t("ADMIN_USER_MESSAGES_ACTIVE", "🟢 Active") if message.is_active else texts.t("ADMIN_USER_MESSAGES_INACTIVE", "🔴 Inactive")

    text = texts.t(
        "ADMIN_USER_MESSAGES_VIEW_DETAILS",
        "📋 <b>Message ID {id}</b>\n\n"
        "<b>Status:</b> {status}\n"
        "<b>Created:</b> {created}\n"
        "<b>Updated:</b> {updated}\n\n"
        "<b>Content:</b>\n"
        "<blockquote>{content}</blockquote>"
    ).format(
        id=message.id,
        status=status_text,
        created=message.created_at.strftime('%d.%m.%Y %H:%M'),
        updated=message.updated_at.strftime('%d.%m.%Y %H:%M'),
        content=safe_content
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_message_actions_keyboard(
            message_id, message.is_active, db_user.language
        ),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_message_status(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    try:
        message_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_USER_MESSAGES_INVALID_ID", "❌ Invalid message ID"), show_alert=True)
        return
    
    message = await toggle_user_message_status(db, message_id)
    
    if not message:
        await callback.answer(texts.t("ADMIN_USER_MESSAGES_NOT_FOUND", "❌ Message not found"), show_alert=True)
        return
    
    status_text = texts.t("ADMIN_USER_MESSAGES_ACTIVATED", "activated") if message.is_active else texts.t("ADMIN_USER_MESSAGES_DEACTIVATED", "deactivated")
    await callback.answer(texts.t("ADMIN_USER_MESSAGES_TOGGLE_SUCCESS", "✅ Message {status}").format(status=status_text))
    
    await view_user_message(callback, db_user, db)


@admin_required
@error_handler
async def delete_message_confirm(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    try:
        message_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_USER_MESSAGES_INVALID_ID", "❌ Invalid message ID"), show_alert=True)
        return
    
    success = await delete_user_message(db, message_id)
    
    if success:
        await callback.answer(texts.t("ADMIN_USER_MESSAGES_DELETED", "✅ Message deleted"))
        await list_user_messages(
            types.CallbackQuery(
                id=callback.id,
                from_user=callback.from_user,
                chat_instance=callback.chat_instance,
                data="list_user_messages:0",
                message=callback.message
            ),
            db_user,
            db
        )
    else:
        await callback.answer(texts.t("ADMIN_USER_MESSAGES_DELETE_ERROR", "❌ Error deleting message"), show_alert=True)


@admin_required
@error_handler
async def show_messages_stats(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    stats = await get_user_messages_stats(db)
    
    text = texts.t(
        "ADMIN_USER_MESSAGES_STATS_DETAILS",
        "📊 <b>Message statistics</b>\n\n"
        "📝 Total messages: <b>{total}</b>\n"
        "🟢 Active: <b>{active}</b>\n"
        "🔴 Inactive: <b>{inactive}</b>\n\n"
        "Active messages are shown to users randomly "
        "in the main menu between subscription information and action buttons."
    ).format(
        total=stats['total_messages'],
        active=stats['active_messages'],
        inactive=stats['inactive_messages']
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_USER_MESSAGES_NAV_BACK", "🔙 Back"),
                callback_data="user_messages_panel"
            )
        ]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@admin_required
@error_handler
async def edit_user_message_start(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    try:
        message_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_USER_MESSAGES_INVALID_ID", "❌ Invalid message ID"), show_alert=True)
        return
    
    message = await get_user_message_by_id(db, message_id)
    
    if not message:
        await callback.answer(texts.t("ADMIN_USER_MESSAGES_NOT_FOUND", "❌ Message not found"), show_alert=True)
        return
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_USER_MESSAGES_EDIT_PROMPT",
            "✏️ <b>Editing message ID {id}</b>\n\n"
            "<b>Current text:</b>\n"
            "<blockquote>{current}</blockquote>\n\n"
            "Enter the new message text or send /cancel to cancel:"
        ).format(
            id=message.id,
            current=sanitize_html(message.message_text)
        ),
        parse_mode="HTML"
    )
    
    await state.set_data({"editing_message_id": message_id})
    await state.set_state(UserMessageStates.waiting_for_edit_text)
    await callback.answer()

@admin_required
@error_handler
async def process_edit_message_text(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            texts.t("ADMIN_USER_MESSAGES_EDIT_CANCELLED", "❌ Editing cancelled."),
            reply_markup=get_user_messages_keyboard(db_user.language)
        )
        return
    
    data = await state.get_data()
    message_id = data.get("editing_message_id")
    
    if not message_id:
        await state.clear()
        await message.answer(texts.t("ADMIN_USER_MESSAGES_EDIT_ID_ERROR", "❌ Error: message ID not found"))
        return
    
    new_text = message.text.strip()

    if len(new_text) > 4000:
        await message.answer(
            texts.t(
                "ADMIN_USER_MESSAGES_TOO_LONG",
                "❌ Message is too long. Maximum 4000 characters.\n"
                "Please try again or send /cancel to cancel."
            )
        )
        return

    is_valid, error_msg = validate_html_tags(new_text)
    if not is_valid:
        await message.answer(
            texts.t(
                "ADMIN_USER_MESSAGES_HTML_ERROR",
                "❌ HTML markup error: {error}\n\n"
                "Fix the error and try again, or send /cancel to cancel."
            ).format(error=error_msg),
            parse_mode=None
        )
        return

    try:
        updated_message = await update_user_message(
            db=db,
            message_id=message_id,
            message_text=new_text
        )
        
        if updated_message:
            await state.clear()
            await message.answer(
                texts.t(
                    "ADMIN_USER_MESSAGES_UPDATED_SUCCESS",
                    "✅ <b>Message updated!</b>\n\n"
                    "<b>ID:</b> {id}\n"
                    "<b>Updated:</b> {updated}\n\n"
                    "<b>New text:</b>\n"
                    "<blockquote>{text}</blockquote>"
                ).format(
                    id=updated_message.id,
                    updated=updated_message.updated_at.strftime('%d.%m.%Y %H:%M'),
                    text=sanitize_html(new_text)
                ),
                reply_markup=get_user_messages_keyboard(db_user.language),
                parse_mode="HTML"
            )
        else:
            await state.clear()
            await message.answer(
                texts.t("ADMIN_USER_MESSAGES_UPDATE_ERROR", "❌ Message not found or update error."),
                reply_markup=get_user_messages_keyboard(db_user.language)
            )
        
    except Exception as e:
        logger.error(f"Error updating message: {e}")
        await state.clear()
        await message.answer(
            texts.t("ADMIN_USER_MESSAGES_UPDATE_EXCEPTION", "❌ An error occurred while updating the message."),
            reply_markup=get_user_messages_keyboard(db_user.language)
        )


def register_handlers(dp: Dispatcher):
    
    dp.callback_query.register(
        show_user_messages_panel,
        F.data == "user_messages_panel"
    )
    
    dp.callback_query.register(
        add_user_message_start,
        F.data == "add_user_message"
    )
    
    dp.message.register(
        process_new_message_text,
        StateFilter(UserMessageStates.waiting_for_message_text)
    )

    dp.callback_query.register(
        edit_user_message_start,
        F.data.startswith("edit_user_message:")
    )
    
    dp.message.register(
        process_edit_message_text,
        StateFilter(UserMessageStates.waiting_for_edit_text)
    )
    
    dp.callback_query.register(
        list_user_messages,
        F.data.startswith("list_user_messages")
    )
    
    dp.callback_query.register(
        view_user_message,
        F.data.startswith("view_user_message:")
    )
    
    dp.callback_query.register(
        toggle_message_status,
        F.data.startswith("toggle_user_message:")
    )
    
    dp.callback_query.register(
        delete_message_confirm,
        F.data.startswith("delete_user_message:")
    )
    
    dp.callback_query.register(
        show_messages_stats,
        F.data == "user_messages_stats"
    )
