import logging
from datetime import datetime
from html import escape
from pathlib import Path

from aiogram import Dispatcher, F, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.localization.texts import get_texts
from app.utils.decorators import admin_required, error_handler

logger = logging.getLogger(__name__)

LOG_PREVIEW_LIMIT = 2300


def _resolve_log_path() -> Path:
    log_path = Path(settings.LOG_FILE)
    if not log_path.is_absolute():
        log_path = Path.cwd() / log_path
    return log_path


def _format_preview_block(text: str) -> str:
    escaped_text = escape(text) if text else ""
    return f"<blockquote expandable><pre><code>{escaped_text}</code></pre></blockquote>"


def _build_logs_message(log_path: Path, language: str = "en") -> str:
    texts = get_texts(language)
    
    if not log_path.exists():
        message = texts.t(
            "ADMIN_LOGS_NOT_CREATED",
            "🧾 <b>System logs</b>\n\nFile <code>{log_path}</code> has not been created yet.\nLogs will appear automatically after the first entry."
        ).format(log_path=log_path)
        return message

    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as error:
        logger.error("Error reading log file %s: %s", log_path, error)
        message = texts.t(
            "ADMIN_LOGS_READ_ERROR",
            "❌ <b>Error reading logs</b>\n\nFailed to read file <code>{log_path}</code>."
        ).format(log_path=log_path)
        return message

    total_length = len(content)
    stats = log_path.stat()
    updated_at = datetime.fromtimestamp(stats.st_mtime)

    if not content:
        preview_text = texts.t("ADMIN_LOGS_EMPTY", "Log file is empty.")
        truncated = False
    else:
        preview_text = content[-LOG_PREVIEW_LIMIT:]
        truncated = total_length > LOG_PREVIEW_LIMIT

    truncated_text = texts.t("ADMIN_LOGS_SHOWING_LAST", "👇 Showing last {count} characters.").format(count=LOG_PREVIEW_LIMIT) if truncated else texts.t("ADMIN_LOGS_SHOWING_ALL", "📄 Showing entire file content.")

    details_lines = [
        texts.t("ADMIN_LOGS_TITLE", "🧾 <b>System logs</b>"),
        "",
        texts.t("ADMIN_LOGS_FILE", "📁 <b>File:</b> <code>{log_path}</code>").format(log_path=log_path),
        texts.t("ADMIN_LOGS_UPDATED", "🕒 <b>Updated:</b> {time}").format(time=updated_at.strftime('%d.%m.%Y %H:%M:%S')),
        texts.t("ADMIN_LOGS_SIZE", "🧮 <b>Size:</b> {size} characters").format(size=total_length),
        truncated_text,
        "",
        _format_preview_block(preview_text),
    ]

    return "\n".join(details_lines)


def _get_logs_keyboard(language: str = "en") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.t("ADMIN_LOGS_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_system_logs_refresh")],
            [InlineKeyboardButton(text=texts.t("ADMIN_LOGS_BTN_DOWNLOAD", "⬇️ Download log"), callback_data="admin_system_logs_download")],
            [InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_system")],
        ]
    )


@admin_required
@error_handler
async def show_system_logs(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    log_path = _resolve_log_path()
    message = _build_logs_message(log_path, db_user.language)

    reply_markup = _get_logs_keyboard(db_user.language)
    await callback.message.edit_text(message, reply_markup=reply_markup, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def refresh_system_logs(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    log_path = _resolve_log_path()
    message = _build_logs_message(log_path, db_user.language)

    reply_markup = _get_logs_keyboard(db_user.language)
    await callback.message.edit_text(message, reply_markup=reply_markup, parse_mode="HTML")
    await callback.answer(texts.t("REFRESHED", "🔄 Refreshed"))


@admin_required
@error_handler
async def download_system_logs(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    log_path = _resolve_log_path()

    if not log_path.exists() or not log_path.is_file():
        await callback.answer(texts.t("ADMIN_LOGS_NOT_FOUND", "❌ Log file not found"), show_alert=True)
        return

    try:
        await callback.answer(texts.t("ADMIN_LOGS_SENDING", "⬇️ Sending log..."))

        document = FSInputFile(log_path)
        stats = log_path.stat()
        updated_at = datetime.fromtimestamp(stats.st_mtime).strftime("%d.%m.%Y %H:%M:%S")
        caption = texts.t(
            "ADMIN_LOGS_CAPTION",
            "🧾 Log file <code>{filename}</code>\n📁 Path: <code>{path}</code>\n🕒 Updated: {updated}"
        ).format(filename=log_path.name, path=log_path, updated=updated_at)
        await callback.message.answer_document(document=document, caption=caption, parse_mode="HTML")
    except Exception as error:
        logger.error("Error sending log file %s: %s", log_path, error)
        await callback.message.answer(
            texts.t(
                "ADMIN_LOGS_SEND_ERROR",
                "❌ <b>Failed to send log file</b>\n\nCheck application logs or try again later."
            ),
            parse_mode="HTML",
        )


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(
        show_system_logs,
        F.data == "admin_system_logs",
    )
    dp.callback_query.register(
        refresh_system_logs,
        F.data == "admin_system_logs_refresh",
    )
    dp.callback_query.register(
        download_system_logs,
        F.data == "admin_system_logs_download",
    )
