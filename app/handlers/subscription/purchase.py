import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from urllib.parse import quote
from aiogram import Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings, PERIOD_PRICES, get_traffic_prices
from app.database.crud.discount_offer import (
    get_offer_by_id,
    mark_offer_claimed,
)
from app.database.crud.promo_offer_template import get_promo_offer_template_by_id
from app.database.crud.subscription import (
    create_trial_subscription,
    create_paid_subscription, add_subscription_traffic, add_subscription_devices,
    update_subscription_autopay
)
from app.database.crud.transaction import create_transaction
from app.database.crud.user import subtract_user_balance
from app.database.models import (
    User, TransactionType, SubscriptionStatus,
    Subscription
)
from app.keyboards.inline import (
    get_subscription_keyboard, get_trial_keyboard,
    get_subscription_period_keyboard, get_traffic_packages_keyboard,
    get_countries_keyboard, get_devices_keyboard,
    get_subscription_confirm_keyboard, get_autopay_keyboard,
    get_autopay_days_keyboard, get_back_keyboard,
    get_add_traffic_keyboard,
    get_change_devices_keyboard, get_reset_traffic_confirm_keyboard,
    get_manage_countries_keyboard,
    get_device_selection_keyboard, get_connection_guide_keyboard,
    get_app_selection_keyboard, get_specific_app_keyboard,
    get_updated_subscription_settings_keyboard, get_insufficient_balance_keyboard,
    get_extend_subscription_keyboard_with_prices, get_confirm_change_devices_keyboard,
    get_devices_management_keyboard, get_device_management_help_keyboard,
    get_happ_cryptolink_keyboard,
    get_happ_download_platform_keyboard, get_happ_download_link_keyboard,
    get_happ_download_button_row,
    get_payment_methods_keyboard_with_cart,
    get_subscription_confirm_keyboard_with_cart,
    get_insufficient_balance_keyboard_with_cart
)
from app.services.user_cart_service import user_cart_service
from app.localization.texts import get_texts
from app.services.admin_notification_service import AdminNotificationService
from app.services.remnawave_service import RemnaWaveConfigurationError, RemnaWaveService
from app.services.subscription_checkout_service import (
    clear_subscription_checkout_draft,
    get_subscription_checkout_draft,
    save_subscription_checkout_draft,
    should_offer_checkout_resume,
)
from app.services.subscription_service import SubscriptionService
from app.services.trial_activation_service import (
    TrialPaymentChargeFailed,
    TrialPaymentInsufficientFunds,
    charge_trial_activation_if_required,
    preview_trial_activation_charge,
    revert_trial_activation,
    rollback_trial_subscription_activation,
)


def _serialize_markup(markup: Optional[InlineKeyboardMarkup]) -> Optional[Any]:
    if markup is None:
        return None

    model_dump = getattr(markup, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump(exclude_none=True)
        except TypeError:
            return model_dump()

    to_python = getattr(markup, "to_python", None)
    if callable(to_python):
        return to_python()

    return markup


def _message_needs_update(
    message: types.Message,
    new_text: str,
    new_markup: Optional[InlineKeyboardMarkup],
) -> bool:
    current_text = getattr(message, "text", None)

    if current_text != new_text:
        return True

    current_markup = getattr(message, "reply_markup", None)

    return _serialize_markup(current_markup) != _serialize_markup(new_markup)
from app.utils.miniapp_buttons import build_miniapp_or_callback_button
from app.services.promo_offer_service import promo_offer_service
from app.states import SubscriptionStates
from app.utils.pagination import paginate_list
from app.utils.pricing_utils import (
    calculate_months_from_days,
    compute_simple_subscription_price,
    get_remaining_months,
    calculate_prorated_price,
    validate_pricing_calculation,
    format_period_description,
    apply_percentage_discount,
)
from app.utils.price_display import PriceInfo, format_price_text, calculate_user_price
from app.utils.subscription_utils import (
    convert_subscription_link_to_happ_scheme,
    get_display_subscription_link,
    get_happ_cryptolink_redirect_link,
    resolve_simple_subscription_device_limit,
)
from app.utils.timezone import format_local_datetime
from app.utils.promo_offer import (
    build_promo_offer_hint,
    get_user_active_promo_discount_percent,
)

from .common import _apply_promo_offer_discount, _get_promo_offer_discount_percent, logger, update_traffic_prices
from .autopay import (
    handle_autopay_menu,
    handle_subscription_cancel,
    handle_subscription_config_back,
    set_autopay_days,
    show_autopay_days,
    toggle_autopay,
)
from .countries import (
    _get_available_countries,
    _should_show_countries_management,
    apply_countries_changes,
    countries_continue,
    handle_add_countries,
    handle_manage_country,
    select_country,
)
from .devices import (
    confirm_add_devices,
    confirm_change_devices,
    confirm_reset_devices,
    execute_change_devices,
    get_current_devices_count,
    get_servers_display_names,
    handle_all_devices_reset_from_management,
    handle_app_selection,
    handle_change_devices,
    handle_device_guide,
    handle_device_management,
    handle_devices_page,
    handle_reset_devices,
    handle_single_device_reset,
    handle_specific_app_guide,
    show_device_connection_help,
)
from .happ import (
    handle_happ_download_back,
    handle_happ_download_close,
    handle_happ_download_platform_choice,
    handle_happ_download_request,
)
from .links import handle_connect_subscription, handle_open_subscription_link
from .pricing import _build_subscription_period_prompt, _prepare_subscription_summary
from .promo import (
    _build_promo_group_discount_text,
    _get_promo_offer_hint,
    claim_discount_offer,
    handle_promo_offer_close,
)
from .traffic import (
    confirm_reset_traffic,
    confirm_switch_traffic,
    execute_switch_traffic,
    handle_no_traffic_packages,
    handle_reset_traffic,
    handle_switch_traffic,
    select_traffic,
)
from .summary import present_subscription_summary

async def show_subscription_info(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    await db.refresh(db_user)

    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    if not subscription:
        await callback.message.edit_text(
            texts.SUBSCRIPTION_NONE,
            reply_markup=get_back_keyboard(db_user.language)
        )
        await callback.answer()
        return

    from app.database.crud.subscription import check_and_update_subscription_status
    subscription = await check_and_update_subscription_status(db, subscription)

    subscription_service = SubscriptionService()
    await subscription_service.sync_subscription_usage(db, subscription)

    await db.refresh(subscription)

    current_time = datetime.utcnow()

    if subscription.status == "expired" or subscription.end_date <= current_time:
        actual_status = "expired"
        status_display = texts.t("SUBSCRIPTION_STATUS_EXPIRED", "Expired")
        status_emoji = "🔴"
    elif subscription.status == "active" and subscription.end_date > current_time:
        if subscription.is_trial:
            actual_status = "trial_active"
            status_display = texts.t("SUBSCRIPTION_STATUS_TRIAL", "Trial")
            status_emoji = "🎯"
        else:
            actual_status = "paid_active"
            status_display = texts.t("SUBSCRIPTION_STATUS_ACTIVE", "Active")
            status_emoji = "💎"
    else:
        actual_status = "unknown"
        status_display = texts.t("SUBSCRIPTION_STATUS_UNKNOWN", "Unknown")
        status_emoji = "❓"

    if subscription.end_date <= current_time:
        days_left = 0
        time_left_text = texts.t("SUBSCRIPTION_TIME_LEFT_EXPIRED", "expired")
        warning_text = ""
    else:
        delta = subscription.end_date - current_time
        days_left = delta.days
        hours_left = delta.seconds // 3600

        if days_left > 1:
            time_left_text = texts.t("SUBSCRIPTION_TIME_LEFT_DAYS", "{days} days").format(days=days_left)
            warning_text = ""
        elif days_left == 1:
            time_left_text = texts.t("SUBSCRIPTION_TIME_LEFT_DAYS", "{days} days").format(days=days_left)
            warning_text = texts.t("SUBSCRIPTION_WARNING_TOMORROW", "\n⚠️ expires tomorrow!")
        elif hours_left > 0:
            time_left_text = texts.t("SUBSCRIPTION_TIME_LEFT_HOURS", "{hours} h.").format(hours=hours_left)
            warning_text = texts.t("SUBSCRIPTION_WARNING_TODAY", "\n⚠️ expires today!")
        else:
            minutes_left = (delta.seconds % 3600) // 60
            time_left_text = texts.t("SUBSCRIPTION_TIME_LEFT_MINUTES", "{minutes} min.").format(
                minutes=minutes_left
            )
            warning_text = texts.t(
                "SUBSCRIPTION_WARNING_MINUTES",
                "\n🔴 expires in a few minutes!",
            )

    subscription_type = (
        texts.t("SUBSCRIPTION_TYPE_TRIAL", "Trial")
        if subscription.is_trial
        else texts.t("SUBSCRIPTION_TYPE_PAID", "Paid")
    )

    used_traffic = f"{subscription.traffic_used_gb:.1f}"
    if subscription.traffic_limit_gb == 0:
        traffic_used_display = texts.t(
            "SUBSCRIPTION_TRAFFIC_UNLIMITED",
            "∞ (unlimited) | Used: {used} GB",
        ).format(used=used_traffic)
    else:
        traffic_used_display = texts.t(
            "SUBSCRIPTION_TRAFFIC_LIMITED",
            "{used} / {limit} GB",
        ).format(used=used_traffic, limit=subscription.traffic_limit_gb)

    devices_used_str = "—"
    devices_list = []
    devices_count = 0

    show_devices = settings.is_devices_selection_enabled()
    devices_used_str = ""
    devices_list: List[Dict[str, Any]] = []

    if show_devices:
        try:
            if db_user.remnawave_uuid:
                from app.services.remnawave_service import RemnaWaveService
                service = RemnaWaveService()

                async with service.get_api_client() as api:
                    response = await api._make_request('GET', f'/api/hwid/devices/{db_user.remnawave_uuid}')

                    if response and 'response' in response:
                        devices_info = response['response']
                        devices_count = devices_info.get('total', 0)
                        devices_list = devices_info.get('devices', [])
                        devices_used_str = str(devices_count)
                        logger.info(f"Found {devices_count} devices for user {db_user.telegram_id}")
                    else:
                        logger.warning(f"Failed to get device information for {db_user.telegram_id}")

        except Exception as e:
            logger.error(f"Error getting devices for display: {e}")
            devices_used = await get_current_devices_count(db_user)
            devices_used_str = str(devices_used)

    servers_names = await get_servers_display_names(subscription.connected_squads)
    servers_display = (
        servers_names
        if servers_names
        else texts.t("SUBSCRIPTION_NO_SERVERS", "No servers")
    )

    message_template = texts.t(
        "SUBSCRIPTION_OVERVIEW_TEMPLATE",
        """👤 {full_name}
💰 Balance: {balance}
📱 Subscription: {status_emoji} {status_display}{warning}

📱 Subscription Info
🎭 Type: {subscription_type}
📅 Valid until: {end_date}
⏰ Remaining: {time_left}
📈 Traffic: {traffic}
🌍 Servers: {servers}
📱 Devices: {devices_used} / {device_limit}""",
    )

    if not show_devices:
        message_template = message_template.replace(
            "\n📱 Devices: {devices_used} / {device_limit}",
            "",
        )

    message = message_template.format(
        full_name=db_user.full_name,
        balance=settings.format_price(db_user.balance_kopeks),
        status_emoji=status_emoji,
        status_display=status_display,
        warning=warning_text,
        subscription_type=subscription_type,
        end_date=format_local_datetime(subscription.end_date, "%d.%m.%Y %H:%M"),
        time_left=time_left_text,
        traffic=traffic_used_display,
        servers=servers_display,
        devices_used=devices_used_str,
        device_limit=subscription.device_limit,
    )

    if show_devices and devices_list:
        message += "\n\n" + texts.t(
            "SUBSCRIPTION_CONNECTED_DEVICES_TITLE",
            "<blockquote>📱 <b>Connected devices:</b>\n",
        )
        for device in devices_list[:5]:
            platform = device.get('platform', 'Unknown')
            device_model = device.get('deviceModel', 'Unknown')
            device_info = f"{platform} - {device_model}"

            if len(device_info) > 35:
                device_info = device_info[:32] + "..."
            message += f"• {device_info}\n"
        message += texts.t("SUBSCRIPTION_CONNECTED_DEVICES_FOOTER", "</blockquote>")

    subscription_link = get_display_subscription_link(subscription)
    hide_subscription_link = settings.should_hide_subscription_link()

    if (
            subscription_link
            and actual_status in ["trial_active", "paid_active"]
            and not hide_subscription_link
    ):
        message += "\n\n" + texts.t(
            "SUBSCRIPTION_CONNECT_LINK_SECTION",
            "🔗 <b>Connection link:</b>\n<code>{subscription_url}</code>",
        ).format(subscription_url=subscription_link)
        message += "\n\n" + texts.t(
            "SUBSCRIPTION_CONNECT_LINK_PROMPT",
            "📱 Copy the link and add it to your VPN app",
        )

    await callback.message.edit_text(
        message,
        reply_markup=get_subscription_keyboard(
            db_user.language,
            has_subscription=True,
            is_trial=subscription.is_trial,
            subscription=subscription
        ),
        parse_mode="HTML"
    )
    await callback.answer()

async def show_trial_offer(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    texts = get_texts(db_user.language)

    if db_user.subscription or db_user.has_had_paid_subscription:
        await callback.message.edit_text(
            texts.TRIAL_ALREADY_USED,
            reply_markup=get_back_keyboard(db_user.language)
        )
        await callback.answer()
        return

    trial_server_name = texts.t("TRIAL_SERVER_DEFAULT_NAME", "🎯 Test server")
    try:
        from app.database.crud.server_squad import get_trial_eligible_server_squads

        trial_squads = await get_trial_eligible_server_squads(db, include_unavailable=True)

        if trial_squads:
            if len(trial_squads) == 1:
                trial_server_name = trial_squads[0].display_name
            else:
                trial_server_name = texts.t(
                    "TRIAL_SERVER_RANDOM_POOL",
                    "🎲 Random from {count} servers",
                ).format(count=len(trial_squads))
        else:
            logger.warning("No squads configured for trial issuance")

    except Exception as e:
        logger.error(f"Error getting trial server: {e}")

    trial_device_limit = settings.TRIAL_DEVICE_LIMIT
    if not settings.is_devices_selection_enabled():
        forced_limit = settings.get_disabled_mode_device_limit()
        if forced_limit is not None:
            trial_device_limit = forced_limit

    devices_line = ""
    if settings.is_devices_selection_enabled():
        devices_line_template = texts.t(
            "TRIAL_AVAILABLE_DEVICES_LINE",
            "\n📱 <b>Devices:</b> {devices} pcs.",
        )
        devices_line = devices_line_template.format(
            devices=trial_device_limit,
        )

    price_line = ""
    if settings.is_trial_paid_activation_enabled():
        trial_price = settings.get_trial_activation_price()
        if trial_price > 0:
            price_line = texts.t(
                "TRIAL_PAYMENT_PRICE_LINE",
                "\n💳 <b>Activation cost:</b> {price}",
            ).format(price=settings.format_price(trial_price))

    trial_text = texts.TRIAL_AVAILABLE.format(
        days=settings.TRIAL_DURATION_DAYS,
        traffic=texts.format_traffic(settings.TRIAL_TRAFFIC_LIMIT_GB),
        devices=trial_device_limit if trial_device_limit is not None else "",
        devices_line=devices_line,
        server_name=trial_server_name,
        price_line=price_line,
    )

    await callback.message.edit_text(
        trial_text,
        reply_markup=get_trial_keyboard(db_user.language)
    )
    await callback.answer()

async def activate_trial(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    from app.services.admin_notification_service import AdminNotificationService

    texts = get_texts(db_user.language)

    if db_user.subscription or db_user.has_had_paid_subscription:
        await callback.message.edit_text(
            texts.TRIAL_ALREADY_USED,
            reply_markup=get_back_keyboard(db_user.language)
        )
        await callback.answer()
        return

    try:
        preview_trial_activation_charge(db_user)
    except TrialPaymentInsufficientFunds as error:
        required_label = settings.format_price(error.required_amount)
        balance_label = settings.format_price(error.balance_amount)
        missing_label = settings.format_price(error.missing_amount)
        message = texts.t(
            "TRIAL_PAYMENT_INSUFFICIENT_FUNDS",
            "⚠️ Insufficient funds to activate trial.\n"
            "Required: {required}\nBalance: {balance}\n"
            "Missing: {missing}\n\nTop up your balance and try again.",
        ).format(required=required_label, balance=balance_label, missing=missing_label)

        await callback.message.edit_text(
            message,
            reply_markup=get_insufficient_balance_keyboard(
                db_user.language,
                amount_kopeks=error.required_amount,
            ),
        )
        await callback.answer()
        return

    charged_amount = 0
    subscription: Optional[Subscription] = None
    remnawave_user = None

    try:
        forced_devices = None
        if not settings.is_devices_selection_enabled():
            forced_devices = settings.get_disabled_mode_device_limit()

        subscription = await create_trial_subscription(
            db,
            db_user.id,
            device_limit=forced_devices,
        )

        await db.refresh(db_user)

        try:
            charged_amount = await charge_trial_activation_if_required(
                db,
                db_user,
                description="Trial activation via bot",
            )
        except TrialPaymentInsufficientFunds as error:
            rollback_success = await rollback_trial_subscription_activation(db, subscription)
            await db.refresh(db_user)
            if not rollback_success:
                await callback.answer(
                    texts.t(
                        "TRIAL_ROLLBACK_FAILED",
                        "Failed to cancel trial activation. Try again later.",
                    ),
                    show_alert=True,
                )
                return

            logger.error(
                "Insufficient funds detected after trial creation for user %s: %s",
                db_user.id,
                error,
            )
            required_label = settings.format_price(error.required_amount)
            balance_label = settings.format_price(error.balance_amount)
            missing_label = settings.format_price(error.missing_amount)
            message = texts.t(
                "TRIAL_PAYMENT_INSUFFICIENT_FUNDS",
                "⚠️ Insufficient funds to activate trial.\n"
                "Required: {required}\nBalance: {balance}\n"
                "Missing: {missing}\n\nTop up your balance and try again.",
            ).format(
                required=required_label,
                balance=balance_label,
                missing=missing_label,
            )

            await callback.message.edit_text(
                message,
                reply_markup=get_insufficient_balance_keyboard(
                    db_user.language,
                    amount_kopeks=error.required_amount,
                ),
            )
            await callback.answer()
            return
        except TrialPaymentChargeFailed:
            rollback_success = await rollback_trial_subscription_activation(db, subscription)
            await db.refresh(db_user)
            if not rollback_success:
                await callback.answer(
                    texts.t(
                        "TRIAL_ROLLBACK_FAILED",
                        "Failed to cancel trial activation. Try again later.",
                    ),
                    show_alert=True,
                )
                return

            await callback.answer(
                texts.t(
                    "TRIAL_PAYMENT_FAILED",
                    "Failed to debit funds for trial activation. Try again later.",
                ),
                show_alert=True,
            )
            return

        subscription_service = SubscriptionService()
        try:
            remnawave_user = await subscription_service.create_remnawave_user(
                db,
                subscription,
            )
        except RemnaWaveConfigurationError as error:
            logger.error("RemnaWave update skipped due to configuration error: %s", error)
            revert_result = await revert_trial_activation(
                db,
                db_user,
                subscription,
                charged_amount,
                refund_description=texts.t("subscription.trial.refund_description", "Trial activation refund via bot"),
            )
            if not revert_result.subscription_rolled_back:
                failure_text = texts.t(
                    "TRIAL_ROLLBACK_FAILED",
                    "Failed to cancel trial activation after debit error. Contact support and try again later.",
                )
            elif charged_amount > 0 and not revert_result.refunded:
                failure_text = texts.t(
                    "TRIAL_REFUND_FAILED",
                    "Failed to refund payment for trial activation. Contact support immediately.",
                )
            else:
                failure_text = texts.t(
                    "TRIAL_PROVISIONING_FAILED",
                    "Failed to complete trial activation. Funds returned to balance. Try again later.",
                )

            await callback.message.edit_text(
                failure_text,
                reply_markup=get_back_keyboard(db_user.language),
            )
            await callback.answer()
            return
        except Exception as error:
            logger.error(
                "Failed to create RemnaWave user for trial subscription %s: %s",
                getattr(subscription, "id", "<unknown>"),
                error,
            )
            revert_result = await revert_trial_activation(
                db,
                db_user,
                subscription,
                charged_amount,
                refund_description=texts.t("subscription.trial.refund_description", "Trial activation refund via bot"),
            )
            if not revert_result.subscription_rolled_back:
                failure_text = texts.t(
                    "TRIAL_ROLLBACK_FAILED",
                    "Failed to cancel trial activation after debit error. Contact support and try again later.",
                )
            elif charged_amount > 0 and not revert_result.refunded:
                failure_text = texts.t(
                    "TRIAL_REFUND_FAILED",
                    "Failed to refund payment for trial activation. Contact support immediately.",
                )
            else:
                failure_text = texts.t(
                    "TRIAL_PROVISIONING_FAILED",
                    "Failed to complete trial activation. Funds returned to balance. Try again later.",
                )

            await callback.message.edit_text(
                failure_text,
                reply_markup=get_back_keyboard(db_user.language),
            )
            await callback.answer()
            return

        await db.refresh(db_user)

        try:
            notification_service = AdminNotificationService(callback.bot)
            await notification_service.send_trial_activation_notification(
                db,
                db_user,
                subscription,
                charged_amount_kopeks=charged_amount,
            )
        except Exception as e:
            logger.error(f"Error sending trial notification: {e}")

        subscription_link = get_display_subscription_link(subscription)
        hide_subscription_link = settings.should_hide_subscription_link()

        payment_note = ""
        if charged_amount > 0:
            payment_note = "\n\n" + texts.t(
                "TRIAL_PAYMENT_CHARGED_NOTE",
                "💳 Your balance has been debited {amount}.",
            ).format(amount=settings.format_price(charged_amount))

        if remnawave_user and subscription_link:
            if settings.is_happ_cryptolink_mode():
                trial_success_text = (
                    f"{texts.TRIAL_ACTIVATED}\n\n"
                    + texts.t(
                        "SUBSCRIPTION_HAPP_LINK_PROMPT",
                        "🔒 Subscription link created. Click the \"Connect\" button below to open it in Happ.",
                    )
                    + "\n\n"
                    + texts.t(
                        "SUBSCRIPTION_IMPORT_INSTRUCTION_PROMPT",
                        "📱 Click the button below to get VPN setup instructions for your device",
                    )
                )
            elif hide_subscription_link:
                trial_success_text = (
                    f"{texts.TRIAL_ACTIVATED}\n\n"
                    + texts.t(
                        "SUBSCRIPTION_LINK_HIDDEN_NOTICE",
                        "ℹ️ The subscription link is available via the buttons below or in the 'My Subscription' section.",
                    )
                    + "\n\n"
                    + texts.t(
                        "SUBSCRIPTION_IMPORT_INSTRUCTION_PROMPT",
                        "📱 Click the button below to get VPN setup instructions for your device",
                    )
                )
            else:
                subscription_import_link = texts.t(
                    "SUBSCRIPTION_IMPORT_LINK_SECTION",
                    "🔗 <b>Your import link for VPN app:</b>\n<code>{subscription_url}</code>",
                ).format(subscription_url=subscription_link)

                trial_success_text = (
                    f"{texts.TRIAL_ACTIVATED}\n\n"
                    f"{subscription_import_link}\n\n"
                    f"{texts.t('SUBSCRIPTION_IMPORT_INSTRUCTION_PROMPT', '📱 Click the button below to get VPN setup instructions for your device')}"
                )

            trial_success_text += payment_note

            connect_mode = settings.CONNECT_BUTTON_MODE

            if connect_mode == "miniapp_subscription":
                connect_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                            web_app=types.WebAppInfo(url=subscription_link),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ Back to main menu"),
                            callback_data="back_to_menu",
                        )
                    ],
                ])
            elif connect_mode == "miniapp_custom":
                if not settings.MINIAPP_CUSTOM_URL:
                    await callback.answer(
                        texts.t(
                            "CUSTOM_MINIAPP_URL_NOT_SET",
                            "⚠ Custom mini-app URL is not configured",
                        ),
                        show_alert=True,
                    )
                    return

                connect_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                            web_app=types.WebAppInfo(url=settings.MINIAPP_CUSTOM_URL),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ Back to main menu"),
                            callback_data="back_to_menu",
                        )
                    ],
                ])
            elif connect_mode == "link":
                rows = [
                    [
                        InlineKeyboardButton(
                            text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                            url=subscription_link,
                        )
                    ]
                ]
                happ_row = get_happ_download_button_row(texts)
                if happ_row:
                    rows.append(happ_row)
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ Back to main menu"),
                            callback_data="back_to_menu",
                        )
                    ]
                )
                connect_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
            elif connect_mode == "happ_cryptolink":
                rows = [
                    [
                        InlineKeyboardButton(
                            text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                            callback_data="open_subscription_link",
                        )
                    ]
                ]
                happ_row = get_happ_download_button_row(texts)
                if happ_row:
                    rows.append(happ_row)
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ Back to main menu"),
                            callback_data="back_to_menu",
                        )
                    ]
                )
                connect_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
            else:
                connect_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                                callback_data="subscription_connect",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ Back to main menu"),
                                callback_data="back_to_menu",
                            )
                        ],
                    ]
                )

            await callback.message.edit_text(
                trial_success_text,
                reply_markup=connect_keyboard,
                parse_mode="HTML",
            )
        else:
            trial_success_text = (
                f"{texts.TRIAL_ACTIVATED}\n\n"
                + texts.t("subscription.trial.link_generating", "⚠️ Link is being generated, try going to 'My subscription' section in a few seconds.")
            )
            trial_success_text += payment_note
            await callback.message.edit_text(
                trial_success_text,
                reply_markup=get_back_keyboard(db_user.language),
            )

        logger.info(
            f"✅ Trial subscription activated for user {db_user.telegram_id}"
        )

    except Exception as e:
        logger.error(f"Trial activation error: {e}")
        failure_text = texts.ERROR

        if subscription and remnawave_user is None:
            revert_result = await revert_trial_activation(
                db,
                db_user,
                subscription,
                charged_amount,
                refund_description=texts.t("subscription.trial.refund_description", "Trial activation refund via bot"),
            )
            if not revert_result.subscription_rolled_back:
                failure_text = texts.t(
                    "TRIAL_ROLLBACK_FAILED",
                    "Failed to cancel trial activation after debit error. Contact support and try again later.",
                )
            elif charged_amount > 0 and not revert_result.refunded:
                failure_text = texts.t(
                    "TRIAL_REFUND_FAILED",
                    "Failed to refund payment for trial activation. Contact support immediately.",
                )
            else:
                failure_text = texts.t(
                    "TRIAL_PROVISIONING_FAILED",
                    "Failed to complete trial activation. Funds returned to balance. Try again later.",
                )

        await callback.message.edit_text(
            failure_text,
            reply_markup=get_back_keyboard(db_user.language)
        )
        await callback.answer()
        return

    await callback.answer()

async def start_subscription_purchase(
        callback: types.CallbackQuery,
        state: FSMContext,
        db_user: User,
        db: AsyncSession,
):
    texts = get_texts(db_user.language)

    keyboard = get_subscription_period_keyboard(db_user.language, db_user)
    prompt_text = await _build_subscription_period_prompt(db_user, texts, db)

    await _edit_message_text_or_caption(
        callback.message,
        prompt_text,
        keyboard,
    )

    subscription = getattr(db_user, 'subscription', None)

    if settings.is_devices_selection_enabled():
        initial_devices = settings.DEFAULT_DEVICE_LIMIT
        if subscription and getattr(subscription, 'device_limit', None) is not None:
            initial_devices = max(settings.DEFAULT_DEVICE_LIMIT, subscription.device_limit)
    else:
        forced_limit = settings.get_disabled_mode_device_limit()
        if forced_limit is None:
            initial_devices = settings.DEFAULT_DEVICE_LIMIT
        else:
            initial_devices = forced_limit

    initial_data = {
        'period_days': None,
        'countries': [],
        'devices': initial_devices,
        'total_price': 0
    }

    if settings.is_traffic_fixed():
        initial_data['traffic_gb'] = settings.get_fixed_traffic_limit()
    else:
        initial_data['traffic_gb'] = None

    await state.set_data(initial_data)
    await state.set_state(SubscriptionStates.selecting_period)
    await callback.answer()


async def _edit_message_text_or_caption(
    message: types.Message,
    text: str,
    reply_markup: InlineKeyboardMarkup,
    parse_mode: Optional[str] = "HTML",
) -> None:
    """Edits message text when possible, falls back to caption or re-sends message."""

    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramBadRequest as error:
        error_message = str(error).lower()

        if "message is not modified" in error_message:
            return

        if "there is no text in the message to edit" in error_message:
            if message.caption is not None:
                await message.edit_caption(
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                return

            await message.delete()
            await message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return

        raise

async def save_cart_and_redirect_to_topup(
        callback: types.CallbackQuery,
        state: FSMContext,
        db_user: User,
        missing_amount: int
):
    texts = get_texts(db_user.language)
    data = await state.get_data()

    # Save cart data to Redis
    cart_data = {
        **data,
        'saved_cart': True,
        'missing_amount': missing_amount,
        'return_to_cart': True,
        'user_id': db_user.id
    }
    
    await user_cart_service.save_user_cart(db_user.id, cart_data)

    message_text = texts.t(
        "subscription.cart.insufficient_funds_with_cart",
        "💰 Insufficient funds to complete subscription purchase\n\n"
        "Required: {required}\n"
        "You have: {balance}\n\n"
        "🛒 Your cart has been saved!\n"
        "After topping up your balance, you can return to complete the subscription purchase.\n\n"
        "Choose a top-up method:"
    ).format(
        required=texts.format_price(missing_amount),
        balance=texts.format_price(db_user.balance_kopeks)
    )

    await callback.message.edit_text(
        message_text,
        reply_markup=get_payment_methods_keyboard_with_cart(
            db_user.language,
            missing_amount,
        ),
        parse_mode="HTML"
    )

async def return_to_saved_cart(
        callback: types.CallbackQuery,
        state: FSMContext,
        db_user: User,
        db: AsyncSession
):
    # Get cart data from Redis
    cart_data = await user_cart_service.get_user_cart(db_user.id)
    
    if not cart_data:
        texts = get_texts(db_user.language)
        await callback.answer(
            texts.t("subscription.cart.not_found", "❌ Saved cart not found"),
            show_alert=True
        )
        return

    texts = get_texts(db_user.language)

    preserved_metadata_keys = {
        'saved_cart',
        'missing_amount',
        'return_to_cart',
        'user_id',
    }
    preserved_metadata = {
        key: cart_data[key]
        for key in preserved_metadata_keys
        if key in cart_data
    }

    prepared_cart_data = dict(cart_data)

    if not settings.is_devices_selection_enabled():
        try:
            from .pricing import _prepare_subscription_summary

            _, recalculated_data = await _prepare_subscription_summary(
                db_user,
                prepared_cart_data,
                texts,
            )
        except ValueError as recalculation_error:
            logger.error(
                "Failed to recalculate saved cart for user %s: %s",
                db_user.telegram_id,
                recalculation_error,
            )
            forced_limit = settings.get_disabled_mode_device_limit()
            if forced_limit is None:
                forced_limit = settings.DEFAULT_DEVICE_LIMIT
            prepared_cart_data['devices'] = forced_limit
            removed_devices_total = prepared_cart_data.pop('total_devices_price', 0) or 0
            if removed_devices_total:
                prepared_cart_data['total_price'] = max(
                    0,
                    prepared_cart_data.get('total_price', 0) - removed_devices_total,
                )
            prepared_cart_data.pop('devices_discount_percent', None)
            prepared_cart_data.pop('devices_discount_total', None)
            prepared_cart_data.pop('devices_discounted_price_per_month', None)
            prepared_cart_data.pop('devices_price_per_month', None)
        else:
            normalized_cart_data = dict(prepared_cart_data)
            normalized_cart_data.update(recalculated_data)

            for key, value in preserved_metadata.items():
                normalized_cart_data[key] = value

            prepared_cart_data = normalized_cart_data

        if prepared_cart_data != cart_data:
            await user_cart_service.save_user_cart(db_user.id, prepared_cart_data)

    total_price = prepared_cart_data.get('total_price', 0)

    if db_user.balance_kopeks < total_price:
        missing_amount = total_price - db_user.balance_kopeks
        insufficient_keyboard = get_insufficient_balance_keyboard_with_cart(
            db_user.language,
            missing_amount,
        )
        insufficient_text = texts.t(
            "subscription.cart.still_insufficient",
            "❌ Still insufficient funds\n\n"
            "Required: {required}\n"
            "You have: {balance}\n"
            "Missing: {missing}"
        ).format(
            required=texts.format_price(total_price),
            balance=texts.format_price(db_user.balance_kopeks),
            missing=texts.format_price(missing_amount)
        )

        if _message_needs_update(callback.message, insufficient_text, insufficient_keyboard):
            await callback.message.edit_text(
                insufficient_text,
                reply_markup=insufficient_keyboard,
            )
        else:
            await callback.answer(
                texts.t("subscription.cart.topup_to_complete", "ℹ️ Top up your balance to complete the purchase.")
            )
        return

    countries = await _get_available_countries(db_user.promo_group_id)
    selected_countries_names = []

    period_display = format_period_description(prepared_cart_data['period_days'], db_user.language)

    # Check if 'countries' key exists in cart data
    cart_countries = prepared_cart_data.get('countries', [])
    for country in countries:
        if country['uuid'] in cart_countries:
            selected_countries_names.append(country['name'])

    if settings.is_traffic_fixed():
        traffic_value = prepared_cart_data.get('traffic_gb')
        if traffic_value is None:
            traffic_value = settings.get_fixed_traffic_limit()
        traffic_display = texts.t("TRAFFIC_UNLIMITED_SHORT", "Unlimited") if traffic_value == 0 else f"{traffic_value} GB"
    else:
        traffic_value = prepared_cart_data.get('traffic_gb', 0) or 0
        traffic_display = texts.t("TRAFFIC_UNLIMITED_SHORT", "Unlimited") if traffic_value == 0 else f"{traffic_value} GB"

    summary_lines = [
        texts.t("subscription.cart.restored_cart", "🛒 Restored cart"),
        "",
        texts.t("subscription.cart.period", "📅 Period: {period}").format(period=period_display),
        texts.t("subscription.cart.traffic", "📊 Traffic: {traffic}").format(traffic=traffic_display),
        texts.t("subscription.cart.countries", "🌍 Countries: {countries}").format(countries=', '.join(selected_countries_names)),
    ]

    if settings.is_devices_selection_enabled():
        devices_value = prepared_cart_data.get('devices')
        if devices_value is not None:
            summary_lines.append(
                texts.t("subscription.cart.devices", "📱 Devices: {devices}").format(devices=devices_value)
            )

    summary_lines.extend([
        "",
        texts.t("subscription.cart.total_price", "💎 Total cost: {price}").format(price=texts.format_price(total_price)),
        "",
        texts.t("subscription.cart.confirm_purchase", "Confirm purchase?"),
    ])

    summary_text = "\n".join(summary_lines)

    # Set data in FSM to continue the process
    await state.set_data(prepared_cart_data)
    await state.set_state(SubscriptionStates.confirming_purchase)

    confirm_keyboard = get_subscription_confirm_keyboard_with_cart(db_user.language)

    if _message_needs_update(callback.message, summary_text, confirm_keyboard):
        await callback.message.edit_text(
            summary_text,
            reply_markup=confirm_keyboard,
            parse_mode="HTML"
        )

    await callback.answer(texts.t("subscription.cart.restored", "✅ Cart restored!"))

async def handle_extend_subscription(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    if not subscription or subscription.is_trial:
        await callback.answer(
            texts.t("subscription.extend.paid_only", "⚠ Extension is available only for paid subscriptions"),
            show_alert=True
        )
        return

    subscription_service = SubscriptionService()

    available_periods = settings.get_available_renewal_periods()
    renewal_prices = {}
    promo_offer_percent = _get_promo_offer_discount_percent(db_user)

    for days in available_periods:
        try:
            months_in_period = calculate_months_from_days(days)

            from app.config import PERIOD_PRICES

            # 1. Calculate period price with promo group discount using unified system
            base_price_original = PERIOD_PRICES.get(days, 0)
            period_price_info = calculate_user_price(db_user, base_price_original, days, "period")

            # 2. Calculate servers price with promo group discount
            servers_price_per_month, _ = await subscription_service.get_countries_price_by_uuids(
                subscription.connected_squads,
                db,
                promo_group_id=db_user.promo_group_id,
            )
            servers_total_base = servers_price_per_month * months_in_period
            servers_price_info = calculate_user_price(db_user, servers_total_base, days, "servers")

            # 3. Calculate devices price with promo group discount
            device_limit = subscription.device_limit
            if device_limit is None:
                if settings.is_devices_selection_enabled():
                    device_limit = settings.DEFAULT_DEVICE_LIMIT
                else:
                    forced_limit = settings.get_disabled_mode_device_limit()
                    if forced_limit is None:
                        device_limit = settings.DEFAULT_DEVICE_LIMIT
                    else:
                        device_limit = forced_limit

            additional_devices = max(0, (device_limit or 0) - settings.DEFAULT_DEVICE_LIMIT)
            devices_price_per_month = additional_devices * settings.PRICE_PER_DEVICE
            devices_total_base = devices_price_per_month * months_in_period
            devices_price_info = calculate_user_price(db_user, devices_total_base, days, "devices")

            # 4. Calculate traffic price with promo group discount
            traffic_price_per_month = settings.get_traffic_price(subscription.traffic_limit_gb)
            traffic_total_base = traffic_price_per_month * months_in_period
            traffic_price_info = calculate_user_price(db_user, traffic_total_base, days, "traffic")

            # 5. Calculate ORIGINAL price (before ALL discounts)
            total_original_price = (
                period_price_info.base_price +
                servers_price_info.base_price +
                devices_price_info.base_price +
                traffic_price_info.base_price
            )

            # 6. Sum prices with promo group discounts applied
            total_price = (
                period_price_info.final_price +
                servers_price_info.final_price +
                devices_price_info.final_price +
                traffic_price_info.final_price
            )

            # 7. Apply promo offer discount on top of promo group discounts
            promo_component = _apply_promo_offer_discount(db_user, total_price)

            # Store: original = price before discounts, final = price with all discounts
            renewal_prices[days] = {
                "final": promo_component["discounted"],
                "original": total_original_price,
            }

        except Exception as e:
            logger.error(f"Error calculating price for period {days}: {e}")
            continue

    if not renewal_prices:
        await callback.answer(
            texts.t("subscription.extend.no_periods", "⚠ No available periods for extension"),
            show_alert=True
        )
        return

    prices_text = ""

    for days in available_periods:
        if days not in renewal_prices:
            continue

        price_info = renewal_prices[days]

        if isinstance(price_info, dict):
            final_price = price_info.get("final")
            if final_price is None:
                final_price = price_info.get("original", 0)
            original_price = price_info.get("original", final_price)
        else:
            final_price = price_info
            original_price = final_price

        period_display = format_period_description(days, db_user.language)

        # Calculate discount percentage for PriceInfo
        discount_percent = 0
        if original_price > final_price and original_price > 0:
            discount_percent = ((original_price - final_price) * 100) // original_price

        # Create PriceInfo and format text using unified system
        price_info_obj = PriceInfo(
            base_price=original_price,
            final_price=final_price,
            discount_percent=discount_percent
        )

        prices_text += format_price_text(
            period_label=period_display,
            price_info=price_info_obj,
            format_price_func=texts.format_price
        ) + "\n"

    promo_discounts_text = await _build_promo_group_discount_text(
        db_user,
        available_periods,
        texts=texts,
    )

    renewal_lines = [
        texts.t("subscription.extend.title", "⏰ Extend subscription"),
        "",
        texts.t("subscription.extend.days_left", "Days left: {days}").format(days=subscription.days_left),
        "",
        texts.t("subscription.extend.current_config", "<b>Your current configuration:</b>"),
        texts.t("subscription.extend.servers", "🌍 Servers: {count}").format(count=len(subscription.connected_squads)),
        texts.t("subscription.extend.traffic", "📊 Traffic: {traffic}").format(traffic=texts.format_traffic(subscription.traffic_limit_gb)),
    ]

    if settings.is_devices_selection_enabled():
        renewal_lines.append(
            texts.t("subscription.extend.devices", "📱 Devices: {count}").format(count=subscription.device_limit)
        )

    renewal_lines.extend([
        "",
        texts.t("subscription.extend.select_period", "<b>Select extension period:</b>"),
        prices_text.rstrip(),
        "",
    ])

    message_text = "\n".join(renewal_lines)

    if promo_discounts_text:
        message_text += f"{promo_discounts_text}\n\n"

    promo_offer_hint = await _get_promo_offer_hint(
        db,
        db_user,
        texts,
        promo_offer_percent,
    )
    if promo_offer_hint:
        message_text += f"{promo_offer_hint}\n\n"

    message_text += texts.t("subscription.extend.price_note", "💡 <i>Price includes all your current servers and settings</i>")

    await callback.message.edit_text(
        message_text,
        reply_markup=get_extend_subscription_keyboard_with_prices(db_user.language, renewal_prices),
        parse_mode="HTML"
    )

    await callback.answer()

async def confirm_extend_subscription(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    from app.services.admin_notification_service import AdminNotificationService

    days = int(callback.data.split('_')[2])
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    if not subscription:
        await callback.answer(
            texts.t("subscription.extend.no_active", "⚠ You don't have an active subscription"),
            show_alert=True
        )
        return

    months_in_period = calculate_months_from_days(days)
    old_end_date = subscription.end_date
    server_uuid_prices: Dict[str, int] = {}

    try:
        from app.config import PERIOD_PRICES

        base_price_original = PERIOD_PRICES.get(days, 0)
        period_discount_percent = db_user.get_promo_discount("period", days)
        base_price, base_discount_total = apply_percentage_discount(
            base_price_original,
            period_discount_percent,
        )

        subscription_service = SubscriptionService()
        servers_price_per_month, per_server_monthly_prices = await subscription_service.get_countries_price_by_uuids(
            subscription.connected_squads,
            db,
            promo_group_id=db_user.promo_group_id,
        )
        servers_discount_percent = db_user.get_promo_discount(
            "servers",
            days,
        )
        total_servers_price = 0
        total_servers_discount = 0

        for squad_uuid, server_monthly_price in zip(subscription.connected_squads, per_server_monthly_prices):
            discount_per_month = server_monthly_price * servers_discount_percent // 100
            discounted_per_month = server_monthly_price - discount_per_month
            total_servers_price += discounted_per_month * months_in_period
            total_servers_discount += discount_per_month * months_in_period
            server_uuid_prices[squad_uuid] = discounted_per_month * months_in_period

        discounted_servers_price_per_month = servers_price_per_month - (
                servers_price_per_month * servers_discount_percent // 100
        )

        device_limit = subscription.device_limit
        if device_limit is None:
            if settings.is_devices_selection_enabled():
                device_limit = settings.DEFAULT_DEVICE_LIMIT
            else:
                forced_limit = settings.get_disabled_mode_device_limit()
                if forced_limit is None:
                    device_limit = settings.DEFAULT_DEVICE_LIMIT
                else:
                    device_limit = forced_limit

        additional_devices = max(0, (device_limit or 0) - settings.DEFAULT_DEVICE_LIMIT)
        devices_price_per_month = additional_devices * settings.PRICE_PER_DEVICE
        devices_discount_percent = db_user.get_promo_discount(
            "devices",
            days,
        )
        devices_discount_per_month = devices_price_per_month * devices_discount_percent // 100
        discounted_devices_price_per_month = devices_price_per_month - devices_discount_per_month
        total_devices_price = discounted_devices_price_per_month * months_in_period

        traffic_price_per_month = settings.get_traffic_price(subscription.traffic_limit_gb)
        traffic_discount_percent = db_user.get_promo_discount(
            "traffic",
            days,
        )
        traffic_discount_per_month = traffic_price_per_month * traffic_discount_percent // 100
        discounted_traffic_price_per_month = traffic_price_per_month - traffic_discount_per_month
        total_traffic_price = discounted_traffic_price_per_month * months_in_period

        price = base_price + total_servers_price + total_devices_price + total_traffic_price
        original_price = price
        promo_component = _apply_promo_offer_discount(db_user, price)
        if promo_component["discount"] > 0:
            price = promo_component["discounted"]

        monthly_additions = (
                discounted_servers_price_per_month
                + discounted_devices_price_per_month
                + discounted_traffic_price_per_month
        )
        is_valid = validate_pricing_calculation(base_price, monthly_additions, months_in_period, original_price)

        if not is_valid:
            logger.error(f"Error calculating extension price for user {db_user.telegram_id}")
            await callback.answer(
                texts.t("subscription.extend.price_calculation_error", "Price calculation error. Please contact support."),
                show_alert=True
            )
            return

        logger.info(f"💰 Extension price calculation for subscription {subscription.id} for {days} days ({months_in_period} months):")
        base_log = f"   📅 Period {days} days: {base_price_original / 100}₽"
        if base_discount_total > 0:
            base_log += (
                f" → {base_price / 100}₽"
                f" (discount {period_discount_percent}%: -{base_discount_total / 100}₽)"
            )
        logger.info(base_log)
        if total_servers_price > 0:
            logger.info(
                f"   🌐 Servers: {servers_price_per_month / 100}₽/month × {months_in_period}"
                f" = {total_servers_price / 100}₽"
                + (
                    f" (discount {servers_discount_percent}%:"
                    f" -{total_servers_discount / 100}₽)"
                    if total_servers_discount > 0
                    else ""
                )
            )
        if total_devices_price > 0:
            logger.info(
                f"   📱 Devices: {devices_price_per_month / 100}₽/month × {months_in_period}"
                f" = {total_devices_price / 100}₽"
                + (
                    f" (discount {devices_discount_percent}%:"
                    f" -{devices_discount_per_month * months_in_period / 100}₽)"
                    if devices_discount_percent > 0 and devices_discount_per_month > 0
                    else ""
                )
            )
        if total_traffic_price > 0:
            logger.info(
                f"   📊 Traffic: {traffic_price_per_month / 100}₽/month × {months_in_period}"
                f" = {total_traffic_price / 100}₽"
                + (
                    f" (discount {traffic_discount_percent}%:"
                    f" -{traffic_discount_per_month * months_in_period / 100}₽)"
                    if traffic_discount_percent > 0 and traffic_discount_per_month > 0
                    else ""
                )
            )
        if promo_component["discount"] > 0:
            logger.info(
                "   🎯 Promo offer: -%s₽ (%s%%)",
                promo_component["discount"] / 100,
                promo_component["percent"],
            )
        logger.info(f"   💎 TOTAL: {price / 100}₽")

    except Exception as e:
        logger.error(f"⚠ PRICE CALCULATION ERROR: {e}")
        await callback.answer(
            texts.t("subscription.extend.price_error", "⚠ Price calculation error"),
            show_alert=True
        )
        return

    if db_user.balance_kopeks < price:
        missing_kopeks = price - db_user.balance_kopeks
        required_text = texts.format_price(price)
        message_text = texts.t(
            "ADDON_INSUFFICIENT_FUNDS_MESSAGE",
            (
                "⚠️ <b>Insufficient funds</b>\n\n"
                "Service price: {required}\n"
                "Balance: {balance}\n"
                "Missing: {missing}\n\n"
                "Choose a top-up method. The amount will be filled in automatically."
            ),
        ).format(
            required=required_text,
            balance=texts.format_price(db_user.balance_kopeks),
            missing=texts.format_price(missing_kopeks),
        )

        # Prepare data for saving to cart
        cart_data = {
            'cart_mode': 'extend',
            'subscription_id': subscription.id,
            'period_days': days,
            'total_price': price,
            'user_id': db_user.id,
            'saved_cart': True,
            'missing_amount': missing_kopeks,
            'return_to_cart': True,
            'description': texts.t("subscription.extend.description", "Extension for {days} days").format(days=days),
            'consume_promo_offer': bool(promo_component["discount"] > 0),
        }
        
        await user_cart_service.save_user_cart(db_user.id, cart_data)

        await callback.message.edit_text(
            message_text,
            reply_markup=get_insufficient_balance_keyboard(
                db_user.language,
                amount_kopeks=missing_kopeks,
                has_saved_cart=True  # Indicate that there is a saved cart
            ),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    try:
        success = await subtract_user_balance(
            db,
            db_user,
            price,
            texts.t("subscription.extend.description", "Extension for {days} days").format(days=days),
            consume_promo_offer=promo_component["discount"] > 0,
        )

        if not success:
            await callback.answer(
                texts.t("subscription.extend.charge_error", "⚠ Charge error"),
                show_alert=True
            )
            return

        current_time = datetime.utcnow()

        if subscription.end_date > current_time:
            new_end_date = subscription.end_date + timedelta(days=days)
        else:
            new_end_date = current_time + timedelta(days=days)

        subscription.end_date = new_end_date

        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.updated_at = current_time

        await db.commit()
        await db.refresh(subscription)
        await db.refresh(db_user)

        # ensure freshly loaded values are available even if SQLAlchemy expires
        # attributes on subsequent access
        refreshed_end_date = subscription.end_date
        refreshed_balance = db_user.balance_kopeks

        from app.database.crud.server_squad import get_server_ids_by_uuids
        from app.database.crud.subscription import add_subscription_servers

        server_ids = await get_server_ids_by_uuids(db, subscription.connected_squads)
        if server_ids:
            from sqlalchemy import select
            from app.database.models import ServerSquad

            result = await db.execute(
                select(ServerSquad.id, ServerSquad.squad_uuid).where(ServerSquad.id.in_(server_ids))
            )
            id_to_uuid = {row.id: row.squad_uuid for row in result}
            default_price = total_servers_price // len(server_ids) if server_ids else 0
            server_prices_for_period = [
                server_uuid_prices.get(id_to_uuid.get(server_id, ""), default_price)
                for server_id in server_ids
            ]
            await add_subscription_servers(db, subscription, server_ids, server_prices_for_period)

        try:
            remnawave_result = await subscription_service.update_remnawave_user(
                db,
                subscription,
                reset_traffic=settings.RESET_TRAFFIC_ON_PAYMENT,
                reset_reason=texts.t("subscription.extend.reset_reason", "subscription extension"),
            )
            if remnawave_result:
                logger.info("✅ RemnaWave updated successfully")
            else:
                logger.error("⚠ REMNAWAVE UPDATE ERROR")
        except Exception as e:
            logger.error(f"⚠ EXCEPTION DURING REMNAWAVE UPDATE: {e}")

        transaction = await create_transaction(
            db=db,
            user_id=db_user.id,
            type=TransactionType.SUBSCRIPTION_PAYMENT,
            amount_kopeks=price,
            description=texts.t("subscription.extend.transaction_description", "Extension for {days} days ({months} months)").format(days=days, months=months_in_period)
        )

        try:
            notification_service = AdminNotificationService(callback.bot)
            await notification_service.send_subscription_extension_notification(
                db,
                db_user,
                subscription,
                transaction,
                days,
                old_end_date,
                new_end_date=refreshed_end_date,
                balance_after=refreshed_balance,
            )
        except Exception as e:
            logger.error(f"Error sending extension notification: {e}")

        success_message = (
            texts.t("subscription.extend.success", "✅ Subscription successfully extended!\n\n") +
            texts.t("subscription.extend.added_days", "⏰ Added: {days} days\n").format(days=days) +
            texts.t("subscription.extend.valid_until", "Valid until: {date}\n\n").format(date=format_local_datetime(refreshed_end_date, '%d.%m.%Y %H:%M')) +
            texts.t("subscription.extend.charged", "💰 Charged: {price}").format(price=texts.format_price(price))
        )

        if promo_component["discount"] > 0:
            success_message += (
                texts.t("subscription.extend.discount_note", " (including extra discount {percent}%: -{amount})").format(
                    percent=promo_component['percent'],
                    amount=texts.format_price(promo_component['discount'])
                )
            )

        await callback.message.edit_text(
            success_message,
            reply_markup=get_back_keyboard(db_user.language)
        )

        logger.info(f"✅ User {db_user.telegram_id} extended subscription for {days} days for {price / 100}₽")

    except Exception as e:
        logger.error(f"⚠ CRITICAL EXTENSION ERROR: {e}")
        import traceback
        logger.error(f"TRACEBACK: {traceback.format_exc()}")

        await callback.message.edit_text(
            texts.t("subscription.extend.error", "⚠ An error occurred while extending subscription. Please contact support."),
            reply_markup=get_back_keyboard(db_user.language)
        )

    await callback.answer()

async def select_period(
        callback: types.CallbackQuery,
        state: FSMContext,
        db_user: User
):
    period_days = int(callback.data.split('_')[1])
    texts = get_texts(db_user.language)

    data = await state.get_data()
    data['period_days'] = period_days
    data['total_price'] = PERIOD_PRICES[period_days]

    if settings.is_traffic_fixed():
        fixed_traffic_price = settings.get_traffic_price(settings.get_fixed_traffic_limit())
        data['total_price'] += fixed_traffic_price
        data['traffic_gb'] = settings.get_fixed_traffic_limit()

    await state.set_data(data)

    if settings.is_traffic_selectable():
        available_packages = [pkg for pkg in settings.get_traffic_packages() if pkg['enabled']]

        if not available_packages:
            await callback.answer(
                texts.t("TRAFFIC_PACKAGES_NOT_CONFIGURED", "⚠️ Traffic packages are not configured"),
                show_alert=True
            )
            return

        await callback.message.edit_text(
            texts.SELECT_TRAFFIC,
            reply_markup=get_traffic_packages_keyboard(db_user.language)
        )
        await state.set_state(SubscriptionStates.selecting_traffic)
        await callback.answer()
        return

    if await _should_show_countries_management(db_user):
        countries = await _get_available_countries(db_user.promo_group_id)
        await callback.message.edit_text(
            texts.SELECT_COUNTRIES,
            reply_markup=get_countries_keyboard(countries, [], db_user.language)
        )
        await state.set_state(SubscriptionStates.selecting_countries)
        await callback.answer()
        return

    countries = await _get_available_countries(db_user.promo_group_id)
    available_countries = [c for c in countries if c.get('is_available', True)]
    data['countries'] = [available_countries[0]['uuid']] if available_countries else []
    await state.set_data(data)

    if settings.is_devices_selection_enabled():
        selected_devices = data.get('devices', settings.DEFAULT_DEVICE_LIMIT)

        await callback.message.edit_text(
            texts.SELECT_DEVICES,
            reply_markup=get_devices_keyboard(selected_devices, db_user.language)
        )
        await state.set_state(SubscriptionStates.selecting_devices)
        await callback.answer()
        return

    if await present_subscription_summary(callback, state, db_user, texts):
        await callback.answer()

async def select_devices(
        callback: types.CallbackQuery,
        state: FSMContext,
        db_user: User
):
    texts = get_texts(db_user.language)

    if not settings.is_devices_selection_enabled():
        await callback.answer(
            texts.t("DEVICES_SELECTION_DISABLED", "⚠️ Device selection unavailable"),
            show_alert=True,
        )
        return

    if not callback.data.startswith("devices_") or callback.data == "devices_continue":
        await callback.answer(texts.t("DEVICES_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    try:
        devices = int(callback.data.split('_')[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("DEVICES_INVALID_COUNT", "❌ Invalid device count"), show_alert=True)
        return

    data = await state.get_data()

    base_price = (
            PERIOD_PRICES[data['period_days']] +
            settings.get_traffic_price(data['traffic_gb'])
    )

    countries = await _get_available_countries(db_user.promo_group_id)
    # Check that 'countries' key exists in data before accessing it
    selected_countries = data.get('countries', [])
    countries_price = sum(
        c['price_kopeks'] for c in countries
        if c['uuid'] in selected_countries
    )

    devices_price = max(0, devices - settings.DEFAULT_DEVICE_LIMIT) * settings.PRICE_PER_DEVICE

    previous_devices = data.get('devices', settings.DEFAULT_DEVICE_LIMIT)

    data['devices'] = devices
    data['total_price'] = base_price + countries_price + devices_price
    await state.set_data(data)

    if devices != previous_devices:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=get_devices_keyboard(devices, db_user.language)
            )
        except TelegramBadRequest as error:
            if "message is not modified" in str(error).lower():
                logger.debug(
                    texts.t("DEVICES_KEYBOARD_SKIP_UPDATE", "ℹ️ Skipping devices keyboard update: content unchanged")
                )
            else:
                raise

    await callback.answer()

async def devices_continue(
        callback: types.CallbackQuery,
        state: FSMContext,
        db_user: User,
        db: AsyncSession
):
    texts = get_texts(db_user.language)
    if not callback.data == "devices_continue":
        await callback.answer(
            texts.t("DEVICES_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return

    if await present_subscription_summary(callback, state, db_user):
        await callback.answer()

async def confirm_purchase(
        callback: types.CallbackQuery,
        state: FSMContext,
        db_user: User,
        db: AsyncSession
):
    from app.services.admin_notification_service import AdminNotificationService

    data = await state.get_data()
    texts = get_texts(db_user.language)

    await save_subscription_checkout_draft(db_user.id, dict(data))
    resume_callback = (
        "subscription_resume_checkout"
        if should_offer_checkout_resume(db_user, True)
        else None
    )

    countries = await _get_available_countries(db_user.promo_group_id)

    period_days = data.get('period_days')
    if period_days is None:
        await callback.message.edit_text(
            texts.t("SUBSCRIPTION_PURCHASE_ERROR", "Error processing subscription. Please start over."),
            reply_markup=get_back_keyboard(db_user.language)
        )
        await callback.answer()
        return
    months_in_period = data.get('months_in_period', calculate_months_from_days(period_days))

    base_price = data.get('base_price')
    base_price_original = data.get('base_price_original')
    base_discount_percent = data.get('base_discount_percent')
    base_discount_total = data.get('base_discount_total')

    if base_price is None:
        base_price_original = PERIOD_PRICES[period_days]
        base_discount_percent = db_user.get_promo_discount(
            "period",
            period_days,
        )
        base_price, base_discount_total = apply_percentage_discount(
            base_price_original,
            base_discount_percent,
        )
    else:
        if base_price_original is None:
            base_price_original = PERIOD_PRICES[period_days]
        if base_discount_percent is None:
            base_discount_percent = db_user.get_promo_discount(
                "period",
                period_days,
            )
        if base_discount_total is None:
            _, base_discount_total = apply_percentage_discount(
                base_price_original,
                base_discount_percent,
            )
    server_prices = data.get('server_prices_for_period', [])

    if not server_prices:
        countries_price_per_month = 0
        per_month_prices: List[int] = []
        for country in countries:
            # Check that 'countries' key exists in data before accessing it
            selected_countries = data.get('countries', [])
            if country['uuid'] in selected_countries:
                server_price_per_month = country['price_kopeks']
                countries_price_per_month += server_price_per_month
                per_month_prices.append(server_price_per_month)

        servers_discount_percent = db_user.get_promo_discount(
            "servers",
            period_days,
        )
        total_servers_price = 0
        total_servers_discount = 0
        discounted_servers_price_per_month = 0
        server_prices = []

        for server_price_per_month in per_month_prices:
            discounted_per_month, discount_per_month = apply_percentage_discount(
                server_price_per_month,
                servers_discount_percent,
            )
            total_price_for_server = discounted_per_month * months_in_period
            total_discount_for_server = discount_per_month * months_in_period

            discounted_servers_price_per_month += discounted_per_month
            total_servers_price += total_price_for_server
            total_servers_discount += total_discount_for_server
            server_prices.append(total_price_for_server)

        total_countries_price = total_servers_price
    else:
        total_countries_price = data.get('total_servers_price', sum(server_prices))
        countries_price_per_month = data.get('servers_price_per_month', 0)
        discounted_servers_price_per_month = data.get('servers_discounted_price_per_month', countries_price_per_month)
        total_servers_discount = data.get('servers_discount_total', 0)
        servers_discount_percent = data.get('servers_discount_percent', 0)

    devices_selection_enabled = settings.is_devices_selection_enabled()
    forced_disabled_limit: Optional[int] = None
    if devices_selection_enabled:
        devices_selected = data.get('devices', settings.DEFAULT_DEVICE_LIMIT)
    else:
        forced_disabled_limit = settings.get_disabled_mode_device_limit()
        if forced_disabled_limit is None:
            devices_selected = settings.DEFAULT_DEVICE_LIMIT
        else:
            devices_selected = forced_disabled_limit

    additional_devices = max(0, devices_selected - settings.DEFAULT_DEVICE_LIMIT)
    devices_price_per_month = data.get(
        'devices_price_per_month', additional_devices * settings.PRICE_PER_DEVICE
    )

    devices_discount_percent = 0
    discounted_devices_price_per_month = 0
    devices_discount_total = 0
    total_devices_price = 0

    if devices_selection_enabled and additional_devices > 0:
        if 'devices_discount_percent' in data:
            devices_discount_percent = data.get('devices_discount_percent', 0)
            discounted_devices_price_per_month = data.get(
                'devices_discounted_price_per_month', devices_price_per_month
            )
            devices_discount_total = data.get('devices_discount_total', 0)
            total_devices_price = data.get(
                'total_devices_price', discounted_devices_price_per_month * months_in_period
            )
        else:
            devices_discount_percent = db_user.get_promo_discount(
                "devices",
                period_days,
            )
            discounted_devices_price_per_month, discount_per_month = apply_percentage_discount(
                devices_price_per_month,
                devices_discount_percent,
            )
            devices_discount_total = discount_per_month * months_in_period
            total_devices_price = discounted_devices_price_per_month * months_in_period

    if settings.is_traffic_fixed():
        final_traffic_gb = settings.get_fixed_traffic_limit()
        traffic_price_per_month = data.get(
            'traffic_price_per_month', settings.get_traffic_price(final_traffic_gb)
        )
    else:
        final_traffic_gb = data.get('final_traffic_gb', data.get('traffic_gb'))
        traffic_gb = data.get('traffic_gb')
        if traffic_gb is not None:
            traffic_price_per_month = data.get(
                'traffic_price_per_month', settings.get_traffic_price(traffic_gb)
            )
        else:
            traffic_price_per_month = data.get(
                'traffic_price_per_month', 0
            )

    if 'traffic_discount_percent' in data:
        traffic_discount_percent = data.get('traffic_discount_percent', 0)
        discounted_traffic_price_per_month = data.get(
            'traffic_discounted_price_per_month', traffic_price_per_month
        )
        traffic_discount_total = data.get('traffic_discount_total', 0)
        total_traffic_price = data.get(
            'total_traffic_price', discounted_traffic_price_per_month * months_in_period
        )
    else:
        traffic_discount_percent = db_user.get_promo_discount(
            "traffic",
            period_days,
        )
        discounted_traffic_price_per_month, discount_per_month = apply_percentage_discount(
            traffic_price_per_month,
            traffic_discount_percent,
        )
        traffic_discount_total = discount_per_month * months_in_period
        total_traffic_price = discounted_traffic_price_per_month * months_in_period

    total_servers_price = data.get('total_servers_price', total_countries_price)

    cached_total_price = data.get('total_price', 0)
    cached_promo_discount_value = data.get('promo_offer_discount_value', 0)

    validation_total_price = data.get('total_price_before_promo_offer')
    if validation_total_price is None and cached_promo_discount_value > 0:
        validation_total_price = cached_total_price + cached_promo_discount_value
    if validation_total_price is None:
        validation_total_price = cached_total_price

    current_promo_offer_percent = _get_promo_offer_discount_percent(db_user)
    if current_promo_offer_percent > 0:
        final_price, promo_offer_discount_value = apply_percentage_discount(
            validation_total_price,
            current_promo_offer_percent,
        )
        promo_offer_discount_percent = current_promo_offer_percent
    else:
        final_price = validation_total_price
        promo_offer_discount_value = 0
        promo_offer_discount_percent = 0

    discounted_monthly_additions = data.get(
        'discounted_monthly_additions',
        discounted_traffic_price_per_month
        + discounted_servers_price_per_month
        + discounted_devices_price_per_month,
    )

    is_valid = validate_pricing_calculation(
        base_price,
        discounted_monthly_additions,
        months_in_period,
        validation_total_price,
    )

    if not is_valid:
        logger.error(f"Subscription price calculation error for user {db_user.telegram_id}")
        await callback.answer(
            texts.t("SUBSCRIPTION_PRICE_CALCULATION_ERROR", "Price calculation error. Please contact support."),
            show_alert=True
        )
        return

    logger.info(f"Subscription purchase calculation for {data['period_days']} days ({months_in_period} months):")
    base_log = f"   Period: {base_price_original / 100}₽"
    if base_discount_total and base_discount_total > 0:
        base_log += (
            f" → {base_price / 100}₽"
            f" (discount {base_discount_percent}%: -{base_discount_total / 100}₽)"
        )
    logger.info(base_log)
    if total_traffic_price > 0:
        message = (
            f"   Traffic: {traffic_price_per_month / 100}₽/month × {months_in_period}"
            f" = {total_traffic_price / 100}₽"
        )
        if traffic_discount_total > 0:
            message += (
                f" (discount {traffic_discount_percent}%:"
                f" -{traffic_discount_total / 100}₽)"
            )
        logger.info(message)
    if total_servers_price > 0:
        message = (
            f"   Servers: {countries_price_per_month / 100}₽/month × {months_in_period}"
            f" = {total_servers_price / 100}₽"
        )
        if total_servers_discount > 0:
            message += (
                f" (discount {servers_discount_percent}%:"
                f" -{total_servers_discount / 100}₽)"
            )
        logger.info(message)
    if total_devices_price > 0:
        message = (
            f"   Devices: {devices_price_per_month / 100}₽/month × {months_in_period}"
            f" = {total_devices_price / 100}₽"
        )
        if devices_discount_total > 0:
            message += (
                f" (discount {devices_discount_percent}%:"
                f" -{devices_discount_total / 100}₽)"
            )
        logger.info(message)
    if promo_offer_discount_value > 0:
        logger.info(
            "   🎯 Promo offer: -%s₽ (%s%%)",
            promo_offer_discount_value / 100,
            promo_offer_discount_percent,
        )
    logger.info(f"   TOTAL: {final_price / 100}₽")

    if db_user.balance_kopeks < final_price:
        missing_kopeks = final_price - db_user.balance_kopeks
        message_text = texts.t(
            "ADDON_INSUFFICIENT_FUNDS_MESSAGE",
            (
                "⚠️ <b>Insufficient funds</b>\n\n"
                "Service price: {required}\n"
                "Balance: {balance}\n"
                "Missing: {missing}\n\n"
                "Choose a top-up method. The amount will be filled in automatically."
            ),
        ).format(
            required=texts.format_price(final_price),
            balance=texts.format_price(db_user.balance_kopeks),
            missing=texts.format_price(missing_kopeks),
        )

        # Save cart data to Redis before proceeding to top-up
        cart_data = {
            **data,
            'saved_cart': True,
            'missing_amount': missing_kopeks,
            'return_to_cart': True,
            'user_id': db_user.id
        }
        
        await user_cart_service.save_user_cart(db_user.id, cart_data)

        await callback.message.edit_text(
            message_text,
            reply_markup=get_insufficient_balance_keyboard(
                db_user.language,
                resume_callback=resume_callback,
                amount_kopeks=missing_kopeks,
                has_saved_cart=True  # Indicate that there is a saved cart
            ),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    purchase_completed = False

    try:
        success = await subtract_user_balance(
            db,
            db_user,
            final_price,
            texts.t("SUBSCRIPTION_PURCHASE_TRANSACTION_DESCRIPTION", "Subscription purchase for {days} days").format(days=data['period_days']),
            consume_promo_offer=promo_offer_discount_value > 0,
        )

        if not success:
            missing_kopeks = final_price - db_user.balance_kopeks
            message_text = texts.t(
                "ADDON_INSUFFICIENT_FUNDS_MESSAGE",
                (
                    "⚠️ <b>Insufficient funds</b>\n\n"
                    "Service price: {required}\n"
                    "Balance: {balance}\n"
                    "Missing: {missing}\n\n"
                    "Choose a top-up method. The amount will be filled in automatically."
                ),
            ).format(
                required=texts.format_price(final_price),
                balance=texts.format_price(db_user.balance_kopeks),
                missing=texts.format_price(missing_kopeks),
            )

            await callback.message.edit_text(
                message_text,
                reply_markup=get_insufficient_balance_keyboard(
                    db_user.language,
                    resume_callback=resume_callback,
                    amount_kopeks=missing_kopeks,
                ),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        existing_subscription = db_user.subscription
        if devices_selection_enabled:
            selected_devices = devices_selected
        else:
            selected_devices = forced_disabled_limit

        should_update_devices = selected_devices is not None

        was_trial_conversion = False
        current_time = datetime.utcnow()

        if existing_subscription:
            logger.info(f"Updating existing subscription for user {db_user.telegram_id}")

            bonus_period = timedelta()

            if existing_subscription.is_trial:
                logger.info(f"Trial to paid conversion for user {db_user.telegram_id}")
                was_trial_conversion = True

                trial_duration = (current_time - existing_subscription.start_date).days

                if settings.TRIAL_ADD_REMAINING_DAYS_TO_PAID and existing_subscription.end_date:
                    remaining_trial_delta = existing_subscription.end_date - current_time
                    if remaining_trial_delta.total_seconds() > 0:
                        bonus_period = remaining_trial_delta
                        logger.info(
                            "Adding remaining trial time (%s) to new subscription for user %s",
                            bonus_period,
                            db_user.telegram_id,
                        )

                try:
                    from app.database.crud.subscription_conversion import create_subscription_conversion
                    await create_subscription_conversion(
                        db=db,
                        user_id=db_user.id,
                        trial_duration_days=trial_duration,
                        payment_method="balance",
                        first_payment_amount_kopeks=final_price,
                        first_paid_period_days=period_days
                    )
                    logger.info(
                        f"Conversion recorded: {trial_duration} days trial → {period_days} days paid for {final_price / 100}₽")
                except Exception as conversion_error:
                    logger.error(f"Error recording conversion: {conversion_error}")

            existing_subscription.is_trial = False
            existing_subscription.status = SubscriptionStatus.ACTIVE.value
            existing_subscription.traffic_limit_gb = final_traffic_gb
            if should_update_devices:
                existing_subscription.device_limit = selected_devices
            # Check that when updating existing subscription there is at least one country
            selected_countries = data.get('countries', [])
            if not selected_countries:
                # If subscription already existed, don't allow disabling all countries
                # If subscription is new, allow it, but usually through UI user should select at least one server
                if existing_subscription and existing_subscription.connected_squads is not None:
                    # Check that data contains information that this is an update of existing subscription
                    # or something indicates that we shouldn't disable all countries
                    pass  # For simplicity, just check that country list is not empty
                else:
                    # For new subscription allow empty list if it's not an update
                    pass

                # But for safety - if country list is empty, check that it's allowed
                # otherwise return error
                if not selected_countries:
                    texts = get_texts(db_user.language)
                    await callback.message.edit_text(
                        texts.t(
                            "COUNTRIES_MINIMUM_REQUIRED",
                            "❌ Cannot disconnect all countries. At least one country must remain connected."
                        ),
                        reply_markup=get_back_keyboard(db_user.language)
                    )
                    await callback.answer()
                    return

            existing_subscription.connected_squads = selected_countries

            existing_subscription.start_date = current_time
            existing_subscription.end_date = current_time + timedelta(days=period_days) + bonus_period
            existing_subscription.updated_at = current_time

            existing_subscription.traffic_used_gb = 0.0

            await db.commit()
            await db.refresh(existing_subscription)
            subscription = existing_subscription

        else:
            logger.info(f"Creating new subscription for user {db_user.telegram_id}")
            default_device_limit = getattr(settings, "DEFAULT_DEVICE_LIMIT", 1)
            resolved_device_limit = selected_devices

            if resolved_device_limit is None:
                if devices_selection_enabled:
                    resolved_device_limit = default_device_limit
                else:
                    if forced_disabled_limit is not None:
                        resolved_device_limit = forced_disabled_limit
                    else:
                        resolved_device_limit = default_device_limit

            if resolved_device_limit is None and devices_selection_enabled:
                resolved_device_limit = default_device_limit

            # Check that for new subscription there is also at least one country, if user goes through countries interface
            new_subscription_countries = data.get('countries', [])
            if not new_subscription_countries:
                # Check if this was a purchase through countries interface, and if yes, require at least one country
                # If data explicitly indicates this is countries interface, or there are other signs - require country
                # For simplicity - check that country is required if going through countries UI
                texts = get_texts(db_user.language)
                await callback.message.edit_text(
                    texts.t(
                        "COUNTRIES_MINIMUM_REQUIRED",
                        "❌ Cannot disconnect all countries. At least one country must remain connected."
                    ),
                    reply_markup=get_back_keyboard(db_user.language)
                )
                await callback.answer()
                return

            subscription = await create_paid_subscription_with_traffic_mode(
                db=db,
                user_id=db_user.id,
                duration_days=period_days,
                device_limit=resolved_device_limit,
                connected_squads=new_subscription_countries,
                traffic_gb=final_traffic_gb
            )

        from app.utils.user_utils import mark_user_as_had_paid_subscription
        await mark_user_as_had_paid_subscription(db, db_user)

        from app.database.crud.server_squad import get_server_ids_by_uuids, add_user_to_servers
        from app.database.crud.subscription import add_subscription_servers

        server_ids = await get_server_ids_by_uuids(db, data.get('countries', []))

        if server_ids:
            await add_subscription_servers(db, subscription, server_ids, server_prices)
            await add_user_to_servers(db, server_ids)

            logger.info(f"Saved server prices for entire period: {server_prices}")
    
        await db.refresh(db_user)
    
        subscription_service = SubscriptionService()
    
        if db_user.remnawave_uuid:
            remnawave_user = await subscription_service.update_remnawave_user(
                db,
                subscription,
                reset_traffic=settings.RESET_TRAFFIC_ON_PAYMENT,
                reset_reason="subscription_purchase",
            )
        else:
            remnawave_user = await subscription_service.create_remnawave_user(
                db,
                subscription,
                reset_traffic=settings.RESET_TRAFFIC_ON_PAYMENT,
                reset_reason="subscription_purchase",
            )
    
        if not remnawave_user:
            logger.error(f"Failed to create/update RemnaWave user for {db_user.telegram_id}")
            remnawave_user = await subscription_service.create_remnawave_user(
                db,
                subscription,
                reset_traffic=settings.RESET_TRAFFIC_ON_PAYMENT,
                reset_reason="subscription_purchase_retry",
            )
    
        transaction = await create_transaction(
            db=db,
            user_id=db_user.id,
            type=TransactionType.SUBSCRIPTION_PAYMENT,
            amount_kopeks=final_price,
            description=texts.t("SUBSCRIPTION_TRANSACTION_DESCRIPTION", "Subscription for {days} days ({months} months)").format(days=period_days, months=months_in_period)
        )

        try:
            notification_service = AdminNotificationService(callback.bot)
            await notification_service.send_subscription_purchase_notification(
                db, db_user, subscription, transaction, period_days, was_trial_conversion
            )
        except Exception as e:
            logger.error(f"Error sending purchase notification: {e}")

        await db.refresh(db_user)
        await db.refresh(subscription)

        subscription_link = get_display_subscription_link(subscription)
        hide_subscription_link = settings.should_hide_subscription_link()

        discount_note = ""
        if promo_offer_discount_value > 0:
            discount_note = texts.t(
                "SUBSCRIPTION_PROMO_DISCOUNT_NOTE",
                "⚡ Extra discount {percent}%: -{amount}",
            ).format(
                percent=promo_offer_discount_percent,
                amount=texts.format_price(promo_offer_discount_value),
            )

        if remnawave_user and subscription_link:
            if settings.is_happ_cryptolink_mode():
                success_text = (
                        f"{texts.SUBSCRIPTION_PURCHASED}\n\n"
                        + texts.t(
                    "SUBSCRIPTION_HAPP_LINK_PROMPT",
                    "🔒 Subscription link created. Click the 'Connect' button below to open it in Happ.",
                )
                        + "\n\n"
                        + texts.t(
                    "SUBSCRIPTION_IMPORT_INSTRUCTION_PROMPT",
                    "📱 Click the button below to get VPN setup instructions for your device",
                )
                )
            elif hide_subscription_link:
                success_text = (
                        f"{texts.SUBSCRIPTION_PURCHASED}\n\n"
                        + texts.t(
                    "SUBSCRIPTION_LINK_HIDDEN_NOTICE",
                    "ℹ️ Subscription link is available via buttons below or in the 'My subscription' section.",
                )
                        + "\n\n"
                        + texts.t(
                    "SUBSCRIPTION_IMPORT_INSTRUCTION_PROMPT",
                    "📱 Click the button below to get VPN setup instructions for your device",
                )
                )
            else:
                import_link_section = texts.t(
                    "SUBSCRIPTION_IMPORT_LINK_SECTION",
                    "🔗 <b>Your import link for VPN app:</b>\n<code>{subscription_url}</code>",
                ).format(subscription_url=subscription_link)

                success_text = (
                    f"{texts.SUBSCRIPTION_PURCHASED}\n\n"
                    f"{import_link_section}\n\n"
                    f"{texts.t('SUBSCRIPTION_IMPORT_INSTRUCTION_PROMPT', '📱 Click the button below to get VPN setup instructions for your device')}"
                )

            if discount_note:
                success_text = f"{success_text}\n\n{discount_note}"

            connect_mode = settings.CONNECT_BUTTON_MODE

            if connect_mode == "miniapp_subscription":
                connect_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                            web_app=types.WebAppInfo(url=subscription_link),
                        )
                    ],
                    [InlineKeyboardButton(text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ Back to main menu"),
                                          callback_data="back_to_menu")],
                ])
            elif connect_mode == "miniapp_custom":
                if not settings.MINIAPP_CUSTOM_URL:
                    await callback.answer(
                        texts.t(
                            "CUSTOM_MINIAPP_URL_NOT_SET",
                            "⚠ Custom mini-app URL is not configured",
                        ),
                        show_alert=True,
                    )
                    return

                connect_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                            web_app=types.WebAppInfo(url=settings.MINIAPP_CUSTOM_URL),
                        )
                    ],
                    [InlineKeyboardButton(text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ Back to main menu"),
                                          callback_data="back_to_menu")],
                ])
            elif connect_mode == "link":
                rows = [
                    [InlineKeyboardButton(text=texts.t("CONNECT_BUTTON", "🔗 Connect"), url=subscription_link)]
                ]
                happ_row = get_happ_download_button_row(texts)
                if happ_row:
                    rows.append(happ_row)
                rows.append([InlineKeyboardButton(text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ Back to main menu"),
                                                  callback_data="back_to_menu")])
                connect_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
            elif connect_mode == "happ_cryptolink":
                rows = [
                    [
                        InlineKeyboardButton(
                            text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                            callback_data="open_subscription_link",
                        )
                    ]
                ]
                happ_row = get_happ_download_button_row(texts)
                if happ_row:
                    rows.append(happ_row)
                rows.append([InlineKeyboardButton(text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ Back to main menu"),
                                                  callback_data="back_to_menu")])
                connect_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
            else:
                connect_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=texts.t("CONNECT_BUTTON", "🔗 Connect"),
                                          callback_data="subscription_connect")],
                    [InlineKeyboardButton(text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "⬅️ Back to main menu"),
                                          callback_data="back_to_menu")],
                ])

            await callback.message.edit_text(
                success_text,
                reply_markup=connect_keyboard,
                parse_mode="HTML"
            )
        else:
            purchase_text = texts.SUBSCRIPTION_PURCHASED
            if discount_note:
                purchase_text = f"{purchase_text}\n\n{discount_note}"
            await callback.message.edit_text(
                texts.t(
                    "SUBSCRIPTION_LINK_GENERATING_NOTICE",
                    "{purchase_text}\n\nThe link is being generated, go to the 'My subscription' section in a few seconds.",
                ).format(purchase_text=purchase_text),
                reply_markup=get_back_keyboard(db_user.language)
            )

        purchase_completed = True
        logger.info(
            f"User {db_user.telegram_id} purchased subscription for {data['period_days']} days for {final_price / 100}₽")

    except Exception as e:
        logger.error(f"Subscription purchase error: {e}")
        await callback.message.edit_text(
            texts.ERROR,
            reply_markup=get_back_keyboard(db_user.language)
        )

    if purchase_completed:
        await clear_subscription_checkout_draft(db_user.id)

    await state.clear()
    await callback.answer()

async def resume_subscription_checkout(
        callback: types.CallbackQuery,
        state: FSMContext,
        db_user: User,
):
    texts = get_texts(db_user.language)

    draft = await get_subscription_checkout_draft(db_user.id)

    if not draft:
        await callback.answer(texts.NO_SAVED_SUBSCRIPTION_ORDER, show_alert=True)
        return

    try:
        summary_text, prepared_data = await _prepare_subscription_summary(db_user, draft, texts)
    except ValueError as exc:
        logger.error(
            f"Error restoring subscription order for user {db_user.telegram_id}: {exc}"
        )
        await clear_subscription_checkout_draft(db_user.id)
        await callback.answer(texts.NO_SAVED_SUBSCRIPTION_ORDER, show_alert=True)
        return

    await state.set_data(prepared_data)
    await state.set_state(SubscriptionStates.confirming_purchase)
    await save_subscription_checkout_draft(db_user.id, prepared_data)

    await callback.message.edit_text(
        summary_text,
        reply_markup=get_subscription_confirm_keyboard(db_user.language),
        parse_mode="HTML",
    )

    await callback.answer()

async def create_paid_subscription_with_traffic_mode(
        db: AsyncSession,
        user_id: int,
        duration_days: int,
        device_limit: Optional[int],
        connected_squads: List[str],
        traffic_gb: Optional[int] = None
):
    from app.config import settings

    if traffic_gb is None:
        if settings.is_traffic_fixed():
            traffic_limit_gb = settings.get_fixed_traffic_limit()
        else:
            traffic_limit_gb = 0
    else:
        traffic_limit_gb = traffic_gb

    create_kwargs = dict(
        db=db,
        user_id=user_id,
        duration_days=duration_days,
        traffic_limit_gb=traffic_limit_gb,
        connected_squads=connected_squads,
        update_server_counters=False,
    )

    if device_limit is not None:
        create_kwargs['device_limit'] = device_limit

    subscription = await create_paid_subscription(**create_kwargs)

    logger.info(f"📋 Created subscription with traffic: {traffic_limit_gb} GB (mode: {settings.TRAFFIC_SELECTION_MODE})")

    return subscription

async def handle_subscription_settings(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    if not subscription or subscription.is_trial:
        await callback.answer(
            texts.t(
                "SUBSCRIPTION_SETTINGS_PAID_ONLY",
                "⚠️ Settings are only available for paid subscriptions",
            ),
            show_alert=True,
        )
        return

    show_devices = settings.is_devices_selection_enabled()

    if show_devices:
        devices_used = await get_current_devices_count(db_user)
    else:
        devices_used = 0

    settings_template = texts.t(
        "SUBSCRIPTION_SETTINGS_OVERVIEW",
        (
            "⚙️ <b>Subscription settings</b>\n\n"
            "📊 <b>Current parameters:</b>\n"
            "🌐 Countries: {countries_count}\n"
            "📈 Traffic: {traffic_used} / {traffic_limit}\n"
            "📱 Devices: {devices_used} / {devices_limit}\n\n"
            "Choose what you want to change:"
        ),
    )

    if not show_devices:
        settings_template = settings_template.replace(
            "\n📱 Devices: {devices_used} / {devices_limit}",
            "",
        )

    settings_text = settings_template.format(
        countries_count=len(subscription.connected_squads),
        traffic_used=texts.format_traffic(subscription.traffic_used_gb),
        traffic_limit=texts.format_traffic(subscription.traffic_limit_gb),
        devices_used=devices_used,
        devices_limit=subscription.device_limit,
    )

    show_countries = await _should_show_countries_management(db_user)

    await callback.message.edit_text(
        settings_text,
        reply_markup=get_updated_subscription_settings_keyboard(db_user.language, show_countries),
        parse_mode="HTML"
    )
    await callback.answer()

async def clear_saved_cart(
        callback: types.CallbackQuery,
        state: FSMContext,
        db_user: User,
        db: AsyncSession
):
    # Clear both FSM and Redis
    await state.clear()
    await user_cart_service.delete_user_cart(db_user.id)

    from app.handlers.menu import show_main_menu
    await show_main_menu(callback, db_user, db)

    texts = get_texts(db_user.language)
    await callback.answer(texts.t("subscription.cart.cleared", "🗑️ Cart cleared"))

def register_handlers(dp: Dispatcher):
    update_traffic_prices()

    dp.callback_query.register(
        show_subscription_info,
        F.data == "menu_subscription"
    )

    dp.callback_query.register(
        show_trial_offer,
        F.data == "menu_trial"
    )

    dp.callback_query.register(
        activate_trial,
        F.data == "trial_activate"
    )

    dp.callback_query.register(
        start_subscription_purchase,
        F.data.in_(["menu_buy", "subscription_upgrade", "subscription_purchase"])
    )

    dp.callback_query.register(
        handle_add_countries,
        F.data == "subscription_add_countries"
    )

    dp.callback_query.register(
        handle_switch_traffic,
        F.data == "subscription_switch_traffic"
    )

    dp.callback_query.register(
        confirm_switch_traffic,
        F.data.startswith("switch_traffic_")
    )

    dp.callback_query.register(
        execute_switch_traffic,
        F.data.startswith("confirm_switch_traffic_")
    )

    dp.callback_query.register(
        handle_change_devices,
        F.data == "subscription_change_devices"
    )

    dp.callback_query.register(
        confirm_change_devices,
        F.data.startswith("change_devices_")
    )

    dp.callback_query.register(
        execute_change_devices,
        F.data.startswith("confirm_change_devices_")
    )

    dp.callback_query.register(
        handle_extend_subscription,
        F.data == "subscription_extend"
    )

    dp.callback_query.register(
        handle_reset_traffic,
        F.data == "subscription_reset_traffic"
    )

    dp.callback_query.register(
        confirm_add_devices,
        F.data.startswith("add_devices_")
    )

    dp.callback_query.register(
        confirm_extend_subscription,
        F.data.startswith("extend_period_")
    )

    dp.callback_query.register(
        confirm_reset_traffic,
        F.data == "confirm_reset_traffic"
    )

    dp.callback_query.register(
        handle_reset_devices,
        F.data == "subscription_reset_devices"
    )

    dp.callback_query.register(
        confirm_reset_devices,
        F.data == "confirm_reset_devices"
    )

    dp.callback_query.register(
        select_period,
        F.data.startswith("period_"),
        SubscriptionStates.selecting_period
    )

    dp.callback_query.register(
        select_traffic,
        F.data.startswith("traffic_"),
        SubscriptionStates.selecting_traffic
    )

    dp.callback_query.register(
        select_devices,
        F.data.startswith("devices_") & ~F.data.in_(["devices_continue"]),
        SubscriptionStates.selecting_devices
    )

    dp.callback_query.register(
        devices_continue,
        F.data == "devices_continue",
        SubscriptionStates.selecting_devices
    )

    dp.callback_query.register(
        confirm_purchase,
        F.data == "subscription_confirm",
        SubscriptionStates.confirming_purchase
    )

    dp.callback_query.register(
        resume_subscription_checkout,
        F.data == "subscription_resume_checkout",
    )

    dp.callback_query.register(
        return_to_saved_cart,
        F.data == "return_to_saved_cart",
    )

    dp.callback_query.register(
        clear_saved_cart,
        F.data == "clear_saved_cart",
    )

    dp.callback_query.register(
        handle_autopay_menu,
        F.data == "subscription_autopay"
    )

    dp.callback_query.register(
        toggle_autopay,
        F.data.in_(["autopay_enable", "autopay_disable"])
    )

    dp.callback_query.register(
        show_autopay_days,
        F.data == "autopay_set_days"
    )

    dp.callback_query.register(
        handle_subscription_config_back,
        F.data == "subscription_config_back"
    )

    dp.callback_query.register(
        handle_subscription_cancel,
        F.data == "subscription_cancel"
    )

    dp.callback_query.register(
        set_autopay_days,
        F.data.startswith("autopay_days_")
    )

    dp.callback_query.register(
        select_country,
        F.data.startswith("country_"),
        SubscriptionStates.selecting_countries
    )

    dp.callback_query.register(
        countries_continue,
        F.data == "countries_continue",
        SubscriptionStates.selecting_countries
    )

    dp.callback_query.register(
        handle_manage_country,
        F.data.startswith("country_manage_")
    )

    dp.callback_query.register(
        apply_countries_changes,
        F.data == "countries_apply"
    )

    dp.callback_query.register(
        claim_discount_offer,
        F.data.startswith("claim_discount_")
    )

    dp.callback_query.register(
        handle_promo_offer_close,
        F.data == "promo_offer_close",
    )

    dp.callback_query.register(
        handle_happ_download_request,
        F.data == "subscription_happ_download"
    )

    dp.callback_query.register(
        handle_happ_download_platform_choice,
        F.data.in_([
            "happ_download_ios",
            "happ_download_android",
            "happ_download_pc",
            "happ_download_macos",
            "happ_download_windows",
        ])
    )

    dp.callback_query.register(
        handle_happ_download_close,
        F.data == "happ_download_close"
    )

    dp.callback_query.register(
        handle_happ_download_back,
        F.data == "happ_download_back"
    )

    dp.callback_query.register(
        handle_connect_subscription,
        F.data == "subscription_connect"
    )

    dp.callback_query.register(
        handle_device_guide,
        F.data.startswith("device_guide_")
    )

    dp.callback_query.register(
        handle_app_selection,
        F.data.startswith("app_list_")
    )

    dp.callback_query.register(
        handle_specific_app_guide,
        F.data.startswith("app_")
    )

    dp.callback_query.register(
        handle_open_subscription_link,
        F.data == "open_subscription_link"
    )

    dp.callback_query.register(
        handle_subscription_settings,
        F.data == "subscription_settings"
    )

    dp.callback_query.register(
        handle_no_traffic_packages,
        F.data == "no_traffic_packages"
    )

    dp.callback_query.register(
        handle_device_management,
        F.data == "subscription_manage_devices"
    )

    dp.callback_query.register(
        handle_devices_page,
        F.data.startswith("devices_page_")
    )

    dp.callback_query.register(
        handle_single_device_reset,
        F.data.regexp(r"^reset_device_\d+_\d+$")
    )

    dp.callback_query.register(
        handle_all_devices_reset_from_management,
        F.data == "reset_all_devices"
    )

    dp.callback_query.register(
        show_device_connection_help,
        F.data == "device_connection_help"
    )
    
    # Register handler for simple purchase
    dp.callback_query.register(
        handle_simple_subscription_purchase,
        F.data == "simple_subscription_purchase"
    )


async def handle_simple_subscription_purchase(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession,
):
    """Handles simple subscription purchase."""
    texts = get_texts(db_user.language)
    
    if not settings.SIMPLE_SUBSCRIPTION_ENABLED:
        await callback.answer(
            texts.t("SIMPLE_SUBSCRIPTION_UNAVAILABLE", "❌ Simple subscription purchase is temporarily unavailable"),
            show_alert=True
        )
        return
    
    # Determine device limit for current mode
    simple_device_limit = resolve_simple_subscription_device_limit()

    # Check if user has active subscription
    from app.database.crud.subscription import get_subscription_by_user_id
    current_subscription = await get_subscription_by_user_id(db, db_user.id)

    # If user already has active subscription, extend it
    if current_subscription and current_subscription.is_active:
        # Extend existing subscription
        await _extend_existing_subscription(
            callback=callback,
            db_user=db_user,
            db=db,
            current_subscription=current_subscription,
            period_days=settings.SIMPLE_SUBSCRIPTION_PERIOD_DAYS,
            device_limit=simple_device_limit,
            traffic_limit_gb=settings.SIMPLE_SUBSCRIPTION_TRAFFIC_GB,
            squad_uuid=settings.SIMPLE_SUBSCRIPTION_SQUAD_UUID
        )
        return

    # Prepare simple subscription parameters
    subscription_params = {
        "period_days": settings.SIMPLE_SUBSCRIPTION_PERIOD_DAYS,
        "device_limit": simple_device_limit,
        "traffic_limit_gb": settings.SIMPLE_SUBSCRIPTION_TRAFFIC_GB,
        "squad_uuid": settings.SIMPLE_SUBSCRIPTION_SQUAD_UUID
    }
    
    # Save parameters to state
    await state.update_data(subscription_params=subscription_params)
    
    # Check user balance
    user_balance_kopeks = getattr(db_user, "balance_kopeks", 0)
    # Calculate subscription price
    price_kopeks, price_breakdown = await _calculate_simple_subscription_price(
        db,
        subscription_params,
        user=db_user,
        resolved_squad_uuid=subscription_params.get("squad_uuid"),
    )
    logger.debug(
        "SIMPLE_SUBSCRIPTION_PURCHASE_PRICE | user=%s | total=%s | base=%s | traffic=%s | devices=%s | servers=%s | discount=%s",
        db_user.id,
        price_kopeks,
        price_breakdown.get("base_price", 0),
        price_breakdown.get("traffic_price", 0),
        price_breakdown.get("devices_price", 0),
        price_breakdown.get("servers_price", 0),
        price_breakdown.get("total_discount", 0),
    )
    traffic_text = (
        texts.t("TRAFFIC_UNLIMITED", "Unlimited")
        if subscription_params["traffic_limit_gb"] == 0
        else texts.t("TRAFFIC_GB_FORMAT", "{gb} GB").format(gb=subscription_params['traffic_limit_gb'])
    )
    
    if user_balance_kopeks >= price_kopeks:
        # If balance is sufficient, offer to pay from balance
        simple_lines = [
            texts.t("SIMPLE_SUBSCRIPTION_TITLE", "⚡ <b>Simple subscription purchase</b>"),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_PERIOD", "📅 Period: {days} days").format(days=subscription_params['period_days']),
        ]

        if settings.is_devices_selection_enabled():
            simple_lines.append(
                texts.t("SIMPLE_SUBSCRIPTION_DEVICES", "📱 Devices: {count}").format(count=subscription_params['device_limit'])
            )

        server_text = (
            texts.t("SIMPLE_SUBSCRIPTION_SERVER_ANY", "Any available")
            if not subscription_params['squad_uuid']
            else texts.t("SIMPLE_SUBSCRIPTION_SERVER_SELECTED", "Selected")
        )
        
        simple_lines.extend([
            texts.t("SIMPLE_SUBSCRIPTION_TRAFFIC", "📊 Traffic: {traffic}").format(traffic=traffic_text),
            texts.t("SIMPLE_SUBSCRIPTION_SERVER", "🌍 Server: {server}").format(server=server_text),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_COST", "💰 Cost: {cost}").format(cost=settings.format_price(price_kopeks)),
            texts.t("SIMPLE_SUBSCRIPTION_BALANCE", "💳 Your balance: {balance}").format(balance=settings.format_price(user_balance_kopeks)),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_PAYMENT_OPTIONS", "You can pay for the subscription from your balance or choose another payment method."),
        ])

        message_text = "\n".join(simple_lines)
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("PAY_WITH_BALANCE_BUTTON", "✅ Pay with balance"), callback_data="simple_subscription_pay_with_balance")],
            [types.InlineKeyboardButton(text=texts.t("OTHER_PAYMENT_METHODS_BUTTON", "💳 Other payment methods"), callback_data="simple_subscription_other_payment_methods")],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")]
        ])
    else:
        # If balance is insufficient, offer external payment methods
        simple_lines = [
            texts.t("SIMPLE_SUBSCRIPTION_TITLE", "⚡ <b>Simple subscription purchase</b>"),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_PERIOD", "📅 Period: {days} days").format(days=subscription_params['period_days']),
        ]

        if settings.is_devices_selection_enabled():
            simple_lines.append(
                texts.t("SIMPLE_SUBSCRIPTION_DEVICES", "📱 Devices: {count}").format(count=subscription_params['device_limit'])
            )

        server_text = (
            texts.t("SIMPLE_SUBSCRIPTION_SERVER_ANY", "Any available")
            if not subscription_params['squad_uuid']
            else texts.t("SIMPLE_SUBSCRIPTION_SERVER_SELECTED", "Selected")
        )
        
        simple_lines.extend([
            texts.t("SIMPLE_SUBSCRIPTION_TRAFFIC", "📊 Traffic: {traffic}").format(traffic=traffic_text),
            texts.t("SIMPLE_SUBSCRIPTION_SERVER", "🌍 Server: {server}").format(server=server_text),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_COST", "💰 Cost: {cost}").format(cost=settings.format_price(price_kopeks)),
            texts.t("SIMPLE_SUBSCRIPTION_BALANCE", "💳 Your balance: {balance}").format(balance=settings.format_price(user_balance_kopeks)),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_CHOOSE_PAYMENT", "Choose payment method:"),
        ])

        message_text = "\n".join(simple_lines)
        
        keyboard = _get_simple_subscription_payment_keyboard(db_user.language)
    
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(SubscriptionStates.waiting_for_simple_subscription_payment_method)
    await callback.answer()

    


async def _calculate_simple_subscription_price(
    db: AsyncSession,
    params: dict,
    *,
    user: Optional[User] = None,
    resolved_squad_uuid: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Calculates simple subscription price."""

    resolved_uuids = [resolved_squad_uuid] if resolved_squad_uuid else None
    return await compute_simple_subscription_price(
        db,
        params,
        user=user,
        resolved_squad_uuids=resolved_uuids,
    )


def _get_simple_subscription_payment_keyboard(language: str) -> types.InlineKeyboardMarkup:
    """Creates keyboard with payment methods for simple subscription."""
    texts = get_texts(language)
    keyboard = []
    
    # Add available payment methods
    if settings.TELEGRAM_STARS_ENABLED:
        keyboard.append([types.InlineKeyboardButton(
            text="⭐ Telegram Stars",
            callback_data="simple_subscription_stars"
        )])
    
    if settings.is_yookassa_enabled():
        yookassa_methods = []
        if settings.YOOKASSA_SBP_ENABLED:
            yookassa_methods.append(types.InlineKeyboardButton(
                text=texts.t("PAYMENT_SBP_YOOKASSA", "🏦 YooKassa (SBP)"),
                callback_data="simple_subscription_yookassa_sbp"
            ))
        yookassa_methods.append(types.InlineKeyboardButton(
            text=texts.t("PAYMENT_CARD_YOOKASSA", "💳 YooKassa (Card)"),
            callback_data="simple_subscription_yookassa"
        ))
        if yookassa_methods:
            keyboard.append(yookassa_methods)
    
    if settings.is_cryptobot_enabled():
        keyboard.append([types.InlineKeyboardButton(
            text="🪙 CryptoBot",
            callback_data="simple_subscription_cryptobot"
        )])
    
    if settings.is_mulenpay_enabled():
        mulenpay_name = settings.get_mulenpay_display_name()
        keyboard.append([types.InlineKeyboardButton(
            text=f"💳 {mulenpay_name}",
            callback_data="simple_subscription_mulenpay"
        )])
    
    if settings.is_pal24_enabled():
        keyboard.append([types.InlineKeyboardButton(
            text="💳 PayPalych",
            callback_data="simple_subscription_pal24"
        )])
    
    if settings.is_wata_enabled():
        keyboard.append([types.InlineKeyboardButton(
            text="💳 WATA",
            callback_data="simple_subscription_wata"
        )])
    
    # Back button
    keyboard.append([types.InlineKeyboardButton(
        text=texts.BACK,
        callback_data="subscription_purchase"
    )])
    
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


async def _extend_existing_subscription(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    current_subscription: Subscription,
    period_days: int,
    device_limit: int,
    traffic_limit_gb: int,
    squad_uuid: str
):
    """Extends existing subscription."""
    from app.services.admin_notification_service import AdminNotificationService
    from app.database.crud.transaction import create_transaction
    from app.database.crud.user import subtract_user_balance
    from app.database.models import TransactionType
    from app.services.subscription_service import SubscriptionService
    from app.utils.pricing_utils import calculate_months_from_days
    from datetime import datetime, timedelta
    
    texts = get_texts(db_user.language)
    
    # Calculate subscription price
    subscription_params = {
        "period_days": period_days,
        "device_limit": device_limit,
        "traffic_limit_gb": traffic_limit_gb,
        "squad_uuid": squad_uuid
    }
    price_kopeks, price_breakdown = await _calculate_simple_subscription_price(
        db,
        subscription_params,
        user=db_user,
        resolved_squad_uuid=squad_uuid,
    )
    logger.debug(
        "SIMPLE_SUBSCRIPTION_EXTEND_PRICE | user=%s | total=%s | base=%s | traffic=%s | devices=%s | servers=%s | discount=%s",
        db_user.id,
        price_kopeks,
        price_breakdown.get("base_price", 0),
        price_breakdown.get("traffic_price", 0),
        price_breakdown.get("devices_price", 0),
        price_breakdown.get("servers_price", 0),
        price_breakdown.get("total_discount", 0),
    )
    
    # Check user balance
    if db_user.balance_kopeks < price_kopeks:
        missing_kopeks = price_kopeks - db_user.balance_kopeks
        message_text = texts.t(
            "ADDON_INSUFFICIENT_FUNDS_MESSAGE",
            (
                "⚠️ <b>Insufficient funds</b>\n\n"
                "Service price: {required}\n"
                "Balance: {balance}\n"
                "Missing: {missing}\n\n"
                "Choose a top-up method. The amount will be filled in automatically."
            ),
        ).format(
            required=texts.format_price(price_kopeks),
            balance=texts.format_price(db_user.balance_kopeks),
            missing=texts.format_price(missing_kopeks),
        )
        
        # Prepare data for saving to cart
        from app.services.user_cart_service import user_cart_service
        cart_data = {
            'cart_mode': 'extend',
            'subscription_id': current_subscription.id,
            'period_days': period_days,
            'total_price': price_kopeks,
            'user_id': db_user.id,
            'saved_cart': True,
            'missing_amount': missing_kopeks,
            'return_to_cart': True,
            'description': texts.t("subscription.extend.description", "Extension for {days} days").format(days=period_days),
            'device_limit': device_limit,
            'traffic_limit_gb': traffic_limit_gb,
            'squad_uuid': squad_uuid,
            'consume_promo_offer': False,
        }
        
        await user_cart_service.save_user_cart(db_user.id, cart_data)
        
        await callback.message.edit_text(
            message_text,
            reply_markup=get_insufficient_balance_keyboard(
                db_user.language,
                amount_kopeks=missing_kopeks,
                has_saved_cart=True
            ),
            parse_mode="HTML",
        )
        await callback.answer()
        return
    
    # Deduct funds
    months = calculate_months_from_days(period_days)
    success = await subtract_user_balance(
        db,
        db_user,
        price_kopeks,
        texts.t("subscription.extend.transaction_description", "Subscription extension for {days} days ({months} months)").format(days=period_days, months=months),
        consume_promo_offer=False,  # Simple purchase does not use promo discounts
    )
    
    if not success:
        await callback.answer(
            texts.t("PAYMENT_CHARGE_ERROR", "⚠️ Payment charge error"),
            show_alert=True
        )
        return
    
    # Update subscription parameters
    current_time = datetime.utcnow()
    old_end_date = current_subscription.end_date
    
    # Update parameters depending on current subscription type
    if current_subscription.is_trial:
        # When extending trial subscription, convert it to regular
        current_subscription.is_trial = False
        current_subscription.status = "active"
        # Remove limitations from trial subscription
        current_subscription.traffic_limit_gb = traffic_limit_gb
        current_subscription.device_limit = device_limit
        # If squad_uuid is specified, add it to existing servers
        if squad_uuid and squad_uuid not in current_subscription.connected_squads:
            # Use += for safe addition to SQLAlchemy list
            current_subscription.connected_squads = current_subscription.connected_squads + [squad_uuid]
    else:
        # For regular subscription just extend
        # Update traffic and devices if needed
        if traffic_limit_gb != 0:  # If not unlimited, update
            current_subscription.traffic_limit_gb = traffic_limit_gb
        if device_limit > current_subscription.device_limit:
            current_subscription.device_limit = device_limit
        # If squad_uuid is specified and not yet in subscription, add it
        if squad_uuid and squad_uuid not in current_subscription.connected_squads:
            # Use += for safe addition to SQLAlchemy list
            current_subscription.connected_squads = current_subscription.connected_squads + [squad_uuid]
    
    # Extend subscription
    if current_subscription.end_date > current_time:
        # If subscription is still active, add days to current end date
        new_end_date = current_subscription.end_date + timedelta(days=period_days)
    else:
        # If subscription has already expired, start from current time
        new_end_date = current_time + timedelta(days=period_days)
    
    current_subscription.end_date = new_end_date
    current_subscription.updated_at = current_time
    
    # Save changes
    await db.commit()
    await db.refresh(current_subscription)
    await db.refresh(db_user)
    
    # Update user in Remnawave
    subscription_service = SubscriptionService()
    try:
        remnawave_result = await subscription_service.update_remnawave_user(
            db,
            current_subscription,
            reset_traffic=settings.RESET_TRAFFIC_ON_PAYMENT,
            reset_reason="subscription_extension",
        )
        if remnawave_result:
            logger.info("✅ RemnaWave updated successfully")
        else:
            logger.error("⚠ REMNAWAVE UPDATE ERROR")
    except Exception as e:
        logger.error(f"⚠ EXCEPTION DURING REMNAWAVE UPDATE: {e}")
    
    # Create transaction
    months = calculate_months_from_days(period_days)
    transaction = await create_transaction(
        db=db,
        user_id=db_user.id,
        type=TransactionType.SUBSCRIPTION_PAYMENT,
        amount_kopeks=price_kopeks,
        description=texts.t("subscription.extend.transaction_description", "Subscription extension for {days} days ({months} months)").format(days=period_days, months=months)
    )
    
    # Send notification to admin
    try:
        notification_service = AdminNotificationService(callback.bot)
        await notification_service.send_subscription_extension_notification(
            db,
            db_user,
            current_subscription,
            transaction,
            period_days,
            old_end_date,
            new_end_date=new_end_date,
            balance_after=db_user.balance_kopeks,
        )
    except Exception as e:
        logger.error(f"Error sending extension notification: {e}")
    
    # Send message to user
    success_message = (
        texts.t("subscription.extend.success", "✅ Subscription successfully extended!\n\n")
        + texts.t("subscription.extend.added_days", "⏰ Added: {days} days\n").format(days=period_days)
        + texts.t("subscription.extend.valid_until", "Valid until: {date}\n\n").format(date=format_local_datetime(new_end_date, '%d.%m.%Y %H:%M'))
        + texts.t("subscription.extend.charged", "💰 Charged: {price}").format(price=texts.format_price(price_kopeks))
    )
    
    # If this was a trial subscription, add conversion information
    if current_subscription.is_trial:
        success_message += "\n" + texts.t("SUBSCRIPTION_TRIAL_CONVERTED_TO_PAID", "🎯 Trial subscription converted to paid")
    
    await callback.message.edit_text(
        success_message,
        reply_markup=get_back_keyboard(db_user.language)
    )
    
    logger.info(f"✅ User {db_user.telegram_id} extended subscription for {period_days} days for {price_kopeks / 100}₽")
    await callback.answer()
