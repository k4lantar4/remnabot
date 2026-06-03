from datetime import UTC, datetime
from html import escape
from pathlib import Path

import structlog
from aiogram import Dispatcher, F, types
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.localization.texts import get_texts
from app.utils.decorators import admin_required, error_handler


logger = structlog.get_logger(__name__)

LOG_PREVIEW_LIMIT = 2300


def _resolve_log_path() -> Path:
    log_path = Path(settings.LOG_FILE)
    if not log_path.is_absolute():
        log_path = Path.cwd() / log_path
    return log_path


def _format_preview_block(text: str) -> str:
    escaped_text = escape(text) if text else ''
    return f'<blockquote expandable><pre><code>{escaped_text}</code></pre></blockquote>'


def _build_logs_message(log_path: Path, texts) -> str:
    if not log_path.exists():
        return texts.t(
            'ADMIN_SYSTEM_LOGS_MISSING',
            '🧾 <b>Системные логи</b>\n\n'
            'Файл <code>{path}</code> пока не создан.\n'
            'Логи появятся автоматически после первой записи.',
        ).format(path=log_path)

    try:
        content = log_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as error:  # pragma: no cover - защита от проблем чтения
        logger.error('Ошибка чтения лог-файла', log_path=log_path, error=error)
        return texts.t(
            'ADMIN_SYSTEM_LOGS_READ_ERROR',
            '❌ <b>Ошибка чтения логов</b>\n\nНе удалось прочитать файл <code>{path}</code>.',
        ).format(path=log_path)

    total_length = len(content)
    stats = log_path.stat()
    updated_at = datetime.fromtimestamp(stats.st_mtime, tz=UTC)

    if not content:
        preview_text = texts.t('ADMIN_SYSTEM_LOGS_EMPTY', 'Лог-файл пуст.')
        truncated = False
    else:
        preview_text = content[-LOG_PREVIEW_LIMIT:]
        truncated = total_length > LOG_PREVIEW_LIMIT

    details_lines = [
        texts.t('ADMIN_SYSTEM_LOGS_HEADER', '🧾 <b>Системные логи</b>'),
        '',
        texts.t('ADMIN_SYSTEM_LOGS_FILE', '📁 <b>Файл:</b> <code>{path}</code>').format(path=log_path),
        texts.t('ADMIN_SYSTEM_LOGS_UPDATED', '🕒 <b>Обновлен:</b> {time}').format(
            time=updated_at.strftime('%d.%m.%Y %H:%M:%S')
        ),
        texts.t('ADMIN_SYSTEM_LOGS_SIZE', '🧮 <b>Размер:</b> {size} символов').format(size=total_length),
        (
            texts.t('ADMIN_SYSTEM_LOGS_TRUNCATED', '👇 Показаны последние {limit} символов.').format(
                limit=LOG_PREVIEW_LIMIT
            )
            if truncated
            else texts.t('ADMIN_SYSTEM_LOGS_FULL', '📄 Показано все содержимое файла.')
        ),
        '',
        _format_preview_block(preview_text),
    ]

    return '\n'.join(details_lines)


def _get_logs_keyboard(texts) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.t('ADMIN_SYSTEM_LOGS_REFRESH', '🔄 Обновить'),
                    callback_data='admin_system_logs_refresh',
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts.t('ADMIN_SYSTEM_LOGS_DOWNLOAD', '⬇️ Скачать лог'),
                    callback_data='admin_system_logs_download',
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts.t('ADMIN_BACK_TO_MONITORING', '⬅️ Назад'),
                    callback_data='admin_submenu_system',
                )
            ],
        ]
    )


@admin_required
@error_handler
async def show_system_logs(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    log_path = _resolve_log_path()
    message = _build_logs_message(log_path, texts)

    reply_markup = _get_logs_keyboard(texts)
    await callback.message.edit_text(message, reply_markup=reply_markup, parse_mode='HTML')
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
    message = _build_logs_message(log_path, texts)

    reply_markup = _get_logs_keyboard(texts)
    await callback.message.edit_text(message, reply_markup=reply_markup, parse_mode='HTML')
    await callback.answer(texts.t('ADMIN_SYSTEM_LOGS_REFRESHED', '🔄 Обновлено'))


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
        await callback.answer(texts.t('ADMIN_SYSTEM_LOGS_FILE_NOT_FOUND', '❌ Лог-файл не найден'), show_alert=True)
        return

    try:
        await callback.answer(texts.t('ADMIN_SYSTEM_LOGS_SENDING', '⬇️ Отправляю лог...'))

        document = FSInputFile(log_path)
        stats = log_path.stat()
        updated_at = datetime.fromtimestamp(stats.st_mtime, tz=UTC).strftime('%d.%m.%Y %H:%M:%S')
        caption = texts.t(
            'ADMIN_SYSTEM_LOGS_DOCUMENT_CAPTION',
            '🧾 Лог-файл <code>{name}</code>\n📁 Путь: <code>{path}</code>\n🕒 Обновлен: {time}',
        ).format(name=log_path.name, path=log_path, time=updated_at)
        await callback.message.answer_document(document=document, caption=caption, parse_mode='HTML')
    except Exception as error:  # pragma: no cover - защита от ошибок отправки
        logger.error('Ошибка отправки лог-файла', log_path=log_path, error=error)
        await callback.message.answer(
            texts.t(
                'ADMIN_SYSTEM_LOGS_SEND_ERROR',
                '❌ <b>Не удалось отправить лог-файл</b>\n\nПроверьте журналы приложения или повторите попытку позже.',
            ),
            parse_mode='HTML',
        )


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(
        show_system_logs,
        F.data == 'admin_system_logs',
    )
    dp.callback_query.register(
        refresh_system_logs,
        F.data == 'admin_system_logs_refresh',
    )
    dp.callback_query.register(
        download_system_logs,
        F.data == 'admin_system_logs_download',
    )
