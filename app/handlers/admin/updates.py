import logging
from aiogram import Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.localization.texts import get_texts
from app.services.version_service import version_service
from app.utils.decorators import admin_required, error_handler

logger = logging.getLogger(__name__)


def get_updates_keyboard(language: str = "en") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    buttons = [
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_UPDATES_BTN_CHECK", "🔄 Check updates"),
                callback_data="admin_updates_check"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_UPDATES_BTN_INFO", "📋 Version info"),
                callback_data="admin_updates_info"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_UPDATES_BTN_REPO", "🔗 Open repository"),
                url=f"https://github.com/{version_service.repo}/releases"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.BACK,
                callback_data="admin_panel"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_version_info_keyboard(language: str = "en") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    buttons = [
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_UPDATES_BTN_REFRESH", "🔄 Refresh"),
                callback_data="admin_updates_info"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_UPDATES_BTN_BACK", "◀️ To updates"),
                callback_data="admin_updates"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@admin_required
@error_handler
async def show_updates_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    try:
        version_info = await version_service.get_version_info()
        
        current_version = version_info['current_version']
        has_updates = version_info['has_updates']
        total_newer = version_info['total_newer']
        last_check = version_info['last_check']
        
        status_icon = "🆕" if has_updates else "✅"
        status_text = texts.t("ADMIN_UPDATES_AVAILABLE", "{count} updates available").format(count=total_newer) if has_updates else texts.t("ADMIN_UPDATES_UP_TO_DATE", "Up to date")
        
        last_check_text = ""
        if last_check:
            last_check_text = texts.t("ADMIN_UPDATES_LAST_CHECK", "\n🕐 Last check: {time}").format(time=last_check.strftime('%d.%m.%Y %H:%M'))
        
        message = texts.t(
            "ADMIN_UPDATES_MENU",
            """🔄 <b>UPDATE SYSTEM</b>

📦 <b>Current version:</b> <code>{current_version}</code>
{status_icon} <b>Status:</b> {status_text}

🔗 <b>Repository:</b> {repo}{last_check}

ℹ️ System automatically checks for updates every hour and sends notifications about new versions."""
        ).format(
            current_version=current_version,
            status_icon=status_icon,
            status_text=status_text,
            repo=version_service.repo,
            last_check=last_check_text
        )
        
        await callback.message.edit_text(
            message,
            reply_markup=get_updates_keyboard(db_user.language),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing updates menu: {e}")
        await callback.answer(texts.t("ADMIN_UPDATES_LOAD_ERROR", "❌ Error loading updates menu"), show_alert=True)


@admin_required
@error_handler
async def check_updates(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    await callback.answer(texts.t("ADMIN_UPDATES_CHECKING", "🔄 Checking updates..."))
    
    try:
        has_updates, newer_releases = await version_service.check_for_updates(force=True)
        
        if not has_updates:
            message = texts.t(
                "ADMIN_UPDATES_NO_UPDATES",
                """✅ <b>NO UPDATES FOUND</b>

📦 <b>Current version:</b> <code>{current_version}</code>
🎯 <b>Status:</b> You have the latest version installed

🔗 <b>Repository:</b> {repo}"""
            ).format(current_version=version_service.current_version, repo=version_service.repo)
            
        else:
            updates_list = []
            for i, release in enumerate(newer_releases[:5]): 
                icon = version_service.format_version_display(release).split()[0]
                updates_list.append(
                    f"{i+1}. {icon} <code>{release.tag_name}</code> • {release.formatted_date}"
                )
            
            updates_text = "\n".join(updates_list)
            more_text = texts.t("ADMIN_UPDATES_MORE", "\n\n📋 And {count} more updates...").format(count=len(newer_releases) - 5) if len(newer_releases) > 5 else ""
            
            message = texts.t(
                "ADMIN_UPDATES_FOUND",
                """🆕 <b>UPDATES FOUND</b>

📦 <b>Current version:</b> <code>{current_version}</code>
🎯 <b>Updates available:</b> {count}

📋 <b>Latest versions:</b>
{updates_text}{more_text}

🔗 <b>Repository:</b> {repo}"""
            ).format(
                current_version=version_service.current_version,
                count=len(newer_releases),
                updates_text=updates_text,
                more_text=more_text,
                repo=version_service.repo
            )
        
        keyboard = get_updates_keyboard(db_user.language)
        
        if has_updates:
            keyboard.inline_keyboard.insert(-2, [
                InlineKeyboardButton(
                    text=texts.t("ADMIN_UPDATES_BTN_DETAILS", "📋 Version details"),
                    callback_data="admin_updates_info"
                )
            ])
        
        await callback.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error checking updates: {e}")
        await callback.message.edit_text(
            texts.t(
                "ADMIN_UPDATES_CHECK_ERROR",
                "❌ <b>UPDATE CHECK ERROR</b>\n\nFailed to connect to GitHub server.\nTry again later.\n\n📦 <b>Current version:</b> <code>{current_version}</code>"
            ).format(current_version=version_service.current_version),
            reply_markup=get_updates_keyboard(db_user.language),
            parse_mode="HTML"
        )


@admin_required
@error_handler
async def show_version_info(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    await callback.answer(texts.t("ADMIN_UPDATES_LOADING_INFO", "📋 Loading version info..."))
    
    try:
        version_info = await version_service.get_version_info()
        
        current_version = version_info['current_version']
        current_release = version_info['current_release']
        newer_releases = version_info['newer_releases']
        has_updates = version_info['has_updates']
        last_check = version_info['last_check']
        repo_url = version_info['repo_url']
        
        current_info = texts.t("ADMIN_UPDATES_CURRENT_HEADER", "📦 <b>CURRENT VERSION</b>\n\n")
        
        if current_release:
            current_info += texts.t("ADMIN_UPDATES_VERSION", "🏷️ <b>Version:</b> <code>{version}</code>\n").format(version=current_release.tag_name)
            current_info += texts.t("ADMIN_UPDATES_RELEASE_DATE", "📅 <b>Release date:</b> {date}\n").format(date=current_release.formatted_date)
            if current_release.short_description:
                current_info += texts.t("ADMIN_UPDATES_DESCRIPTION", "📝 <b>Description:</b>\n{desc}\n").format(desc=current_release.short_description)
        else:
            current_info += texts.t("ADMIN_UPDATES_VERSION", "🏷️ <b>Version:</b> <code>{version}</code>\n").format(version=current_version)
            current_info += texts.t("ADMIN_UPDATES_INFO_UNAVAILABLE", "ℹ️ <b>Status:</b> Release info unavailable\n")
        
        message_parts = [current_info]
        
        if has_updates and newer_releases:
            updates_info = texts.t("ADMIN_UPDATES_AVAILABLE_HEADER", "\n🆕 <b>AVAILABLE UPDATES</b>\n\n")
            
            for i, release in enumerate(newer_releases):
                icon = "🔥" if i == 0 else "📦"
                if release.prerelease:
                    icon = "🧪"
                elif release.is_dev:
                    icon = "🔧"
                
                updates_info += f"{icon} <b>{release.tag_name}</b>\n"
                updates_info += f"   📅 {release.formatted_date}\n"
                if release.short_description:
                    updates_info += f"   📝 {release.short_description}\n"
                updates_info += "\n"
            
            message_parts.append(updates_info.rstrip())
        
        enabled_text = texts.t("ENABLED", "Enabled") if version_service.enabled else texts.t("DISABLED", "Disabled")
        system_info = texts.t("ADMIN_UPDATES_SYSTEM_HEADER", "\n🔧 <b>UPDATE SYSTEM</b>\n\n")
        system_info += texts.t("ADMIN_UPDATES_REPO", "🔗 <b>Repository:</b> {repo}\n").format(repo=version_service.repo)
        system_info += texts.t("ADMIN_UPDATES_AUTO_CHECK", "⚡ <b>Auto-check:</b> {status}\n").format(status=enabled_text)
        system_info += texts.t("ADMIN_UPDATES_INTERVAL", "🕐 <b>Interval:</b> Every hour\n")
        
        if last_check:
            system_info += texts.t("ADMIN_UPDATES_LAST_CHECK_LABEL", "🕐 <b>Last check:</b> {time}\n").format(time=last_check.strftime('%d.%m.%Y %H:%M'))
        
        message_parts.append(system_info.rstrip())
        
        final_message = "\n".join(message_parts)
        
        if len(final_message) > 4000:
            final_message = final_message[:3900] + texts.t("ADMIN_UPDATES_TRUNCATED", "\n\n... (info truncated)")
        
        await callback.message.edit_text(
            final_message,
            reply_markup=get_version_info_keyboard(db_user.language),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error getting version info: {e}")
        await callback.message.edit_text(
            texts.t(
                "ADMIN_UPDATES_INFO_ERROR",
                "❌ <b>LOAD ERROR</b>\n\nFailed to get version info.\n\n📦 <b>Current version:</b> <code>{current_version}</code>"
            ).format(current_version=version_service.current_version),
            reply_markup=get_version_info_keyboard(db_user.language),
            parse_mode="HTML"
        )


def register_handlers(dp: Dispatcher):
    
    dp.callback_query.register(
        show_updates_menu,
        F.data == "admin_updates"
    )
    
    dp.callback_query.register(
        check_updates,
        F.data == "admin_updates_check"
    )
    
    dp.callback_query.register(
        show_version_info,
        F.data == "admin_updates_info"
    )
