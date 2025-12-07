import logging
from typing import List, Dict, Any, Optional
from aiogram import Dispatcher, types, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from datetime import datetime, timedelta
import time
import html

from app.database.models import User, Ticket, TicketStatus
from app.database.crud.ticket import TicketCRUD, TicketMessageCRUD
from app.states import TicketStates, AdminTicketStates
from app.keyboards.inline import (
    get_admin_tickets_keyboard,
    get_admin_ticket_view_keyboard,
    get_admin_ticket_reply_cancel_keyboard
)
from app.localization.texts import get_texts
from app.utils.pagination import paginate_list, get_pagination_info
from app.services.admin_notification_service import AdminNotificationService
from app.services.support_settings_service import SupportSettingsService
from app.config import settings
from app.utils.cache import RateLimitCache

logger = logging.getLogger(__name__)


 


async def show_admin_tickets(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Show all tickets for admins"""
    # permission gate: admin or active moderator only
    if not (settings.is_admin(callback.from_user.id) or SupportSettingsService.is_moderator(callback.from_user.id)):
        texts = get_texts(db_user.language)
        await callback.answer(texts.ACCESS_DENIED, show_alert=True)
        return
    texts = get_texts(db_user.language)
    
    # Determine current page and scope
    current_page = 1
    scope = "open"
    data_str = callback.data
    if data_str == "admin_tickets_scope_open":
        scope = "open"
    elif data_str == "admin_tickets_scope_closed":
        scope = "closed"
    elif data_str.startswith("admin_tickets_page_"):
        try:
            parts = data_str.split("_")
            # format: admin_tickets_page_{scope}_{page}
            if len(parts) >= 5:
                scope = parts[3]
                current_page = int(parts[4])
            else:
                current_page = int(data_str.replace("admin_tickets_page_", ""))
        except ValueError:
            current_page = 1
    statuses = [TicketStatus.OPEN.value, TicketStatus.ANSWERED.value] if scope == "open" else [TicketStatus.CLOSED.value]
    page_size = 10
    # total count for proper pagination
    total_count = await TicketCRUD.count_tickets_by_statuses(db, statuses)
    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count > 0 else 1
    if current_page < 1:
        current_page = 1
    if current_page > total_pages:
        current_page = total_pages
    offset = (current_page - 1) * page_size
    tickets = await TicketCRUD.get_tickets_by_statuses(db, statuses=statuses, limit=page_size, offset=offset)
    
    # Show section switchers even if no tickets
    
    # Build data for keyboard
    ticket_data = []
    for ticket in tickets:
        user_name = ticket.user.full_name if ticket.user else "Unknown"
        username = ticket.user.username if ticket.user else None
        telegram_id = ticket.user.telegram_id if ticket.user else None
        ticket_data.append({
            'id': ticket.id,
            'title': ticket.title,
            'status_emoji': ticket.status_emoji,
            'priority_emoji': ticket.priority_emoji,
            'user_name': user_name,
            'username': username,
            'telegram_id': telegram_id,
            'is_closed': ticket.is_closed,
            'locked_emoji': ("🔒" if ticket.is_user_reply_blocked else "")
        })
    
    # Total pages already calculated above
    header_text = (
        texts.t("ADMIN_TICKETS_TITLE_OPEN", "🎫 Open support tickets:")
        if scope == "open"
        else texts.t("ADMIN_TICKETS_TITLE_CLOSED", "🎫 Closed support tickets:")
    )
    # Determine proper back target for moderators
    back_cb = "admin_submenu_support"
    try:
        if not settings.is_admin(callback.from_user.id) and SupportSettingsService.is_moderator(callback.from_user.id):
            back_cb = "moderator_panel"
    except Exception:
        pass

    keyboard = get_admin_tickets_keyboard(
        ticket_data,
        current_page=current_page,
        total_pages=total_pages,
        language=db_user.language,
        scope=scope,
        back_callback=back_cb,
    )
    from app.utils.photo_message import edit_or_answer_photo
    await edit_or_answer_photo(
        callback=callback,
        caption=header_text,
        keyboard=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


async def view_admin_ticket(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: Optional[FSMContext] = None,
    ticket_id: Optional[int] = None
):
    """Show ticket details for admin"""
    if not (settings.is_admin(callback.from_user.id) or SupportSettingsService.is_moderator(callback.from_user.id)):
        texts = get_texts(db_user.language)
        await callback.answer(texts.ACCESS_DENIED, show_alert=True)
        return
    
    if ticket_id is None:
        try:
            ticket_id = int((callback.data or "").split("_")[-1])
        except (ValueError, AttributeError):
            texts = get_texts(db_user.language)
            await callback.answer(
                texts.t("TICKET_NOT_FOUND", "Ticket not found."),
                show_alert=True
            )
            return

    if state is None:
        state = FSMContext(callback.bot, callback.from_user.id)
    
    ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=True, load_user=True)
    
    if not ticket:
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
    
    user_name = ticket.user.full_name if ticket.user else "Unknown"
    telegram_id_display = ticket.user.telegram_id if ticket.user else "—"
    username_value = ticket.user.username if ticket.user else None

    ticket_text = texts.t("TICKET_CARD_ID", "🎫 Ticket #{id}").format(id=ticket.id) + "\n\n"
    ticket_text += texts.t("TICKET_CARD_USER", "👤 User: {name}").format(name=user_name) + "\n"
    ticket_text += texts.t("TICKET_CARD_TELEGRAM_ID", "🆔 Telegram ID: {id}").format(id=f"<code>{telegram_id_display}</code>") + "\n"
    if username_value:
        safe_username = html.escape(username_value)
        ticket_text += texts.t("TICKET_CARD_USERNAME", "📱 Username: @{username}").format(username=safe_username) + "\n"
        pm_link = f"<a href=\"tg://resolve?domain={safe_username}\">tg://resolve?domain={safe_username}</a>"
        ticket_text += texts.t("TICKET_CARD_PM_LINK", "🔗 PM: {link}").format(link=pm_link) + "\n"
    else:
        ticket_text += texts.t("TICKET_CARD_USERNAME_MISSING", "📱 Username: none") + "\n"
        if ticket.user and ticket.user.telegram_id:
            chat_link = f"tg://user?id={int(ticket.user.telegram_id)}"
            chat_link_html = f"<a href=\"{chat_link}\">{chat_link}</a>"
            ticket_text += texts.t("TICKET_CARD_CHAT_BY_ID", "🔗 Chat by ID: {link}").format(link=chat_link_html) + "\n"
    ticket_text += "\n"
    ticket_text += texts.t("TICKET_CARD_TITLE", "📝 Title: {title}").format(title=ticket.title) + "\n"
    ticket_text += texts.t("TICKET_CARD_STATUS", "📊 Status: {emoji} {status}").format(emoji=ticket.status_emoji, status=status_text) + "\n"
    ticket_text += texts.t("TICKET_CARD_CREATED", "📅 Created: {date}").format(date=ticket.created_at.strftime('%d.%m.%Y %H:%M')) + "\n"
    ticket_text += texts.t("TICKET_CARD_UPDATED", "🔄 Updated: {date}").format(date=ticket.updated_at.strftime('%d.%m.%Y %H:%M')) + "\n\n"
    
    if ticket.is_user_reply_blocked:
        if ticket.user_reply_block_permanent:
            ticket_text += texts.t("TICKET_USER_BLOCKED_PERM", "🚫 User is permanently blocked from replying to this ticket") + "\n"
        elif ticket.user_reply_block_until:
            ticket_text += texts.t("TICKET_USER_BLOCKED_UNTIL", "⏳ Blocked until: {date}").format(date=ticket.user_reply_block_until.strftime('%d.%m.%Y %H:%M')) + "\n"
    
    if ticket.messages:
        ticket_text += texts.t("TICKET_MESSAGES_COUNT", "💬 Messages ({count}):").format(count=len(ticket.messages)) + "\n\n"
        
        for msg in ticket.messages:
            sender = texts.t("TICKET_SENDER_USER", "👤 User") if msg.is_user_message else texts.t("TICKET_SENDER_SUPPORT", "🛠️ Support")
            ticket_text += f"{sender} ({msg.created_at.strftime('%d.%m %H:%M')}):\n"
            ticket_text += f"{msg.message_text}\n\n"
            if getattr(msg, "has_media", False) and getattr(msg, "media_type", None) == "photo":
                ticket_text += texts.t("TICKET_ATTACHMENT_PHOTO", "📎 Attachment: photo") + "\n\n"
    
    # Add "Attachments" button if there are photos
    has_photos = any(getattr(m, "has_media", False) and getattr(m, "media_type", None) == "photo" for m in ticket.messages or [])
    keyboard = get_admin_ticket_view_keyboard(
        ticket_id,
        ticket.is_closed,
        db_user.language,
        is_user_blocked=ticket.is_user_reply_blocked
    )
    # Button to open user profile in admin panel
    try:
        if ticket.user:
            admin_profile_btn = types.InlineKeyboardButton(
                text=texts.t("BTN_TO_USER", "👤 To user"),
                callback_data=f"admin_user_manage_{ticket.user.id}_from_ticket_{ticket.id}"
            )
            keyboard.inline_keyboard.insert(0, [admin_profile_btn])
    except Exception:
        pass
    # PM and profile buttons
    try:
        if ticket.user and ticket.user.telegram_id and ticket.user.username:
            safe_username = html.escape(ticket.user.username)
            buttons_row = []
            pm_url = f"tg://resolve?domain={safe_username}"
            buttons_row.append(types.InlineKeyboardButton(text=texts.t("BTN_WRITE_PM", "✉ Write PM"), url=pm_url))
            profile_url = f"tg://user?id={ticket.user.telegram_id}"
            buttons_row.append(types.InlineKeyboardButton(text=texts.t("BTN_PROFILE", "👤 Profile"), url=profile_url))
            if buttons_row:
                keyboard.inline_keyboard.insert(0, buttons_row)
    except Exception:
        pass
    if has_photos:
        try:
            keyboard.inline_keyboard.insert(0, [types.InlineKeyboardButton(text=texts.t("TICKET_ATTACHMENTS", "📎 Attachments"), callback_data=f"admin_ticket_attachments_{ticket_id}")])
        except Exception:
            pass

    # Render via photo utility (with logo), has text fallbacks inside
    from app.utils.photo_message import edit_or_answer_photo
    await edit_or_answer_photo(
        callback=callback,
        caption=ticket_text,
        keyboard=keyboard,
        parse_mode="HTML",
    )
    # Save id for further actions (reply/statuses)
    if state is not None:
        try:
            await state.update_data(ticket_id=ticket_id)
        except Exception:
            pass
    await callback.answer()


async def reply_to_admin_ticket(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User
):
    """Start reply to ticket from admin"""
    if not (settings.is_admin(callback.from_user.id) or SupportSettingsService.is_moderator(callback.from_user.id)):
        texts = get_texts(db_user.language)
        await callback.answer(texts.ACCESS_DENIED, show_alert=True)
        return
    ticket_id = int(callback.data.replace("admin_reply_ticket_", ""))
    
    await state.update_data(ticket_id=ticket_id, reply_mode=True)
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_TICKET_REPLY_INPUT", "Enter support reply:"),
        reply_markup=get_admin_ticket_reply_cancel_keyboard(db_user.language)
    )

    await state.set_state(AdminTicketStates.waiting_for_reply)
    await callback.answer()


async def handle_admin_ticket_reply(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    if not (settings.is_admin(message.from_user.id) or SupportSettingsService.is_moderator(message.from_user.id)):
        texts = get_texts(db_user.language)
        await message.answer(texts.ACCESS_DENIED)
        await state.clear()
        return
    # Check that user is in correct state
    current_state = await state.get_state()
    if current_state != AdminTicketStates.waiting_for_reply:
        return

    # Anti-spam: one message per short window per ticket
    try:
        data_rl = await state.get_data()
        rl_ticket_id = data_rl.get("ticket_id") or "admin_reply"
        limited = await RateLimitCache.is_rate_limited(db_user.id, f"admin_ticket_reply_{rl_ticket_id}", limit=1, window=2)
        if limited:
            return
    except Exception:
        pass
    try:
        data_rl = await state.get_data()
        last_ts = data_rl.get("admin_rl_ts_reply")
        now_ts = time.time()
        if last_ts and (now_ts - float(last_ts)) < 2:
            return
        await state.update_data(admin_rl_ts_reply=now_ts)
    except Exception:
        pass

    # Handle admin ticket reply
    # Support for photo attachments in admin reply
    reply_text = (message.text or message.caption or "").strip()
    if len(reply_text) > 400:
        reply_text = reply_text[:400]
    media_type = None
    media_file_id = None
    media_caption = None
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
        media_caption = message.caption

    if len(reply_text) < 1 and not media_file_id:
        texts = get_texts(db_user.language)
        await message.answer(
            texts.t("TICKET_REPLY_TOO_SHORT", "Reply must contain at least 5 characters. Try again:")
        )
        return

    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    try:
        ticket_id = int(ticket_id) if ticket_id is not None else None
    except (TypeError, ValueError):
        ticket_id = None

    if not ticket_id:
        texts = get_texts(db_user.language)
        await message.answer(
            texts.t("TICKET_REPLY_ERROR", "Error: ticket ID not found.")
        )
        await state.clear()
        return

    try:
        # If this is block duration input mode
        if not data.get("reply_mode"):
            try:
                minutes = int(reply_text)
                minutes = max(1, min(60*24*365, minutes))
            except ValueError:
                texts = get_texts(db_user.language)
                await message.answer(texts.t("ENTER_INTEGER_MINUTES", "❌ Enter a whole number of minutes"))
                return
            until = datetime.utcnow() + timedelta(minutes=minutes)
            ok = await TicketCRUD.set_user_reply_block(db, ticket_id, permanent=False, until=until)
            texts = get_texts(db_user.language)
            if ok:
                await message.answer(texts.t("USER_BLOCKED_FOR_MINUTES", "✅ User blocked for {minutes} minutes").format(minutes=minutes))
            else:
                await message.answer(texts.t("BLOCK_ERROR", "❌ Block error"))
            await state.clear()
            return

        # Normal admin reply mode
        ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=False, load_user=True)
        if not ticket:
            texts = get_texts(db_user.language)
            await message.answer(
                texts.t("TICKET_NOT_FOUND", "Ticket not found.")
            )
            await state.clear()
            return

        # Add message from admin (inside add_message status becomes ANSWERED)
        await TicketMessageCRUD.add_message(
            db,
            ticket_id,
            db_user.id,
            reply_text,
            is_from_admin=True,
            media_type=media_type,
            media_file_id=media_file_id,
            media_caption=media_caption,
        )

        texts = get_texts(db_user.language)

        await message.answer(
            texts.t("ADMIN_TICKET_REPLY_SENT", "✅ Reply sent!"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=texts.t("VIEW_TICKET", "👁️ View ticket"),
                    callback_data=f"admin_view_ticket_{ticket_id}"
                )],
                [types.InlineKeyboardButton(
                    text=texts.t("BACK_TO_TICKETS", "⬅️ Back to tickets"),
                    callback_data="admin_tickets"
                )]
            ])
        )

        await state.clear()

        # Notify user about new reply
        await notify_user_about_ticket_reply(message.bot, ticket, reply_text, db)
        # Admin notifications for ticket replies are disabled by request

    except Exception as e:
        logger.error(f"Error adding admin ticket reply: {e}")
        texts = get_texts(db_user.language)
        await message.answer(
            texts.t("TICKET_REPLY_ERROR", "❌ An error occurred while sending reply. Try again later.")
        )


async def mark_ticket_as_answered(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    """Mark ticket as answered"""
    ticket_id = int(callback.data.replace("admin_mark_answered_", ""))
    
    try:
        success = await TicketCRUD.update_ticket_status(
            db, ticket_id, TicketStatus.ANSWERED.value
        )
        
        if success:
            texts = get_texts(db_user.language)
            await callback.answer(
                texts.t("TICKET_MARKED_ANSWERED", "✅ Ticket marked as answered."),
                show_alert=True
            )
            
            # Update message
            await view_admin_ticket(callback, db_user, db, state)
        else:
            texts = get_texts(db_user.language)
            await callback.answer(
                texts.t("TICKET_UPDATE_ERROR", "❌ Error updating ticket."),
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"Error marking ticket as answered: {e}")
        texts = get_texts(db_user.language)
        await callback.answer(
            texts.t("TICKET_UPDATE_ERROR", "❌ Error updating ticket."),
            show_alert=True
        )


async def close_all_open_admin_tickets(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Close all open tickets."""
    if not (settings.is_admin(callback.from_user.id) or SupportSettingsService.is_moderator(callback.from_user.id)):
        texts = get_texts(db_user.language)
        await callback.answer(texts.ACCESS_DENIED, show_alert=True)
        return

    texts = get_texts(db_user.language)

    try:
        closed_ticket_ids = await TicketCRUD.close_all_open_tickets(db)
    except Exception as error:
        logger.error("Error closing all open tickets: %s", error)
        await callback.answer(
            texts.t("TICKET_UPDATE_ERROR", "❌ Error updating ticket."),
            show_alert=True
        )
        return

    closed_count = len(closed_ticket_ids)

    if closed_count == 0:
        await callback.answer(
            texts.t("ADMIN_CLOSE_ALL_OPEN_TICKETS_EMPTY", "ℹ️ No open tickets to close."),
            show_alert=True
        )
        return

    try:
        is_moderator = (
            not settings.is_admin(callback.from_user.id)
            and SupportSettingsService.is_moderator(callback.from_user.id)
        )
        await TicketCRUD.add_support_audit(
            db,
            actor_user_id=db_user.id if db_user else None,
            actor_telegram_id=callback.from_user.id,
            is_moderator=is_moderator,
            action="close_all_tickets",
            ticket_id=None,
            target_user_id=None,
            details={
                "count": closed_count,
                "ticket_ids": closed_ticket_ids,
            }
        )
    except Exception as audit_error:
        logger.warning("Failed to add support audit for bulk close: %s", audit_error)

    # Update tickets list
    await show_admin_tickets(callback, db_user, db)

    success_text = texts.t(
        "ADMIN_CLOSE_ALL_OPEN_TICKETS_SUCCESS",
        "✅ Closed open tickets: {count}"
    ).format(count=closed_count)

    notification_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text=texts.t("BTN_DELETE", "🗑 Delete"), callback_data="admin_support_delete_msg")]]
    )

    try:
        await callback.message.answer(success_text, reply_markup=notification_keyboard)
    except Exception:
        # If unable to send separate message, try to respond with alert
        try:
            await callback.answer(success_text, show_alert=True)
        except Exception:
            pass


async def close_admin_ticket(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Close ticket by admin"""
    if not (settings.is_admin(callback.from_user.id) or SupportSettingsService.is_moderator(callback.from_user.id)):
        texts = get_texts(db_user.language)
        await callback.answer(texts.ACCESS_DENIED, show_alert=True)
        return
    ticket_id = int(callback.data.replace("admin_close_ticket_", ""))
    
    try:
        success = await TicketCRUD.close_ticket(db, ticket_id)
        
        if success:
            # audit
            try:
                is_mod = (not settings.is_admin(callback.from_user.id) and SupportSettingsService.is_moderator(callback.from_user.id))
                # Enrich details with ticket user contacts
                details = {}
                try:
                    t = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_user=True)
                    if t and t.user:
                        details.update({
                            "target_telegram_id": t.user.telegram_id,
                            "target_username": t.user.username,
                        })
                except Exception:
                    pass
                await TicketCRUD.add_support_audit(
                    db,
                    actor_user_id=db_user.id if db_user else None,
                    actor_telegram_id=callback.from_user.id,
                    is_moderator=is_mod,
                    action="close_ticket",
                    ticket_id=ticket_id,
                    target_user_id=None,
                    details=details
                )
            except Exception:
                pass
            texts = get_texts(db_user.language)
            # Notify with deletable inline message
            try:
                await callback.message.answer(
                    texts.t("TICKET_CLOSED", "✅ Ticket closed."),
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[[types.InlineKeyboardButton(text=texts.t("BTN_DELETE", "🗑 Delete"), callback_data="admin_support_delete_msg")]]
                    )
                )
            except Exception:
                await callback.answer(texts.t("TICKET_CLOSED", "✅ Ticket closed."), show_alert=True)
            
            # Update inline keyboard in current message without action buttons
            await callback.message.edit_reply_markup(
                reply_markup=get_admin_ticket_view_keyboard(ticket_id, True, db_user.language)
            )
        else:
            texts = get_texts(db_user.language)
            await callback.answer(
                texts.t("TICKET_CLOSE_ERROR", "❌ Error closing ticket."),
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"Error closing admin ticket: {e}")
        texts = get_texts(db_user.language)
        await callback.answer(
            texts.t("TICKET_CLOSE_ERROR", "❌ Error closing ticket."),
            show_alert=True
        )


async def cancel_admin_ticket_reply(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User
):
    """Cancel admin ticket reply"""
    if not (settings.is_admin(callback.from_user.id) or SupportSettingsService.is_moderator(callback.from_user.id)):
        texts = get_texts(db_user.language)
        await callback.answer(texts.ACCESS_DENIED, show_alert=True)
        return
    await state.clear()
    
    texts = get_texts(db_user.language)
    
    await callback.message.edit_text(
        texts.t("TICKET_REPLY_CANCELLED", "Reply cancelled."),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text=texts.t("BACK_TO_TICKETS", "⬅️ Back to tickets"),
                callback_data="admin_tickets"
            )]
        ])
    )
    await callback.answer()


async def block_user_in_ticket(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    if not (settings.is_admin(callback.from_user.id) or SupportSettingsService.is_moderator(callback.from_user.id)):
        texts = get_texts(db_user.language)
        await callback.answer(texts.ACCESS_DENIED, show_alert=True)
        return
    ticket_id = int(callback.data.replace("admin_block_user_ticket_", ""))
    texts = get_texts(db_user.language)
    # Save original ticket message ids to update it after blocking without reopening
    try:
        await state.update_data(origin_chat_id=callback.message.chat.id, origin_message_id=callback.message.message_id)
    except Exception:
        pass
    await callback.message.edit_text(
        texts.t("ENTER_BLOCK_MINUTES", "Enter number of minutes to block user (e.g. 15):"),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text=texts.t("CANCEL_REPLY", "❌ Cancel input"),
                callback_data="cancel_admin_ticket_reply"
            )]
        ])
    )
    await state.update_data(ticket_id=ticket_id)
    await state.set_state(AdminTicketStates.waiting_for_block_duration)
    await callback.answer()


async def handle_admin_block_duration_input(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    # permission gate for message flow
    if not (settings.is_admin(message.from_user.id) or SupportSettingsService.is_moderator(message.from_user.id)):
        texts = get_texts(db_user.language)
        await message.answer(texts.ACCESS_DENIED)
        await state.clear()
        return
    # Check state
    current_state = await state.get_state()
    if current_state != AdminTicketStates.waiting_for_block_duration:
        return
    
    texts = get_texts(db_user.language)
    reply_text = message.text.strip()
    if len(reply_text) < 1:
        await message.answer(texts.t("ENTER_INTEGER_MINUTES", "❌ Enter a whole number of minutes"))
        return
    
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    origin_chat_id = data.get("origin_chat_id")
    origin_message_id = data.get("origin_message_id")
    try:
        minutes = int(reply_text)
        minutes = max(1, min(60*24*365, minutes))  # max 1 year
    except ValueError:
        await message.answer(texts.t("ENTER_INTEGER_MINUTES", "❌ Enter a whole number of minutes"))
        return
    
    if not ticket_id:
        await message.answer(texts.t("TICKET_REPLY_ERROR", "Error: ticket ID not found."))
        await state.clear()
        return
    
    try:
        ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=False)
        if not ticket:
            await message.answer(texts.t("TICKET_NOT_FOUND", "Ticket not found."))
            await state.clear()
            return
        
        until = datetime.utcnow() + timedelta(minutes=minutes)
        ok = await TicketCRUD.set_user_reply_block(db, ticket_id, permanent=False, until=until)
        if not ok:
            await message.answer(texts.t("BLOCK_ERROR", "❌ Block error"))
            return
        # audit
        try:
            is_mod = (not settings.is_admin(message.from_user.id) and SupportSettingsService.is_moderator(message.from_user.id))
            await TicketCRUD.add_support_audit(
                db,
                actor_user_id=db_user.id if db_user else None,
                actor_telegram_id=message.from_user.id,
                is_moderator=is_mod,
                action="block_user_timed",
                ticket_id=ticket_id,
                target_user_id=ticket.user_id if ticket else None,
                details={"minutes": minutes}
            )
        except Exception:
            pass
        # Refresh original ticket card (caption/text and buttons) in place
        try:
            updated = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=True, load_user=True)
            status_text = {
                TicketStatus.OPEN.value: texts.t("TICKET_STATUS_OPEN", "Open"),
                TicketStatus.ANSWERED.value: texts.t("TICKET_STATUS_ANSWERED", "Answered"),
                TicketStatus.CLOSED.value: texts.t("TICKET_STATUS_CLOSED", "Closed"),
                TicketStatus.PENDING.value: texts.t("TICKET_STATUS_PENDING", "Pending")
            }.get(updated.status, updated.status)
            user_name = updated.user.full_name if updated.user else "Unknown"
            ticket_text = texts.t("TICKET_CARD_ID", "🎫 Ticket #{id}").format(id=updated.id) + "\n\n"
            ticket_text += texts.t("TICKET_CARD_USER", "👤 User: {name}").format(name=user_name) + "\n"
            ticket_text += texts.t("TICKET_CARD_TITLE", "📝 Title: {title}").format(title=updated.title) + "\n"
            ticket_text += texts.t("TICKET_CARD_STATUS", "📊 Status: {emoji} {status}").format(emoji=updated.status_emoji, status=status_text) + "\n"
            ticket_text += texts.t("TICKET_CARD_CREATED", "📅 Created: {date}").format(date=updated.created_at.strftime('%d.%m.%Y %H:%M')) + "\n"
            ticket_text += texts.t("TICKET_CARD_UPDATED", "🔄 Updated: {date}").format(date=updated.updated_at.strftime('%d.%m.%Y %H:%M')) + "\n"
            if updated.user and updated.user.telegram_id:
                ticket_text += texts.t("TICKET_CARD_TELEGRAM_ID", "🆔 Telegram ID: {id}").format(id=f"<code>{updated.user.telegram_id}</code>") + "\n"
                if updated.user.username:
                    safe_username = html.escape(updated.user.username)
                    ticket_text += texts.t("TICKET_CARD_USERNAME", "📱 Username: @{username}").format(username=safe_username) + "\n"
                    pm_link = f"<a href=\"tg://resolve?domain={safe_username}\">tg://resolve?domain={safe_username}</a>"
                    ticket_text += texts.t("TICKET_CARD_PM_LINK", "🔗 PM: {link}").format(link=pm_link) + "\n"
                else:
                    ticket_text += texts.t("TICKET_CARD_USERNAME_MISSING", "📱 Username: none") + "\n"
                    chat_link = f"tg://user?id={int(updated.user.telegram_id)}"
                    chat_link_html = f"<a href=\"{chat_link}\">{chat_link}</a>"
                    ticket_text += texts.t("TICKET_CARD_CHAT_BY_ID", "🔗 Chat by ID: {link}").format(link=chat_link_html) + "\n"
            ticket_text += "\n"
            if updated.is_user_reply_blocked:
                if updated.user_reply_block_permanent:
                    ticket_text += texts.t("TICKET_USER_BLOCKED_PERM", "🚫 User is permanently blocked from replying to this ticket") + "\n"
                elif updated.user_reply_block_until:
                    ticket_text += texts.t("TICKET_USER_BLOCKED_UNTIL", "⏳ Blocked until: {date}").format(date=updated.user_reply_block_until.strftime('%d.%m.%Y %H:%M')) + "\n"
            if updated.messages:
                ticket_text += texts.t("TICKET_MESSAGES_COUNT", "💬 Messages ({count}):").format(count=len(updated.messages)) + "\n\n"
                for msg in updated.messages:
                    sender = texts.t("TICKET_SENDER_USER", "👤 User") if msg.is_user_message else texts.t("TICKET_SENDER_SUPPORT", "🛠️ Support")
                    ticket_text += f"{sender} ({msg.created_at.strftime('%d.%m %H:%M')}):\n"
                    ticket_text += f"{msg.message_text}\n\n"
                    if getattr(msg, "has_media", False) and getattr(msg, "media_type", None) == "photo":
                        ticket_text += texts.t("TICKET_ATTACHMENT_PHOTO", "📎 Attachment: photo") + "\n\n"

            kb = get_admin_ticket_view_keyboard(updated.id, updated.is_closed, db_user.language, is_user_blocked=updated.is_user_reply_blocked)
            # Button to open user profile in admin panel
            try:
                if updated.user:
                    admin_profile_btn = types.InlineKeyboardButton(
                        text=texts.t("BTN_TO_USER", "👤 To user"),
                        callback_data=f"admin_user_manage_{updated.user.id}_from_ticket_{updated.id}"
                    )
                    kb.inline_keyboard.insert(0, [admin_profile_btn])
            except Exception:
                pass
            # PM and profile buttons when updating card
            try:
                if updated.user and updated.user.telegram_id and updated.user.username:
                    safe_username = html.escape(updated.user.username)
                    buttons_row = []
                    pm_url = f"tg://resolve?domain={safe_username}"
                    buttons_row.append(types.InlineKeyboardButton(text=texts.t("BTN_WRITE_PM", "✉ Write PM"), url=pm_url))
                    profile_url = f"tg://user?id={updated.user.telegram_id}"
                    buttons_row.append(types.InlineKeyboardButton(text=texts.t("BTN_PROFILE", "👤 Profile"), url=profile_url))
                    if buttons_row:
                        kb.inline_keyboard.insert(0, buttons_row)
            except Exception:
                pass
            has_photos = any(getattr(m, "has_media", False) and getattr(m, "media_type", None) == "photo" for m in updated.messages or [])
            if has_photos:
                try:
                    kb.inline_keyboard.insert(0, [types.InlineKeyboardButton(text=texts.t("TICKET_ATTACHMENTS", "📎 Attachments"), callback_data=f"admin_ticket_attachments_{updated.id}")])
                except Exception:
                    pass
            blocked_msg = texts.t("USER_BLOCKED_FOR_MINUTES", "✅ User blocked for {minutes} minutes").format(minutes=minutes)
            if origin_chat_id and origin_message_id:
                try:
                    await message.bot.edit_message_caption(chat_id=origin_chat_id, message_id=origin_message_id, caption=ticket_text, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    try:
                        await message.bot.edit_message_text(chat_id=origin_chat_id, message_id=origin_message_id, text=ticket_text, reply_markup=kb, parse_mode="HTML")
                    except Exception:
                        await message.answer(blocked_msg)
            else:
                await message.answer(blocked_msg)
        except Exception:
            await message.answer(texts.t("USER_BLOCKED_FOR_MINUTES", "✅ User blocked for {minutes} minutes").format(minutes=minutes))
        finally:
            await state.clear()
    except Exception as e:
        logger.error(f"Error setting block duration: {e}")
        await message.answer(texts.t("TICKET_REPLY_ERROR", "❌ An error occurred. Try again later."))


 

async def unblock_user_in_ticket(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    if not (settings.is_admin(callback.from_user.id) or SupportSettingsService.is_moderator(callback.from_user.id)):
        texts = get_texts(db_user.language)
        await callback.answer(texts.ACCESS_DENIED, show_alert=True)
        return
    ticket_id = int(callback.data.replace("admin_unblock_user_ticket_", ""))
    texts = get_texts(db_user.language)
    ok = await TicketCRUD.set_user_reply_block(db, ticket_id, permanent=False, until=None)
    if ok:
        try:
            await callback.message.answer(
                texts.t("TICKET_BLOCK_REMOVED", "✅ Block removed"),
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text=texts.t("BTN_DELETE", "🗑 Delete"), callback_data="admin_support_delete_msg")]]
                )
            )
        except Exception:
            await callback.answer(texts.t("TICKET_BLOCK_REMOVED", "✅ Block removed"))
        # audit
        try:
            is_mod = (not settings.is_admin(callback.from_user.id) and SupportSettingsService.is_moderator(callback.from_user.id))
            ticket_id = int(callback.data.replace("admin_unblock_user_ticket_", ""))
            details = {}
            try:
                t = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_user=True)
                if t and t.user:
                    details.update({
                        "target_telegram_id": t.user.telegram_id,
                        "target_username": t.user.username,
                    })
            except Exception:
                pass
            await TicketCRUD.add_support_audit(
                db,
                actor_user_id=db_user.id if db_user else None,
                actor_telegram_id=callback.from_user.id,
                is_moderator=is_mod,
                action="unblock_user",
                ticket_id=ticket_id,
                target_user_id=None,
                details=details
            )
        except Exception:
            pass
        await view_admin_ticket(callback, db_user, db, state)
    else:
        await callback.answer(texts.t("ERROR_GENERIC", "❌ Error"), show_alert=True)


async def block_user_permanently(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    if not (settings.is_admin(callback.from_user.id) or SupportSettingsService.is_moderator(callback.from_user.id)):
        texts = get_texts(db_user.language)
        await callback.answer(texts.ACCESS_DENIED, show_alert=True)
        return
    ticket_id = int(callback.data.replace("admin_block_user_perm_ticket_", ""))
    texts = get_texts(db_user.language)
    ok = await TicketCRUD.set_user_reply_block(db, ticket_id, permanent=True, until=None)
    if ok:
        try:
            await callback.message.answer(
                texts.t("USER_BLOCKED_PERMANENTLY", "✅ User permanently blocked"),
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text=texts.t("BTN_DELETE", "🗑 Delete"), callback_data="admin_support_delete_msg")]]
                )
            )
        except Exception:
            await callback.answer(texts.t("USER_BLOCKED_PERMANENTLY", "✅ User permanently blocked"))
        # audit
        try:
            is_mod = (not settings.is_admin(callback.from_user.id) and SupportSettingsService.is_moderator(callback.from_user.id))
            details = {}
            try:
                t = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_user=True)
                if t and t.user:
                    details.update({
                        "target_telegram_id": t.user.telegram_id,
                        "target_username": t.user.username,
                    })
            except Exception:
                pass
            await TicketCRUD.add_support_audit(
                db,
                actor_user_id=db_user.id if db_user else None,
                actor_telegram_id=callback.from_user.id,
                is_moderator=is_mod,
                action="block_user_perm",
                ticket_id=ticket_id,
                target_user_id=None,
                details=details
            )
        except Exception:
            pass
        await view_admin_ticket(callback, db_user, db, state)
    else:
        await callback.answer(texts.t("ERROR_GENERIC", "❌ Error"), show_alert=True)


async def notify_user_about_ticket_reply(bot: Bot, ticket: Ticket, reply_text: str, db: AsyncSession):
    """Notify user about new reply in ticket"""
    try:
        # Respect runtime toggle for user ticket notifications
        try:
            if not SupportSettingsService.get_user_ticket_notifications_enabled():
                return
        except Exception:
            pass
        from app.localization.texts import get_texts

        # Ensure user data is present in ticket object
        ticket_with_user = ticket
        if not getattr(ticket_with_user, "user", None):
            ticket_with_user = await TicketCRUD.get_ticket_by_id(db, ticket.id, load_user=True)

        user = getattr(ticket_with_user, "user", None)
        if not user:
            logger.error(f"User not found for ticket #{ticket.id}")
            return

        if not getattr(user, "telegram_id", None):
            logger.error(
                "Cannot notify ticket #%s user without telegram_id (username=%s)",
                ticket.id,
                getattr(user, "username", None),
            )
            return

        chat_id = int(user.telegram_id)
        texts = get_texts(user.language)

        # Build notification
        base_text = texts.t(
            "TICKET_REPLY_NOTIFICATION",
            "🎫 Reply received for ticket #{ticket_id}\n\n{reply_preview}\n\nClick the button below to go to the ticket:"
        ).format(
            ticket_id=ticket.id,
            reply_preview=reply_text[:100] + "..." if len(reply_text) > 100 else reply_text
        )
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("VIEW_TICKET", "👁️ View ticket"), callback_data=f"view_ticket_{ticket.id}")],
            [types.InlineKeyboardButton(text=texts.t("CLOSE_NOTIFICATION", "❌ Close notification"), callback_data=f"close_ticket_notification_{ticket.id}")]
        ])

        # If there was a photo in the last admin reply - send as photo
        last_message = await TicketMessageCRUD.get_last_message(db, ticket.id)
        if last_message and last_message.has_media and last_message.media_type == "photo" and last_message.is_from_admin:
            caption = base_text
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=last_message.media_file_id,
                    caption=caption,
                    reply_markup=keyboard,
                )
                return
            except TelegramBadRequest as photo_error:
                logger.error(
                    "Failed to send photo notification to user %s for ticket %s: %s",
                    chat_id,
                    ticket.id,
                    photo_error,
                )
            except Exception as e:
                logger.error(f"Failed to send photo notification: {e}")
        # Fallback: text notification
        await bot.send_message(
            chat_id=chat_id,
            text=base_text,
            reply_markup=keyboard,
        )

        logger.info(f"Ticket #{ticket.id} reply notification sent to user {chat_id}")

    except Exception as e:
        logger.error(f"Error notifying user about ticket reply: {e}")


def register_handlers(dp: Dispatcher):
    """Register admin ticket handlers"""
    
    # View tickets
    dp.callback_query.register(show_admin_tickets, F.data == "admin_tickets")
    dp.callback_query.register(show_admin_tickets, F.data == "admin_tickets_scope_open")
    dp.callback_query.register(show_admin_tickets, F.data == "admin_tickets_scope_closed")
    dp.callback_query.register(close_all_open_admin_tickets, F.data == "admin_tickets_close_all_open")

    dp.callback_query.register(view_admin_ticket, F.data.startswith("admin_view_ticket_"))
    
    # Ticket replies
    dp.callback_query.register(
        reply_to_admin_ticket,
        F.data.startswith("admin_reply_ticket_")
    )
    
    dp.message.register(handle_admin_ticket_reply, AdminTicketStates.waiting_for_reply)
    dp.message.register(handle_admin_block_duration_input, AdminTicketStates.waiting_for_block_duration)
    
    # Status management: explicit button no longer used (status changes automatically)
    
    dp.callback_query.register(
        close_admin_ticket,
        F.data.startswith("admin_close_ticket_")
    )
    dp.callback_query.register(block_user_in_ticket, F.data.startswith("admin_block_user_ticket_"))
    dp.callback_query.register(unblock_user_in_ticket, F.data.startswith("admin_unblock_user_ticket_"))
    dp.callback_query.register(block_user_permanently, F.data.startswith("admin_block_user_perm_ticket_"))
    
    # Cancel operations
    dp.callback_query.register(
        cancel_admin_ticket_reply,
        F.data == "cancel_admin_ticket_reply"
    )
    
    # Admin tickets pagination
    dp.callback_query.register(show_admin_tickets, F.data.startswith("admin_tickets_page_"))

    # Reply layout management - (disabled)

    # Ticket attachments (admin)
    async def send_admin_ticket_attachments(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
    ):
        # permission gate for attachments view
        if not (settings.is_admin(callback.from_user.id) or SupportSettingsService.is_moderator(callback.from_user.id)):
            texts = get_texts(db_user.language)
            await callback.answer(texts.ACCESS_DENIED, show_alert=True)
            return
        texts = get_texts(db_user.language)
        try:
            ticket_id = int(callback.data.replace("admin_ticket_attachments_", ""))
        except ValueError:
            await callback.answer(texts.t("TICKET_NOT_FOUND", "Ticket not found."), show_alert=True)
            return
        ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=True)
        if not ticket:
            await callback.answer(texts.t("TICKET_NOT_FOUND", "Ticket not found."), show_alert=True)
            return
        photos = [m.media_file_id for m in ticket.messages if getattr(m, "has_media", False) and getattr(m, "media_type", None) == "photo" and m.media_file_id]
        if not photos:
            await callback.answer(texts.t("NO_ATTACHMENTS", "No attachments."), show_alert=True)
            return
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
        # After sending, add delete button under the last group message
        if last_group_message:
            try:
                kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=texts.t("DELETE_MESSAGE", "🗑 Delete"), callback_data=f"admin_delete_message_{last_group_message.message_id}")]])
                await callback.message.bot.send_message(chat_id=callback.from_user.id, text=texts.t("ATTACHMENTS_SENT", "Attachments sent."), reply_markup=kb)
            except Exception:
                await callback.answer(texts.t("ATTACHMENTS_SENT", "Attachments sent."))
        else:
            await callback.answer(texts.t("ATTACHMENTS_SENT", "Attachments sent."))

    dp.callback_query.register(send_admin_ticket_attachments, F.data.startswith("admin_ticket_attachments_"))

    async def admin_delete_message(
        callback: types.CallbackQuery
    ):
        try:
            msg_id = int(callback.data.replace("admin_delete_message_", ""))
        except ValueError:
            await callback.answer("❌")
            return
        try:
            await callback.message.bot.delete_message(chat_id=callback.from_user.id, message_id=msg_id)
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer("✅")

    dp.callback_query.register(admin_delete_message, F.data.startswith("admin_delete_message_"))

