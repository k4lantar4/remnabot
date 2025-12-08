import logging
import os
from datetime import datetime
from pathlib import Path
from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.localization.texts import get_texts
from app.services.backup_service import backup_service
from app.utils.decorators import admin_required, error_handler

logger = logging.getLogger(__name__)


class BackupStates(StatesGroup):
    waiting_backup_file = State()
    waiting_settings_update = State()


def get_backup_main_keyboard(language: str = "en"):
    texts = get_texts(language)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_CREATE", "🚀 Create backup"), callback_data="backup_create"),
            InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_RESTORE", "📥 Restore"), callback_data="backup_restore")
        ],
        [
            InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_LIST", "📋 Backup list"), callback_data="backup_list"),
            InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_SETTINGS", "⚙️ Settings"), callback_data="backup_settings")
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")
        ]
    ])


def get_backup_list_keyboard(backups: list, page: int = 1, per_page: int = 5, language: str = "en"):
    texts = get_texts(language)
    keyboard = []
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_backups = backups[start_idx:end_idx]
    
    for backup in page_backups:
        try:
            if backup.get("timestamp"):
                dt = datetime.fromisoformat(backup["timestamp"].replace('Z', '+00:00'))
                date_str = dt.strftime("%d.%m %H:%M")
            else:
                date_str = "?"
        except:
            date_str = "?"
        
        size_str = f"{backup.get('file_size_mb', 0):.1f}MB"
        records_str = backup.get('total_records', '?')
        
        button_text = f"📦 {date_str} • {size_str} • {records_str} records"
        callback_data = f"backup_manage_{backup['filename']}"
        
        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    if len(backups) > per_page:
        total_pages = (len(backups) + per_page - 1) // per_page
        nav_row = []
        
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"backup_list_page_{page-1}"))
        
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
        
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"backup_list_page_{page+1}"))
        
        keyboard.append(nav_row)
    
    keyboard.extend([
        [InlineKeyboardButton(text=texts.BACK, callback_data="backup_panel")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_backup_manage_keyboard(backup_filename: str, language: str = "en"):
    texts = get_texts(language)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_RESTORE", "📥 Restore"), callback_data=f"backup_restore_file_{backup_filename}")
        ],
        [
            InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_DELETE", "🗑️ Delete"), callback_data=f"backup_delete_{backup_filename}")
        ],
        [
            InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_TO_LIST", "◀️ To list"), callback_data="backup_list")
        ]
    ])


def get_backup_settings_keyboard(settings_obj, language: str = "en"):
    texts = get_texts(language)
    enabled_text = texts.t("ENABLED", "✅ Enabled")
    disabled_text = texts.t("DISABLED", "❌ Disabled")
    
    auto_status = enabled_text if settings_obj.auto_backup_enabled else disabled_text
    compression_status = enabled_text if settings_obj.compression_enabled else disabled_text
    logs_status = enabled_text if settings_obj.include_logs else disabled_text
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_BACKUP_BTN_AUTO", "🔄 Auto-backups: {status}").format(status=auto_status), 
                callback_data="backup_toggle_auto"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_BACKUP_BTN_COMPRESSION", "🗜️ Compression: {status}").format(status=compression_status), 
                callback_data="backup_toggle_compression"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_BACKUP_BTN_LOGS", "📋 Logs in backup: {status}").format(status=logs_status), 
                callback_data="backup_toggle_logs"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="backup_panel")
        ]
    ])


@admin_required
@error_handler
async def show_backup_panel(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    settings_obj = await backup_service.get_backup_settings()
    
    enabled_text = texts.t("ENABLED", "✅ Enabled")
    disabled_text = texts.t("DISABLED", "❌ Disabled")
    yes_text = texts.t("YES", "Yes")
    no_text = texts.t("NO", "No")
    
    status_auto = enabled_text if settings_obj.auto_backup_enabled else disabled_text
    compression_text = yes_text if settings_obj.compression_enabled else no_text
    
    text = texts.t(
        "ADMIN_BACKUP_PANEL_TEXT",
        """🗄️ <b>BACKUP SYSTEM</b>

📊 <b>Status:</b>
• Auto-backups: {auto_status}
• Interval: {interval} hours
• Keep: {max_backups} files
• Compression: {compression}

📁 <b>Location:</b> <code>/app/data/backups</code>

⚡ <b>Available operations:</b>
• Create full backup of all data
• Restore from backup file
• Manage automatic backups
"""
    ).format(
        auto_status=status_auto,
        interval=settings_obj.backup_interval_hours,
        max_backups=settings_obj.max_backups_keep,
        compression=compression_text
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_backup_main_keyboard(db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def create_backup_handler(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    await callback.answer(texts.t("ADMIN_BACKUP_CREATING", "🔄 Creating backup..."))
    
    progress_msg = await callback.message.edit_text(
        texts.t(
            "ADMIN_BACKUP_PROGRESS",
            "🔄 <b>Creating backup...</b>\n\n⏳ Exporting data from database...\nThis may take a few minutes."
        ),
        parse_mode="HTML"
    )
    
    success, message, file_path = await backup_service.create_backup(
        created_by=db_user.telegram_id,
        compress=True
    )
    
    if success:
        await progress_msg.edit_text(
            texts.t("ADMIN_BACKUP_SUCCESS", "✅ <b>Backup created successfully!</b>\n\n{message}").format(message=message),
            parse_mode="HTML",
            reply_markup=get_backup_main_keyboard(db_user.language)
        )
    else:
        await progress_msg.edit_text(
            texts.t("ADMIN_BACKUP_ERROR", "❌ <b>Backup creation error</b>\n\n{message}").format(message=message),
            parse_mode="HTML",
            reply_markup=get_backup_main_keyboard(db_user.language)
        )


@admin_required
@error_handler
async def show_backup_list(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    page = 1
    if callback.data.startswith("backup_list_page_"):
        try:
            page = int(callback.data.split("_")[-1])
        except:
            page = 1
    
    backups = await backup_service.get_backup_list()
    
    if not backups:
        text = texts.t("ADMIN_BACKUP_LIST_EMPTY", "📦 <b>Backup list is empty</b>\n\nNo backups have been created yet.")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_CREATE_FIRST", "🚀 Create first backup"), callback_data="backup_create")],
            [InlineKeyboardButton(text=texts.BACK, callback_data="backup_panel")]
        ])
    else:
        text = texts.t("ADMIN_BACKUP_LIST_TITLE", "📦 <b>Backup list</b> (total: {count})\n\nSelect a backup to manage:").format(count=len(backups))
        keyboard = get_backup_list_keyboard(backups, page, language=db_user.language)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@admin_required
@error_handler
async def manage_backup_file(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    filename = callback.data.replace("backup_manage_", "")
    
    backups = await backup_service.get_backup_list()
    backup_info = None
    
    for backup in backups:
        if backup["filename"] == filename:
            backup_info = backup
            break
    
    if not backup_info:
        await callback.answer(texts.t("ADMIN_BACKUP_FILE_NOT_FOUND", "❌ Backup file not found"), show_alert=True)
        return
    
    try:
        if backup_info.get("timestamp"):
            dt = datetime.fromisoformat(backup_info["timestamp"].replace('Z', '+00:00'))
            date_str = dt.strftime("%d.%m.%Y %H:%M:%S")
        else:
            date_str = texts.t("UNKNOWN", "Unknown")
    except:
        date_str = texts.t("DATE_FORMAT_ERROR", "Date format error")
    
    yes_text = texts.t("YES", "Yes")
    no_text = texts.t("NO", "No")
    
    text = texts.t(
        "ADMIN_BACKUP_INFO",
        """📦 <b>Backup information</b>

📄 <b>File:</b> <code>{filename}</code>
📅 <b>Created:</b> {date}
💾 <b>Size:</b> {size:.2f} MB
📊 <b>Tables:</b> {tables}
📈 <b>Records:</b> {records:,}
🗜️ <b>Compression:</b> {compression}
🗄️ <b>DB:</b> {db_type}
"""
    ).format(
        filename=filename,
        date=date_str,
        size=backup_info.get('file_size_mb', 0),
        tables=backup_info.get('tables_count', '?'),
        records=backup_info.get('total_records', 0) or 0,
        compression=yes_text if backup_info.get('compressed') else no_text,
        db_type=backup_info.get('database_type', 'unknown')
    )
    
    if backup_info.get("error"):
        text += texts.t("ADMIN_BACKUP_ERROR_LABEL", "\n⚠️ <b>Error:</b> {error}").format(error=backup_info['error'])
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_backup_manage_keyboard(filename, db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def delete_backup_confirm(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    filename = callback.data.replace("backup_delete_", "")
    
    text = texts.t(
        "ADMIN_BACKUP_DELETE_CONFIRM",
        "🗑️ <b>Delete backup</b>\n\nAre you sure you want to delete this backup?\n\n📄 <code>{filename}</code>\n\n⚠️ <b>This action cannot be undone!</b>"
    ).format(filename=filename)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_YES_DELETE", "✅ Yes, delete"), callback_data=f"backup_delete_confirm_{filename}"),
            InlineKeyboardButton(text=texts.t("CANCEL", "❌ Cancel"), callback_data=f"backup_manage_{filename}")
        ]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@admin_required
@error_handler
async def delete_backup_execute(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    filename = callback.data.replace("backup_delete_confirm_", "")
    
    success, message = await backup_service.delete_backup(filename)
    
    if success:
        await callback.message.edit_text(
            texts.t("ADMIN_BACKUP_DELETED", "✅ <b>Backup deleted</b>\n\n{message}").format(message=message),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_TO_LIST", "📋 To backup list"), callback_data="backup_list")]
            ])
        )
    else:
        await callback.message.edit_text(
            texts.t("ADMIN_BACKUP_DELETE_ERROR", "❌ <b>Delete error</b>\n\n{message}").format(message=message),
            parse_mode="HTML",
            reply_markup=get_backup_manage_keyboard(filename, db_user.language)
        )
    
    await callback.answer()


@admin_required
@error_handler
async def restore_backup_start(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    if callback.data.startswith("backup_restore_file_"):
        filename = callback.data.replace("backup_restore_file_", "")
        
        text = texts.t(
            "ADMIN_BACKUP_RESTORE_FILE_CONFIRM",
            """📥 <b>Restore from backup</b>

📄 <b>File:</b> <code>{filename}</code>

⚠️ <b>WARNING!</b>
• Process may take several minutes
• It is recommended to create a backup before restoring
• Existing data will be supplemented

Continue with restore?"""
        ).format(filename=filename)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_YES_RESTORE", "✅ Yes, restore"), callback_data=f"backup_restore_execute_{filename}"),
                InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_CLEAR_RESTORE", "🗑️ Clear and restore"), callback_data=f"backup_restore_clear_{filename}")
            ],
            [
                InlineKeyboardButton(text=texts.t("CANCEL", "❌ Cancel"), callback_data=f"backup_manage_{filename}")
            ]
        ])
    else:
        text = texts.t(
            "ADMIN_BACKUP_RESTORE_UPLOAD",
            """📥 <b>Restore from backup</b>

📎 Send a backup file (.json or .json.gz)

⚠️ <b>IMPORTANT:</b>
• File must be created by this backup system
• Process may take several minutes
• It is recommended to create a backup before restoring

💡 Or select from existing backups below."""
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_SELECT_FROM_LIST", "📋 Select from list"), callback_data="backup_list")],
            [InlineKeyboardButton(text=texts.t("CANCEL", "❌ Cancel"), callback_data="backup_panel")]
        ])
        
        await state.set_state(BackupStates.waiting_backup_file)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@admin_required
@error_handler
async def restore_backup_execute(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    if callback.data.startswith("backup_restore_execute_"):
        filename = callback.data.replace("backup_restore_execute_", "")
        clear_existing = False
    elif callback.data.startswith("backup_restore_clear_"):
        filename = callback.data.replace("backup_restore_clear_", "")
        clear_existing = True
    else:
        await callback.answer(texts.t("ADMIN_BACKUP_INVALID_COMMAND", "❌ Invalid command format"), show_alert=True)
        return
    
    await callback.answer(texts.t("ADMIN_BACKUP_RESTORING", "🔄 Restore started..."))
    
    action_text = texts.t("ADMIN_BACKUP_ACTION_CLEAR_RESTORE", "clearing and restoring") if clear_existing else texts.t("ADMIN_BACKUP_ACTION_RESTORE", "restoring")
    progress_msg = await callback.message.edit_text(
        texts.t(
            "ADMIN_BACKUP_RESTORE_PROGRESS",
            "📥 <b>Restoring from backup...</b>\n\n⏳ Working on {action} data...\n📄 File: <code>{filename}</code>\n\nThis may take several minutes."
        ).format(action=action_text, filename=filename),
        parse_mode="HTML"
    )
    
    backup_path = backup_service.backup_dir / filename
    
    success, message = await backup_service.restore_backup(
        str(backup_path),
        clear_existing=clear_existing
    )
    
    if success:
        await progress_msg.edit_text(
            texts.t("ADMIN_BACKUP_RESTORE_SUCCESS", "✅ <b>Restore completed!</b>\n\n{message}").format(message=message),
            parse_mode="HTML",
            reply_markup=get_backup_main_keyboard(db_user.language)
        )
    else:
        await progress_msg.edit_text(
            texts.t("ADMIN_BACKUP_RESTORE_ERROR", "❌ <b>Restore error</b>\n\n{message}").format(message=message),
            parse_mode="HTML",
            reply_markup=get_backup_manage_keyboard(filename, db_user.language)
        )


@admin_required
@error_handler
async def handle_backup_file_upload(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    if not message.document:
        await message.answer(
            texts.t("ADMIN_BACKUP_UPLOAD_FILE", "❌ Please send a backup file (.json or .json.gz)"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=texts.t("CANCEL", "◀️ Cancel"), callback_data="backup_panel")]
            ])
        )
        return
    
    document = message.document
    
    if not (document.file_name.endswith('.json') or document.file_name.endswith('.json.gz')):
        await message.answer(
            texts.t("ADMIN_BACKUP_UNSUPPORTED_FORMAT", "❌ Unsupported file format. Upload a .json or .json.gz file"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=texts.t("CANCEL", "◀️ Cancel"), callback_data="backup_panel")]
            ])
        )
        return
    
    if document.file_size > 50 * 1024 * 1024:
        await message.answer(
            texts.t("ADMIN_BACKUP_FILE_TOO_LARGE", "❌ File is too large (maximum 50MB)"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=texts.t("CANCEL", "◀️ Cancel"), callback_data="backup_panel")]
            ])
        )
        return
    
    try:
        file = await message.bot.get_file(document.file_id)
        
        temp_path = backup_service.backup_dir / f"uploaded_{document.file_name}"
        
        await message.bot.download_file(file.file_path, temp_path)
        
        text = texts.t(
            "ADMIN_BACKUP_FILE_UPLOADED",
            """📥 <b>File uploaded</b>

📄 <b>Name:</b> <code>{filename}</code>
💾 <b>Size:</b> {size:.2f} MB

⚠️ <b>WARNING!</b>
The restore process will modify database data.
It is recommended to create a backup before restoring.

Continue?"""
        ).format(filename=document.file_name, size=document.file_size / 1024 / 1024)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_YES_RESTORE", "✅ Restore"), callback_data=f"backup_restore_uploaded_{temp_path.name}"),
                InlineKeyboardButton(text=texts.t("ADMIN_BACKUP_BTN_CLEAR_RESTORE", "🗑️ Clear and restore"), callback_data=f"backup_restore_uploaded_clear_{temp_path.name}")
            ],
            [
                InlineKeyboardButton(text=texts.t("CANCEL", "❌ Cancel"), callback_data="backup_panel")
            ]
        ])
        
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error uploading backup file: {e}")
        await message.answer(
            texts.t("ADMIN_BACKUP_UPLOAD_ERROR", "❌ File upload error: {error}").format(error=str(e)),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=texts.t("CANCEL", "◀️ Cancel"), callback_data="backup_panel")]
            ])
        )


@admin_required
@error_handler
async def show_backup_settings(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    settings_obj = await backup_service.get_backup_settings()
    
    enabled_text = texts.t("ENABLED", "✅ Enabled")
    disabled_text = texts.t("DISABLED", "❌ Disabled")
    yes_text = texts.t("YES", "✅ Yes")
    no_text = texts.t("NO", "❌ No")
    
    text = texts.t(
        "ADMIN_BACKUP_SETTINGS_TEXT",
        """⚙️ <b>Backup system settings</b>

🔄 <b>Automatic backups:</b>
• Status: {auto_status}
• Interval: {interval} hours
• Start time: {backup_time}

📦 <b>Storage:</b>
• Maximum files: {max_files}
• Compression: {compression}
• Include logs: {include_logs}

📁 <b>Location:</b> <code>{location}</code>
"""
    ).format(
        auto_status=enabled_text if settings_obj.auto_backup_enabled else disabled_text,
        interval=settings_obj.backup_interval_hours,
        backup_time=settings_obj.backup_time,
        max_files=settings_obj.max_backups_keep,
        compression=enabled_text if settings_obj.compression_enabled else disabled_text,
        include_logs=yes_text if settings_obj.include_logs else no_text,
        location=settings_obj.backup_location
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_backup_settings_keyboard(settings_obj, db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_backup_setting(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    settings_obj = await backup_service.get_backup_settings()
    
    enabled_text = texts.t("ENABLED_SHORT", "enabled")
    disabled_text = texts.t("DISABLED_SHORT", "disabled")
    
    if callback.data == "backup_toggle_auto":
        new_value = not settings_obj.auto_backup_enabled
        await backup_service.update_backup_settings(auto_backup_enabled=new_value)
        status = enabled_text if new_value else disabled_text
        await callback.answer(texts.t("ADMIN_BACKUP_AUTO_TOGGLED", "Auto-backups {status}").format(status=status))
        
    elif callback.data == "backup_toggle_compression":
        new_value = not settings_obj.compression_enabled
        await backup_service.update_backup_settings(compression_enabled=new_value)
        status = enabled_text if new_value else disabled_text
        await callback.answer(texts.t("ADMIN_BACKUP_COMPRESSION_TOGGLED", "Compression {status}").format(status=status))
        
    elif callback.data == "backup_toggle_logs":
        new_value = not settings_obj.include_logs
        await backup_service.update_backup_settings(include_logs=new_value)
        status = enabled_text if new_value else disabled_text
        await callback.answer(texts.t("ADMIN_BACKUP_LOGS_TOGGLED", "Logs in backup {status}").format(status=status))
    
    await show_backup_settings(callback, db_user, db)


def register_handlers(dp: Dispatcher):
    
    dp.callback_query.register(
        show_backup_panel,
        F.data == "backup_panel"
    )
    
    dp.callback_query.register(
        create_backup_handler,
        F.data == "backup_create"
    )
    
    dp.callback_query.register(
        show_backup_list,
        F.data.startswith("backup_list")
    )
    
    dp.callback_query.register(
        manage_backup_file,
        F.data.startswith("backup_manage_")
    )
    
    dp.callback_query.register(
        delete_backup_confirm,
        F.data.startswith("backup_delete_") & ~F.data.startswith("backup_delete_confirm_")
    )
    
    dp.callback_query.register(
        delete_backup_execute,
        F.data.startswith("backup_delete_confirm_")
    )
    
    dp.callback_query.register(
        restore_backup_start,
        F.data.in_(["backup_restore"]) | F.data.startswith("backup_restore_file_")
    )
    
    dp.callback_query.register(
        restore_backup_execute,
        F.data.startswith("backup_restore_execute_") | F.data.startswith("backup_restore_clear_")
    )
    
    dp.callback_query.register(
        show_backup_settings,
        F.data == "backup_settings"
    )
    
    dp.callback_query.register(
        toggle_backup_setting,
        F.data.in_(["backup_toggle_auto", "backup_toggle_compression", "backup_toggle_logs"])
    )
    
    dp.message.register(
        handle_backup_file_upload,
        BackupStates.waiting_backup_file
    )
