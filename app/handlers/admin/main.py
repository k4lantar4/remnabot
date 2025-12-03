import logging
from aiogram import Dispatcher, types, F
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.keyboards.admin import (
    get_admin_main_keyboard,
    get_admin_users_submenu_keyboard,
    get_admin_promo_submenu_keyboard,
    get_admin_communications_submenu_keyboard,
    get_admin_support_submenu_keyboard,
    get_admin_settings_submenu_keyboard,
    get_admin_system_submenu_keyboard
)
from app.localization.texts import get_texts
from app.handlers.admin import support_settings as support_settings_handlers
from app.utils.decorators import admin_required, error_handler
from app.services.support_settings_service import SupportSettingsService
from app.database.crud.rules import clear_all_rules, get_rules_statistics
from app.localization.texts import clear_rules_cache
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.database.crud.ticket import TicketCRUD

logger = logging.getLogger(__name__)


@admin_required
@error_handler
async def show_admin_panel(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    admin_text = texts.ADMIN_PANEL
    try:
        from app.services.remnawave_service import RemnaWaveService
        remnawave_service = RemnaWaveService()
        stats = await remnawave_service.get_system_statistics()
        system_stats = stats.get("system", {})
        users_online = system_stats.get("users_online", 0)
        users_today = system_stats.get("users_last_day", 0)
        users_week = system_stats.get("users_last_week", 0)
        select_section_text = texts.t("ADMIN_SELECT_SECTION", "Select section for management:")
        admin_text = admin_text.replace(
            f"\n\n{select_section_text}",
            (
                f"\n\n- 🟢 {texts.t('ADMIN_ONLINE_NOW', 'Online now')}: {users_online}"
                f"\n- 📅 {texts.t('ADMIN_ONLINE_TODAY', 'Online today')}: {users_today}"
                f"\n- 🗓️ {texts.t('ADMIN_ONLINE_WEEK', 'This week')}: {users_week}"
                f"\n\n{select_section_text}"
            ),
        )
    except Exception as e:
        logger.error(f"Failed to get Remnawave statistics for admin panel: {e}")
    
    await callback.message.edit_text(
        admin_text,
        reply_markup=get_admin_main_keyboard(db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_users_submenu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)

    await callback.message.edit_text(
        texts.t("ADMIN_USERS_SUBMENU_TITLE", "👥 **User and Subscription Management**\n\n") +
        texts.t("ADMIN_SUBMENU_SELECT_SECTION", "Select the desired section:"),
        reply_markup=get_admin_users_submenu_keyboard(db_user.language),
        parse_mode="Markdown"
    )
    await callback.answer()


@admin_required
@error_handler
async def show_promo_submenu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)

    await callback.message.edit_text(
        texts.t("ADMIN_PROMO_SUBMENU_TITLE", "💰 **Promocodes and Statistics**\n\n") +
        texts.t("ADMIN_SUBMENU_SELECT_SECTION", "Select the desired section:"),
        reply_markup=get_admin_promo_submenu_keyboard(db_user.language),
        parse_mode="Markdown"
    )
    await callback.answer()


@admin_required
@error_handler
async def show_communications_submenu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)

    await callback.message.edit_text(
        texts.t("ADMIN_COMMUNICATIONS_SUBMENU_TITLE", "📨 **Communications**\n\n") +
        texts.t("ADMIN_COMMUNICATIONS_SUBMENU_DESCRIPTION", "Manage broadcasts and interface texts:"),
        reply_markup=get_admin_communications_submenu_keyboard(db_user.language),
        parse_mode="Markdown"
    )
    await callback.answer()


@admin_required
@error_handler
async def show_support_submenu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    # Moderators have access only to tickets and not to settings
    is_moderator_only = (not settings.is_admin(callback.from_user.id) and SupportSettingsService.is_moderator(callback.from_user.id))
    
    kb = get_admin_support_submenu_keyboard(db_user.language)
    if is_moderator_only:
        # Rebuild keyboard to include only tickets and back to main menu
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=texts.t("ADMIN_SUPPORT_TICKETS", "🎫 Support Tickets"), callback_data="admin_tickets")],
            [InlineKeyboardButton(text=texts.BACK, callback_data="back_to_menu")]
        ])
    await callback.message.edit_text(
        texts.t("ADMIN_SUPPORT_SUBMENU_TITLE", "🛟 **Support**\n\n") + (
            texts.t("ADMIN_SUPPORT_SUBMENU_DESCRIPTION_MODERATOR", "Access to tickets.")
            if is_moderator_only
            else texts.t("ADMIN_SUPPORT_SUBMENU_DESCRIPTION", "Manage tickets and support settings:")
        ),
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()


# Moderator panel entry (from main menu quick button)
async def show_moderator_panel(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.t("ADMIN_SUPPORT_TICKETS", "🎫 Тикеты поддержки"), callback_data="admin_tickets")],
        [InlineKeyboardButton(text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ В главное меню"), callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(
        texts.t("ADMIN_SUPPORT_MODERATION_TITLE", "🧑‍⚖️ <b>Support Moderation</b>") + "\n\n" +
        texts.t("ADMIN_SUPPORT_MODERATION_DESCRIPTION", "Access to support tickets."),
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()


@admin_required
@error_handler
async def show_support_audit(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    # pagination
    page = 1
    if callback.data.startswith("admin_support_audit_page_"):
        try:
            page = int(callback.data.split("_")[-1])
        except Exception:
            page = 1
    per_page = 10
    total = await TicketCRUD.count_support_audit(db)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page
    logs = await TicketCRUD.list_support_audit(db, limit=per_page, offset=offset)

    lines = [texts.t("ADMIN_SUPPORT_AUDIT_TITLE", "🧾 <b>Moderator Audit</b>"), ""]
    if not logs:
        lines.append(texts.t("ADMIN_SUPPORT_AUDIT_EMPTY", "Empty for now"))
    else:
        for log in logs:
            role = (
                texts.t("ADMIN_SUPPORT_AUDIT_ROLE_MODERATOR", "Moderator")
                if getattr(log, 'is_moderator', False)
                else texts.t("ADMIN_SUPPORT_AUDIT_ROLE_ADMIN", "Admin")
            )
            ts = log.created_at.strftime('%d.%m.%Y %H:%M') if getattr(log, 'created_at', None) else ''
            action_map = {
                'close_ticket': texts.t("ADMIN_SUPPORT_AUDIT_ACTION_CLOSE_TICKET", "Close ticket"),
                'block_user_timed': texts.t("ADMIN_SUPPORT_AUDIT_ACTION_BLOCK_TIMED", "Block (timed)"),
                'block_user_perm': texts.t("ADMIN_SUPPORT_AUDIT_ACTION_BLOCK_PERM", "Block (permanent)"),
                'close_all_tickets': texts.t("ADMIN_SUPPORT_AUDIT_ACTION_CLOSE_ALL_TICKETS", "Mass close tickets"),
                'unblock_user': texts.t("ADMIN_SUPPORT_AUDIT_ACTION_UNBLOCK", "Unblock"),
            }
            action_text = action_map.get(log.action, log.action)
            ticket_part = f" {texts.t('TICKET', 'ticket')} #{log.ticket_id}" if log.ticket_id else ""
            details = log.details or {}
            extra = ""
            if log.action == 'block_user_timed' and 'minutes' in details:
                extra = f" ({details['minutes']} {texts.t('MINUTES', 'min')})"
            elif log.action == 'close_all_tickets' and 'count' in details:
                extra = f" ({details['count']})"
            lines.append(f"{ts} • {role} <code>{log.actor_telegram_id}</code> — {action_text}{ticket_part}{extra}")

    # keyboard with pagination
    nav_row = []
    if total_pages > 1:
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_support_audit_page_{page-1}"))
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="current_page"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_support_audit_page_{page+1}"))

    kb_rows = []
    if nav_row:
        kb_rows.append(nav_row)
    kb_rows.append([InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_support")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@admin_required
@error_handler
async def show_settings_submenu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)

    await callback.message.edit_text(
        texts.t("ADMIN_SETTINGS_SUBMENU_TITLE", "⚙️ **System Settings**\n\n") +
        texts.t("ADMIN_SETTINGS_SUBMENU_DESCRIPTION", "Manage Remnawave, monitoring and other settings:"),
        reply_markup=get_admin_settings_submenu_keyboard(db_user.language),
        parse_mode="Markdown"
    )
    await callback.answer()


@admin_required
@error_handler
async def show_system_submenu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)

    await callback.message.edit_text(
        texts.t("ADMIN_SYSTEM_SUBMENU_TITLE", "🛠️ **System Functions**\n\n") +
        texts.t("ADMIN_SYSTEM_SUBMENU_DESCRIPTION", "Reports, updates, logs, backups and system operations:"),
        reply_markup=get_admin_system_submenu_keyboard(db_user.language),
        parse_mode="Markdown"
    )
    await callback.answer()



@admin_required
@error_handler
async def clear_rules_command(
    message: types.Message,
    db_user: User,
    db: AsyncSession
):
    try:
        stats = await get_rules_statistics(db)
        
        if stats['total_active'] == 0:
            texts = get_texts(db_user.language)
            await message.reply(
                texts.t("ADMIN_RULES_ALREADY_CLEARED", "ℹ️ <b>Rules already cleared</b>\n\n")
                + texts.t("ADMIN_RULES_NO_ACTIVE", "No active rules in system. Default rules are being used.")
            )
            return
        
        success = await clear_all_rules(db, db_user.language)
        
        if success:
            clear_rules_cache()
            
            texts = get_texts(db_user.language)
            await message.reply(
                texts.t("ADMIN_RULES_CLEARED_SUCCESS", "✅ <b>Rules successfully cleared!</b>\n\n")
                + texts.t("ADMIN_RULES_STATS_HEADER", "📊 <b>Statistics:</b>\n")
                + texts.t("ADMIN_RULES_CLEARED_COUNT", "• Rules cleared: {count}\n").format(count=stats['total_active'])
                + texts.t("ADMIN_RULES_LANGUAGE", "• Language: {lang}\n").format(lang=db_user.language)
                + texts.t("ADMIN_RULES_EXECUTED_BY", "• Executed by: {name}\n\n").format(name=db_user.full_name)
                + texts.t("ADMIN_RULES_NOW_DEFAULT", "Default rules are now being used.")
            )
            
            logger.info(f"Rules cleared by admin command from {db_user.telegram_id} ({db_user.full_name})")
        else:
            texts = get_texts(db_user.language)
            await message.reply(
                texts.t("ADMIN_RULES_NO_RULES_TO_CLEAR", "⚠️ <b>No rules to clear</b>\n\n")
                + texts.t("ADMIN_RULES_ACTIVE_NOT_FOUND", "No active rules found.")
            )
            
    except Exception as e:
        logger.error(f"Error clearing rules by command: {e}")
        texts = get_texts(db_user.language)
        await message.reply(
            texts.t("ADMIN_RULES_CLEAR_ERROR", "❌ <b>Error clearing rules</b>\n\n")
            + texts.t("ADMIN_ERROR_OCCURRED", "An error occurred: {error}\n").format(error=str(e))
            + texts.t("ADMIN_TRY_LATER", "Try through admin panel or retry later.")
        )


@admin_required
@error_handler
async def rules_stats_command(
    message: types.Message,
    db_user: User,
    db: AsyncSession
):
    try:
        stats = await get_rules_statistics(db)
        
        if 'error' in stats:
            texts = get_texts(db_user.language)
            await message.reply(texts.t("ADMIN_RULES_STATS_ERROR", "❌ Error getting statistics: {error}").format(error=stats['error']))
            return
        
        texts = get_texts(db_user.language)
        text = texts.t("ADMIN_RULES_STATS_TITLE", "📊 <b>Service Rules Statistics</b>\n\n")
        text += texts.t("ADMIN_RULES_STATS_GENERAL", "📋 <b>General Information:</b>\n")
        text += texts.t("ADMIN_RULES_STATS_ACTIVE", "• Active rules: {count}\n").format(count=stats['total_active'])
        text += texts.t("ADMIN_RULES_STATS_TOTAL", "• Total in history: {count}\n").format(count=stats['total_all_time'])
        text += texts.t("ADMIN_RULES_STATS_LANGUAGES", "• Supported languages: {count}\n\n").format(count=stats['total_languages'])
        
        if stats['languages']:
            text += texts.t("ADMIN_RULES_STATS_BY_LANGUAGE", "🌐 <b>By Language:</b>\n")
            for lang, lang_stats in stats['languages'].items():
                text += texts.t("ADMIN_RULES_STATS_LANG_LINE", "• <code>{lang}</code>: {count} rules, {chars} characters\n").format(
                    lang=lang, count=lang_stats['active_count'], chars=lang_stats['content_length']
                )
                if lang_stats['last_updated']:
                    text += texts.t("ADMIN_RULES_STATS_UPDATED", "  Updated: {date}\n").format(
                        date=lang_stats['last_updated'].strftime('%d.%m.%Y %H:%M')
                    )
        else:
            text += texts.t("ADMIN_RULES_STATS_NO_ACTIVE", "ℹ️ No active rules - default rules are being used")
        
        await message.reply(text)
        
    except Exception as e:
        logger.error(f"Error getting rules statistics: {e}")
        texts = get_texts(db_user.language)
        await message.reply(
            texts.t("ADMIN_RULES_STATS_ERROR_TITLE", "❌ <b>Error getting statistics</b>\n\n")
            + texts.t("ADMIN_ERROR_OCCURRED", "An error occurred: {error}").format(error=str(e))
        )


@admin_required
@error_handler
async def admin_commands_help(
    message: types.Message,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    help_text = texts.t("ADMIN_HELP_TITLE", "🔧 <b>Available Admin Commands:</b>") + "\n\n"
    help_text += texts.t("ADMIN_HELP_RULES_SECTION", "<b>📋 Rules Management:</b>") + "\n"
    help_text += texts.t("ADMIN_HELP_CLEAR_RULES", "• <code>/clear_rules</code> - clear all rules") + "\n"
    help_text += texts.t("ADMIN_HELP_RULES_STATS", "• <code>/rules_stats</code> - rules statistics") + "\n\n"
    help_text += texts.t("ADMIN_HELP_INFO_SECTION", "<b>ℹ️ Help:</b>") + "\n"
    help_text += texts.t("ADMIN_HELP_COMMAND", "• <code>/admin_help</code> - this message") + "\n\n"
    help_text += texts.t("ADMIN_HELP_PANEL_SECTION", "<b>📱 Control Panel:</b>") + "\n"
    help_text += texts.t("ADMIN_HELP_PANEL_DESCRIPTION", "Use the 'Admin Panel' button in the main menu for full access to all functions.") + "\n\n"
    help_text += texts.t("ADMIN_HELP_IMPORTANT", "<b>⚠️ Important:</b>") + "\n"
    help_text += texts.t("ADMIN_HELP_LOGGING", "All commands are logged and require admin rights.")
    
    await message.reply(help_text)


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(
        show_admin_panel,
        F.data == "admin_panel"
    )
    
    dp.callback_query.register(
        show_users_submenu,
        F.data == "admin_submenu_users"
    )
    
    dp.callback_query.register(
        show_promo_submenu,
        F.data == "admin_submenu_promo"
    )
    
    dp.callback_query.register(
        show_communications_submenu,
        F.data == "admin_submenu_communications"
    )
    
    dp.callback_query.register(
        show_support_submenu,
        F.data == "admin_submenu_support"
    )
    dp.callback_query.register(
        show_support_audit,
        F.data.in_(["admin_support_audit"]) | F.data.startswith("admin_support_audit_page_")
    )
    
    dp.callback_query.register(
        show_settings_submenu,
        F.data == "admin_submenu_settings"
    )
    
    dp.callback_query.register(
        show_system_submenu,
        F.data == "admin_submenu_system"
    )
    dp.callback_query.register(
        show_moderator_panel,
        F.data == "moderator_panel"
    )
    # Support settings module
    support_settings_handlers.register_handlers(dp)
    
    dp.message.register(
        clear_rules_command,
        Command("clear_rules")
    )
    
    dp.message.register(
        rules_stats_command,
        Command("rules_stats")
    )
    
    dp.message.register(
        admin_commands_help,
        Command("admin_help")
    )
