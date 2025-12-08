import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from app.config import settings
from app.database.database import get_db
from app.services.monitoring_service import monitoring_service
from app.utils.decorators import admin_required
from app.utils.pagination import paginate_list
from app.keyboards.admin import get_monitoring_keyboard, get_admin_main_keyboard
from app.localization.texts import get_texts
from app.services.notification_settings_service import NotificationSettingsService
from app.states import AdminStates

logger = logging.getLogger(__name__)
router = Router()


def _format_toggle(enabled: bool, language: str = "en") -> str:
    texts = get_texts(language)
    return texts.t("ENABLED", "🟢 On") if enabled else texts.t("DISABLED", "🔴 Off")


def _build_notification_settings_view(language: str):
    texts = get_texts(language)
    config = NotificationSettingsService.get_config()

    second_percent = NotificationSettingsService.get_second_wave_discount_percent()
    second_hours = NotificationSettingsService.get_second_wave_valid_hours()
    third_percent = NotificationSettingsService.get_third_wave_discount_percent()
    third_hours = NotificationSettingsService.get_third_wave_valid_hours()
    third_days = NotificationSettingsService.get_third_wave_trigger_days()

    trial_1h_status = _format_toggle(config["trial_inactive_1h"].get("enabled", True), language)
    trial_24h_status = _format_toggle(config["trial_inactive_24h"].get("enabled", True), language)
    trial_channel_status = _format_toggle(
        config["trial_channel_unsubscribed"].get("enabled", True), language
    )
    expired_1d_status = _format_toggle(config["expired_1d"].get("enabled", True), language)
    second_wave_status = _format_toggle(config["expired_second_wave"].get("enabled", True), language)
    third_wave_status = _format_toggle(config["expired_third_wave"].get("enabled", True), language)

    summary_text = texts.t("ADMIN_MON_NOTIFICATIONS_TITLE", "🔔 <b>User Notifications</b>") + "\n\n"
    summary_text += texts.t("ADMIN_MON_NOTIFY_TRIAL_1H", "• 1 hour after trial: {status}").format(status=trial_1h_status) + "\n"
    summary_text += texts.t("ADMIN_MON_NOTIFY_TRIAL_24H", "• 24 hours after trial: {status}").format(status=trial_24h_status) + "\n"
    summary_text += texts.t("ADMIN_MON_NOTIFY_CHANNEL_UNSUB", "• Channel unsubscription: {status}").format(status=trial_channel_status) + "\n"
    summary_text += texts.t("ADMIN_MON_NOTIFY_EXPIRED_1D", "• 1 day after expiration: {status}").format(status=expired_1d_status) + "\n"
    summary_text += texts.t("ADMIN_MON_NOTIFY_2_3_DAYS", "• 2-3 days (discount {percent}% / {hours} h): {status}").format(
        percent=second_percent, hours=second_hours, status=second_wave_status
    ) + "\n"
    summary_text += texts.t("ADMIN_MON_NOTIFY_N_DAYS", "• {days} days (discount {percent}% / {hours} h): {status}").format(
        days=third_days, percent=third_percent, hours=third_hours, status=third_wave_status
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{trial_1h_status} • {texts.t('ADMIN_MON_NOTIFY_TRIAL_1H_LABEL', '1 hour after trial')}", callback_data="admin_mon_notify_toggle_trial_1h")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_TEST_TRIAL_1H", "🧪 Test: 1 hour after trial"), callback_data="admin_mon_notify_preview_trial_1h")],
        [InlineKeyboardButton(text=f"{trial_24h_status} • {texts.t('ADMIN_MON_NOTIFY_TRIAL_24H_LABEL', '24 hours after trial')}", callback_data="admin_mon_notify_toggle_trial_24h")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_TEST_TRIAL_24H", "🧪 Test: 24 hours after trial"), callback_data="admin_mon_notify_preview_trial_24h")],
        [InlineKeyboardButton(text=f"{trial_channel_status} • {texts.t('ADMIN_MON_NOTIFY_CHANNEL_UNSUB_LABEL', 'Channel unsubscription')}", callback_data="admin_mon_notify_toggle_trial_channel")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_TEST_CHANNEL_UNSUB", "🧪 Test: channel unsubscription"), callback_data="admin_mon_notify_preview_trial_channel")],
        [InlineKeyboardButton(text=f"{expired_1d_status} • {texts.t('ADMIN_MON_NOTIFY_EXPIRED_1D_LABEL', '1 day after expiration')}", callback_data="admin_mon_notify_toggle_expired_1d")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_TEST_EXPIRED_1D", "🧪 Test: 1 day after expiration"), callback_data="admin_mon_notify_preview_expired_1d")],
        [InlineKeyboardButton(text=f"{second_wave_status} • {texts.t('ADMIN_MON_NOTIFY_2_3_DAYS_LABEL', '2-3 days with discount')}", callback_data="admin_mon_notify_toggle_expired_2d")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_TEST_2_3_DAYS", "🧪 Test: discount 2-3 days"), callback_data="admin_mon_notify_preview_expired_2d")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_EDIT_2_3_DISCOUNT", "✏️ Discount 2-3 days: {percent}%").format(percent=second_percent), callback_data="admin_mon_notify_edit_2d_percent")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_EDIT_2_3_HOURS", "⏱️ Discount period 2-3 days: {hours} h").format(hours=second_hours), callback_data="admin_mon_notify_edit_2d_hours")],
        [InlineKeyboardButton(text=f"{third_wave_status} • {texts.t('ADMIN_MON_NOTIFY_N_DAYS_LABEL', '{days} days with discount').format(days=third_days)}", callback_data="admin_mon_notify_toggle_expired_nd")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_TEST_N_DAYS", "🧪 Test: discount after days"), callback_data="admin_mon_notify_preview_expired_nd")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_EDIT_N_DISCOUNT", "✏️ Discount {days} days: {percent}%").format(days=third_days, percent=third_percent), callback_data="admin_mon_notify_edit_nd_percent")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_EDIT_N_HOURS", "⏱️ Discount period {days} days: {hours} h").format(days=third_days, hours=third_hours), callback_data="admin_mon_notify_edit_nd_hours")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_NOTIFY_THRESHOLD", "📆 Notification threshold: {days} days").format(days=third_days), callback_data="admin_mon_notify_edit_nd_threshold")],
        [InlineKeyboardButton(text=texts.t("ADMIN_MON_SEND_ALL_TESTS", "🧪 Send all tests"), callback_data="admin_mon_notify_preview_all")],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_mon_settings")],
    ])

    return summary_text, keyboard


def _build_notification_preview_message(language: str, notification_type: str):
    texts = get_texts(language)
    now = datetime.now()
    price_30_days = settings.format_price(settings.PRICE_30_DAYS)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    header = texts.t("ADMIN_MON_TEST_NOTIFICATION_HEADER", "🧪 <b>Monitoring Test Notification</b>") + "\n\n"

    if notification_type == "trial_inactive_1h":
        template = texts.get(
            "TRIAL_INACTIVE_1H",
            (
                "⏳ <b>An hour has passed without connection</b>\n\n"
                "If you have difficulties getting started, please use the instructions."
            ),
        )
        message = template.format(
            price=price_30_days,
            end_date=(now + timedelta(days=settings.TRIAL_DURATION_DAYS)).strftime("%d.%m.%Y %H:%M"),
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                        callback_data="subscription_connect",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("MY_SUBSCRIPTION_BUTTON", "📱 My subscription"),
                        callback_data="menu_subscription",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("SUPPORT_BUTTON", "🆘 Support"),
                        callback_data="menu_support",
                    )
                ],
            ]
        )
    elif notification_type == "trial_inactive_24h":
        template = texts.get(
            "TRIAL_INACTIVE_24H",
            (
                "⏳ <b>You haven't connected to VPN yet</b>\n\n"
                "24 hours have passed since trial activation, but no traffic was recorded."
                "\n\nPress the button below to connect."
            ),
        )
        message = template.format(
            price=price_30_days,
            end_date=(now + timedelta(days=1)).strftime("%d.%m.%Y %H:%M"),
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                        callback_data="subscription_connect",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("MY_SUBSCRIPTION_BUTTON", "📱 My subscription"),
                        callback_data="menu_subscription",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("SUPPORT_BUTTON", "🆘 Support"),
                        callback_data="menu_support",
                    )
                ],
            ]
        )
    elif notification_type == "trial_channel_unsubscribed":
        template = texts.get(
            "TRIAL_CHANNEL_UNSUBSCRIBED",
            (
                "🚫 <b>Access suspended</b>\n\n"
                "We couldn't find your subscription to our channel, so your trial subscription has been disabled.\n\n"
                "Subscribe to the channel and press \"{check_button}\" to restore access."
            ),
        )
        check_button = texts.t("CHANNEL_CHECK_BUTTON", "✅ I subscribed")
        message = template.format(check_button=check_button)
        buttons: list[list[InlineKeyboardButton]] = []
        if settings.CHANNEL_LINK:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=texts.t("CHANNEL_SUBSCRIBE_BUTTON", "🔗 Subscribe"),
                        url=settings.CHANNEL_LINK,
                    )
                ]
            )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=check_button,
                    callback_data="sub_channel_check",
                )
            ]
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    elif notification_type == "expired_1d":
        template = texts.get(
            "SUBSCRIPTION_EXPIRED_1D",
            (
                "⛔ <b>Subscription expired</b>\n\n"
                "Access was disabled on {end_date}. Renew your subscription to return to the service."
            ),
        )
        message = template.format(
            end_date=(now - timedelta(days=1)).strftime("%d.%m.%Y %H:%M"),
            price=price_30_days,
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=texts.t("SUBSCRIPTION_EXTEND", "💎 Extend subscription"),
                        callback_data="subscription_extend",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("BALANCE_TOPUP", "💳 Top up balance"),
                        callback_data="balance_topup",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("SUPPORT_BUTTON", "🆘 Support"),
                        callback_data="menu_support",
                    )
                ],
            ]
        )
    elif notification_type == "expired_2d":
        percent = NotificationSettingsService.get_second_wave_discount_percent()
        valid_hours = NotificationSettingsService.get_second_wave_valid_hours()
        template = texts.get(
            "SUBSCRIPTION_EXPIRED_SECOND_WAVE",
            (
                "🔥 <b>{percent}% discount on renewal</b>\n\n"
                "Activate this offer to get an additional discount. "
                "It stacks with your promo group and is valid until {expires_at}."
            ),
        )
        message = template.format(
            percent=percent,
            expires_at=(now + timedelta(hours=valid_hours)).strftime("%d.%m.%Y %H:%M"),
            trigger_days=3,
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=texts.t("CLAIM_DISCOUNT", "🎁 Get discount"),
                        callback_data="claim_discount_preview",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("SUBSCRIPTION_EXTEND", "💎 Extend subscription"),
                        callback_data="subscription_extend",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("BALANCE_TOPUP", "💳 Top up balance"),
                        callback_data="balance_topup",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("SUPPORT_BUTTON", "🆘 Support"),
                        callback_data="menu_support",
                    )
                ],
            ]
        )
    elif notification_type == "expired_nd":
        percent = NotificationSettingsService.get_third_wave_discount_percent()
        valid_hours = NotificationSettingsService.get_third_wave_valid_hours()
        trigger_days = NotificationSettingsService.get_third_wave_trigger_days()
        template = texts.get(
            "SUBSCRIPTION_EXPIRED_THIRD_WAVE",
            (
                "🎁 <b>Individual {percent}% discount</b>\n\n"
                "{trigger_days} days without subscription — come back and activate an additional discount. "
                "It stacks with promo group and is valid until {expires_at}."
            ),
        )
        message = template.format(
            percent=percent,
            trigger_days=trigger_days,
            expires_at=(now + timedelta(hours=valid_hours)).strftime("%d.%m.%Y %H:%M"),
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=texts.t("CLAIM_DISCOUNT", "🎁 Get discount"),
                        callback_data="claim_discount_preview",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("SUBSCRIPTION_EXTEND", "💎 Extend subscription"),
                        callback_data="subscription_extend",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("BALANCE_TOPUP", "💳 Top up balance"),
                        callback_data="balance_topup",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=texts.t("SUPPORT_BUTTON", "🆘 Support"),
                        callback_data="menu_support",
                    )
                ],
            ]
        )
    else:
        raise ValueError(f"Unsupported notification type: {notification_type}")

    footer = texts.t("ADMIN_MON_TEST_FOOTER", "\n\n<i>This message was sent only to you for design verification.</i>")
    return header + message + footer, keyboard


async def _send_notification_preview(bot, chat_id: int, language: str, notification_type: str) -> None:
    message, keyboard = _build_notification_preview_message(language, notification_type)
    await bot.send_message(
        chat_id,
        message,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def _render_notification_settings(callback: CallbackQuery) -> None:
    language = (callback.from_user.language_code or settings.DEFAULT_LANGUAGE)
    text, keyboard = _build_notification_settings_view(language)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


async def _render_notification_settings_for_state(
    bot,
    chat_id: int,
    message_id: int,
    language: str,
    business_connection_id: str | None = None,
) -> None:
    text, keyboard = _build_notification_settings_view(language)

    edit_kwargs = {
        "text": text,
        "chat_id": chat_id,
        "message_id": message_id,
        "parse_mode": "HTML",
        "reply_markup": keyboard,
    }

    if business_connection_id:
        edit_kwargs["business_connection_id"] = business_connection_id

    try:
        await bot.edit_message_text(**edit_kwargs)
    except TelegramBadRequest as exc:
        if "no text in the message to edit" in (exc.message or "").lower():
            caption_kwargs = {
                "chat_id": chat_id,
                "message_id": message_id,
                "caption": text,
                "parse_mode": "HTML",
                "reply_markup": keyboard,
            }

            if business_connection_id:
                caption_kwargs["business_connection_id"] = business_connection_id

            await bot.edit_message_caption(**caption_kwargs)
        else:
            raise

@router.callback_query(F.data == "admin_monitoring")
@admin_required
async def admin_monitoring_menu(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        async for db in get_db():
            status = await monitoring_service.get_monitoring_status(db)
            
            running_status = texts.t("ADMIN_MON_STATUS_RUNNING", "🟢 Running") if status['is_running'] else texts.t("ADMIN_MON_STATUS_STOPPED", "🔴 Stopped")
            last_update = status['last_update'].strftime('%H:%M:%S') if status['last_update'] else texts.t("NEVER", "Never")
            
            text = texts.t(
                "ADMIN_MON_MENU_TEXT",
                """
🔍 <b>Monitoring System</b>

📊 <b>Status:</b> {running_status}
🕐 <b>Last update:</b> {last_update}
⚙️ <b>Check interval:</b> {interval} min

📈 <b>Statistics for 24 hours:</b>
• Total events: {total_events}
• Successful: {successful}
• Errors: {failed}
• Success rate: {success_rate}%

🔧 Select an action:
"""
            ).format(
                running_status=running_status,
                last_update=last_update,
                interval=settings.MONITORING_INTERVAL,
                total_events=status['stats_24h']['total_events'],
                successful=status['stats_24h']['successful'],
                failed=status['stats_24h']['failed'],
                success_rate=status['stats_24h']['success_rate']
            )
            
            keyboard = get_monitoring_keyboard(language)
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            break
            
    except Exception as e:
        logger.error(f"Error in admin monitoring menu: {e}")
        await callback.answer(texts.t("ADMIN_MON_ERROR_LOADING", "❌ Error loading data"), show_alert=True)


@router.callback_query(F.data == "admin_mon_settings")
@admin_required
async def admin_monitoring_settings(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        enabled_text = texts.t("ENABLED", "🟢 Enabled")
        disabled_text = texts.t("DISABLED", "🔴 Disabled")
        global_status = enabled_text if NotificationSettingsService.are_notifications_globally_enabled() else disabled_text
        second_percent = NotificationSettingsService.get_second_wave_discount_percent()
        third_percent = NotificationSettingsService.get_third_wave_discount_percent()
        third_days = NotificationSettingsService.get_third_wave_trigger_days()

        text = texts.t(
            "ADMIN_MON_SETTINGS_TEXT",
            "⚙️ <b>Monitoring settings</b>\n\n🔔 <b>User notifications:</b> {global_status}\n• Discount 2-3 days: {second_percent}%\n• Discount after {third_days} days: {third_percent}%\n\nSelect a section to configure."
        ).format(
            global_status=global_status,
            second_percent=second_percent,
            third_days=third_days,
            third_percent=third_percent
        )

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=texts.t("ADMIN_MON_BTN_USER_NOTIFICATIONS", "🔔 User notifications"), callback_data="admin_mon_notify_settings")],
            [InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_settings")],
        ])

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error displaying monitoring settings: {e}")
        await callback.answer(texts.t("ADMIN_MON_ERROR_OPENING_SETTINGS", "❌ Failed to open settings"), show_alert=True)


@router.callback_query(F.data == "admin_mon_notify_settings")
@admin_required
async def admin_notify_settings(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        await _render_notification_settings(callback)
    except Exception as e:
        logger.error(f"Error displaying notification settings: {e}")
        await callback.answer(texts.t("ADMIN_MON_ERROR_LOADING_SETTINGS", "❌ Failed to load settings"), show_alert=True)


@router.callback_query(F.data == "admin_mon_notify_toggle_trial_1h")
@admin_required
async def toggle_trial_1h_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    enabled = NotificationSettingsService.is_trial_inactive_1h_enabled()
    NotificationSettingsService.set_trial_inactive_1h_enabled(not enabled)
    await callback.answer(texts.t("ENABLED", "✅ Enabled") if not enabled else texts.t("DISABLED", "⏸️ Disabled"))
    await _render_notification_settings(callback)


@router.callback_query(F.data == "admin_mon_notify_preview_trial_1h")
@admin_required
async def preview_trial_1h_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        await _send_notification_preview(callback.bot, callback.from_user.id, language, "trial_inactive_1h")
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_SENT", "✅ Preview sent"))
    except Exception as exc:
        logger.error("Failed to send trial 1h preview: %s", exc)
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_FAILED", "❌ Failed to send test"), show_alert=True)


@router.callback_query(F.data == "admin_mon_notify_toggle_trial_24h")
@admin_required
async def toggle_trial_24h_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    enabled = NotificationSettingsService.is_trial_inactive_24h_enabled()
    NotificationSettingsService.set_trial_inactive_24h_enabled(not enabled)
    await callback.answer(texts.t("ENABLED", "✅ Enabled") if not enabled else texts.t("DISABLED", "⏸️ Disabled"))
    await _render_notification_settings(callback)


@router.callback_query(F.data == "admin_mon_notify_preview_trial_24h")
@admin_required
async def preview_trial_24h_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        await _send_notification_preview(callback.bot, callback.from_user.id, language, "trial_inactive_24h")
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_SENT", "✅ Preview sent"))
    except Exception as exc:
        logger.error("Failed to send trial 24h preview: %s", exc)
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_FAILED", "❌ Failed to send test"), show_alert=True)


@router.callback_query(F.data == "admin_mon_notify_toggle_trial_channel")
@admin_required
async def toggle_trial_channel_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    enabled = NotificationSettingsService.is_trial_channel_unsubscribed_enabled()
    NotificationSettingsService.set_trial_channel_unsubscribed_enabled(not enabled)
    await callback.answer(texts.t("ENABLED", "✅ Enabled") if not enabled else texts.t("DISABLED", "⏸️ Disabled"))
    await _render_notification_settings(callback)


@router.callback_query(F.data == "admin_mon_notify_preview_trial_channel")
@admin_required
async def preview_trial_channel_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        await _send_notification_preview(callback.bot, callback.from_user.id, language, "trial_channel_unsubscribed")
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_SENT", "✅ Preview sent"))
    except Exception as exc:
        logger.error("Failed to send trial channel preview: %s", exc)
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_FAILED", "❌ Failed to send test"), show_alert=True)


@router.callback_query(F.data == "admin_mon_notify_toggle_expired_1d")
@admin_required
async def toggle_expired_1d_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    enabled = NotificationSettingsService.is_expired_1d_enabled()
    NotificationSettingsService.set_expired_1d_enabled(not enabled)
    await callback.answer(texts.t("ENABLED", "✅ Enabled") if not enabled else texts.t("DISABLED", "⏸️ Disabled"))
    await _render_notification_settings(callback)


@router.callback_query(F.data == "admin_mon_notify_preview_expired_1d")
@admin_required
async def preview_expired_1d_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        await _send_notification_preview(callback.bot, callback.from_user.id, language, "expired_1d")
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_SENT", "✅ Preview sent"))
    except Exception as exc:
        logger.error("Failed to send expired 1d preview: %s", exc)
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_FAILED", "❌ Failed to send test"), show_alert=True)


@router.callback_query(F.data == "admin_mon_notify_toggle_expired_2d")
@admin_required
async def toggle_second_wave_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    enabled = NotificationSettingsService.is_second_wave_enabled()
    NotificationSettingsService.set_second_wave_enabled(not enabled)
    await callback.answer(texts.t("ENABLED", "✅ Enabled") if not enabled else texts.t("DISABLED", "⏸️ Disabled"))
    await _render_notification_settings(callback)


@router.callback_query(F.data == "admin_mon_notify_preview_expired_2d")
@admin_required
async def preview_second_wave_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        await _send_notification_preview(callback.bot, callback.from_user.id, language, "expired_2d")
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_SENT", "✅ Preview sent"))
    except Exception as exc:
        logger.error("Failed to send second wave preview: %s", exc)
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_FAILED", "❌ Failed to send test"), show_alert=True)


@router.callback_query(F.data == "admin_mon_notify_toggle_expired_nd")
@admin_required
async def toggle_third_wave_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    enabled = NotificationSettingsService.is_third_wave_enabled()
    NotificationSettingsService.set_third_wave_enabled(not enabled)
    await callback.answer(texts.t("ENABLED", "✅ Enabled") if not enabled else texts.t("DISABLED", "⏸️ Disabled"))
    await _render_notification_settings(callback)


@router.callback_query(F.data == "admin_mon_notify_preview_expired_nd")
@admin_required
async def preview_third_wave_notification(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        await _send_notification_preview(callback.bot, callback.from_user.id, language, "expired_nd")
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_SENT", "✅ Preview sent"))
    except Exception as exc:
        logger.error("Failed to send third wave preview: %s", exc)
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_FAILED", "❌ Failed to send test"), show_alert=True)


@router.callback_query(F.data == "admin_mon_notify_preview_all")
@admin_required
async def preview_all_notifications(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        chat_id = callback.from_user.id
        for notification_type in [
            "trial_inactive_1h",
            "trial_inactive_24h",
            "trial_channel_unsubscribed",
            "expired_1d",
            "expired_2d",
            "expired_nd",
        ]:
            await _send_notification_preview(callback.bot, chat_id, language, notification_type)
        await callback.answer(texts.t("ADMIN_MON_ALL_PREVIEWS_SENT", "✅ All test notifications sent"))
    except Exception as exc:
        logger.error("Failed to send all notification previews: %s", exc)
        await callback.answer(texts.t("ADMIN_MON_PREVIEW_FAILED", "❌ Failed to send tests"), show_alert=True)


async def _start_notification_value_edit(
    callback: CallbackQuery,
    state: FSMContext,
    setting_key: str,
    field: str,
    prompt_key: str,
    default_prompt: str,
):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    await state.set_state(AdminStates.editing_notification_value)
    await state.update_data(
        notification_setting_key=setting_key,
        notification_setting_field=field,
        settings_message_chat=callback.message.chat.id,
        settings_message_id=callback.message.message_id,
        settings_business_connection_id=(
            str(getattr(callback.message, "business_connection_id", None))
            if getattr(callback.message, "business_connection_id", None) is not None
            else None
        ),
        settings_language=language,
    )
    texts = get_texts(language)
    await callback.answer()
    await callback.message.answer(texts.get(prompt_key, default_prompt))


@router.callback_query(F.data == "admin_mon_notify_edit_2d_percent")
@admin_required
async def edit_second_wave_percent(callback: CallbackQuery, state: FSMContext):
    await _start_notification_value_edit(
        callback,
        state,
        "expired_second_wave",
        "percent",
        "NOTIFY_PROMPT_SECOND_PERCENT",
        "Enter new discount percentage for 2-3 day notification (0-100):",
    )


@router.callback_query(F.data == "admin_mon_notify_edit_2d_hours")
@admin_required
async def edit_second_wave_hours(callback: CallbackQuery, state: FSMContext):
    await _start_notification_value_edit(
        callback,
        state,
        "expired_second_wave",
        "hours",
        "NOTIFY_PROMPT_SECOND_HOURS",
        "Enter discount validity hours (1-168):",
    )


@router.callback_query(F.data == "admin_mon_notify_edit_nd_percent")
@admin_required
async def edit_third_wave_percent(callback: CallbackQuery, state: FSMContext):
    await _start_notification_value_edit(
        callback,
        state,
        "expired_third_wave",
        "percent",
        "NOTIFY_PROMPT_THIRD_PERCENT",
        "Enter new discount percentage for late offer (0-100):",
    )


@router.callback_query(F.data == "admin_mon_notify_edit_nd_hours")
@admin_required
async def edit_third_wave_hours(callback: CallbackQuery, state: FSMContext):
    await _start_notification_value_edit(
        callback,
        state,
        "expired_third_wave",
        "hours",
        "NOTIFY_PROMPT_THIRD_HOURS",
        "Enter discount validity hours (1-168):",
    )


@router.callback_query(F.data == "admin_mon_notify_edit_nd_threshold")
@admin_required
async def edit_third_wave_threshold(callback: CallbackQuery, state: FSMContext):
    await _start_notification_value_edit(
        callback,
        state,
        "expired_third_wave",
        "trigger",
        "NOTIFY_PROMPT_THIRD_DAYS",
        "After how many days after expiration to send offer? (minimum 2):",
    )


@router.callback_query(F.data == "admin_mon_start")
@admin_required
async def start_monitoring_callback(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        if monitoring_service.is_running:
            await callback.answer(texts.t("ADMIN_MON_ALREADY_RUNNING", "ℹ️ Monitoring is already running"))
            return
        
        if not monitoring_service.bot:
            monitoring_service.bot = callback.bot
        
        asyncio.create_task(monitoring_service.start_monitoring())
        
        await callback.answer(texts.t("ADMIN_MON_STARTED", "✅ Monitoring started!"))
        
        await admin_monitoring_menu(callback)
        
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        await callback.answer(texts.t("ADMIN_MON_START_ERROR", "❌ Start error: {error}").format(error=str(e)), show_alert=True)


@router.callback_query(F.data == "admin_mon_stop")
@admin_required
async def stop_monitoring_callback(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        if not monitoring_service.is_running:
            await callback.answer(texts.t("ADMIN_MON_ALREADY_STOPPED", "ℹ️ Monitoring is already stopped"))
            return
        
        monitoring_service.stop_monitoring()
        await callback.answer(texts.t("ADMIN_MON_STOPPED", "⏹️ Monitoring stopped!"))
        
        await admin_monitoring_menu(callback)
        
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        await callback.answer(texts.t("ADMIN_MON_STOP_ERROR", "❌ Stop error: {error}").format(error=str(e)), show_alert=True)


@router.callback_query(F.data == "admin_mon_force_check")
@admin_required
async def force_check_callback(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        await callback.answer(texts.t("ADMIN_MON_CHECKING", "⏳ Running subscription check..."))
        
        async for db in get_db():
            results = await monitoring_service.force_check_subscriptions(db)
            
            text = texts.t(
                "ADMIN_MON_FORCE_CHECK_RESULT",
                """
✅ <b>Forced check completed</b>

📊 <b>Check results:</b>
• Expired subscriptions: {expired}
• Expiring subscriptions: {expiring}
• Ready for autopay: {autopay_ready}

🕐 <b>Check time:</b> {time}

Press "Back" to return to monitoring menu.
"""
            ).format(
                expired=results['expired'],
                expiring=results['expiring'],
                autopay_ready=results['autopay_ready'],
                time=datetime.now().strftime('%H:%M:%S')
            )
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=texts.BACK, callback_data="admin_monitoring")]
            ])
            
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            break
            
    except Exception as e:
        logger.error(f"Error in forced check: {e}")
        await callback.answer(texts.t("ADMIN_MON_CHECK_ERROR", "❌ Check error: {error}").format(error=str(e)), show_alert=True)


@router.callback_query(F.data.startswith("admin_mon_logs"))
@admin_required
async def monitoring_logs_callback(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        page = 1
        if "_page_" in callback.data:
            page = int(callback.data.split("_page_")[1])
        
        async for db in get_db():
            all_logs = await monitoring_service.get_monitoring_logs(db, limit=1000)
            
            if not all_logs:
                text = texts.t("ADMIN_MON_LOGS_EMPTY", "📋 <b>Monitoring logs are empty</b>\n\nSystem has not performed checks yet.")
                keyboard = get_monitoring_logs_back_keyboard(language)
                await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
                return
            
            per_page = 8
            paginated_logs = paginate_list(all_logs, page=page, per_page=per_page)
            
            text = texts.t("ADMIN_MON_LOGS_TITLE", "📋 <b>Monitoring logs</b> (page {page}/{total})\n\n").format(page=page, total=paginated_logs.total_pages)
            
            for log in paginated_logs.items:
                icon = "✅" if log['is_success'] else "❌"
                time_str = log['created_at'].strftime('%m-%d %H:%M')
                event_type = log['event_type'].replace('_', ' ').title()
                
                message = log['message']
                if len(message) > 45:
                    message = message[:45] + "..."
                
                text += f"{icon} <code>{time_str}</code> {event_type}\n"
                text += f"   📄 {message}\n\n"
            
            total_success = sum(1 for log in all_logs if log['is_success'])
            total_failed = len(all_logs) - total_success
            success_rate = round(total_success / len(all_logs) * 100, 1) if all_logs else 0
            
            text += texts.t(
                "ADMIN_MON_LOGS_STATS",
                "📊 <b>Overall statistics:</b>\n• Total events: {total}\n• Successful: {success}\n• Errors: {failed}\n• Success rate: {rate}%"
            ).format(total=len(all_logs), success=total_success, failed=total_failed, rate=success_rate)
            
            keyboard = get_monitoring_logs_keyboard(page, paginated_logs.total_pages, language)
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            break
            
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        await callback.answer(texts.t("ADMIN_MON_LOGS_ERROR", "❌ Error getting logs"), show_alert=True)


@router.callback_query(F.data == "admin_mon_clear_logs")
@admin_required
async def clear_logs_callback(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        async for db in get_db():
            deleted_count = await monitoring_service.cleanup_old_logs(db, days=0) 
            
            if deleted_count > 0:
                await callback.answer(texts.t("ADMIN_MON_LOGS_DELETED", "🗑️ Deleted {count} log entries").format(count=deleted_count))
            else:
                await callback.answer(texts.t("ADMIN_MON_LOGS_ALREADY_EMPTY", "ℹ️ Logs are already empty"))
            
            await monitoring_logs_callback(callback)
            break
            
    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        await callback.answer(texts.t("ADMIN_MON_LOGS_CLEAR_ERROR", "❌ Clear error: {error}").format(error=str(e)), show_alert=True)


@router.callback_query(F.data == "admin_mon_test_notifications")
@admin_required
async def test_notifications_callback(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        running_status = texts.t("ADMIN_MON_STATUS_RUNNING", "🟢 Running") if monitoring_service.is_running else texts.t("ADMIN_MON_STATUS_STOPPED", "🔴 Stopped")
        notif_status = texts.t("ENABLED", "🟢 Enabled") if settings.ENABLE_NOTIFICATIONS else texts.t("DISABLED", "🔴 Disabled")
        
        test_message = texts.t(
            "ADMIN_MON_TEST_MESSAGE",
            """
🧪 <b>Monitoring system test notification</b>

This is a test message to check the notification system.

📊 <b>System status:</b>
• Monitoring: {running_status}
• Notifications: {notif_status}
• Test time: {time}

✅ If you received this message, the notification system is working correctly!
"""
        ).format(
            running_status=running_status,
            notif_status=notif_status,
            time=datetime.now().strftime('%H:%M:%S %d.%m.%Y')
        )
        
        await callback.bot.send_message(
            callback.from_user.id,
            test_message,
            parse_mode="HTML"
        )
        
        await callback.answer(texts.t("ADMIN_MON_TEST_SENT", "✅ Test notification sent!"))
        
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        await callback.answer(texts.t("ADMIN_MON_TEST_ERROR", "❌ Send error: {error}").format(error=str(e)), show_alert=True)


@router.callback_query(F.data == "admin_mon_statistics")
@admin_required
async def monitoring_statistics_callback(callback: CallbackQuery):
    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        async for db in get_db():
            from app.database.crud.subscription import get_subscriptions_statistics
            sub_stats = await get_subscriptions_statistics(db)
            
            mon_status = await monitoring_service.get_monitoring_status(db)
            
            week_ago = datetime.now() - timedelta(days=7)
            week_logs = await monitoring_service.get_monitoring_logs(db, limit=1000)
            week_logs = [log for log in week_logs if log['created_at'] >= week_ago]
            
            week_success = sum(1 for log in week_logs if log['is_success'])
            week_errors = len(week_logs) - week_success
            
            notif_status = texts.t("ENABLED_SHORT", "On") if getattr(settings, 'ENABLE_NOTIFICATIONS', True) else texts.t("DISABLED_SHORT", "Off")
            
            text = texts.t(
                "ADMIN_MON_STATISTICS_TEXT",
                """
📊 <b>Monitoring Statistics</b>

📱 <b>Subscriptions:</b>
• Total: {total_subs}
• Active: {active_subs}
• Trial: {trial_subs}
• Paid: {paid_subs}

📈 <b>Today:</b>
• Successful operations: {today_success}
• Errors: {today_errors}
• Success rate: {today_rate}%

📊 <b>This week:</b>
• Total events: {week_total}
• Successful: {week_success}
• Errors: {week_errors}
• Success rate: {week_rate}%

🔧 <b>System:</b>
• Interval: {interval} min
• Notifications: {notif_status}
• Autopay: {autopay_days} days
"""
            ).format(
                total_subs=sub_stats['total_subscriptions'],
                active_subs=sub_stats['active_subscriptions'],
                trial_subs=sub_stats['trial_subscriptions'],
                paid_subs=sub_stats['paid_subscriptions'],
                today_success=mon_status['stats_24h']['successful'],
                today_errors=mon_status['stats_24h']['failed'],
                today_rate=mon_status['stats_24h']['success_rate'],
                week_total=len(week_logs),
                week_success=week_success,
                week_errors=week_errors,
                week_rate=round(week_success/len(week_logs)*100, 1) if week_logs else 0,
                interval=settings.MONITORING_INTERVAL,
                notif_status=notif_status,
                autopay_days=', '.join(map(str, settings.get_autopay_warning_days()))
            )
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=texts.BACK, callback_data="admin_monitoring")]
            ])
            
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            break
            
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        await callback.answer(texts.t("ADMIN_MON_STATS_ERROR", "❌ Error getting statistics: {error}").format(error=str(e)), show_alert=True)


def get_monitoring_logs_keyboard(current_page: int, total_pages: int, language: str = "en"):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    texts = get_texts(language)
    
    keyboard = []
    
    if total_pages > 1:
        nav_row = []
        
        if current_page > 1:
            nav_row.append(InlineKeyboardButton(
                text="⬅️", 
                callback_data=f"admin_mon_logs_page_{current_page - 1}"
            ))
        
        nav_row.append(InlineKeyboardButton(
            text=f"{current_page}/{total_pages}", 
            callback_data="current_page"
        ))
        
        if current_page < total_pages:
            nav_row.append(InlineKeyboardButton(
                text="➡️", 
                callback_data=f"admin_mon_logs_page_{current_page + 1}"
            ))
        
        keyboard.append(nav_row)
    
    keyboard.extend([
        [
            InlineKeyboardButton(text=texts.t("ADMIN_MON_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_mon_logs"),
            InlineKeyboardButton(text=texts.t("ADMIN_MON_BTN_CLEAR", "🗑️ Clear"), callback_data="admin_mon_clear_logs")
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_monitoring")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_monitoring_logs_back_keyboard(language: str = "en"):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    texts = get_texts(language)
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texts.t("ADMIN_MON_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_mon_logs"),
            InlineKeyboardButton(text=texts.t("ADMIN_MON_BTN_FILTERS", "🔍 Filters"), callback_data="admin_mon_logs_filters")
        ],
        [
            InlineKeyboardButton(text=texts.t("ADMIN_MON_BTN_CLEAR_LOGS", "🗑️ Clear logs"), callback_data="admin_mon_clear_logs")
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_monitoring")]
    ])


@router.message(Command("monitoring"))
@admin_required
async def monitoring_command(message: Message):
    language = message.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    try:
        async for db in get_db():
            status = await monitoring_service.get_monitoring_status(db)
            
            running_status = texts.t("ADMIN_MON_STATUS_RUNNING", "🟢 Running") if status['is_running'] else texts.t("ADMIN_MON_STATUS_STOPPED", "🔴 Stopped")
            
            text = texts.t(
                "ADMIN_MON_QUICK_STATUS",
                """
🔍 <b>Quick monitoring status</b>

📊 <b>Status:</b> {running_status}
📈 <b>Events in 24h:</b> {total_events}
✅ <b>Success rate:</b> {success_rate}%

Use admin panel for detailed management.
"""
            ).format(
                running_status=running_status,
                total_events=status['stats_24h']['total_events'],
                success_rate=status['stats_24h']['success_rate']
            )
            
            await message.answer(text, parse_mode="HTML")
            break
            
    except Exception as e:
        logger.error(f"Error in /monitoring command: {e}")
        await message.answer(texts.t("ERROR_GENERIC", "❌ Error: {error}").format(error=str(e)))


@router.message(AdminStates.editing_notification_value)
async def process_notification_value_input(message: Message, state: FSMContext):
    data = await state.get_data()
    language = data.get("settings_language") or message.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    
    if not data:
        await state.clear()
        await message.answer(texts.t("ADMIN_MON_CONTEXT_LOST", "ℹ️ Context lost, please try again from settings menu."))
        return

    raw_value = (message.text or "").strip()
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        await message.answer(texts.get("NOTIFICATION_VALUE_INVALID", "❌ Enter an integer."))
        return

    key = data.get("notification_setting_key")
    field = data.get("notification_setting_field")

    if (key == "expired_second_wave" and field == "percent") or (key == "expired_third_wave" and field == "percent"):
        if value < 0 or value > 100:
            await message.answer(texts.t("ADMIN_MON_PERCENT_RANGE_ERROR", "❌ Discount percent must be between 0 and 100."))
            return
    elif (key == "expired_second_wave" and field == "hours") or (key == "expired_third_wave" and field == "hours"):
        if value < 1 or value > 168:
            await message.answer(texts.t("ADMIN_MON_HOURS_RANGE_ERROR", "❌ Hours must be between 1 and 168."))
            return
    elif key == "expired_third_wave" and field == "trigger":
        if value < 2:
            await message.answer(texts.t("ADMIN_MON_DAYS_MIN_ERROR", "❌ Days must be at least 2."))
            return

    success = False
    if key == "expired_second_wave" and field == "percent":
        success = NotificationSettingsService.set_second_wave_discount_percent(value)
    elif key == "expired_second_wave" and field == "hours":
        success = NotificationSettingsService.set_second_wave_valid_hours(value)
    elif key == "expired_third_wave" and field == "percent":
        success = NotificationSettingsService.set_third_wave_discount_percent(value)
    elif key == "expired_third_wave" and field == "hours":
        success = NotificationSettingsService.set_third_wave_valid_hours(value)
    elif key == "expired_third_wave" and field == "trigger":
        success = NotificationSettingsService.set_third_wave_trigger_days(value)

    if not success:
        await message.answer(texts.get("NOTIFICATION_VALUE_INVALID", "❌ Invalid value, please try again."))
        return

    back_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.get("BACK", "⬅️ Back"),
                    callback_data="admin_mon_notify_settings",
                )
            ]
        ]
    )

    await message.answer(
        texts.get("NOTIFICATION_VALUE_UPDATED", "✅ Settings updated."),
        reply_markup=back_keyboard,
    )

    chat_id = data.get("settings_message_chat")
    message_id = data.get("settings_message_id")
    business_connection_id = data.get("settings_business_connection_id")
    if chat_id and message_id:
        await _render_notification_settings_for_state(
            message.bot,
            chat_id,
            message_id,
            language,
            business_connection_id=business_connection_id,
        )

    await state.clear()


def register_handlers(dp):
    dp.include_router(router)
