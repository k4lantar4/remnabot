import logging
from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.services.maintenance_service import maintenance_service
from app.keyboards.admin import get_maintenance_keyboard, get_admin_main_keyboard
from app.localization.texts import get_texts
from app.utils.decorators import admin_required, error_handler

logger = logging.getLogger(__name__)


class MaintenanceStates(StatesGroup):
    waiting_for_reason = State()
    waiting_for_notification_message = State()


@admin_required
@error_handler
async def show_maintenance_panel(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    
    status_info = maintenance_service.get_status_info()
    
    try:
        from app.services.remnawave_service import RemnaWaveService
        rw_service = RemnaWaveService()
        panel_status = await rw_service.get_panel_status_summary()
    except Exception as e:
        logger.error(f"Failed to get panel status: {e}")
        panel_status = {"description": "❓ Failed to check", "has_issues": True}
    
    status_emoji = "🔧" if status_info["is_active"] else "✅"
    status_text = texts.get_text("ADMIN_MAINTENANCE_STATUS_ENABLED", "Enabled") if status_info["is_active"] else texts.get_text("ADMIN_MAINTENANCE_STATUS_DISABLED", "Disabled")
    
    api_emoji = "✅" if status_info["api_status"] else "❌"
    api_text = texts.get_text("ADMIN_MAINTENANCE_API_AVAILABLE", "Available") if status_info["api_status"] else texts.get_text("ADMIN_MAINTENANCE_API_UNAVAILABLE", "Unavailable")
    
    monitoring_emoji = "🔄" if status_info["monitoring_active"] else "⏹️"
    monitoring_text = texts.get_text("ADMIN_MAINTENANCE_MONITORING_RUNNING", "Running") if status_info["monitoring_active"] else texts.get_text("ADMIN_MAINTENANCE_MONITORING_STOPPED", "Stopped")
    
    enabled_info = ""
    if status_info["is_active"] and status_info["enabled_at"]:
        enabled_time = status_info["enabled_at"].strftime("%d.%m.%Y %H:%M:%S")
        enabled_info = f"\n📅 <b>{texts.get_text('ADMIN_MAINTENANCE_ENABLED_AT', 'Enabled at:')}</b> {enabled_time}"
        if status_info["reason"]:
            enabled_info += f"\n📝 <b>{texts.get_text('ADMIN_MAINTENANCE_REASON', 'Reason:')}</b> {status_info['reason']}"
    
    last_check_info = ""
    if status_info["last_check"]:
        last_check_time = status_info["last_check"].strftime("%H:%M:%S")
        last_check_info = f"\n🕐 <b>{texts.get_text('ADMIN_MAINTENANCE_LAST_CHECK', 'Last check:')}</b> {last_check_time}"
    
    failures_info = ""
    if status_info["consecutive_failures"] > 0:
        failures_info = f"\n⚠️ <b>{texts.get_text('ADMIN_MAINTENANCE_CONSECUTIVE_FAILURES', 'Consecutive failed checks:')}</b> {status_info['consecutive_failures']}"
    
    panel_info = f"\n🌐 <b>{texts.get_text('ADMIN_MAINTENANCE_PANEL_STATUS', 'Remnawave panel:')}</b> {panel_status['description']}"
    if panel_status.get("response_time"):
        panel_info += f"\n⚡ <b>{texts.get_text('ADMIN_MAINTENANCE_RESPONSE_TIME', 'Response time:')}</b> {panel_status['response_time']}s"
    
    message_text = texts.get_text(
        "ADMIN_MAINTENANCE_PANEL_TEXT",
        "🔧 <b>Maintenance mode management</b>\n\n"
        "{status_emoji} <b>Maintenance mode:</b> {status_text}\n"
        "{api_emoji} <b>Remnawave API:</b> {api_text}\n"
        "{monitoring_emoji} <b>Monitoring:</b> {monitoring_text}\n"
        "🛠️ <b>{autostart_label}</b> {autostart_status}\n"
        "⏱️ <b>{interval_label}</b> {interval}s\n"
        "🤖 <b>{auto_enable_label}</b> {auto_enable_status}\n"
        "{panel_info}\n"
        "{enabled_info}\n"
        "{last_check_info}\n"
        "{failures_info}\n\n"
        "ℹ️ <i>In maintenance mode, regular users cannot use the bot. Administrators have full access.</i>"
    ).format(
        status_emoji=status_emoji,
        status_text=status_text,
        api_emoji=api_emoji,
        api_text=api_text,
        monitoring_emoji=monitoring_emoji,
        monitoring_text=monitoring_text,
        autostart_label=texts.get_text('ADMIN_MAINTENANCE_MONITORING_AUTOSTART', 'Monitoring autostart:'),
        autostart_status=texts.get_text('ADMIN_MAINTENANCE_STATUS_ENABLED', 'Enabled') if status_info['monitoring_configured'] else texts.get_text('ADMIN_MAINTENANCE_STATUS_DISABLED', 'Disabled'),
        interval_label=texts.get_text('ADMIN_MAINTENANCE_CHECK_INTERVAL', 'Check interval:'),
        interval=status_info['check_interval'],
        auto_enable_label=texts.get_text('ADMIN_MAINTENANCE_AUTO_ENABLE', 'Auto-enable:'),
        auto_enable_status=texts.get_text('ADMIN_MAINTENANCE_STATUS_ENABLED', 'Enabled') if status_info['auto_enable_configured'] else texts.get_text('ADMIN_MAINTENANCE_STATUS_DISABLED', 'Disabled'),
        panel_info=panel_info,
        enabled_info=enabled_info,
        last_check_info=last_check_info,
        failures_info=failures_info,
    )
    
    await callback.message.edit_text(
        message_text,
        reply_markup=get_maintenance_keyboard(
            db_user.language, 
            status_info["is_active"], 
            status_info["monitoring_active"],
            panel_status.get("has_issues", False)
        )
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_maintenance_mode(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    is_active = maintenance_service.is_maintenance_active()
    
    texts = get_texts(db_user.language)
    if is_active:
        success = await maintenance_service.disable_maintenance()
        if success:
            await callback.answer(texts.get_text("ADMIN_MAINTENANCE_DISABLED", "Maintenance mode disabled"), show_alert=True)
        else:
            await callback.answer(texts.get_text("ADMIN_MAINTENANCE_DISABLE_ERROR", "Error disabling maintenance mode"), show_alert=True)
    else:
        await state.set_state(MaintenanceStates.waiting_for_reason)
        await callback.message.edit_text(
            texts.get_text("ADMIN_MAINTENANCE_ENABLE_PROMPT", "🔧 <b>Enable maintenance mode</b>\n\nEnter the reason for enabling maintenance or send /skip to skip:"),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.get_text("ADMIN_CANCEL", "❌ Cancel"), callback_data="maintenance_panel")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler
async def process_maintenance_reason(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    current_state = await state.get_state()
    
    if current_state != MaintenanceStates.waiting_for_reason:
        return
    
    reason = None
    if message.text and message.text != "/skip":
        reason = message.text[:200] 
    
    texts = get_texts(db_user.language)
    success = await maintenance_service.enable_maintenance(reason=reason, auto=False)
    
    if success:
        response_text = texts.get_text("ADMIN_MAINTENANCE_ENABLED", "Maintenance mode enabled")
        if reason:
            response_text += texts.get_text("ADMIN_MAINTENANCE_ENABLED_WITH_REASON", "\nReason: {reason}").format(reason=reason)
    else:
        response_text = texts.get_text("ADMIN_MAINTENANCE_ENABLE_ERROR", "Error enabling maintenance mode")
    
    await message.answer(response_text)
    await state.clear()
    
    status_info = maintenance_service.get_status_info()
    await message.answer(
        texts.get_text("ADMIN_MAINTENANCE_RETURN_PROMPT", "Return to maintenance panel:"),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.get_text("ADMIN_MAINTENANCE_PANEL_BUTTON", "🔧 Maintenance panel"), callback_data="maintenance_panel")]
        ])
    )


@admin_required  
@error_handler
async def toggle_monitoring(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    status_info = maintenance_service.get_status_info()
    
    if status_info["monitoring_active"]:
        success = await maintenance_service.stop_monitoring()
        message = texts.get_text("ADMIN_MAINTENANCE_MONITORING_STOPPED", "Monitoring stopped") if success else texts.get_text("ADMIN_MAINTENANCE_MONITORING_STOP_ERROR", "Error stopping monitoring")
    else:
        success = await maintenance_service.start_monitoring()
        message = texts.get_text("ADMIN_MAINTENANCE_MONITORING_STARTED", "Monitoring started") if success else texts.get_text("ADMIN_MAINTENANCE_MONITORING_START_ERROR", "Error starting monitoring")
    
    await callback.answer(message, show_alert=True)
    
    await show_maintenance_panel(callback, db_user, db, None)


@admin_required
@error_handler
async def force_api_check(
    callback: types.CallbackQuery,
    db_user: User, 
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    await callback.answer(texts.get_text("ADMIN_MAINTENANCE_CHECKING_API", "Checking API..."), show_alert=False)
    
    check_result = await maintenance_service.force_api_check()
    
    if check_result["success"]:
        status_text = texts.get_text("ADMIN_MAINTENANCE_API_AVAILABLE", "available") if check_result["api_available"] else texts.get_text("ADMIN_MAINTENANCE_API_UNAVAILABLE", "unavailable")
        message = texts.get_text("ADMIN_MAINTENANCE_API_CHECK_RESULT", "API {status}\nResponse time: {time}s").format(
            status=status_text, time=check_result['response_time']
        )
    else:
        message = texts.get_text("ADMIN_MAINTENANCE_API_CHECK_ERROR", "Check error: {error}").format(
            error=check_result.get('error', texts.get_text("ADMIN_MAINTENANCE_UNKNOWN_ERROR", "Unknown error"))
        )
    
    await callback.message.answer(message)
    
    await show_maintenance_panel(callback, db_user, db, None)


@admin_required
@error_handler
async def check_panel_status(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    await callback.answer(texts.get_text("ADMIN_MAINTENANCE_CHECKING_PANEL", "Checking panel status..."), show_alert=False)
    
    try:
        from app.services.remnawave_service import RemnaWaveService
        rw_service = RemnaWaveService()
        
        status_data = await rw_service.check_panel_health()
        
        status_text = {
            "online": texts.get_text("ADMIN_MAINTENANCE_PANEL_ONLINE", "🟢 Panel is working normally"),
            "offline": texts.get_text("ADMIN_MAINTENANCE_PANEL_OFFLINE", "🔴 Panel is unavailable"), 
            "degraded": texts.get_text("ADMIN_MAINTENANCE_PANEL_DEGRADED", "🟡 Panel is working with issues")
        }.get(status_data["status"], texts.get_text("ADMIN_MAINTENANCE_PANEL_UNKNOWN", "❓ Status unknown"))
        
        message_parts = [
            texts.get_text("ADMIN_MAINTENANCE_PANEL_STATUS_TITLE", "🌐 <b>Remnawave panel status</b>"),
            status_text,
            texts.get_text("ADMIN_MAINTENANCE_PANEL_RESPONSE_TIME", "⚡ Response time: {time}s").format(time=status_data.get('response_time', 0)),
            texts.get_text("ADMIN_MAINTENANCE_PANEL_USERS_ONLINE", "👥 Users online: {count}").format(count=status_data.get('users_online', 0)),
            texts.get_text("ADMIN_MAINTENANCE_PANEL_NODES_ONLINE", "🖥️ Nodes online: {online}/{total}").format(
                online=status_data.get('nodes_online', 0), total=status_data.get('total_nodes', 0)
            )
        ]

        attempts_used = status_data.get("attempts_used")
        if attempts_used:
            message_parts.append(texts.get_text("ADMIN_MAINTENANCE_PANEL_ATTEMPTS", "🔁 Check attempts: {count}").format(count=attempts_used))

        if status_data.get("api_error"):
            message_parts.append(texts.get_text("ADMIN_MAINTENANCE_PANEL_ERROR", "❌ Error: {error}").format(error=status_data['api_error'][:100]))
        
        message = "\n".join(message_parts)
        
        await callback.message.answer(message, parse_mode="HTML")
        
    except Exception as e:
        await callback.message.answer(texts.get_text("ADMIN_MAINTENANCE_PANEL_CHECK_ERROR", "❌ Status check error: {error}").format(error=str(e)))


@admin_required
@error_handler
async def send_manual_notification(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    await state.set_state(MaintenanceStates.waiting_for_notification_message)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text=texts.get_text("ADMIN_MAINTENANCE_NOTIFY_ONLINE", "🟢 Online"), callback_data="manual_notify_online"),
            types.InlineKeyboardButton(text=texts.get_text("ADMIN_MAINTENANCE_NOTIFY_OFFLINE", "🔴 Offline"), callback_data="manual_notify_offline")
        ],
        [
            types.InlineKeyboardButton(text=texts.get_text("ADMIN_MAINTENANCE_NOTIFY_DEGRADED", "🟡 Issues"), callback_data="manual_notify_degraded"),
            types.InlineKeyboardButton(text=texts.get_text("ADMIN_MAINTENANCE_NOTIFY_MAINTENANCE", "🔧 Maintenance"), callback_data="manual_notify_maintenance")
        ],
        [types.InlineKeyboardButton(text=texts.get_text("ADMIN_CANCEL", "❌ Cancel"), callback_data="maintenance_panel")]
    ])
    
    await callback.message.edit_text(
        texts.get_text("ADMIN_MAINTENANCE_MANUAL_NOTIFY_TITLE", "📢 <b>Manual notification</b>\n\nSelect status for notification:"),
        reply_markup=keyboard
    )


@admin_required
@error_handler
async def handle_manual_notification(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    status_map = {
        "manual_notify_online": "online",
        "manual_notify_offline": "offline", 
        "manual_notify_degraded": "degraded",
        "manual_notify_maintenance": "maintenance"
    }
    
    texts = get_texts(db_user.language)
    status = status_map.get(callback.data)
    if not status:
        await callback.answer(texts.get_text("ADMIN_MAINTENANCE_UNKNOWN_STATUS", "Unknown status"))
        return
    
    await state.update_data(notification_status=status)
    
    status_names = {
        "online": texts.get_text("ADMIN_MAINTENANCE_NOTIFY_ONLINE", "🟢 Online"),
        "offline": texts.get_text("ADMIN_MAINTENANCE_NOTIFY_OFFLINE", "🔴 Offline"),
        "degraded": texts.get_text("ADMIN_MAINTENANCE_NOTIFY_DEGRADED", "🟡 Issues"), 
        "maintenance": texts.get_text("ADMIN_MAINTENANCE_NOTIFY_MAINTENANCE", "🔧 Maintenance")
    }
    
    await callback.message.edit_text(
        texts.get_text("ADMIN_MAINTENANCE_SENDING_NOTIFY", "📢 <b>Sending notification: {status}</b>\n\nEnter notification message or send /skip to send without additional text:").format(status=status_names[status]),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.get_text("ADMIN_CANCEL", "❌ Cancel"), callback_data="maintenance_panel")]
        ])
    )


@admin_required
@error_handler
async def process_notification_message(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    current_state = await state.get_state()
    
    if current_state != MaintenanceStates.waiting_for_notification_message:
        return
    
    texts = get_texts(db_user.language)
    data = await state.get_data()
    status = data.get("notification_status")
    
    if not status:
        await message.answer(texts.get_text("ADMIN_MAINTENANCE_STATUS_NOT_SELECTED", "Error: status not selected"))
        await state.clear()
        return
    
    notification_message = ""
    if message.text and message.text != "/skip":
        notification_message = message.text[:300]
    
    try:
        from app.services.remnawave_service import RemnaWaveService
        rw_service = RemnaWaveService()
        
        success = await rw_service.send_manual_status_notification(
            message.bot, 
            status, 
            notification_message
        )
        
        if success:
            await message.answer(texts.get_text("ADMIN_MAINTENANCE_NOTIFICATION_SENT", "✅ Notification sent"))
        else:
            await message.answer(texts.get_text("ADMIN_MAINTENANCE_NOTIFICATION_ERROR", "❌ Error sending notification"))
            
    except Exception as e:
        logger.error(f"Error sending manual notification: {e}")
        await message.answer(texts.get_text("ADMIN_MAINTENANCE_NOTIFICATION_ERROR_DETAIL", "❌ Error: {error}").format(error=str(e)))
    
    await state.clear()
    
    await message.answer(
        texts.get_text("ADMIN_MAINTENANCE_RETURN_PROMPT", "Return to maintenance panel:"),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.get_text("ADMIN_MAINTENANCE_PANEL_BUTTON", "🔧 Maintenance panel"), callback_data="maintenance_panel")]
        ])
    )


@admin_required
@error_handler
async def back_to_admin_panel(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    await callback.message.edit_text(
        texts.ADMIN_PANEL,
        reply_markup=get_admin_main_keyboard(db_user.language)
    )
    await callback.answer()


def register_handlers(dp: Dispatcher):
    
    dp.callback_query.register(
        show_maintenance_panel,
        F.data == "maintenance_panel"
    )
    
    dp.callback_query.register(
        toggle_maintenance_mode,
        F.data == "maintenance_toggle"
    )
    
    dp.callback_query.register(
        toggle_monitoring,
        F.data == "maintenance_monitoring"
    )
    
    dp.callback_query.register(
        force_api_check,
        F.data == "maintenance_check_api"
    )
    
    dp.callback_query.register(
        check_panel_status,
        F.data == "maintenance_check_panel"
    )
    
    dp.callback_query.register(
        send_manual_notification,
        F.data == "maintenance_manual_notify"
    )
    
    dp.callback_query.register(
        handle_manual_notification,
        F.data.startswith("manual_notify_")
    )
    
    dp.callback_query.register(
        back_to_admin_panel,
        F.data == "admin_panel"
    )
    
    dp.message.register(
        process_maintenance_reason,
        MaintenanceStates.waiting_for_reason
    )
    
    dp.message.register(
        process_notification_message,
        MaintenanceStates.waiting_for_notification_message
    )
