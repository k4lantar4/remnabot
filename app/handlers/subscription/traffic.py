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

from .common import _apply_addon_discount, _get_addon_discount_percent_for_user, _get_period_hint_from_subscription, get_confirm_switch_traffic_keyboard, get_traffic_switch_keyboard, logger
from .countries import _get_available_countries, _should_show_countries_management
from .summary import present_subscription_summary

async def handle_add_traffic(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    from app.config import settings

    texts = get_texts(db_user.language)

    if settings.is_traffic_fixed():
        await callback.answer(
            texts.t(
                "TRAFFIC_FIXED_MODE",
                "⚠️ In current mode traffic is fixed and cannot be changed",
            ),
            show_alert=True,
        )
        return

    subscription = db_user.subscription

    if not subscription or subscription.is_trial:
        await callback.answer(
            texts.t("PAID_FEATURE_ONLY", "⚠️ This feature is only available for paid subscriptions"),
            show_alert=True,
        )
        return

    if subscription.traffic_limit_gb == 0:
        await callback.answer(
            texts.t("TRAFFIC_ALREADY_UNLIMITED", "⚠️ You already have unlimited traffic"),
            show_alert=True,
        )
        return

    current_traffic = subscription.traffic_limit_gb
    period_hint_days = _get_period_hint_from_subscription(subscription)
    traffic_discount_percent = _get_addon_discount_percent_for_user(
        db_user,
        "traffic",
        period_hint_days,
    )

    prompt_text = texts.t(
        "ADD_TRAFFIC_PROMPT",
        (
            "📈 <b>Add traffic to your subscription</b>\n\n"
            "Current limit: {current_traffic}\n"
            "Choose extra traffic:"
        ),
    ).format(current_traffic=texts.format_traffic(current_traffic))

    await callback.message.edit_text(
        prompt_text,
        reply_markup=get_add_traffic_keyboard(
            db_user.language,
            subscription.end_date,
            traffic_discount_percent,
        ),
        parse_mode="HTML"
    )

    await callback.answer()

async def handle_reset_traffic(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    from app.config import settings

    if settings.is_traffic_fixed():
        await callback.answer(
            texts.t("TRAFFIC_FIXED_MODE", "⚠️ In current mode traffic is fixed and cannot be reset"),
            show_alert=True
        )
        return

    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    if not subscription or subscription.is_trial:
        await callback.answer(
            texts.t("PAID_FEATURE_ONLY", "⚠️ This feature is only available for paid subscriptions"),
            show_alert=True
        )
        return

    if subscription.traffic_limit_gb == 0:
        await callback.answer(
            texts.t("TRAFFIC_ALREADY_UNLIMITED", "⚠️ You already have unlimited traffic"),
            show_alert=True
        )
        return

    reset_price = PERIOD_PRICES[30]

    if db_user.balance_kopeks < reset_price:
        await callback.answer(
            texts.t("subscription.traffic.reset.insufficient_balance", "⌛ Insufficient balance"),
            show_alert=True
        )
        return

    reset_text = texts.t(
        "subscription.traffic.reset.prompt",
        (
            "🔄 <b>Reset traffic</b>\n\n"
            "Used: {used}\n"
            "Limit: {limit}\n\n"
            "Reset cost: {price}\n\n"
            "After reset, the used traffic counter will become 0."
        )
    ).format(
        used=texts.format_traffic(subscription.traffic_used_gb),
        limit=texts.format_traffic(subscription.traffic_limit_gb),
        price=texts.format_price(reset_price)
    )
    
    await callback.message.edit_text(
        reset_text,
        reply_markup=get_reset_traffic_confirm_keyboard(reset_price, db_user.language)
    )

    await callback.answer()

async def confirm_reset_traffic(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    from app.config import settings

    if settings.is_traffic_fixed():
        await callback.answer(
            texts.t("TRAFFIC_FIXED_MODE", "⚠️ In current mode traffic is fixed"),
            show_alert=True
        )
        return

    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    reset_price = PERIOD_PRICES[30]

    if db_user.balance_kopeks < reset_price:
        missing_kopeks = reset_price - db_user.balance_kopeks
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
            required=texts.format_price(reset_price),
            balance=texts.format_price(db_user.balance_kopeks),
            missing=texts.format_price(missing_kopeks),
        )

        await callback.message.edit_text(
            message_text,
            reply_markup=get_insufficient_balance_keyboard(
                db_user.language,
                amount_kopeks=missing_kopeks,
            ),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    try:
        success = await subtract_user_balance(
            db, db_user, reset_price,
            texts.t("subscription.traffic.reset.transaction_desc", "Traffic reset")
        )

        if not success:
            await callback.answer(
                texts.t("PAYMENT_CHARGE_ERROR", "⚠️ Payment charge error"),
                show_alert=True
            )
            return

        subscription.traffic_used_gb = 0.0
        subscription.updated_at = datetime.utcnow()
        await db.commit()

        subscription_service = SubscriptionService()
        remnawave_service = RemnaWaveService()

        user = db_user
        if user.remnawave_uuid:
            async with remnawave_service.get_api_client() as api:
                await api.reset_user_traffic(user.remnawave_uuid)

        await create_transaction(
            db=db,
            user_id=db_user.id,
            type=TransactionType.SUBSCRIPTION_PAYMENT,
            amount_kopeks=reset_price,
            description=texts.t("subscription.traffic.reset.transaction_desc", "Traffic reset")
        )

        await db.refresh(db_user)
        await db.refresh(subscription)

        success_text = texts.t(
            "subscription.traffic.reset.success",
            (
                "✅ Traffic successfully reset!\n\n"
                "🔄 Used traffic reset to zero\n"
                "📊 Limit: {limit}"
            )
        ).format(limit=texts.format_traffic(subscription.traffic_limit_gb))
        
        await callback.message.edit_text(
            success_text,
            reply_markup=get_back_keyboard(db_user.language)
        )

        logger.info(f"✅ User {db_user.telegram_id} reset traffic")

    except Exception as e:
        logger.error(f"Error resetting traffic: {e}")
        await callback.message.edit_text(
            texts.ERROR,
            reply_markup=get_back_keyboard(db_user.language)
        )

    await callback.answer()

async def refresh_traffic_config():
    try:
        from app.config import refresh_traffic_prices
        refresh_traffic_prices()

        packages = settings.get_traffic_packages()
        enabled_count = sum(1 for pkg in packages if pkg['enabled'])

        logger.info(f"🔄 Traffic configuration updated: {enabled_count} active packages")
        for pkg in packages:
            if pkg['enabled']:
                gb_text = "♾️ Unlimited" if pkg['gb'] == 0 else f"{pkg['gb']} GB"
                logger.info(f"   📦 {gb_text}: {pkg['price'] / 100} RUB")

        return True

    except Exception as e:
        logger.error(f"⚠️ Error updating traffic configuration: {e}")
        return False

async def get_traffic_packages_info() -> str:
    try:
        packages = settings.get_traffic_packages()

        info_lines = ["📦 Configured traffic packages:"]

        enabled_packages = [pkg for pkg in packages if pkg['enabled']]
        disabled_packages = [pkg for pkg in packages if not pkg['enabled']]

        if enabled_packages:
            info_lines.append("\n✅ Active:")
            for pkg in enabled_packages:
                gb_text = "♾️ Unlimited" if pkg['gb'] == 0 else f"{pkg['gb']} GB"
                info_lines.append(f"   • {gb_text}: {pkg['price'] // 100} RUB")

        if disabled_packages:
            info_lines.append("\n❌ Disabled:")
            for pkg in disabled_packages:
                gb_text = "♾️ Unlimited" if pkg['gb'] == 0 else f"{pkg['gb']} GB"
                info_lines.append(f"   • {gb_text}: {pkg['price'] // 100} RUB")

        info_lines.append(f"\n📊 Total packages: {len(packages)}")
        info_lines.append(f"🟢 Active: {len(enabled_packages)}")
        info_lines.append(f"🔴 Disabled: {len(disabled_packages)}")

        return "\n".join(info_lines)

    except Exception as e:
        return f"⚠️ Error fetching information: {e}"

async def select_traffic(
        callback: types.CallbackQuery,
        state: FSMContext,
        db_user: User
):
    traffic_gb = int(callback.data.split('_')[1])
    texts = get_texts(db_user.language)

    data = await state.get_data()
    data['traffic_gb'] = traffic_gb

    traffic_price = settings.get_traffic_price(traffic_gb)
    data['total_price'] += traffic_price

    await state.set_data(data)

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

async def add_traffic(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    if settings.is_traffic_fixed():
        await callback.answer(
            texts.t("TRAFFIC_FIXED_MODE", "⚠️ In current mode traffic is fixed"),
            show_alert=True
        )
        return

    traffic_gb = int(callback.data.split('_')[2])
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    base_price = settings.get_traffic_price(traffic_gb)

    if base_price == 0 and traffic_gb != 0:
        await callback.answer(
            texts.t("subscription.traffic.package_price_not_set", "⚠️ Price for this package is not configured"),
            show_alert=True
        )
        return

    period_hint_days = _get_period_hint_from_subscription(subscription)
    discount_result = _apply_addon_discount(
        db_user,
        "traffic",
        base_price,
        period_hint_days,
    )

    discounted_per_month = discount_result["discounted"]
    discount_per_month = discount_result["discount"]
    charged_months = 1

    if subscription:
        price, charged_months = calculate_prorated_price(
            discounted_per_month,
            subscription.end_date,
        )
    else:
        price = discounted_per_month

    total_discount_value = discount_per_month * charged_months

    if db_user.balance_kopeks < price:
        missing_kopeks = price - db_user.balance_kopeks
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
            required=texts.format_price(price),
            balance=texts.format_price(db_user.balance_kopeks),
            missing=texts.format_price(missing_kopeks),
        )

        await callback.message.edit_text(
            message_text,
            reply_markup=get_insufficient_balance_keyboard(
                db_user.language,
                amount_kopeks=missing_kopeks,
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
            texts.t("subscription.traffic.add_transaction_desc", "Adding {gb} GB traffic").format(gb=traffic_gb),
        )

        if not success:
            await callback.answer(
                texts.t("PAYMENT_CHARGE_ERROR", "⚠️ Payment charge error"),
                show_alert=True
            )
            return

        if traffic_gb == 0:
            subscription.traffic_limit_gb = 0
        else:
            await add_subscription_traffic(db, subscription, traffic_gb)

        subscription_service = SubscriptionService()
        await subscription_service.update_remnawave_user(db, subscription)

        await create_transaction(
            db=db,
            user_id=db_user.id,
            type=TransactionType.SUBSCRIPTION_PAYMENT,
            amount_kopeks=price,
            description=texts.t("subscription.traffic.add_transaction_desc", "Adding {gb} GB traffic").format(gb=traffic_gb),
        )

        await db.refresh(db_user)
        await db.refresh(subscription)

        if traffic_gb == 0:
            success_text = texts.t(
                "subscription.traffic.add.unlimited_success",
                "✅ Traffic successfully added!\n\n🎉 You now have unlimited traffic!"
            )
        else:
            success_text = texts.t(
                "subscription.traffic.add.success",
                (
                    "✅ Traffic successfully added!\n\n"
                    "📈 Added: {gb} GB\n"
                    "New limit: {limit}"
                )
            ).format(
                gb=traffic_gb,
                limit=texts.format_traffic(subscription.traffic_limit_gb)
            )

        if price > 0:
            success_text += "\n" + texts.t("subscription.traffic.add.charged", "💰 Charged: {amount}").format(
                amount=texts.format_price(price)
            )
            if total_discount_value > 0:
                success_text += texts.t(
                    "subscription.traffic.add.discount_info",
                    " (discount {percent}%: -{amount})"
                ).format(
                    percent=discount_result['percent'],
                    amount=texts.format_price(total_discount_value)
                )

        await callback.message.edit_text(
            success_text,
            reply_markup=get_back_keyboard(db_user.language)
        )

        logger.info(f"✅ User {db_user.telegram_id} added {traffic_gb} GB traffic")

    except Exception as e:
        logger.error(f"Error adding traffic: {e}")
        await callback.message.edit_text(
            texts.ERROR,
            reply_markup=get_back_keyboard(db_user.language)
        )

    await callback.answer()

async def handle_no_traffic_packages(
        callback: types.CallbackQuery,
        db_user: User
):
    texts = get_texts(db_user.language)
    await callback.answer(
        texts.t(
            "subscription.traffic.no_packages",
            "⚠️ No traffic packages available at the moment. Please contact support for information."
        ),
        show_alert=True
    )

async def handle_switch_traffic(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    from app.config import settings

    texts = get_texts(db_user.language)

    if settings.is_traffic_fixed():
        await callback.answer(
            texts.t("TRAFFIC_FIXED_MODE", "⚠️ In current mode traffic is fixed"),
            show_alert=True
        )
        return
    subscription = db_user.subscription

    if not subscription or subscription.is_trial:
        await callback.answer(
            texts.t("PAID_FEATURE_ONLY", "⚠️ This feature is only available for paid subscriptions"),
            show_alert=True
        )
        return

    current_traffic = subscription.traffic_limit_gb
    period_hint_days = _get_period_hint_from_subscription(subscription)
    traffic_discount_percent = _get_addon_discount_percent_for_user(
        db_user,
        "traffic",
        period_hint_days,
    )

    switch_text = texts.t(
        "subscription.traffic.switch.prompt",
        (
            "🔄 <b>Switch traffic limit</b>\n\n"
            "Current limit: {current}\n"
            "Choose new traffic limit:\n\n"
            "💡 <b>Important:</b>\n"
            "• When increasing - additional payment for the difference\n"
            "• When decreasing - no refund is provided"
        )
    ).format(current=texts.format_traffic(current_traffic))
    
    await callback.message.edit_text(
        switch_text,
        reply_markup=get_traffic_switch_keyboard(
            current_traffic,
            db_user.language,
            subscription.end_date,
            traffic_discount_percent,
        ),
        parse_mode="HTML"
    )

    await callback.answer()

async def confirm_switch_traffic(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    new_traffic_gb = int(callback.data.split('_')[2])
    texts = get_texts(db_user.language)
    subscription = db_user.subscription

    current_traffic = subscription.traffic_limit_gb

    if new_traffic_gb == current_traffic:
        await callback.answer(
            texts.t("TRAFFIC_NO_CHANGE", "ℹ️ Traffic limit unchanged"),
            show_alert=True
        )
        return

    old_price_per_month = settings.get_traffic_price(current_traffic)
    new_price_per_month = settings.get_traffic_price(new_traffic_gb)

    months_remaining = get_remaining_months(subscription.end_date)
    period_hint_days = months_remaining * 30 if months_remaining > 0 else None
    traffic_discount_percent = _get_addon_discount_percent_for_user(
        db_user,
        "traffic",
        period_hint_days,
    )

    discounted_old_per_month, _ = apply_percentage_discount(
        old_price_per_month,
        traffic_discount_percent,
    )
    discounted_new_per_month, _ = apply_percentage_discount(
        new_price_per_month,
        traffic_discount_percent,
    )
    price_difference_per_month = discounted_new_per_month - discounted_old_per_month
    discount_savings_per_month = (
            (new_price_per_month - old_price_per_month) - price_difference_per_month
    )

    if price_difference_per_month > 0:
        total_price_difference = price_difference_per_month * months_remaining

        if db_user.balance_kopeks < total_price_difference:
            missing_kopeks = total_price_difference - db_user.balance_kopeks
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
                required=texts.t("subscription.countries.charged_period", "{amount} (for {months} months)").format(
                    amount=texts.format_price(total_price_difference),
                    months=months_remaining
                ),
                balance=texts.format_price(db_user.balance_kopeks),
                missing=texts.format_price(missing_kopeks),
            )

            await callback.message.edit_text(
                message_text,
                reply_markup=get_insufficient_balance_keyboard(
                    db_user.language,
                    amount_kopeks=missing_kopeks,
                ),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        action_text = texts.t("subscription.traffic.switch.action_increase", "increase to {limit}").format(
            limit=texts.format_traffic(new_traffic_gb)
        )
        cost_text = texts.t("subscription.traffic.switch.additional_payment", "Additional payment: {amount} (for {months} months)").format(
            amount=texts.format_price(total_price_difference),
            months=months_remaining
        )
        if discount_savings_per_month > 0:
            total_discount_savings = discount_savings_per_month * months_remaining
            cost_text += texts.t(
                "subscription.traffic.switch.discount_info",
                " (discount {percent}%: -{amount})"
            ).format(
                percent=traffic_discount_percent,
                amount=texts.format_price(total_discount_savings)
            )
    else:
        total_price_difference = 0
        action_text = texts.t("subscription.traffic.switch.action_decrease", "decrease to {limit}").format(
            limit=texts.format_traffic(new_traffic_gb)
        )
        cost_text = texts.t("subscription.traffic.switch.no_refund", "No refund provided")

    confirm_text = texts.t(
        "subscription.traffic.switch.confirmation",
        (
            "🔄 <b>Confirm traffic switch</b>\n\n"
            "Current limit: {current}\n"
            "New limit: {new}\n\n"
            "Action: {action}\n"
            "💰 {cost}\n\n"
            "Confirm switch?"
        )
    ).format(
        current=texts.format_traffic(current_traffic),
        new=texts.format_traffic(new_traffic_gb),
        action=action_text,
        cost=cost_text
    )

    await callback.message.edit_text(
        confirm_text,
        reply_markup=get_confirm_switch_traffic_keyboard(new_traffic_gb, total_price_difference, db_user.language),
        parse_mode="HTML"
    )

    await callback.answer()

async def execute_switch_traffic(
        callback: types.CallbackQuery,
        db_user: User,
        db: AsyncSession
):
    callback_parts = callback.data.split('_')
    new_traffic_gb = int(callback_parts[3])
    price_difference = int(callback_parts[4])

    texts = get_texts(db_user.language)
    subscription = db_user.subscription
    current_traffic = subscription.traffic_limit_gb

    try:
        if price_difference > 0:
            success = await subtract_user_balance(
                db, db_user, price_difference,
                texts.t("subscription.traffic.switch.transaction_desc", "Switching traffic from {old}GB to {new}GB").format(
                    old=current_traffic,
                    new=new_traffic_gb
                )
            )

            if not success:
                await callback.answer(
                    texts.t("PAYMENT_CHARGE_ERROR", "⚠️ Payment charge error"),
                    show_alert=True
                )
                return

            months_remaining = get_remaining_months(subscription.end_date)
            await create_transaction(
                db=db,
                user_id=db_user.id,
                type=TransactionType.SUBSCRIPTION_PAYMENT,
                amount_kopeks=price_difference,
                description=texts.t("subscription.traffic.switch.transaction_desc_full", "Switching traffic from {old}GB to {new}GB for {months} months").format(
                    old=current_traffic,
                    new=new_traffic_gb,
                    months=months_remaining
                )
            )

        subscription.traffic_limit_gb = new_traffic_gb
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
                db, db_user, subscription, "traffic", current_traffic, new_traffic_gb, price_difference
            )
        except Exception as e:
            logger.error(f"Error sending traffic change notification: {e}")

        if new_traffic_gb > current_traffic:
            success_text = texts.t("subscription.traffic.switch.increase_success", "✅ Traffic limit increased!\n\n")
            success_text += texts.t("subscription.traffic.switch.result_line", "📊 Was: {old} → Now: {new}\n").format(
                old=texts.format_traffic(current_traffic),
                new=texts.format_traffic(new_traffic_gb)
            )
            if price_difference > 0:
                success_text += texts.t("subscription.traffic.switch.charged", "💰 Charged: {amount}").format(
                    amount=texts.format_price(price_difference)
                )
        elif new_traffic_gb < current_traffic:
            success_text = texts.t("subscription.traffic.switch.decrease_success", "✅ Traffic limit decreased!\n\n")
            success_text += texts.t("subscription.traffic.switch.result_line", "📊 Was: {old} → Now: {new}\n").format(
                old=texts.format_traffic(current_traffic),
                new=texts.format_traffic(new_traffic_gb)
            )
            success_text += texts.t("subscription.traffic.switch.no_refund_info", "ℹ️ No refund provided")

        await callback.message.edit_text(
            success_text,
            reply_markup=get_back_keyboard(db_user.language)
        )

        logger.info(
            f"✅ User {db_user.telegram_id} switched traffic from {current_traffic}GB to {new_traffic_gb}GB, additional payment: {price_difference / 100} RUB")

    except Exception as e:
        logger.error(f"Error switching traffic: {e}")
        await callback.message.edit_text(
            texts.ERROR,
            reply_markup=get_back_keyboard(db_user.language)
        )

    await callback.answer()
