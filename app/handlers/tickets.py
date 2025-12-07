import logging
from typing import List, Dict, Any
import asyncio
import time
from aiogram import Dispatcher, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.database.models import User, Ticket, TicketStatus
from app.database.crud.ticket import TicketCRUD, TicketMessageCRUD
from app.database.crud.user import get_user_by_id
from app.keyboards.inline import (
    get_ticket_cancel_keyboard,
    get_my_tickets_keyboard,
    get_ticket_view_keyboard,
    get_ticket_reply_cancel_keyboard,
    get_admin_tickets_keyboard,
    get_admin_ticket_view_keyboard,
    get_admin_ticket_reply_cancel_keyboard
)
from app.localization.texts import get_texts
from app.config import settings
from app.services.admin_notification_service import AdminNotificationService
from app.utils.pagination import paginate_list, get_pagination_info
from app.utils.photo_message import edit_or_answer_photo
from app.utils.cache import RateLimitCache, cache, cache_key

logger = logging.getLogger(__name__)


class TicketStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_message = State()
    waiting_for_reply = State()


async def show_ticket_priority_selection(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    """Start ticket creation without priority selection: ask for title immediately"""
    texts = get_texts(db_user.language)
    
    # Global block and check for active ticket
    from app.database.crud.ticket import TicketCRUD
    blocked_until = await TicketCRUD.is_user_globally_blocked(db, db_user.id)
    if blocked_until:
        if blocked_until.year > 9999 - 1:
            await callback.answer(texts.t("USER_BLOCKED_FOREVER", "You are blocked from contacting support."), show_alert=True)
        else:
            await callback.answer(
                texts.t("USER_BLOCKED_UNTIL", "You are blocked until {time}").format(time=blocked_until.strftime('%d.%m.%Y %H:%M')),
                show_alert=True
            )
        return
    if await TicketCRUD.user_has_active_ticket(db, db_user.id):
        await callback.answer(
            texts.t("TICKET_ALREADY_OPEN", "You already have an open ticket. Please close it first."),
            show_alert=True
        )
        return
    
    await callback.message.edit_text(
        texts.t("TICKET_TITLE_INPUT", "Enter ticket title:"),
        reply_markup=get_ticket_cancel_keyboard(db_user.language)
    )
    # Remember original bot message to edit it later instead of sending new ones
    await state.update_data(prompt_chat_id=callback.message.chat.id, prompt_message_id=callback.message.message_id)
    await state.set_state(TicketStates.waiting_for_title)
    await callback.answer()


async def handle_ticket_title_input(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    # Check that user is in correct state
    current_state = await state.get_state()
    if current_state != TicketStates.waiting_for_title:
        return
    
    # Handle ticket title input
    title = message.text.strip()
    
    data_prompt = await state.get_data()
    prompt_chat_id = data_prompt.get("prompt_chat_id")
    prompt_message_id = data_prompt.get("prompt_message_id")
    # Delete user message after 2 seconds to keep chat clean
    asyncio.create_task(_try_delete_message_later(message.bot, message.chat.id, message.message_id, 2.0))
    if len(title) < 5:
        texts = get_texts(db_user.language)
        if prompt_chat_id and prompt_message_id:
            text_val = texts.t("TICKET_TITLE_TOO_SHORT", "Title must contain at least 5 characters. Try again:")
            if settings.ENABLE_LOGO_MODE:
                await message.bot.edit_message_caption(
                    chat_id=prompt_chat_id,
                    message_id=prompt_message_id,
                    caption=text_val,
                    reply_markup=get_ticket_cancel_keyboard(db_user.language),
                    parse_mode=None,
                )
            else:
                await message.bot.edit_message_text(
                    chat_id=prompt_chat_id,
                    message_id=prompt_message_id,
                    text=text_val,
                    reply_markup=get_ticket_cancel_keyboard(db_user.language),
                )
        else:
            await message.answer(
                texts.t("TICKET_TITLE_TOO_SHORT", "Title must contain at least 5 characters. Try again:")
            )
        return
    
    if len(title) > 255:
        texts = get_texts(db_user.language)
        if prompt_chat_id and prompt_message_id:
            text_val = texts.t("TICKET_TITLE_TOO_LONG", "Title is too long. Maximum 255 characters. Try again:")
            if settings.ENABLE_LOGO_MODE:
                await message.bot.edit_message_caption(
                    chat_id=prompt_chat_id,
                    message_id=prompt_message_id,
                    caption=text_val,
                    reply_markup=get_ticket_cancel_keyboard(db_user.language),
                    parse_mode=None,
                )
            else:
                await message.bot.edit_message_text(
                    chat_id=prompt_chat_id,
                    message_id=prompt_message_id,
                    text=text_val,
                    reply_markup=get_ticket_cancel_keyboard(db_user.language),
                )
        else:
            await message.answer(
                texts.t("TICKET_TITLE_TOO_LONG", "Title is too long. Maximum 255 characters. Try again:")
            )
        return
    
    # Global block
    from app.database.crud.ticket import TicketCRUD
    blocked_until = await TicketCRUD.is_user_globally_blocked(db, db_user.id)
    if blocked_until:
        texts = get_texts(db_user.language)
        if blocked_until.year > 9999 - 1:
            await message.answer(texts.t("USER_BLOCKED_FOREVER", "You are blocked from contacting support."))
        else:
            await message.answer(
                texts.t("USER_BLOCKED_UNTIL", "You are blocked until {time}").format(time=blocked_until.strftime('%d.%m.%Y %H:%M'))
            )
        await state.clear()
        return

    await state.update_data(title=title)
    
    texts = get_texts(db_user.language)
    
    if prompt_chat_id and prompt_message_id:
        text_val = texts.t("TICKET_MESSAGE_INPUT", "Describe your problem (up to 500 characters) or send a photo with caption:")
        if settings.ENABLE_LOGO_MODE:
            await message.bot.edit_message_caption(
                chat_id=prompt_chat_id,
                message_id=prompt_message_id,
                caption=text_val,
                reply_markup=get_ticket_cancel_keyboard(db_user.language),
                parse_mode=None,
            )
        else:
            await message.bot.edit_message_text(
                chat_id=prompt_chat_id,
                message_id=prompt_message_id,
                text=text_val,
                reply_markup=get_ticket_cancel_keyboard(db_user.language),
            )
    else:
        await message.answer(
            texts.t("TICKET_MESSAGE_INPUT", "Describe your problem (up to 500 characters) or send a photo with caption:"),
            reply_markup=get_ticket_cancel_keyboard(db_user.language)
        )
    
    await state.set_state(TicketStates.waiting_for_message)


async def handle_ticket_message_input(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    # Check that user is in correct state
    current_state = await state.get_state()
    if current_state != TicketStates.waiting_for_message:
        return
    
    # Anti-spam protection: accept only first message in short window
    try:
        # Global soft suppressor for 6 seconds after ticket creation
        try:
            from_cache = await cache.get(cache_key("suppress_user_input", db_user.id))
            if from_cache:
                asyncio.create_task(_try_delete_message_later(message.bot, message.chat.id, message.message_id, 2.0))
                return
        except Exception:
            pass
        limited = await RateLimitCache.is_rate_limited(db_user.id, "ticket_create_message", limit=1, window=2)
        if limited:
            # Delete excess parts of long message
            try:
                asyncio.create_task(_try_delete_message_later(message.bot, message.chat.id, message.message_id, 2.0))
            except Exception:
                pass
            return
    except Exception:
        pass
    try:
        data_rl = await state.get_data()
        last_ts = data_rl.get("rl_ts_create")
        now_ts = time.time()
        if last_ts and (now_ts - float(last_ts)) < 2:
            try:
                asyncio.create_task(_try_delete_message_later(message.bot, message.chat.id, message.message_id, 2.0))
            except Exception:
                pass
            return
        await state.update_data(rl_ts_create=now_ts)
    except Exception:
        pass

    # Handle ticket message input and create ticket
    # Photo support: if photo with caption is sent - take caption, save file_id
    message_text = (message.text or message.caption or "").strip()
    # Limit ticket description length to avoid caption/render issues
    if len(message_text) > 500:
        message_text = message_text[:500]
    media_type = None
    media_file_id = None
    media_caption = None
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
        media_caption = message.caption
    # Global block
    from app.database.crud.ticket import TicketCRUD
    blocked_until = await TicketCRUD.is_user_globally_blocked(db, db_user.id)
    if blocked_until:
        texts = get_texts(db_user.language)
        data_prompt = await state.get_data()
        prompt_chat_id = data_prompt.get("prompt_chat_id")
        prompt_message_id = data_prompt.get("prompt_message_id")
        text_msg = texts.t("USER_BLOCKED_FOREVER", "You are blocked from contacting support.") if blocked_until.year > 9999 - 1 else texts.t("USER_BLOCKED_UNTIL", "You are blocked until {time}").format(time=blocked_until.strftime('%d.%m.%Y %H:%M'))
        if prompt_chat_id and prompt_message_id:
            if settings.ENABLE_LOGO_MODE:
                await message.bot.edit_message_caption(chat_id=prompt_chat_id, message_id=prompt_message_id, caption=text_msg, parse_mode=None)
            else:
                await message.bot.edit_message_text(chat_id=prompt_chat_id, message_id=prompt_message_id, text=text_msg)
        else:
            await message.answer(text_msg)
        await state.clear()
        return

    # Delete user message after 2 seconds
    asyncio.create_task(_try_delete_message_later(message.bot, message.chat.id, message.message_id, 2.0))
    # Validate: allow empty text if photo is present
    if (not message_text or len(message_text) < 10) and not message.photo:
        texts = get_texts(db_user.language)
        data_prompt = await state.get_data()
        prompt_chat_id = data_prompt.get("prompt_chat_id")
        prompt_message_id = data_prompt.get("prompt_message_id")
        err_text = texts.t("TICKET_MESSAGE_TOO_SHORT", "Message is too short. Describe the problem in more detail or send a photo:")
        if prompt_chat_id and prompt_message_id:
            if settings.ENABLE_LOGO_MODE:
                await message.bot.edit_message_caption(chat_id=prompt_chat_id, message_id=prompt_message_id, caption=err_text, reply_markup=get_ticket_cancel_keyboard(db_user.language), parse_mode=None)
            else:
                await message.bot.edit_message_text(chat_id=prompt_chat_id, message_id=prompt_message_id, text=err_text, reply_markup=get_ticket_cancel_keyboard(db_user.language))
        else:
            await message.answer(err_text)
        return
    
    data = await state.get_data()
    title = data.get("title")
    priority = "normal"
    
    try:
        ticket = await TicketCRUD.create_ticket(
            db,
            db_user.id,
            title,
            message_text,
            priority,
            media_type=media_type,
            media_file_id=media_file_id,
            media_caption=media_caption,
        )
        # Enable temporary suppression of excess user messages (in case of long text splitting)
        try:
            await cache.set(cache_key("suppress_user_input", db_user.id), True, 6)
        except Exception:
            pass
        
        texts = get_texts(db_user.language)
        # Limit confirmation length to not exceed limits
        safe_title = title if len(title) <= 200 else (title[:197] + "...")
        creation_text = (
            texts.t("TICKET_CREATED_HEADER", "✅ <b>Ticket #{id} created</b>").format(id=ticket.id) + "\n\n"
            + texts.t("TICKET_CARD_TITLE", "📝 Title: {title}").format(title=safe_title) + "\n"
            + texts.t("TICKET_CARD_STATUS", "📊 Status: {emoji} {status}").format(emoji=ticket.status_emoji, status=texts.t('TICKET_STATUS_OPEN', 'Open')) + "\n"
            + texts.t("TICKET_CARD_CREATED", "📅 Created: {date}").format(date=ticket.created_at.strftime('%d.%m.%Y %H:%M')) + "\n"
            + (texts.t("TICKET_ATTACHMENT_PHOTO", "📎 Attachment: photo") + "\n" if media_type == 'photo' else "")
        )

        data_prompt = await state.get_data()
        prompt_chat_id = data_prompt.get("prompt_chat_id")
        prompt_message_id = data_prompt.get("prompt_message_id")
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text=texts.t("VIEW_TICKET", "👁️ View ticket"),
                callback_data=f"view_ticket_{ticket.id}"
            )],
            [types.InlineKeyboardButton(
                text=texts.t("BACK_TO_MENU", "🏠 Back to menu"),
                callback_data="back_to_menu"
            )]
        ])
        if prompt_chat_id and prompt_message_id:
            if settings.ENABLE_LOGO_MODE:
                await message.bot.edit_message_caption(
                    chat_id=prompt_chat_id,
                    message_id=prompt_message_id,
                    caption=creation_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                await message.bot.edit_message_text(
                    chat_id=prompt_chat_id,
                    message_id=prompt_message_id,
                    text=creation_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        else:
            await message.answer(creation_text, reply_markup=keyboard, parse_mode="HTML")
        
        await state.clear()
        
        # Notify admins
        await notify_admins_about_new_ticket(ticket, db)
        
    except Exception as e:
        logger.error(f"Error creating ticket: {e}")
        texts = get_texts(db_user.language)
        await message.answer(
            texts.t("TICKET_CREATE_ERROR", "❌ An error occurred while creating the ticket. Try again later.")
        )


async def show_my_tickets(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    # Determine current page
    current_page = 1
    if callback.data.startswith("my_tickets_page_"):
        try:
            current_page = int(callback.data.replace("my_tickets_page_", ""))
        except ValueError:
            current_page = 1
    
    # Pagination of open tickets from DB
    per_page = 10
    total_open = await TicketCRUD.count_user_tickets_by_statuses(db, db_user.id, [TicketStatus.OPEN.value, TicketStatus.ANSWERED.value, TicketStatus.PENDING.value])
    total_pages = max(1, (total_open + per_page - 1) // per_page)
    current_page = max(1, min(current_page, total_pages))
    offset = (current_page - 1) * per_page
    open_tickets = await TicketCRUD.get_user_tickets_by_statuses(db, db_user.id, [TicketStatus.OPEN.value, TicketStatus.ANSWERED.value, TicketStatus.PENDING.value], limit=per_page, offset=offset)

    # Check for no tickets at all (neither open nor closed)
    has_closed_any = await TicketCRUD.count_user_tickets_by_statuses(db, db_user.id, [TicketStatus.CLOSED.value]) > 0
    if not open_tickets and not has_closed_any:
        await callback.message.edit_text(
            texts.t("NO_TICKETS", "You have no tickets yet."),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=texts.t("CREATE_TICKET_BUTTON", "🎫 Create ticket"),
                    callback_data="create_ticket"
                )],
                [types.InlineKeyboardButton(
                    text=texts.t("VIEW_CLOSED_TICKETS", "🟢 Closed tickets"),
                    callback_data="my_tickets_closed"
                )],
                [types.InlineKeyboardButton(
                    text=texts.BACK,
                    callback_data="menu_support"
                )]
            ])
        )
        await callback.answer()
        return
    
    # Open tickets with pagination (DB)
    open_data = [{'id': t.id, 'title': t.title, 'status_emoji': t.status_emoji} for t in open_tickets]
    keyboard = get_my_tickets_keyboard(open_data, current_page=current_page, total_pages=total_pages, language=db_user.language, page_prefix="my_tickets_page_")
    # Add button to navigate to closed tickets
    keyboard.inline_keyboard.insert(0, [types.InlineKeyboardButton(text=texts.t("VIEW_CLOSED_TICKETS", "🟢 Closed tickets"), callback_data="my_tickets_closed")])
    # Always use photo render with logo (utility will fallback if necessary)
    await edit_or_answer_photo(
        callback=callback,
        caption=texts.t("MY_TICKETS_TITLE", "📋 Your tickets:"),
        keyboard=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


async def show_my_tickets_closed(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    # Pagination of closed tickets
    current_page = 1
    data_str = callback.data
    if data_str.startswith("my_tickets_closed_page_"):
        try:
            current_page = int(data_str.replace("my_tickets_closed_page_", ""))
        except ValueError:
            current_page = 1

    per_page = 10
    total_closed = await TicketCRUD.count_user_tickets_by_statuses(db, db_user.id, [TicketStatus.CLOSED.value])
    if total_closed == 0:
        await callback.message.edit_text(
            texts.t("NO_CLOSED_TICKETS", "No closed tickets yet."),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("BACK_TO_OPEN_TICKETS", "🔴 Open tickets"), callback_data="my_tickets")],
                [types.InlineKeyboardButton(text=texts.BACK, callback_data="menu_support")]
            ])
        )
        await callback.answer()
        return
    total_pages = max(1, (total_closed + per_page - 1) // per_page)
    current_page = max(1, min(current_page, total_pages))
    offset = (current_page - 1) * per_page
    tickets = await TicketCRUD.get_user_tickets_by_statuses(db, db_user.id, [TicketStatus.CLOSED.value], limit=per_page, offset=offset)
    data = [{'id': t.id, 'title': t.title, 'status_emoji': t.status_emoji} for t in tickets]
    kb = get_my_tickets_keyboard(data, current_page=current_page, total_pages=total_pages, language=db_user.language, page_prefix="my_tickets_closed_page_")
    kb.inline_keyboard.insert(0, [types.InlineKeyboardButton(text=texts.t("BACK_TO_OPEN_TICKETS", "🔴 Open tickets"), callback_data="my_tickets")])
    await edit_or_answer_photo(
        callback=callback,
        caption=texts.t("CLOSED_TICKETS_TITLE", "🟢 Closed tickets:"),
        keyboard=kb,
        parse_mode="HTML",
    )
    await callback.answer()


def _split_text_into_pages(header: str, message_blocks: list[str], max_len: int = 3500) -> list[str]:
    pages: list[str] = []
    current = header
    for block in message_blocks:
        if len(current) + len(block) > max_len:
            pages.append(current)
            current = header + block
        else:
            current += block
    if current.strip():
        pages.append(current)
    return pages if pages else [header]


async def view_ticket(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Show ticket details with pagination"""
    data_str = callback.data
    page = 1
    ticket_id = None
    if data_str.startswith("ticket_view_page_"):
        # format: ticket_view_page_{ticket_id}_{page}
        try:
            _, _, _, tid, p = data_str.split("_")
            ticket_id = int(tid)
            page = max(1, int(p))
        except Exception:
            pass
    if ticket_id is None:
        ticket_id = int(data_str.replace("view_ticket_", ""))
    
    ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=True)
    
    if not ticket or ticket.user_id != db_user.id:
        texts = get_texts(db_user.language)
        await callback.answer(
            texts.t("TICKET_NOT_FOUND", "Ticket not found."),
            show_alert=True
        )
        return
    
    texts = get_texts(db_user.language)
    
    # Build ticket text
    status_text = {
        TicketStatus.OPEN.value: texts.t("TICKET_STATUS_OPEN", "Open"),
        TicketStatus.ANSWERED.value: texts.t("TICKET_STATUS_ANSWERED", "Answered"),
        TicketStatus.CLOSED.value: texts.t("TICKET_STATUS_CLOSED", "Closed"),
        TicketStatus.PENDING.value: texts.t("TICKET_STATUS_PENDING", "Pending")
    }.get(ticket.status, ticket.status)
    
    header = (
        texts.t("TICKET_CARD_ID", "🎫 Ticket #{id}").format(id=ticket.id) + "\n\n"
        + texts.t("TICKET_CARD_TITLE", "📝 Title: {title}").format(title=ticket.title) + "\n"
        + texts.t("TICKET_CARD_STATUS", "📊 Status: {emoji} {status}").format(emoji=ticket.status_emoji, status=status_text) + "\n"
        + texts.t("TICKET_CARD_CREATED", "📅 Created: {date}").format(date=ticket.created_at.strftime('%d.%m.%Y %H:%M')) + "\n\n"
    )
    message_blocks: list[str] = []
    if ticket.messages:
        message_blocks.append(texts.t("TICKET_MESSAGES_COUNT", "💬 Messages ({count}):").format(count=len(ticket.messages)) + "\n\n")
        for msg in ticket.messages:
            sender = texts.t("TICKET_SENDER_YOU", "👤 You") if msg.is_user_message else texts.t("TICKET_SENDER_SUPPORT", "🛠️ Support")
            block = (
                f"{sender} ({msg.created_at.strftime('%d.%m %H:%M')}):\n"
                f"{msg.message_text}\n\n"
            )
            if getattr(msg, "has_media", False) and getattr(msg, "media_type", None) == "photo":
                block += texts.t("TICKET_ATTACHMENT_PHOTO", "📎 Attachment: photo") + "\n\n"
            message_blocks.append(block)
    pages = _split_text_into_pages(header, message_blocks, max_len=3500)
    total_pages = len(pages)
    if page > total_pages:
        page = total_pages
    
    keyboard = get_ticket_view_keyboard(
        ticket_id,
        ticket.is_closed,
        db_user.language,
    )
    # If there are photo attachments - add button to view them
    has_photos = any(getattr(m, "has_media", False) and getattr(m, "media_type", None) == "photo" for m in ticket.messages or [])
    if has_photos:
        try:
            keyboard.inline_keyboard.insert(0, [types.InlineKeyboardButton(text=texts.t("TICKET_ATTACHMENTS", "📎 Attachments"), callback_data=f"ticket_attachments_{ticket_id}")])
        except Exception:
            pass
    # Pagination
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"ticket_view_page_{ticket_id}_{page-1}"))
        nav_row.append(types.InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_row.append(types.InlineKeyboardButton(text="➡️", callback_data=f"ticket_view_page_{ticket_id}_{page+1}"))
        try:
            keyboard.inline_keyboard.insert(0, nav_row)
        except Exception:
            pass
    # Show as text (to not exceed caption limit)
    page_text = pages[page-1]
    try:
        await callback.message.edit_text(page_text, reply_markup=keyboard)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(page_text, reply_markup=keyboard)
    await callback.answer()


async def send_ticket_attachments(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    try:
        await callback.answer(texts.t("SENDING_ATTACHMENTS", "📎 Sending attachments..."))
    except Exception:
        pass
    try:
        ticket_id = int(callback.data.replace("ticket_attachments_", ""))
    except ValueError:
        await callback.answer(texts.t("TICKET_NOT_FOUND", "Ticket not found."), show_alert=True)
        return

    ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=True)
    if not ticket or ticket.user_id != db_user.id:
        await callback.answer(texts.t("TICKET_NOT_FOUND", "Ticket not found."), show_alert=True)
        return

    photos = [m.media_file_id for m in ticket.messages if getattr(m, "has_media", False) and getattr(m, "media_type", None) == "photo" and m.media_file_id]
    if not photos:
        await callback.answer(texts.t("NO_ATTACHMENTS", "No attachments."), show_alert=True)
        return

    # Telegram limits media group to 10 elements. Send in chunks.
    from aiogram.types import InputMediaPhoto
    chunks = [photos[i:i+10] for i in range(0, len(photos), 10)]
    last_group_message = None
    for chunk in chunks:
        media = [InputMediaPhoto(media=pid) for pid in chunk]
        try:
            messages = await callback.message.bot.send_media_group(chat_id=callback.from_user.id, media=media)
            if messages:
                last_group_message = messages[-1]
        except Exception:
            pass
    if last_group_message:
        try:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=texts.t("DELETE_MESSAGE", "🗑 Delete"), callback_data=f"user_delete_message_{last_group_message.message_id}")]])
            await callback.message.bot.send_message(chat_id=callback.from_user.id, text=texts.t("ATTACHMENTS_SENT", "Attachments sent."), reply_markup=kb)
        except Exception:
            pass
    else:
        try:
            await callback.answer(texts.t("ATTACHMENTS_SENT", "Attachments sent."))
        except Exception:
            pass


async def user_delete_message(
    callback: types.CallbackQuery
):
    try:
        msg_id = int(callback.data.replace("user_delete_message_", ""))
    except ValueError:
        await callback.answer("❌")
        return
    try:
        await callback.message.bot.delete_message(chat_id=callback.from_user.id, message_id=msg_id)
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("✅")


async def _try_delete_message_later(bot: Bot, chat_id: int, message_id: int, delay_seconds: float = 1.0):
    try:
        await asyncio.sleep(delay_seconds)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        # In private chats, deleting user messages may not be available - ignore errors
        pass


async def reply_to_ticket(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User
):
    """Start reply to ticket"""
    ticket_id = int(callback.data.replace("reply_ticket_", ""))
    
    await state.update_data(ticket_id=ticket_id)
    
    texts = get_texts(db_user.language)
    
    await callback.message.edit_text(
        texts.t("TICKET_REPLY_INPUT", "Enter your reply:"),
        reply_markup=get_ticket_reply_cancel_keyboard(db_user.language)
    )
    
    await state.set_state(TicketStates.waiting_for_reply)
    await callback.answer()


async def handle_ticket_reply(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    # Check that user is in correct state
    current_state = await state.get_state()
    if current_state != TicketStates.waiting_for_reply:
        return
    
    # Anti-spam: accept only first message per ticket in short window
    try:
        data_rl = await state.get_data()
        rl_ticket_id = data_rl.get("ticket_id") or "reply"
        limited = await RateLimitCache.is_rate_limited(db_user.id, f"ticket_reply_{rl_ticket_id}", limit=1, window=2)
        if limited:
            try:
                asyncio.create_task(_try_delete_message_later(message.bot, message.chat.id, message.message_id, 2.0))
            except Exception:
                pass
            return
    except Exception:
        pass
    try:
        data_rl = await state.get_data()
        last_ts = data_rl.get("rl_ts_reply")
        now_ts = time.time()
        if last_ts and (now_ts - float(last_ts)) < 2:
            try:
                asyncio.create_task(_try_delete_message_later(message.bot, message.chat.id, message.message_id, 2.0))
            except Exception:
                pass
            return
        await state.update_data(rl_ts_reply=now_ts)
    except Exception:
        pass

    # Handle ticket reply
    # Photo support for user reply
    # User reply limit 500 characters
    reply_text = (message.text or message.caption or "").strip()
    # Stricter cut to 400 to account for formatting/emojis
    if len(reply_text) > 400:
        reply_text = reply_text[:400]
    media_type = None
    media_file_id = None
    media_caption = None
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
        media_caption = message.caption
    
    if len(reply_text) < 5:
        texts = get_texts(db_user.language)
        await message.answer(
            texts.t("TICKET_REPLY_TOO_SHORT", "Reply must contain at least 5 characters. Try again:")
        )
        return
    
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    
    if not ticket_id:
        texts = get_texts(db_user.language)
        await message.answer(
            texts.t("TICKET_REPLY_ERROR", "Error: ticket ID not found.")
        )
        await state.clear()
        return
    
    try:
        # Check that ticket belongs to user and is not closed
        ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=False)
        if not ticket or ticket.user_id != db_user.id:
            texts = get_texts(db_user.language)
            await message.answer(
                texts.t("TICKET_NOT_FOUND", "Ticket not found.")
            )
            await state.clear()
            return
        if ticket.status == TicketStatus.CLOSED.value:
            texts = get_texts(db_user.language)
            await message.answer(
                texts.t("TICKET_CLOSED", "✅ Ticket closed."),
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text=texts.t("CLOSE_NOTIFICATION", "❌ Close notification"), callback_data=f"close_ticket_notification_{ticket.id}")]]
                )
            )
            await state.clear()
            return
        
        # Block adding message if ticket is closed or blocked by admin
        if ticket.status == TicketStatus.CLOSED.value or ticket.is_user_reply_blocked:
            texts = get_texts(db_user.language)
            await message.answer(
                texts.t("TICKET_CLOSED_NO_REPLY", "❌ Ticket is closed, cannot reply."),
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text=texts.t("CLOSE_NOTIFICATION", "❌ Close notification"), callback_data=f"close_ticket_notification_{ticket.id}")]]
                )
            )
            await state.clear()
            return

        # Add message to ticket
        await TicketMessageCRUD.add_message(
            db,
            ticket_id,
            db_user.id,
            reply_text,
            is_from_admin=False,
            media_type=media_type,
            media_file_id=media_file_id,
            media_caption=media_caption,
        )
        
        texts = get_texts(db_user.language)
        
        await message.answer(
            texts.t("TICKET_REPLY_SENT", "✅ Your reply has been sent!"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=texts.t("VIEW_TICKET", "👁️ View ticket"),
                    callback_data=f"view_ticket_{ticket_id}"
                )],
                [types.InlineKeyboardButton(
                    text=texts.t("BACK_TO_MENU", "🏠 Back to menu"),
                    callback_data="back_to_menu"
                )]
            ])
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error adding ticket reply: {e}")
        texts = get_texts(db_user.language)
        await message.answer(
            texts.t("TICKET_REPLY_ERROR", "❌ An error occurred while sending reply. Try again later.")
        )


async def close_ticket(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Close ticket"""
    ticket_id = int(callback.data.replace("close_ticket_", ""))
    
    try:
        # Check that ticket belongs to user
        ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=False)
        if not ticket or ticket.user_id != db_user.id:
            texts = get_texts(db_user.language)
            await callback.answer(
                texts.t("TICKET_NOT_FOUND", "Ticket not found."),
                show_alert=True
            )
            return
        
        # Closing is not blocked if reply is blocked (not required). Close ticket
        success = await TicketCRUD.close_ticket(db, ticket_id)
        
        if success:
            texts = get_texts(db_user.language)
            await callback.answer(
                texts.t("TICKET_CLOSED", "✅ Ticket closed."),
                show_alert=True
            )
            
            # Update inline keyboard of current message (remove buttons)
            await callback.message.edit_reply_markup(
                reply_markup=get_ticket_view_keyboard(ticket_id, True, db_user.language)
            )
        else:
            texts = get_texts(db_user.language)
            await callback.answer(
                texts.t("TICKET_CLOSE_ERROR", "❌ Error closing ticket."),
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"Error closing ticket: {e}")
        texts = get_texts(db_user.language)
        await callback.answer(
            texts.t("TICKET_CLOSE_ERROR", "❌ Error closing ticket."),
            show_alert=True
        )


async def cancel_ticket_creation(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User
):
    """Cancel ticket creation"""
    await state.clear()
    
    texts = get_texts(db_user.language)
    
    await callback.message.edit_text(
        texts.t("TICKET_CREATION_CANCELLED", "Ticket creation cancelled."),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text=texts.t("BACK_TO_SUPPORT", "⬅️ Back to support"),
                callback_data="menu_support"
            )]
        ])
    )
    await callback.answer()


async def cancel_ticket_reply(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User
):
    """Cancel ticket reply"""
    await state.clear()
    
    texts = get_texts(db_user.language)
    
    await callback.message.edit_text(
        texts.t("TICKET_REPLY_CANCELLED", "Reply cancelled."),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text=texts.t("BACK_TO_TICKETS", "⬅️ Back to tickets"),
                callback_data="my_tickets"
            )]
        ])
    )
    await callback.answer()


async def close_ticket_notification(
    callback: types.CallbackQuery,
    db_user: User
):
    """Close ticket notification"""
    texts = get_texts(db_user.language)
    
    await callback.message.delete()
    await callback.answer(texts.t("NOTIFICATION_CLOSED", "Notification closed."))


async def notify_admins_about_new_ticket(ticket: Ticket, db: AsyncSession):
    """Notify admins about new ticket"""
    try:
        from app.config import settings
        if not settings.is_admin_notifications_enabled():
            logger.info(f"Admin notifications disabled. Ticket #{ticket.id} created by user {ticket.user_id}")
            return

        # Get user language for localizing headers in notification
        # and build convenient notification text for admins
        user_texts = get_texts(settings.DEFAULT_LANGUAGE)
        title = (ticket.title or '').strip()
        if len(title) > 60:
            title = title[:57] + "..."

        # Load user to display real Telegram ID and username
        try:
            user = await get_user_by_id(db, ticket.user_id)
        except Exception:
            user = None
        full_name = user.full_name if user else "Unknown"
        telegram_id_display = user.telegram_id if user else "—"
        username_missing = user_texts.t("USERNAME_MISSING", "none")
        username_display = (user.username or username_missing) if user else username_missing

        notification_text = (
            user_texts.t("ADMIN_NEW_TICKET_TITLE", "🎫 <b>NEW TICKET</b>") + "\n\n"
            + user_texts.t("ADMIN_NEW_TICKET_ID", "🆔 <b>ID:</b> {id}").format(id=f"<code>{ticket.id}</code>") + "\n"
            + user_texts.t("ADMIN_NEW_TICKET_USER", "👤 <b>User:</b> {name}").format(name=full_name) + "\n"
            + user_texts.t("ADMIN_NEW_TICKET_TELEGRAM_ID", "🆔 <b>Telegram ID:</b> {id}").format(id=f"<code>{telegram_id_display}</code>") + "\n"
            + user_texts.t("ADMIN_NEW_TICKET_USERNAME", "📱 <b>Username:</b> @{username}").format(username=username_display) + "\n"
            + user_texts.t("ADMIN_NEW_TICKET_SUBJECT", "📝 <b>Subject:</b> {title}").format(title=title or "—") + "\n"
            + user_texts.t("ADMIN_NEW_TICKET_CREATED", "📅 <b>Created:</b> {date}").format(date=ticket.created_at.strftime('%d.%m.%Y %H:%M')) + "\n"
        )

        # Keyboard with quick actions for admins in topic
        # Send through common admin notification service (supports topics)
        # bot is available from Dispatcher in middlewares; safer to get from already used context
        # Here we use lazy import from maintenance_service where bot is stored
        from app.services.maintenance_service import maintenance_service
        bot = maintenance_service._bot or None
        if bot is None:
            logger.warning("Bot instance is not available for admin notifications")
            return

        service = AdminNotificationService(bot)
        await service.send_ticket_event_notification(notification_text, None)
    except Exception as e:
        logger.error(f"Error notifying admins about new ticket: {e}")


def register_handlers(dp: Dispatcher):
    """Register ticket handlers"""
    
    # Ticket creation (now without priority)
    dp.callback_query.register(
        show_ticket_priority_selection,
        F.data == "create_ticket"
    )
    
    dp.message.register(
        handle_ticket_title_input,
        TicketStates.waiting_for_title
    )
    
    dp.message.register(
        handle_ticket_message_input,
        TicketStates.waiting_for_message
    )
    
    # View tickets
    dp.callback_query.register(
        show_my_tickets,
        F.data == "my_tickets"
    )
    dp.callback_query.register(
        show_my_tickets_closed,
        F.data == "my_tickets_closed"
    )
    dp.callback_query.register(
        show_my_tickets_closed,
        F.data.startswith("my_tickets_closed_page_")
    )
    
    dp.callback_query.register(
        view_ticket,
        F.data.startswith("view_ticket_") | F.data.startswith("ticket_view_page_")
    )

    # User attachments
    dp.callback_query.register(
        send_ticket_attachments,
        F.data.startswith("ticket_attachments_")
    )

    dp.callback_query.register(
        user_delete_message,
        F.data.startswith("user_delete_message_")
    )
    
    # Ticket replies
    dp.callback_query.register(
        reply_to_ticket,
        F.data.startswith("reply_ticket_")
    )
    
    dp.message.register(
        handle_ticket_reply,
        TicketStates.waiting_for_reply
    )
    
    # Close tickets
    dp.callback_query.register(
        close_ticket,
        F.data.regexp(r"^close_ticket_\d+$")
    )
    
    # Cancel operations
    dp.callback_query.register(
        cancel_ticket_creation,
        F.data == "cancel_ticket_creation"
    )
    
    dp.callback_query.register(
        cancel_ticket_reply,
        F.data == "cancel_ticket_reply"
    )
    
    # Ticket pagination
    dp.callback_query.register(
        show_my_tickets,
        F.data.startswith("my_tickets_page_")
    )
    
    # Close notifications
    dp.callback_query.register(
        close_ticket_notification,
        F.data.startswith("close_ticket_notification_")
    )
