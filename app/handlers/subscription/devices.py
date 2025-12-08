import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from urllib.parse import quote
from aiogram import Dispatcher, types, F
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
from app.localization.texts import get_texts
from app.services.admin_notification_service import AdminNotificationService
from app.services.remnawave_service import RemnaWaveService
from app.services.subscription_checkout_service import (
    clear_subscription_checkout_draft,
    get_subscription_checkout_draft,
    save_subscription_checkout_draft,
    should_offer_checkout_resume,
)
from app.services.subscription_service import SubscriptionService
from app.utils.miniapp_buttons import build_miniapp_or_callback_button
from app.services.promo_offer_service import promo_offer_service
from app.states import SubscriptionStates
from app.utils.pagination import paginate_list
from app.utils.pricing_utils import (
    calculate_months_from_days,
    get_remaining_months,
    calculate_prorated_price,
    validate_pricing_calculation,
    format_period_description,
    apply_percentage_discount,
)
from app.utils.subscription_utils import (
    get_display_subscription_link,
    get_happ_cryptolink_redirect_link,
    convert_subscription_link_to_happ_scheme,
)
from app.utils.promo_offer import (
    build_promo_offer_hint,
    get_user_active_promo_discount_percent,
)

from .common import _get_addon_discount_percent_for_user, _get_period_hint_from_subscription, format_additional_section, get_apps_for_device, get_device_name, get_step_description, logger
from .countries import _get_available_countries

async def get_current_devices_detailed(db_user: User) -> dict:
    try:
        if not db_user.remnawave_uuid:
            return {"count": 0, "devices": []}

        from app.services.remnawave_service import RemnaWaveService
        service = RemnaWaveService()

        async with service.get_api_client() as api:
            response = await api._make_request('GET', f'/api/hwid/devices/{db_user.remnawave_uuid}')

            if response and 'response' in response:
                devices_info = response['response']
                total_devices = devices_info.get('total', 0)
                devices_list = devices_info.get('devices', [])

                return {
                    "count": total_devices,
                    "devices": devices_list[:5]
                }
            else:
                return {"count": 0, "devices": []}

    except Exception as e:
        logger.error(f"Error fetching detailed device information: {e}")
        return {"count": 0, "devices": []}

async def get_servers_display_names(squad_uuids: List[str]) -> str:
    texts = get_texts()

    if not squad_uuids:
        return texts.t("SUBSCRIPTION_NO_SERVERS", "No servers")

    try:
        from app.database.database import AsyncSessionLocal
        from app.database.crud.server_squad import get_server_squad_by_uuid

        server_names = []

        async with AsyncSessionLocal() as db:
            for uuid in squad_uuids:
                server = await get_server_squad_by_uuid(db, uuid)
                if server:
                    server_names.append(server.display_name)
                    logger.debug(f"Found server in DB: {uuid} -> {server.display_name}")
                else:
                    logger.warning(f"Server with UUID {uuid} not found in DB")

        if not server_names:
            countries = await _get_available_countries()
            for uuid in squad_uuids:
                for country in countries:
                    if country['uuid'] == uuid:
                        server_names.append(country['name'])
                        logger.debug(f"Found server in cache: {uuid} -> {country['name']}")
                        break

        if not server_names:
            if len(squad_uuids) == 1:
                return texts.t("TRIAL_SERVER_DEFAULT_NAME", "🎯 Test server")
            return texts.t("subscription.countries.multiple_countries", "{count} countries").format(count=len(squad_uuids))

        if len(server_names) > 6:
            displayed = ", ".join(server_names[:6])
            remaining = len(server_names) - 6
            return texts.t("subscription.countries.more_servers", "{displayed} and {remaining} more").format(
                displayed=displayed,
                remaining=remaining
            )
        else:
            return ", ".join(server_names)

    except Exception as e:
        logger.error(f"Error fetching server names: {e}")
        if len(squad_uuids) == 1:
            return texts.t("TRIAL_SERVER_DEFAULT_NAME", "🎯 Test server")
        return texts.t("subscription.countries.multiple_countries", "{count} countries").format(count=len(squad_uuids))

async def get_current_devices_count(db_user: User) -> str:
    try:
        if not db_user.remnawave_uuid:
            return "—"

        from app.services.remnawave_service import RemnaWaveService
        service = RemnaWaveService()

        async with service.get_api_client() as api:
            response = await api._make_request('GET', f'/api/hwid/devices/{db_user.remnawave_uuid}')

            if response and 'response' in response:
                total_devices = response['response'].get('total', 0)
                return str(total_devices)
            else:
                return "—"

    except Exception as e:
        logger.error(f"Error fetching device count: {e}")
        return "—"

async def handle_change_devices(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    if not settings.is_devices_selection_enabled():
        await callback.answer(
            texts.t("DEVICES_SELECTION_DISABLED", "⚠️ Device count change unavailable"),
            show_alert=True,
        )
        return

    if not subscription or subscription.is_trial:
        await callback.answer(
            texts.t("PAID_FEATURE_ONLY", "⚠️ This feature is only available for paid subscriptions"),
            show_alert=True,
        )
        return

    current_devices = subscription.device_limit

    period_hint_days = _get_period_hint_from_subscription(subscription)
    devices_discount_percent = _get_addon_discount_percent_for_user(
        db_user,
        "devices",
        period_hint_days,
    )

    prompt_text = texts.t(
        "CHANGE_DEVICES_PROMPT",
        (
            "📱 <b>Change device count</b>\n\n"
            "Current limit: {current_devices} devices\n"
            "Choose new device count:\n\n"
            "💡 <b>Important:</b>\n"
            "• When increasing - additional payment proportional to remaining time\n"
            "• When decreasing - no refund is provided"
        ),
    ).format(current_devices=current_devices)

    await callback.message.edit_text(
        prompt_text,
        reply_markup=get_change_devices_keyboard(
            current_devices,
            db_user.language,
            subscription.end_date,
            devices_discount_percent,
        ),
        parse_mode="HTML"
    )

    await callback.answer()

async def confirm_change_devices(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    new_devices_count = int(callback.data.split('_')[2])
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    if not settings.is_devices_selection_enabled():
        await callback.answer(
            texts.t("DEVICES_SELECTION_DISABLED", "⚠️ Device count change unavailable"),
            show_alert=True,
        )
        return

    current_devices = subscription.device_limit

    if new_devices_count == current_devices:
        await callback.answer(
            texts.t("DEVICES_NO_CHANGE", "ℹ️ Device count was not changed"),
            show_alert=True,
        )
        return

    if settings.MAX_DEVICES_LIMIT > 0 and new_devices_count > settings.MAX_DEVICES_LIMIT:
        await callback.answer(
            texts.t(
                "DEVICES_LIMIT_EXCEEDED",
                "⚠️ Maximum device limit exceeded ({limit})",
            ).format(limit=settings.MAX_DEVICES_LIMIT),
            show_alert=True
        )
        return

    devices_difference = new_devices_count - current_devices

    if devices_difference > 0:
        additional_devices = devices_difference

        if current_devices < settings.DEFAULT_DEVICE_LIMIT:
            free_devices = settings.DEFAULT_DEVICE_LIMIT - current_devices
            chargeable_devices = max(0, additional_devices - free_devices)
        else:
            chargeable_devices = additional_devices

        devices_price_per_month = chargeable_devices * settings.PRICE_PER_DEVICE
        months_hint = get_remaining_months(subscription.end_date)
        period_hint_days = months_hint * 30 if months_hint > 0 else None
        devices_discount_percent = _get_addon_discount_percent_for_user(
            db_user,
            "devices",
            period_hint_days,
        )
        discounted_per_month, discount_per_month = apply_percentage_discount(
            devices_price_per_month,
            devices_discount_percent,
        )
        price, charged_months = calculate_prorated_price(
            discounted_per_month,
            subscription.end_date,
        )
        total_discount = discount_per_month * charged_months

        if price > 0 and db_user.balance_kopeks < price:
            missing_kopeks = price - db_user.balance_kopeks
            required_text = texts.t("subscription.countries.charged_period", "{amount} (for {months} months)").format(
                amount=texts.format_price(price),
                months=charged_months
            )
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

            await callback.message.answer(
                message_text,
                reply_markup=get_insufficient_balance_keyboard(
                    db_user.language,
                    amount_kopeks=missing_kopeks,
                ),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        action_text = texts.t(
            "DEVICE_CHANGE_ACTION_INCREASE",
            "increase to {count}",
        ).format(count=new_devices_count)
        if price > 0:
            cost_text = texts.t(
                "DEVICE_CHANGE_EXTRA_COST",
                "Additional payment: {amount} (for {months} months)",
            ).format(
                amount=texts.format_price(price),
                months=charged_months,
            )
            if total_discount > 0:
                cost_text += texts.t(
                    "DEVICE_CHANGE_DISCOUNT_INFO",
                    " (discount {percent}%: -{amount})",
                ).format(
                    percent=devices_discount_percent,
                    amount=texts.format_price(total_discount),
                )
        else:
            cost_text = texts.t("DEVICE_CHANGE_FREE", "Free")

    else:
        price = 0
        action_text = texts.t(
            "DEVICE_CHANGE_ACTION_DECREASE",
            "decrease to {count}",
        ).format(count=new_devices_count)
        cost_text = texts.t("DEVICE_CHANGE_NO_REFUND", "Refunds are not provided")

    confirm_text = texts.t(
        "DEVICE_CHANGE_CONFIRMATION",
        (
            "📱 <b>Confirm change</b>\n\n"
            "Current count: {current} devices\n"
            "New count: {new} devices\n\n"
            "Action: {action}\n"
            "💰 {cost}\n\n"
            "Confirm change?"
        ),
    ).format(
        current=current_devices,
        new=new_devices_count,
        action=action_text,
        cost=cost_text,
    )

    await callback.message.edit_text(
        confirm_text,
        reply_markup=get_confirm_change_devices_keyboard(new_devices_count, price, db_user.language),
        parse_mode="HTML"
    )

    await callback.answer()

async def execute_change_devices(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    callback_parts = callback.data.split('_')
    new_devices_count = int(callback_parts[3])
    price = int(callback_parts[4])

    texts = get_texts(db_user.language)
    subscription = db_user.subscription
    current_devices = subscription.device_limit

    if not settings.is_devices_selection_enabled():
        await callback.answer(
            texts.t("DEVICES_SELECTION_DISABLED", "⚠️ Device count change unavailable"),
            show_alert=True,
        )
        return

    try:
        if price > 0:
            success = await subtract_user_balance(
                db, db_user, price,
                texts.t("subscription.devices.change_transaction_desc", "Changing device count from {old} to {new}").format(
                    old=current_devices,
                    new=new_devices_count
                )
            )

            if not success:
                await callback.answer(
                    texts.t("PAYMENT_CHARGE_ERROR", "⚠️ Payment charge error"),
                    show_alert=True,
                )
                return

            charged_months = get_remaining_months(subscription.end_date)
            await create_transaction(
                db=db,
                user_id=db_user.id,
                type=TransactionType.SUBSCRIPTION_PAYMENT,
                amount_kopeks=price,
                description=texts.t("subscription.devices.change_transaction_desc_full", "Changing devices from {old} to {new} for {months} months").format(
                    old=current_devices,
                    new=new_devices_count,
                    months=charged_months
                )
            )

        subscription.device_limit = new_devices_count
        subscription.updated_at = datetime.utcnow()

        await db.commit()

        subscription_service = SubscriptionService()
        await subscription_service.update_remnawave_user(db, subscription)

        await db.refresh(db_user)
        await db.refresh(subscription)

        try:
            from app.services.admin_notification_service import AdminNotificationService
            notification_service = AdminNotificationService(callback.bot)
            await notification_service.send_subscription_update_notification(
                db, db_user, subscription, "devices", current_devices, new_devices_count, price
            )
        except Exception as e:
            logger.error(f"Error sending device change notification: {e}")

        if new_devices_count > current_devices:
            success_text = texts.t(
                "DEVICE_CHANGE_INCREASE_SUCCESS",
                "✅ Device count increased!\n\n",
            )
            success_text += texts.t(
                "DEVICE_CHANGE_RESULT_LINE",
                "📱 Was: {old} → Now: {new}\n",
            ).format(old=current_devices, new=new_devices_count)
            if price > 0:
                success_text += texts.t(
                    "DEVICE_CHANGE_CHARGED",
                    "💰 Charged: {amount}",
                ).format(amount=texts.format_price(price))
        else:
            success_text = texts.t(
                "DEVICE_CHANGE_DECREASE_SUCCESS",
                "✅ Device count decreased!\n\n",
            )
            success_text += texts.t(
                "DEVICE_CHANGE_RESULT_LINE",
                "📱 Was: {old} → Now: {new}\n",
            ).format(old=current_devices, new=new_devices_count)
            success_text += texts.t(
                "DEVICE_CHANGE_NO_REFUND_INFO",
                "ℹ️ No refund provided",
            )

        await callback.message.edit_text(
            success_text,
            reply_markup=get_back_keyboard(db_user.language)
        )

        logger.info(
            f"✅ User {db_user.telegram_id} changed device count from {current_devices} to {new_devices_count}, additional payment: {price / 100}₽")

    except Exception as e:
        logger.error(f"Error changing device count: {e}")
        await callback.message.edit_text(
            texts.ERROR,
            reply_markup=get_back_keyboard(db_user.language)
        )

    await callback.answer()

async def handle_device_management(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    if not subscription or subscription.is_trial:
        await callback.answer(
            texts.t("PAID_FEATURE_ONLY", "⚠️ This feature is only available for paid subscriptions"),
            show_alert=True,
        )
        return

    if not db_user.remnawave_uuid:
        await callback.answer(
            texts.t("DEVICE_UUID_NOT_FOUND", "❌ User UUID not found"),
            show_alert=True,
        )
        return

    try:
        from app.services.remnawave_service import RemnaWaveService
        service = RemnaWaveService()

        async with service.get_api_client() as api:
            response = await api._make_request('GET', f'/api/hwid/devices/{db_user.remnawave_uuid}')

            if response and 'response' in response:
                devices_info = response['response']
                total_devices = devices_info.get('total', 0)
                devices_list = devices_info.get('devices', [])

                if total_devices == 0:
                    await callback.message.edit_text(
                        texts.t("DEVICE_NONE_CONNECTED", "ℹ️ You have no connected devices"),
                        reply_markup=get_back_keyboard(db_user.language)
                    )
                    await callback.answer()
                    return

                await show_devices_page(callback, db_user, devices_list, page=1)
            else:
                await callback.answer(
                    texts.t(
                        "DEVICE_FETCH_INFO_ERROR",
                        "❌ Error fetching device information",
                    ),
                    show_alert=True,
                )

    except Exception as e:
        logger.error(f"Error fetching device list: {e}")
        await callback.answer(
            texts.t(
                "DEVICE_FETCH_INFO_ERROR",
                "❌ Error fetching device information",
            ),
            show_alert=True,
        )

    await callback.answer()

async def show_devices_page(
        callback: types.CallbackQuery,
        db_user: User,
        devices_list: List[dict],
        page: int = 1
):
    texts = get_texts(db_user.language)
    devices_per_page = 5

    pagination = paginate_list(devices_list, page=page, per_page=devices_per_page)

    devices_text = texts.t(
        "DEVICE_MANAGEMENT_OVERVIEW",
        (
            "🔄 <b>Device management</b>\n\n"
            "📊 Total connected: {total} devices\n"
            "📄 Page {page} of {pages}\n\n"
        ),
    ).format(total=len(devices_list), page=pagination.page, pages=pagination.total_pages)

    if pagination.items:
        devices_text += texts.t(
            "DEVICE_MANAGEMENT_CONNECTED_HEADER",
            "<b>Connected devices:</b>\n",
        )
        for i, device in enumerate(pagination.items, 1):
            platform = device.get('platform', 'Unknown')
            device_model = device.get('deviceModel', 'Unknown')
            device_info = f"{platform} - {device_model}"

            if len(device_info) > 35:
                device_info = device_info[:32] + "..."

            devices_text += texts.t(
                "DEVICE_MANAGEMENT_LIST_ITEM",
                "• {device}\n",
            ).format(device=device_info)

    devices_text += texts.t(
        "DEVICE_MANAGEMENT_ACTIONS",
        (
            "\n💡 <b>Actions:</b>\n"
            "• Select a device to reset\n"
            "• Or reset all devices at once"
        ),
    )

    await callback.message.edit_text(
        devices_text,
        reply_markup=get_devices_management_keyboard(
            pagination.items,
            pagination,
            db_user.language
        ),
        parse_mode="HTML"
    )

async def handle_devices_page(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    page = int(callback.data.split('_')[2])
    texts = get_texts(db_user.language)

    try:
        from app.services.remnawave_service import RemnaWaveService
        service = RemnaWaveService()

        async with service.get_api_client() as api:
            response = await api._make_request('GET', f'/api/hwid/devices/{db_user.remnawave_uuid}')

            if response and 'response' in response:
                devices_list = response['response'].get('devices', [])
                await show_devices_page(callback, db_user, devices_list, page=page)
            else:
                await callback.answer(
                    texts.t("DEVICE_FETCH_ERROR", "❌ Error fetching devices"),
                    show_alert=True,
                )

    except Exception as e:
        logger.error(f"Error navigating to devices page: {e}")
        await callback.answer(
            texts.t("DEVICE_PAGE_LOAD_ERROR", "❌ Error loading page"),
            show_alert=True,
        )

async def handle_single_device_reset(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    try:
        callback_parts = callback.data.split('_')
        if len(callback_parts) < 4:
            logger.error(f"Invalid callback_data format: {callback.data}")
            await callback.answer(
                texts.t("DEVICE_RESET_INVALID_REQUEST", "❌ Error: invalid request"),
                show_alert=True,
            )
            return

        device_index = int(callback_parts[2])
        page = int(callback_parts[3])

        logger.info(f"🔧 Resetting device: index={device_index}, page={page}")

    except (ValueError, IndexError) as e:
        logger.error(f"❌ Error parsing callback_data {callback.data}: {e}")
        await callback.answer(
            texts.t("DEVICE_RESET_PARSE_ERROR", "❌ Error processing request"),
            show_alert=True,
        )
        return

    texts = get_texts(db_user.language)

    try:
        from app.services.remnawave_service import RemnaWaveService
        service = RemnaWaveService()

        async with service.get_api_client() as api:
            response = await api._make_request('GET', f'/api/hwid/devices/{db_user.remnawave_uuid}')

            if response and 'response' in response:
                devices_list = response['response'].get('devices', [])

                devices_per_page = 5
                pagination = paginate_list(devices_list, page=page, per_page=devices_per_page)

                if device_index < len(pagination.items):
                    device = pagination.items[device_index]
                    device_hwid = device.get('hwid')

                    if device_hwid:
                        delete_data = {
                            "userUuid": db_user.remnawave_uuid,
                            "hwid": device_hwid
                        }

                        await api._make_request('POST', '/api/hwid/devices/delete', data=delete_data)

                        platform = device.get('platform', 'Unknown')
                        device_model = device.get('deviceModel', 'Unknown')
                        device_info = f"{platform} - {device_model}"

                        await callback.answer(
                            texts.t(
                                "DEVICE_RESET_SUCCESS",
                                "✅ Device {device} successfully reset!",
                            ).format(device=device_info),
                            show_alert=True,
                        )

                        updated_response = await api._make_request('GET', f'/api/hwid/devices/{db_user.remnawave_uuid}')
                        if updated_response and 'response' in updated_response:
                            updated_devices = updated_response['response'].get('devices', [])

                            if updated_devices:
                                updated_pagination = paginate_list(updated_devices, page=page,
                                                                   per_page=devices_per_page)
                                if not updated_pagination.items and page > 1:
                                    page = page - 1

                                await show_devices_page(callback, db_user, updated_devices, page=page)
                            else:
                                await callback.message.edit_text(
                                    texts.t(
                                        "DEVICE_RESET_ALL_DONE",
                                        "ℹ️ All devices have been reset",
                                    ),
                                    reply_markup=get_back_keyboard(db_user.language)
                                )

                        logger.info(f"✅ User {db_user.telegram_id} reset device {device_info}")
                    else:
                        await callback.answer(
                            texts.t(
                                "DEVICE_RESET_ID_FAILED",
                                "❌ Failed to get device ID",
                            ),
                            show_alert=True,
                        )
                else:
                    await callback.answer(
                        texts.t("DEVICE_RESET_NOT_FOUND", "❌ Device not found"),
                        show_alert=True,
                    )
            else:
                await callback.answer(
                    texts.t("DEVICE_FETCH_ERROR", "❌ Error fetching devices"),
                    show_alert=True,
                )

    except Exception as e:
        logger.error(f"Error resetting device: {e}")
        await callback.answer(
            texts.t("DEVICE_RESET_ERROR", "❌ Error resetting device"),
            show_alert=True,
        )

async def handle_all_devices_reset_from_management(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    texts = get_texts(db_user.language)

    if not db_user.remnawave_uuid:
        await callback.answer(
            texts.t("DEVICE_UUID_NOT_FOUND", "❌ User UUID not found"),
            show_alert=True,
        )
        return

    try:
        from app.services.remnawave_service import RemnaWaveService
        service = RemnaWaveService()

        async with service.get_api_client() as api:
            devices_response = await api._make_request('GET', f'/api/hwid/devices/{db_user.remnawave_uuid}')

            if not devices_response or 'response' not in devices_response:
                await callback.answer(
                    texts.t(
                        "DEVICE_LIST_FETCH_ERROR",
                        "❌ Error fetching device list",
                    ),
                    show_alert=True,
                )
                return

            devices_list = devices_response['response'].get('devices', [])

            if not devices_list:
                await callback.answer(
                        texts.t("DEVICE_NONE_CONNECTED", "ℹ️ You have no connected devices"),
                    show_alert=True,
                )
                return

            logger.info(f"🔧 Found {len(devices_list)} devices to reset")

            success_count = 0
            failed_count = 0

            for device in devices_list:
                device_hwid = device.get('hwid')
                if device_hwid:
                    try:
                        delete_data = {
                            "userUuid": db_user.remnawave_uuid,
                            "hwid": device_hwid
                        }

                        await api._make_request('POST', '/api/hwid/devices/delete', data=delete_data)
                        success_count += 1
                        logger.info(f"✅ Device {device_hwid} deleted")

                    except Exception as device_error:
                        failed_count += 1
                        logger.error(f"❌ Error deleting device {device_hwid}: {device_error}")
                else:
                    failed_count += 1
                    logger.warning(f"⚠️ Device has no HWID: {device}")

            if success_count > 0:
                if failed_count == 0:
                    await callback.message.edit_text(
                        texts.t(
                            "DEVICE_RESET_ALL_SUCCESS_MESSAGE",
                            (
                                "✅ <b>All devices successfully reset!</b>\n\n"
                                "🔄 Reset: {count} devices\n"
                                "📱 You can now reconnect your devices\n\n"
                                "💡 Use the link from the 'My subscription' section to reconnect"
                            ),
                        ).format(count=success_count),
                        reply_markup=get_back_keyboard(db_user.language),
                        parse_mode="HTML"
                    )
                    logger.info(f"✅ User {db_user.telegram_id} successfully reset {success_count} devices")
                else:
                    await callback.message.edit_text(
                        texts.t(
                            "DEVICE_RESET_PARTIAL_MESSAGE",
                            (
                                "⚠️ <b>Partial device reset</b>\n\n"
                                "✅ Removed: {success} devices\n"
                                "❌ Failed to remove: {failed} devices\n\n"
                                "Try again or contact support."
                            ),
                        ).format(success=success_count, failed=failed_count),
                        reply_markup=get_back_keyboard(db_user.language),
                        parse_mode="HTML"
                    )
                    logger.warning(
                        f"⚠️ Partial reset for user {db_user.telegram_id}: {success_count}/{len(devices_list)}")
            else:
                await callback.message.edit_text(
                    texts.t(
                        "DEVICE_RESET_ALL_FAILED_MESSAGE",
                        (
                            "❌ <b>Failed to reset devices</b>\n\n"
                            "Please try again later or contact support.\n\n"
                            "Total devices: {total}"
                        ),
                    ).format(total=len(devices_list)),
                    reply_markup=get_back_keyboard(db_user.language),
                    parse_mode="HTML"
                )
                logger.error(f"❌ Failed to reset any devices for user {db_user.telegram_id}")

    except Exception as e:
        logger.error(f"Error resetting all devices: {e}")
        await callback.message.edit_text(
            texts.ERROR,
            reply_markup=get_back_keyboard(db_user.language)
        )

    await callback.answer()

async def confirm_add_devices(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    devices_count = int(callback.data.split('_')[2])
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    if not settings.is_devices_selection_enabled():
        await callback.answer(
            texts.t("DEVICES_SELECTION_DISABLED", "⚠️ Device count change unavailable"),
            show_alert=True,
        )
        return

    resume_callback = None

    new_total_devices = subscription.device_limit + devices_count

    if settings.MAX_DEVICES_LIMIT > 0 and new_total_devices > settings.MAX_DEVICES_LIMIT:
        await callback.answer(
            texts.t("DEVICES_LIMIT_EXCEEDED", "⚠️ Maximum device limit exceeded ({limit})").format(limit=settings.MAX_DEVICES_LIMIT) +
            f"\nCurrent: {subscription.device_limit}, adding: {devices_count}",
            show_alert=True
        )
        return

    devices_price_per_month = devices_count * settings.PRICE_PER_DEVICE
    months_hint = get_remaining_months(subscription.end_date)
    period_hint_days = months_hint * 30 if months_hint > 0 else None
    devices_discount_percent = _get_addon_discount_percent_for_user(
        db_user,
        "devices",
        period_hint_days,
    )
    discounted_per_month, discount_per_month = apply_percentage_discount(
        devices_price_per_month,
        devices_discount_percent,
    )
    price, charged_months = calculate_prorated_price(
        discounted_per_month,
        subscription.end_date,
    )
    total_discount = discount_per_month * charged_months

    logger.info(
        "Adding %s devices: %.2f₽/month × %s months = %.2f₽ (discount %.2f₽)",
        devices_count,
        discounted_per_month / 100,
        charged_months,
        price / 100,
        total_discount / 100,
    )

    if db_user.balance_kopeks < price:
        missing_kopeks = price - db_user.balance_kopeks
        required_text = texts.t("subscription.countries.charged_period", "{amount} (for {months} months)").format(
            amount=texts.format_price(price),
            months=charged_months
        )
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

    try:
        success = await subtract_user_balance(
            db, db_user, price,
            texts.t("subscription.devices.add_transaction_desc", "Adding {count} devices for {months} months").format(
                count=devices_count,
                months=charged_months
            )
        )

        if not success:
            await callback.answer(
                texts.t("PAYMENT_CHARGE_ERROR", "⚠️ Payment charge error"),
                show_alert=True
            )
            return

        await add_subscription_devices(db, subscription, devices_count)

        subscription_service = SubscriptionService()
        await subscription_service.update_remnawave_user(db, subscription)

        await create_transaction(
            db=db,
            user_id=db_user.id,
            type=TransactionType.SUBSCRIPTION_PAYMENT,
            amount_kopeks=price,
            description=texts.t("subscription.devices.add_transaction_desc", "Adding {count} devices for {months} months").format(
                count=devices_count,
                months=charged_months
            )
        )

        await db.refresh(db_user)
        await db.refresh(subscription)

        success_text = (
            texts.t("subscription.devices.add_success", "✅ Devices successfully added!\n\n") +
            texts.t("subscription.devices.added_count", "📱 Added: {count} devices\n").format(count=devices_count) +
            texts.t("subscription.devices.new_limit", "New limit: {limit} devices\n").format(limit=subscription.device_limit)
        )
        success_text += texts.t("subscription.countries.charged_period", "{amount} (for {months} months)").format(
            amount=texts.format_price(price),
            months=charged_months
        )
        if total_discount > 0:
            success_text += texts.t("DEVICE_CHANGE_DISCOUNT_INFO", " (discount {percent}%: -{amount})").format(
                percent=devices_discount_percent,
                amount=texts.format_price(total_discount)
            )

        await callback.message.edit_text(
            success_text,
            reply_markup=get_back_keyboard(db_user.language)
        )

        logger.info(f"✅ User {db_user.telegram_id} added {devices_count} devices for {price / 100}₽")

    except Exception as e:
        logger.error(f"Error adding devices: {e}")
        await callback.message.edit_text(
            texts.ERROR,
            reply_markup=get_back_keyboard(db_user.language)
        )

    await callback.answer()

async def handle_reset_devices(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    await handle_device_management(callback, db_user, db)

async def confirm_reset_devices(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    await handle_device_management(callback, db_user, db)

async def handle_device_guide(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    device_type = callback.data.split('_')[2]
    texts = get_texts(db_user.language)
    subscription = db_user.subscription
    subscription_link = get_display_subscription_link(subscription)

    if not subscription_link:
        await callback.answer(
            texts.t("SUBSCRIPTION_LINK_UNAVAILABLE", "❌ Subscription link unavailable"),
            show_alert=True,
        )
        return

    apps = get_apps_for_device(device_type, db_user.language)
    hide_subscription_link = settings.should_hide_subscription_link()

    if not apps:
        await callback.answer(
            texts.t("SUBSCRIPTION_DEVICE_APPS_NOT_FOUND", "❌ No apps found for this device"),
            show_alert=True,
        )
        return

    featured_app = next((app for app in apps if app.get('isFeatured', False)), apps[0])
    featured_app_id = featured_app.get('id')
    other_apps = [
        app for app in apps
        if isinstance(app, dict) and app.get('id') and app.get('id') != featured_app_id
    ]

    other_app_names = ", ".join(
        str(app.get('name')).strip()
        for app in other_apps
        if isinstance(app.get('name'), str) and app.get('name').strip()
    )

    if hide_subscription_link:
        link_section = (
                texts.t("SUBSCRIPTION_DEVICE_LINK_TITLE", "🔗 <b>Subscription link:</b>")
                + "\n"
                + texts.t(
            "SUBSCRIPTION_LINK_HIDDEN_NOTICE",
            "ℹ️ Subscription link is available via buttons below or in the 'My subscription' section.",
        )
                + "\n\n"
        )
    else:
        link_section = (
                texts.t("SUBSCRIPTION_DEVICE_LINK_TITLE", "🔗 <b>Subscription link:</b>")
                + f"\n<code>{subscription_link}</code>\n\n"
        )

    installation_description = get_step_description(featured_app, "installationStep", db_user.language)
    add_description = get_step_description(featured_app, "addSubscriptionStep", db_user.language)
    connect_description = get_step_description(featured_app, "connectAndUseStep", db_user.language)
    additional_before_text = format_additional_section(
        featured_app.get("additionalBeforeAddSubscriptionStep"),
        texts,
        db_user.language,
    )
    additional_after_text = format_additional_section(
        featured_app.get("additionalAfterAddSubscriptionStep"),
        texts,
        db_user.language,
    )

    guide_text = (
            texts.t(
                "SUBSCRIPTION_DEVICE_GUIDE_TITLE",
                "📱 <b>Setup for {device_name}</b>",
            ).format(device_name=get_device_name(device_type, db_user.language))
            + "\n\n"
            + link_section
            + texts.t(
        "SUBSCRIPTION_DEVICE_FEATURED_APP",
        "📋 <b>Recommended app:</b> {app_name}",
    ).format(app_name=featured_app.get('name', ''))
    )

    if other_app_names:
        guide_text += "\n\n" + texts.t(
            "SUBSCRIPTION_DEVICE_OTHER_APPS",
            "📦 <b>Other apps:</b> {app_list}",
        ).format(app_list=other_app_names)
        guide_text += "\n" + texts.t(
            "SUBSCRIPTION_DEVICE_OTHER_APPS_HINT",
            "Tap the 'Other apps' button below to choose another app.",
        )

    guide_text += "\n\n" + texts.t("SUBSCRIPTION_DEVICE_STEP_INSTALL_TITLE", "<b>Step 1 - Install:</b>")
    if installation_description:
        guide_text += f"\n{installation_description}"

    if additional_before_text:
        guide_text += f"\n\n{additional_before_text}"

    guide_text += "\n\n" + texts.t("SUBSCRIPTION_DEVICE_STEP_ADD_TITLE", "<b>Step 2 - Add subscription:</b>")
    if add_description:
        guide_text += f"\n{add_description}"

    guide_text += "\n\n" + texts.t("SUBSCRIPTION_DEVICE_STEP_CONNECT_TITLE", "<b>Step 3 - Connect:</b>")
    if connect_description:
        guide_text += f"\n{connect_description}"

    guide_text += "\n\n" + texts.t("SUBSCRIPTION_DEVICE_HOW_TO_TITLE", "💡 <b>How to connect:</b>")
    guide_text += "\n" + "\n".join(
        [
            texts.t(
                "SUBSCRIPTION_DEVICE_HOW_TO_STEP1",
                "1. Install the app from the link above",
            ),
            texts.t(
                "SUBSCRIPTION_DEVICE_HOW_TO_STEP2",
                "2. Tap the 'Connect' button below",
            ),
            texts.t(
                "SUBSCRIPTION_DEVICE_HOW_TO_STEP3",
                "3. Open the app and paste the link",
            ),
            texts.t(
                "SUBSCRIPTION_DEVICE_HOW_TO_STEP4",
                "4. Connect to a server",
            ),
        ]
    )

    if additional_after_text:
        guide_text += f"\n\n{additional_after_text}"

    await callback.message.edit_text(
        guide_text,
        reply_markup=get_connection_guide_keyboard(
            subscription_link,
            featured_app,
            device_type,
            db_user.language,
            has_other_apps=bool(other_apps),
        ),
        parse_mode="HTML"
    )
    await callback.answer()

async def handle_app_selection(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    device_type = callback.data.split('_')[2]
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    apps = get_apps_for_device(device_type, db_user.language)

    if not apps:
        await callback.answer(
            texts.t("SUBSCRIPTION_DEVICE_APPS_NOT_FOUND", "❌ No apps found for this device"),
            show_alert=True,
        )
        return

    app_text = (
            texts.t(
                "SUBSCRIPTION_APPS_TITLE",
                "📱 <b>Apps for {device_name}</b>",
            ).format(device_name=get_device_name(device_type, db_user.language))
            + "\n\n"
            + texts.t("SUBSCRIPTION_APPS_PROMPT", "Choose an app to connect:")
    )

    await callback.message.edit_text(
        app_text,
        reply_markup=get_app_selection_keyboard(device_type, apps, db_user.language),
        parse_mode="HTML"
    )
    await callback.answer()

async def handle_specific_app_guide(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    _, device_type, app_id = callback.data.split('_')
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    subscription_link = get_display_subscription_link(subscription)

    if not subscription_link:
        await callback.answer(
            texts.t("SUBSCRIPTION_LINK_UNAVAILABLE", "❌ Subscription link unavailable"),
            show_alert=True,
        )
        return

    apps = get_apps_for_device(device_type, db_user.language)
    app = next((a for a in apps if a['id'] == app_id), None)

    if not app:
        await callback.answer(
            texts.t("SUBSCRIPTION_APP_NOT_FOUND", "❌ App not found"),
            show_alert=True,
        )
        return

    hide_subscription_link = settings.should_hide_subscription_link()

    if hide_subscription_link:
        link_section = (
                texts.t("SUBSCRIPTION_DEVICE_LINK_TITLE", "🔗 <b>Subscription link:</b>")
                + "\n"
                + texts.t(
            "SUBSCRIPTION_LINK_HIDDEN_NOTICE",
            "ℹ️ Subscription link is available via buttons below or in the 'My subscription' section.",
        )
                + "\n\n"
        )
    else:
        link_section = (
                texts.t("SUBSCRIPTION_DEVICE_LINK_TITLE", "🔗 <b>Subscription link:</b>")
                + f"\n<code>{subscription_link}</code>\n\n"
        )

    installation_description = get_step_description(app, "installationStep", db_user.language)
    add_description = get_step_description(app, "addSubscriptionStep", db_user.language)
    connect_description = get_step_description(app, "connectAndUseStep", db_user.language)
    additional_before_text = format_additional_section(
        app.get("additionalBeforeAddSubscriptionStep"),
        texts,
        db_user.language,
    )
    additional_after_text = format_additional_section(
        app.get("additionalAfterAddSubscriptionStep"),
        texts,
        db_user.language,
    )

    guide_text = (
            texts.t(
                "SUBSCRIPTION_SPECIFIC_APP_TITLE",
                "📱 <b>{app_name} - {device_name}</b>",
            ).format(app_name=app.get('name', ''), device_name=get_device_name(device_type, db_user.language))
            + "\n\n"
            + link_section
    )

    guide_text += texts.t("SUBSCRIPTION_DEVICE_STEP_INSTALL_TITLE", "<b>Step 1 - Install:</b>")
    if installation_description:
        guide_text += f"\n{installation_description}"

    if additional_before_text:
        guide_text += f"\n\n{additional_before_text}"

    guide_text += "\n\n" + texts.t("SUBSCRIPTION_DEVICE_STEP_ADD_TITLE", "<b>Step 2 - Add subscription:</b>")
    if add_description:
        guide_text += f"\n{add_description}"

    guide_text += "\n\n" + texts.t("SUBSCRIPTION_DEVICE_STEP_CONNECT_TITLE", "<b>Step 3 - Connect:</b>")
    if connect_description:
        guide_text += f"\n{connect_description}"

    if additional_after_text:
        guide_text += f"\n\n{additional_after_text}"

    await callback.message.edit_text(
        guide_text,
        reply_markup=get_specific_app_keyboard(
            subscription_link,
            app,
            device_type,
            db_user.language
        ),
        parse_mode="HTML"
    )
    await callback.answer()

async def show_device_connection_help(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    subscription = db_user.subscription
    subscription_link = get_display_subscription_link(subscription)

    if not subscription_link:
        await callback.answer(
            texts.t("SUBSCRIPTION_LINK_UNAVAILABLE", "❌ Subscription link unavailable"),
            show_alert=True
        )
        return

    help_text = texts.t(
        "DEVICE_CONNECTION_HELP_TEXT",
        """📱 <b>How to reconnect a device</b>

After resetting a device you need to:

<b>1. Get subscription link:</b>
📋 Copy the link below or find it in the "My subscription" section

<b>2. Configure VPN app:</b>
• Open your VPN app
• Find the "Add subscription" or "Import" function
• Paste the copied link

<b>3. Connect:</b>
• Select a server
• Tap "Connect"

<b>🔗 Your subscription link:</b>
<code>{subscription_link}</code>

💡 <b>Tip:</b> Save this link - you'll need it to connect new devices"""
    ).format(subscription_link=subscription_link)

    await callback.message.edit_text(
        help_text,
        reply_markup=get_device_management_help_keyboard(db_user.language),
        parse_mode="HTML"
    )
    await callback.answer()
