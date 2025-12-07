"""Handlers for simple subscription purchase."""
import html
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from aiogram import types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.keyboards.inline import get_back_keyboard, get_happ_download_button_row
from app.localization.texts import get_texts
from app.services.payment_service import PaymentService
from app.services.subscription_purchase_service import SubscriptionPurchaseService
from app.utils.decorators import error_handler
from app.states import SubscriptionStates
from app.utils.subscription_utils import (
    get_display_subscription_link,
    resolve_simple_subscription_device_limit,
)
from app.utils.pricing_utils import compute_simple_subscription_price

logger = logging.getLogger(__name__)


@error_handler
async def start_simple_subscription_purchase(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    """Starts the simple subscription purchase process."""
    texts = get_texts(db_user.language)
    
    if not settings.SIMPLE_SUBSCRIPTION_ENABLED:
        await callback.answer(
            texts.t("SIMPLE_SUBSCRIPTION_DISABLED", "❌ Simple subscription purchase is temporarily unavailable"),
            show_alert=True
        )
        return

    # Check if user has a subscription
    from app.database.crud.subscription import get_subscription_by_user_id
    current_subscription = await get_subscription_by_user_id(db, db_user.id)

    device_limit = resolve_simple_subscription_device_limit()

    # Prepare simple subscription parameters
    subscription_params = {
        "period_days": settings.SIMPLE_SUBSCRIPTION_PERIOD_DAYS,
        "device_limit": device_limit,
        "traffic_limit_gb": settings.SIMPLE_SUBSCRIPTION_TRAFFIC_GB,
        "squad_uuid": settings.SIMPLE_SUBSCRIPTION_SQUAD_UUID
    }
    
    # Save parameters to state
    await state.update_data(subscription_params=subscription_params)

    data = await state.get_data()
    resolved_squad_uuid = await _ensure_simple_subscription_squad_uuid(
        db,
        state,
        subscription_params,
        user_id=db_user.id,
        state_data=data,
    )

    price_kopeks, price_breakdown = await _calculate_simple_subscription_price(
        db,
        subscription_params,
        user=db_user,
        resolved_squad_uuid=resolved_squad_uuid,
    )

    period_days = subscription_params["period_days"]
    user_balance_kopeks = getattr(db_user, "balance_kopeks", 0)

    logger.warning(
        "SIMPLE_SUBSCRIPTION_DEBUG_START | user=%s | period=%s | base=%s | traffic=%s | devices=%s | servers=%s | discount=%s | total=%s | squads=%s",
        db_user.id,
        period_days,
        price_breakdown.get("base_price", 0),
        price_breakdown.get("traffic_price", 0),
        price_breakdown.get("devices_price", 0),
        price_breakdown.get("servers_price", 0),
        price_breakdown.get("total_discount", 0),
        price_kopeks,
        ",".join(price_breakdown.get("resolved_squad_uuids", []))
        if price_breakdown.get("resolved_squad_uuids")
        else "none",
    )

    can_pay_from_balance = user_balance_kopeks >= price_kopeks
    logger.warning(
        "SIMPLE_SUBSCRIPTION_DEBUG_START_BALANCE | user=%s | balance=%s | min_required=%s | can_pay=%s",
        db_user.id,
        user_balance_kopeks,
        price_kopeks,
        can_pay_from_balance,
    )

    # Check if user has an active paid subscription
    has_active_paid_subscription = False
    trial_notice = ""
    if current_subscription:
        if not getattr(current_subscription, "is_trial", False) and current_subscription.is_active:
            # This is an active paid subscription - require confirmation
            has_active_paid_subscription = True
        elif getattr(current_subscription, "is_trial", False):
            # This is a trial subscription
            try:
                days_left = max(0, (current_subscription.end_date - datetime.utcnow()).days)
            except Exception:
                days_left = 0
            key = "SIMPLE_SUBSCRIPTION_TRIAL_NOTICE_ACTIVE" if current_subscription.is_active else "SIMPLE_SUBSCRIPTION_TRIAL_NOTICE_TRIAL"
            trial_notice = texts.t(
                key,
                "ℹ️ You already have a trial subscription. It expires in {days} days.",
            ).format(days=days_left)

    server_label = _get_simple_subscription_server_label(
        texts,
        subscription_params,
        resolved_squad_uuid,
    )
    show_devices = settings.is_devices_selection_enabled()

    period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
    message_lines = [
        texts.t("SIMPLE_SUBSCRIPTION_PURCHASE_TITLE", "⚡ <b>Simple subscription purchase</b>"),
        "",
        texts.t("SIMPLE_SUBSCRIPTION_PERIOD", "📅 Period: {period}").format(period=period_text),
    ]

    if show_devices:
        devices_text = texts.t("SIMPLE_SUBSCRIPTION_DEVICES", "📱 Devices: {count}").format(count=subscription_params['device_limit'])
        message_lines.append(devices_text)

    traffic_limit_gb = subscription_params["traffic_limit_gb"]
    if traffic_limit_gb == 0:
        traffic_label = texts.t("TRAFFIC_UNLIMITED_LABEL", "Unlimited")
    else:
        traffic_label = texts.t("TRAFFIC_GB", "{gb} GB").format(gb=traffic_limit_gb)

    message_lines.extend([
        texts.t("SIMPLE_SUBSCRIPTION_TRAFFIC", "📊 Traffic: {traffic}").format(traffic=traffic_label),
        texts.t("SIMPLE_SUBSCRIPTION_SERVER", "🌍 Server: {server}").format(server=server_label),
        "",
        texts.t("SIMPLE_SUBSCRIPTION_COST", "💰 Cost: {price}").format(price=settings.format_price(price_kopeks)),
        texts.t("SIMPLE_SUBSCRIPTION_BALANCE", "💳 Your balance: {balance}").format(balance=settings.format_price(user_balance_kopeks)),
        "",
    ])

    # If user already has an active paid subscription, require confirmation
    if has_active_paid_subscription:
        # User already has an active paid subscription
        message_lines.append(
            texts.t(
                "SIMPLE_SUBSCRIPTION_ACTIVE_SUBSCRIPTION_WARNING",
                "⚠️ You already have an active paid subscription. "
                "Purchasing a simple subscription will change the parameters of your current subscription. "
                "Confirmation required."
            )
        )
        message_text = "\n".join(message_lines)

        # Confirmation keyboard
        keyboard_rows = [
            [types.InlineKeyboardButton(
                text=texts.t("CONFIRM_PURCHASE_BUTTON", "✅ Confirm purchase"),
                callback_data="simple_subscription_confirm_purchase"
            )],
            [types.InlineKeyboardButton(
                text=texts.BACK,
                callback_data="subscription_purchase"
            )]
        ]
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    else:
        # User doesn't have an active paid subscription (or only has a trial)
        # Show standard payment method selection
        if can_pay_from_balance:
            message_lines.append(
                texts.t(
                    "SIMPLE_SUBSCRIPTION_PAYMENT_OPTIONS_BALANCE",
                    "You can pay for the subscription from your balance or choose another payment method."
                )
            )
        else:
            message_lines.append(
                texts.t(
                    "SIMPLE_SUBSCRIPTION_PAYMENT_OPTIONS_INSUFFICIENT",
                    "Balance is insufficient for instant payment. Choose a suitable payment method:"
                )
            )
        
        message_text = "\n".join(message_lines)
        
        if trial_notice:
            message_text = f"{trial_notice}\n\n{message_text}"

        methods_keyboard = _get_simple_subscription_payment_keyboard(db_user.language)
        keyboard_rows = []

        if can_pay_from_balance:
            keyboard_rows.append([
                types.InlineKeyboardButton(
                    text=texts.t("PAY_WITH_BALANCE_BUTTON", "✅ Pay from balance"),
                    callback_data="simple_subscription_pay_with_balance",
                )
            ])

        keyboard_rows.extend(methods_keyboard.inline_keyboard)

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    # Set the appropriate state
    if has_active_paid_subscription:
        await state.set_state(SubscriptionStates.waiting_for_simple_subscription_confirmation)
    else:
        await state.set_state(SubscriptionStates.waiting_for_simple_subscription_payment_method)
    await callback.answer()


async def _calculate_simple_subscription_price(
    db: AsyncSession,
    params: dict,
    *,
    user: Optional[User] = None,
    resolved_squad_uuid: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Calculates the price of a simple subscription."""

    resolved_uuids = [resolved_squad_uuid] if resolved_squad_uuid else None
    return await compute_simple_subscription_price(
        db,
        params,
        user=user,
        resolved_squad_uuids=resolved_uuids,
    )


def _get_simple_subscription_payment_keyboard(language: str) -> types.InlineKeyboardMarkup:
    """Creates a keyboard with payment methods for simple subscription."""
    texts = get_texts(language)
    keyboard = []
    
    # Add available payment methods
    if settings.TELEGRAM_STARS_ENABLED:
        keyboard.append([types.InlineKeyboardButton(
            text=texts.t("PAYMENT_METHOD_STARS_BUTTON", "⭐ Telegram Stars"),
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
            text=texts.t("PAYMENT_METHOD_CRYPTOBOT_BUTTON", "🪙 CryptoBot"),
            callback_data="simple_subscription_cryptobot"
        )])

    if settings.is_heleket_enabled():
        keyboard.append([types.InlineKeyboardButton(
            text=texts.t("PAYMENT_METHOD_HELEKET_BUTTON", "🪙 Heleket"),
            callback_data="simple_subscription_heleket"
        )])
    
    if settings.is_mulenpay_enabled():
        mulenpay_name = settings.get_mulenpay_display_name()
        keyboard.append([types.InlineKeyboardButton(
            text=f"💳 {mulenpay_name}",
            callback_data="simple_subscription_mulenpay"
        )])
    
    if settings.is_pal24_enabled():
        keyboard.append([types.InlineKeyboardButton(
            text=texts.t("PAYMENT_METHOD_PAL24_BUTTON", "💳 PayPalych"),
            callback_data="simple_subscription_pal24"
        )])
    
    if settings.is_wata_enabled():
        keyboard.append([types.InlineKeyboardButton(
            text=texts.t("PAYMENT_METHOD_WATA_BUTTON", "💳 WATA"),
            callback_data="simple_subscription_wata"
        )])
    
    # Back button
    keyboard.append([types.InlineKeyboardButton(
        text=texts.BACK,
        callback_data="subscription_purchase"
    )])

    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


def _get_simple_subscription_server_label(
    texts,
    subscription_params: Dict[str, Any],
    resolved_squad_uuid: Optional[str] = None,
) -> str:
    """Returns a localized description of the selected server."""

    if subscription_params.get("squad_uuid"):
        return texts.t("SIMPLE_SUBSCRIPTION_SERVER_SELECTED", "Selected")

    if resolved_squad_uuid:
        return texts.t(
            "SIMPLE_SUBSCRIPTION_SERVER_ASSIGNED",
            "Assigned automatically",
        )

    return texts.t("SIMPLE_SUBSCRIPTION_SERVER_ANY", "Any available")


async def _ensure_simple_subscription_squad_uuid(
    db: AsyncSession,
    state: FSMContext,
    subscription_params: Dict[str, Any],
    *,
    user_id: Optional[int] = None,
    state_data: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Determines the squad UUID for a simple subscription."""

    explicit_uuid = subscription_params.get("squad_uuid")
    if explicit_uuid:
        return explicit_uuid

    if state_data is None:
        state_data = await state.get_data()

    resolved_uuid = state_data.get("resolved_squad_uuid")
    if resolved_uuid:
        return resolved_uuid

    try:
        from app.database.crud.server_squad import get_random_active_squad_uuid

        resolved_uuid = await get_random_active_squad_uuid(db)
    except Exception as error:  # pragma: no cover - defensive logging
        logger.error(
            "SIMPLE_SUBSCRIPTION_RANDOM_SQUAD_ERROR | user=%s | error=%s",
            user_id,
            error,
        )
        return None

    if resolved_uuid:
        await state.update_data(resolved_squad_uuid=resolved_uuid)
        logger.info(
            "SIMPLE_SUBSCRIPTION_RANDOM_SQUAD_ASSIGNED | user=%s | squad=%s",
            user_id,
            resolved_uuid,
        )

    return resolved_uuid


@error_handler
async def handle_simple_subscription_pay_with_balance(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    """Handles payment for simple subscription from balance."""
    texts = get_texts(db_user.language)
    
    data = await state.get_data()
    subscription_params = data.get("subscription_params", {})
    
    if not subscription_params:
        await callback.answer(
            texts.t("SIMPLE_SUBSCRIPTION_DATA_EXPIRED", "❌ Subscription data has expired. Please start over."),
            show_alert=True
        )
        return

    # Check if user has an active paid subscription
    from app.database.crud.subscription import get_subscription_by_user_id
    current_subscription = await get_subscription_by_user_id(db, db_user.id)
    
    if current_subscription and not getattr(current_subscription, "is_trial", False) and current_subscription.is_active:
        # User has an active paid subscription - require confirmation
        await callback.answer(
            texts.t(
                "SIMPLE_SUBSCRIPTION_ACTIVE_REQUIRES_CONFIRMATION",
                "⚠️ You already have an active paid subscription. Please confirm the purchase."
            ),
            show_alert=True
        )
        return

    resolved_squad_uuid = await _ensure_simple_subscription_squad_uuid(
        db,
        state,
        subscription_params,
        user_id=db_user.id,
        state_data=data,
    )

    # Calculate subscription price
    price_kopeks, price_breakdown = await _calculate_simple_subscription_price(
        db,
        subscription_params,
        user=db_user,
        resolved_squad_uuid=resolved_squad_uuid,
    )
    total_required = price_kopeks
    logger.warning(
        "SIMPLE_SUBSCRIPTION_DEBUG_PAY_BALANCE | user=%s | period=%s | base=%s | traffic=%s | devices=%s | servers=%s | discount=%s | total_required=%s | balance=%s",
        db_user.id,
        subscription_params["period_days"],
        price_breakdown.get("base_price", 0),
        price_breakdown.get("traffic_price", 0),
        price_breakdown.get("devices_price", 0),
        price_breakdown.get("servers_price", 0),
        price_breakdown.get("total_discount", 0),
        total_required,
        getattr(db_user, "balance_kopeks", 0),
    )

    # Check user balance
    user_balance_kopeks = getattr(db_user, "balance_kopeks", 0)

    if user_balance_kopeks < total_required:
        await callback.answer(
            texts.t("SIMPLE_SUBSCRIPTION_INSUFFICIENT_BALANCE", "❌ Insufficient balance to pay for subscription"),
            show_alert=True
        )
        return
    
    try:
        # Deduct funds from user balance
        from app.database.crud.user import subtract_user_balance
        period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
        payment_description = texts.t("SIMPLE_SUBSCRIPTION_PAYMENT_DESCRIPTION", "Subscription payment for {period}").format(period=period_text)
        success = await subtract_user_balance(
            db,
            db_user,
            price_kopeks,
            payment_description,
            consume_promo_offer=False,
        )
        
        if not success:
            await callback.answer(
                texts.t("SIMPLE_SUBSCRIPTION_BALANCE_DEDUCTION_ERROR", "❌ Error deducting funds from balance"),
                show_alert=True
            )
            return
        
        # Check if user already has a subscription
        from app.database.crud.subscription import get_subscription_by_user_id, extend_subscription
        
        existing_subscription = await get_subscription_by_user_id(db, db_user.id)
        
        if existing_subscription:
            # If subscription already exists (paid or trial), extend it
            # Save information about current subscription, especially if it's a trial
            was_trial = getattr(existing_subscription, "is_trial", False)
            
            subscription = await extend_subscription(
                db=db,
                subscription=existing_subscription,
                days=subscription_params["period_days"]
            )
            # Update subscription parameters
            subscription.traffic_limit_gb = subscription_params["traffic_limit_gb"]
            subscription.device_limit = subscription_params["device_limit"]
            
            # If current subscription was a trial, and we're updating it
            # need to change subscription status
            if was_trial:
                from app.database.models import SubscriptionStatus
                # Convert subscription from trial to active paid
                subscription.status = SubscriptionStatus.ACTIVE.value
                subscription.is_trial = False
            
            # Set the new selected squad
            if resolved_squad_uuid:
                subscription.connected_squads = [resolved_squad_uuid]
            
            await db.commit()
            await db.refresh(subscription)
        else:
            # If subscription doesn't exist, create a new one
            from app.database.crud.subscription import create_paid_subscription
            subscription = await create_paid_subscription(
                db=db,
                user_id=db_user.id,
                duration_days=subscription_params["period_days"],
                traffic_limit_gb=subscription_params["traffic_limit_gb"],
                device_limit=subscription_params["device_limit"],
                connected_squads=[resolved_squad_uuid] if resolved_squad_uuid else [],
                update_server_counters=True,
            )
        
        if not subscription:
            # Refund to balance in case of error
            from app.services.payment_service import add_user_balance
            period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
            refund_description = texts.t("SIMPLE_SUBSCRIPTION_REFUND_DESCRIPTION", "Refund for failed subscription for {period}").format(period=period_text)
            await add_user_balance(
                db,
                db_user.id,
                price_kopeks,
                refund_description,
            )
            await callback.answer(
                texts.t("SIMPLE_SUBSCRIPTION_CREATION_ERROR", "❌ Error creating subscription. Funds have been refunded to balance."),
                show_alert=True
            )
            return
        
        # Update user balance
        await db.refresh(db_user)

        # Update or create subscription link in RemnaWave
        try:
            from app.services.subscription_service import SubscriptionService
            subscription_service = SubscriptionService()
            remnawave_user = await subscription_service.create_remnawave_user(db, subscription)
            if remnawave_user:
                await db.refresh(subscription)
        except Exception as sync_error:
            logger.error(
                "Error syncing subscription with RemnaWave for user %s: %s",
                db_user.id,
                sync_error,
                exc_info=True
            )
        
        # Send success notification
        server_label = _get_simple_subscription_server_label(
            texts,
            subscription_params,
            resolved_squad_uuid,
        )
        show_devices = settings.is_devices_selection_enabled()

        period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
        success_lines = [
            texts.t("SIMPLE_SUBSCRIPTION_ACTIVATED", "✅ <b>Subscription successfully activated!</b>"),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_PERIOD", "📅 Period: {period}").format(period=period_text),
        ]

        if show_devices:
            devices_text = texts.t("SIMPLE_SUBSCRIPTION_DEVICES", "📱 Devices: {count}").format(count=subscription_params['device_limit'])
            success_lines.append(devices_text)

        success_traffic_gb = subscription_params["traffic_limit_gb"]
        if success_traffic_gb == 0:
            success_traffic_label = texts.t("TRAFFIC_UNLIMITED_LABEL", "Unlimited")
        else:
            success_traffic_label = texts.t("TRAFFIC_GB", "{gb} GB").format(gb=success_traffic_gb)

        success_lines.extend([
            texts.t("SIMPLE_SUBSCRIPTION_TRAFFIC", "📊 Traffic: {traffic}").format(traffic=success_traffic_label),
            texts.t("SIMPLE_SUBSCRIPTION_SERVER", "🌍 Server: {server}").format(server=server_label),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_DEDUCTED", "💰 Deducted from balance: {amount}").format(amount=settings.format_price(price_kopeks)),
            texts.t("SIMPLE_SUBSCRIPTION_BALANCE", "💳 Your balance: {balance}").format(balance=settings.format_price(db_user.balance_kopeks)),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_CONNECT_HINT", "🔗 To connect, go to the 'Connect' section"),
        ])

        success_message = "\n".join(success_lines)
        
        connect_mode = settings.CONNECT_BUTTON_MODE
        subscription_link = get_display_subscription_link(subscription)
        connect_button_text = texts.t("CONNECT_BUTTON", "🔗 Connect")

        def _fallback_connect_button() -> types.InlineKeyboardButton:
            return types.InlineKeyboardButton(
                text=connect_button_text,
                callback_data="subscription_connect",
            )

        if connect_mode == "miniapp_subscription":
            if subscription_link:
                connect_row = [
                    types.InlineKeyboardButton(
                        text=connect_button_text,
                        web_app=types.WebAppInfo(url=subscription_link),
                    )
                ]
            else:
                connect_row = [_fallback_connect_button()]
        elif connect_mode == "miniapp_custom":
            custom_url = settings.MINIAPP_CUSTOM_URL
            if custom_url:
                connect_row = [
                    types.InlineKeyboardButton(
                        text=connect_button_text,
                        web_app=types.WebAppInfo(url=custom_url),
                    )
                ]
            else:
                connect_row = [_fallback_connect_button()]
        elif connect_mode == "link":
            if subscription_link:
                connect_row = [
                    types.InlineKeyboardButton(
                        text=connect_button_text,
                        url=subscription_link,
                    )
                ]
            else:
                connect_row = [_fallback_connect_button()]
        elif connect_mode == "happ_cryptolink":
            if subscription_link:
                connect_row = [
                    types.InlineKeyboardButton(
                        text=connect_button_text,
                        callback_data="open_subscription_link",
                    )
                ]
            else:
                connect_row = [_fallback_connect_button()]
        else:
            connect_row = [_fallback_connect_button()]

        keyboard_rows = [connect_row]

        happ_row = get_happ_download_button_row(texts)
        if happ_row:
            keyboard_rows.append(happ_row)

        keyboard_rows.append(
            [types.InlineKeyboardButton(text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "🏠 Main menu"), callback_data="back_to_menu")]
        )

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        await callback.message.edit_text(
            success_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Send notification to admins
        try:
            from app.services.admin_notification_service import AdminNotificationService
            notification_service = AdminNotificationService(callback.bot)
            await notification_service.send_subscription_purchase_notification(
                db,
                db_user,
                subscription,
                None,  # transaction
                subscription_params["period_days"],
                False,  # was_trial_conversion
                amount_kopeks=price_kopeks,
            )
        except Exception as e:
            logger.error("Error sending purchase notification to admins: %s", e)
        
        await state.clear()
        await callback.answer()

        logger.info(
            "User %s successfully purchased subscription from balance for %s",
            db_user.telegram_id,
            settings.format_price(price_kopeks)
        )

    except Exception as error:
        logger.error(
            "Error paying for simple subscription from balance for user %s: %s",
            db_user.id,
            error,
            exc_info=True,
        )
        await callback.answer(
            texts.t(
                "SIMPLE_SUBSCRIPTION_PAYMENT_ERROR",
                "❌ Error paying for subscription. Please try again later or contact support."
            ),
            show_alert=True,
        )
        await state.clear()


@error_handler
async def handle_simple_subscription_pay_with_balance_disabled(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    """Shows notification if balance is insufficient for direct payment."""
    texts = get_texts(db_user.language)
    await callback.answer(
        texts.t(
            "SIMPLE_SUBSCRIPTION_INSUFFICIENT_BALANCE_ALERT",
            "❌ Insufficient balance. Top up your balance or choose another payment method."
        ),
        show_alert=True,
    )


@error_handler
async def handle_simple_subscription_other_payment_methods(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    """Handles selection of other payment methods."""
    texts = get_texts(db_user.language)
    
    data = await state.get_data()
    subscription_params = data.get("subscription_params", {})

    if not subscription_params:
        await callback.answer(
            texts.t("SIMPLE_SUBSCRIPTION_DATA_EXPIRED", "❌ Subscription data has expired. Please start over."),
            show_alert=True
        )
        return

    resolved_squad_uuid = await _ensure_simple_subscription_squad_uuid(
        db,
        state,
        subscription_params,
        user_id=db_user.id,
        state_data=data,
    )

    # Calculate subscription price
    price_kopeks, price_breakdown = await _calculate_simple_subscription_price(
        db,
        subscription_params,
        user=db_user,
        resolved_squad_uuid=resolved_squad_uuid,
    )

    user_balance_kopeks = getattr(db_user, "balance_kopeks", 0)
    can_pay_from_balance = user_balance_kopeks >= price_kopeks
    logger.warning(
        "SIMPLE_SUBSCRIPTION_DEBUG_METHODS | user=%s | balance=%s | base=%s | traffic=%s | devices=%s | servers=%s | discount=%s | total_required=%s | can_pay=%s",
        db_user.id,
        user_balance_kopeks,
        price_breakdown.get("base_price", 0),
        price_breakdown.get("traffic_price", 0),
        price_breakdown.get("devices_price", 0),
        price_breakdown.get("servers_price", 0),
        price_breakdown.get("total_discount", 0),
        price_kopeks,
        can_pay_from_balance,
    )

    # Display available payment methods
    server_label = _get_simple_subscription_server_label(
        texts,
        subscription_params,
        resolved_squad_uuid,
    )
    show_devices = settings.is_devices_selection_enabled()

    period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
    message_lines = [
        texts.t("SIMPLE_SUBSCRIPTION_PAYMENT_TITLE", "💳 <b>Subscription payment</b>"),
        "",
        texts.t("SIMPLE_SUBSCRIPTION_PERIOD", "📅 Period: {period}").format(period=period_text),
    ]

    if show_devices:
        devices_text = texts.t("SIMPLE_SUBSCRIPTION_DEVICES", "📱 Devices: {count}").format(count=subscription_params['device_limit'])
        message_lines.append(devices_text)

    payment_traffic_gb = subscription_params["traffic_limit_gb"]
    if payment_traffic_gb == 0:
        payment_traffic_label = texts.t("TRAFFIC_UNLIMITED_LABEL", "Unlimited")
    else:
        payment_traffic_label = texts.t("TRAFFIC_GB", "{gb} GB").format(gb=payment_traffic_gb)

    message_lines.extend([
        texts.t("SIMPLE_SUBSCRIPTION_TRAFFIC", "📊 Traffic: {traffic}").format(traffic=payment_traffic_label),
        texts.t("SIMPLE_SUBSCRIPTION_SERVER", "🌍 Server: {server}").format(server=server_label),
        "",
        texts.t("SIMPLE_SUBSCRIPTION_COST", "💰 Cost: {price}").format(price=settings.format_price(price_kopeks)),
        "",
        (
            texts.t(
                "SIMPLE_SUBSCRIPTION_PAYMENT_OPTIONS_BALANCE",
                "You can pay for the subscription from your balance or choose another payment method:"
            )
            if can_pay_from_balance
            else texts.t(
                "SIMPLE_SUBSCRIPTION_PAYMENT_OPTIONS_INSUFFICIENT",
                "Choose a suitable payment method:"
            )
        ),
    ])

    message_text = "\n".join(message_lines)
    
    base_keyboard = _get_simple_subscription_payment_keyboard(db_user.language)
    keyboard_rows = []
    
    if can_pay_from_balance:
        keyboard_rows.append([
            types.InlineKeyboardButton(
                text=texts.t("PAY_WITH_BALANCE_BUTTON", "✅ Pay from balance"),
                callback_data="simple_subscription_pay_with_balance"
            )
        ])
    
    keyboard_rows.extend(base_keyboard.inline_keyboard)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await callback.answer()


@error_handler
async def handle_simple_subscription_payment_method(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    """Handles payment method selection for simple subscription."""
    texts = get_texts(db_user.language)
    
    data = await state.get_data()
    subscription_params = data.get("subscription_params", {})
    
    if not subscription_params:
        await callback.answer(
            texts.t("SIMPLE_SUBSCRIPTION_DATA_EXPIRED", "❌ Subscription data has expired. Please start over."),
            show_alert=True
        )
        return
    
    # Check if user has an active paid subscription
    from app.database.crud.subscription import get_subscription_by_user_id
    current_subscription = await get_subscription_by_user_id(db, db_user.id)
    
    if current_subscription and not getattr(current_subscription, "is_trial", False) and current_subscription.is_active:
        # User has an active paid subscription - show message
        await callback.answer(
            texts.t(
                "SIMPLE_SUBSCRIPTION_ACTIVE_VIA_MENU",
                "⚠️ You already have an active paid subscription. Please confirm the purchase through the main menu."
            ),
            show_alert=True
        )
        return
    
    payment_method = callback.data.replace("simple_subscription_", "")

    try:
        payment_service = PaymentService(callback.bot)
        purchase_service = SubscriptionPurchaseService()

        resolved_squad_uuid = await _ensure_simple_subscription_squad_uuid(
            db,
            state,
            subscription_params,
            user_id=db_user.id,
            state_data=data,
        )

        # Calculate subscription price
        price_kopeks, _ = await _calculate_simple_subscription_price(
            db,
            subscription_params,
            user=db_user,
            resolved_squad_uuid=resolved_squad_uuid,
        )

        if payment_method == "stars":
            # Payment via Telegram Stars
            order = await purchase_service.create_subscription_order(
                db=db,
                user_id=db_user.id,
                period_days=subscription_params["period_days"],
                device_limit=subscription_params["device_limit"],
                traffic_limit_gb=subscription_params["traffic_limit_gb"],
                squad_uuid=resolved_squad_uuid,
                payment_method="telegram_stars",
                total_price_kopeks=price_kopeks,
            )

            if not order:
                await callback.answer(
                    texts.t("SIMPLE_SUBSCRIPTION_ORDER_ERROR", "❌ Failed to prepare order. Please try again later."),
                    show_alert=True
                )
                return

            stars_count = settings.rubles_to_stars(settings.kopeks_to_rubles(price_kopeks))

            stars_traffic_gb = subscription_params["traffic_limit_gb"]
            if stars_traffic_gb == 0:
                stars_traffic_label = texts.t("TRAFFIC_UNLIMITED_LABEL", "Unlimited")
            else:
                stars_traffic_label = texts.t("TRAFFIC_GB", "{gb} GB").format(gb=stars_traffic_gb)

            period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
            invoice_title = texts.t("SIMPLE_SUBSCRIPTION_INVOICE_TITLE", "Subscription for {period}").format(period=period_text)
            invoice_description = texts.t(
                "SIMPLE_SUBSCRIPTION_INVOICE_DESCRIPTION",
                "Simple subscription purchase\nPeriod: {period}\nDevices: {devices}\nTraffic: {traffic}"
            ).format(
                period=period_text,
                devices=subscription_params['device_limit'],
                traffic=stars_traffic_label
            )

            await callback.bot.send_invoice(
                chat_id=callback.from_user.id,
                title=invoice_title,
                description=invoice_description,
                payload=(
                    f"simple_sub_{db_user.id}_{order.id}_{subscription_params['period_days']}"
                ),
                provider_token="",  # Empty token for Telegram Stars
                currency="XTR",  # Telegram Stars
                prices=[types.LabeledPrice(label=texts.t("SUBSCRIPTION_LABEL", "Subscription"), amount=stars_count)]
            )
            
            await state.clear()
            await callback.answer()
            
        elif payment_method in ["yookassa", "yookassa_sbp"]:
            # Payment via YooKassa
            if not settings.is_yookassa_enabled():
                await callback.answer(
                    texts.t("YOOKASSA_DISABLED", "❌ Payment via YooKassa is temporarily unavailable"),
                    show_alert=True
                )
                return
            
            if payment_method == "yookassa_sbp" and not settings.YOOKASSA_SBP_ENABLED:
                await callback.answer(
                    texts.t("YOOKASSA_SBP_DISABLED", "❌ Payment via SBP is temporarily unavailable"),
                    show_alert=True
                )
                return
            
            # Create subscription order
            order = await purchase_service.create_subscription_order(
                db=db,
                user_id=db_user.id,
                period_days=subscription_params["period_days"],
                device_limit=subscription_params["device_limit"],
                traffic_limit_gb=subscription_params["traffic_limit_gb"],
                squad_uuid=resolved_squad_uuid,
                payment_method="yookassa_sbp" if payment_method == "yookassa_sbp" else "yookassa",
                total_price_kopeks=price_kopeks
            )
            
            if not order:
                await callback.answer(
                    texts.t("SIMPLE_SUBSCRIPTION_ORDER_CREATION_ERROR", "❌ Error creating order"),
                    show_alert=True
                )
                return
            
            # Create payment via YooKassa
            period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
            payment_description = texts.t("SIMPLE_SUBSCRIPTION_PAYMENT_DESCRIPTION", "Subscription payment for {period}").format(period=period_text)
            if payment_method == "yookassa_sbp":
                payment_result = await payment_service.create_yookassa_sbp_payment(
                    db=db,
                    user_id=db_user.id,
                    amount_kopeks=price_kopeks,
                    description=payment_description,
                    receipt_email=db_user.email if hasattr(db_user, 'email') and db_user.email else None,
                    receipt_phone=db_user.phone if hasattr(db_user, 'phone') and db_user.phone else None,
                    metadata={
                        "user_telegram_id": str(db_user.telegram_id),
                        "user_username": db_user.username or "",
                        "order_id": str(order.id),
                        "subscription_period": str(subscription_params["period_days"]),
                        "payment_purpose": "simple_subscription_purchase"
                    }
                )
            else:
                payment_result = await payment_service.create_yookassa_payment(
                    db=db,
                    user_id=db_user.id,
                    amount_kopeks=price_kopeks,
                    description=payment_description,
                    receipt_email=db_user.email if hasattr(db_user, 'email') and db_user.email else None,
                    receipt_phone=db_user.phone if hasattr(db_user, 'phone') and db_user.phone else None,
                    metadata={
                        "user_telegram_id": str(db_user.telegram_id),
                        "user_username": db_user.username or "",
                        "order_id": str(order.id),
                        "subscription_period": str(subscription_params["period_days"]),
                        "payment_purpose": "simple_subscription_purchase"
                    }
                )
            
            if not payment_result:
                await callback.answer(
                    texts.t("SIMPLE_SUBSCRIPTION_PAYMENT_CREATION_ERROR", "❌ Error creating payment"),
                    show_alert=True
                )
                return
            
            # Send QR code and/or payment link
            confirmation_url = payment_result.get("confirmation_url")
            qr_confirmation_data = payment_result.get("qr_confirmation_data")
            
            if not confirmation_url and not qr_confirmation_data:
                await callback.answer(
                    texts.t("SIMPLE_SUBSCRIPTION_PAYMENT_DATA_ERROR", "❌ Error getting payment data"),
                    show_alert=True
                )
                return
            
            # Prepare QR code for insertion into main message
            qr_photo = None
            if qr_confirmation_data or confirmation_url:
                try:
                    # Import necessary modules for QR code generation
                    import base64
                    from io import BytesIO
                    import qrcode
                    from aiogram.types import BufferedInputFile
                    
                    # Use qr_confirmation_data if available, otherwise confirmation_url
                    qr_data = qr_confirmation_data if qr_confirmation_data else confirmation_url
                    
                    # Create QR code from received data
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(qr_data)
                    qr.make(fit=True)
                    
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    # Save image to bytes
                    img_bytes = BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    
                    qr_photo = BufferedInputFile(img_bytes.getvalue(), filename="qrcode.png")
                except ImportError:
                    logger.warning("qrcode library not installed, QR code will not be generated")
                except Exception as e:
                    logger.error("Error generating QR code: %s", e)
            
            # Create keyboard with buttons for payment link and status check
            keyboard_buttons = []
            
            # Add payment button if link is available
            if confirmation_url:
                keyboard_buttons.append([types.InlineKeyboardButton(text=texts.t("GO_TO_PAYMENT_BUTTON", "🔗 Go to payment"), url=confirmation_url)])
            else:
                # If link is unavailable, offer to pay via payment ID in bank app
                keyboard_buttons.append([types.InlineKeyboardButton(text=texts.t("PAY_IN_BANK_APP_BUTTON", "📱 Pay in bank app"), callback_data="temp_disabled")])
            
            # Add common buttons
            keyboard_buttons.append([types.InlineKeyboardButton(text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"), callback_data=f"check_yookassa_{payment_result['local_payment_id']}")])
            keyboard_buttons.append([types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")])
            
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            # Prepare message text
            show_devices = settings.is_devices_selection_enabled()

            period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
            message_lines = [
                texts.t("SIMPLE_SUBSCRIPTION_YOOKASSA_TITLE", "💳 <b>Subscription payment via YooKassa</b>"),
                "",
                texts.t("SIMPLE_SUBSCRIPTION_PERIOD", "📅 Period: {period}").format(period=period_text),
            ]

            if show_devices:
                devices_text = texts.t("SIMPLE_SUBSCRIPTION_DEVICES", "📱 Devices: {count}").format(count=subscription_params['device_limit'])
                message_lines.append(devices_text)

            yookassa_traffic_gb = subscription_params["traffic_limit_gb"]
            if yookassa_traffic_gb == 0:
                yookassa_traffic_label = texts.t("TRAFFIC_UNLIMITED_LABEL", "Unlimited")
            else:
                yookassa_traffic_label = texts.t("TRAFFIC_GB", "{gb} GB").format(gb=yookassa_traffic_gb)

            message_lines.extend([
                texts.t("SIMPLE_SUBSCRIPTION_TRAFFIC", "📊 Traffic: {traffic}").format(traffic=yookassa_traffic_label),
                texts.t("SIMPLE_SUBSCRIPTION_AMOUNT", "💰 Amount: {amount}").format(amount=settings.format_price(price_kopeks)),
                texts.t("SIMPLE_SUBSCRIPTION_PAYMENT_ID", "🆔 Payment ID: {id}").format(id=payment_result['yookassa_payment_id'][:8] + "..."),
                "",
            ])

            message_text = "\n".join(message_lines)
            
            # Add instructions depending on available payment methods
            if not confirmation_url:
                payment_instructions = texts.t(
                    "SIMPLE_SUBSCRIPTION_YOOKASSA_INSTRUCTIONS_NO_URL",
                    "📱 <b>Payment instructions:</b>\n"
                    "1. Open your bank app\n"
                    "2. Find payment by details or SBP transfer function\n"
                    "3. Enter payment ID: <code>{payment_id}</code>\n"
                    "4. Confirm payment in bank app\n"
                    "5. Funds will be credited automatically\n\n"
                ).format(payment_id=payment_result['yookassa_payment_id'])
                message_text += payment_instructions
            
            yookassa_info = texts.t(
                "SIMPLE_SUBSCRIPTION_YOOKASSA_INFO",
                "🔒 Payment is processed through secure YooKassa system\n"
                "✅ We accept cards: Visa, MasterCard, MIR\n\n"
                "❓ If you have any problems, contact {support}"
            ).format(support=settings.get_support_contact_display_html())
            message_text += yookassa_info
            
            # Send message with instructions and keyboard
            # If QR code exists, send it as media message
            if qr_photo:
                # Use photo sending method with caption
                await callback.message.edit_media(
                    media=types.InputMediaPhoto(
                        media=qr_photo,
                        caption=message_text,
                        parse_mode="HTML"
                    ),
                    reply_markup=keyboard
                )
            else:
                # If QR code is unavailable, send regular text message
                await callback.message.edit_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            
            await state.clear()
            await callback.answer()
            
        elif payment_method == "cryptobot":
            # Payment via CryptoBot
            if not settings.is_cryptobot_enabled():
                await callback.answer(
                    texts.t("CRYPTOBOT_DISABLED", "❌ Payment via CryptoBot is temporarily unavailable"),
                    show_alert=True
                )
                return

            amount_rubles = price_kopeks / 100
            if amount_rubles < 100 or amount_rubles > 100000:
                await callback.answer(
                    texts.t(
                        "CRYPTOBOT_AMOUNT_RANGE_ERROR",
                        "❌ Amount must be between {min} and {max} for CryptoBot payment"
                    ).format(
                        min=settings.format_price(10000),
                        max=settings.format_price(10000000)
                    ),
                    show_alert=True,
                )
                return

            try:
                from app.utils.currency_converter import currency_converter

                usd_rate = await currency_converter.get_usd_to_rub_rate()
            except Exception as rate_error:
                logger.warning("Failed to get USD rate: %s", rate_error)
                usd_rate = 95.0

            amount_usd = round(amount_rubles / usd_rate, 2)
            if amount_usd < 1:
                await callback.answer(
                    texts.t("CRYPTOBOT_MIN_AMOUNT_ERROR", "❌ Minimum amount for CryptoBot payment is approximately 1 USD"),
                    show_alert=True,
                )
                return
            if amount_usd > 1000:
                await callback.answer(
                    texts.t("CRYPTOBOT_MAX_AMOUNT_ERROR", "❌ Maximum amount for CryptoBot payment is 1000 USD"),
                    show_alert=True,
                )
                return

            payment_service = PaymentService(callback.bot)
            crypto_result = await payment_service.create_cryptobot_payment(
                db=db,
                user_id=db_user.id,
                amount_usd=amount_usd,
                asset=settings.CRYPTOBOT_DEFAULT_ASSET,
                description=settings.get_subscription_payment_description(
                    subscription_params["period_days"],
                    price_kopeks,
                ),
                payload=f"simple_subscription_{db_user.id}_{price_kopeks}",
            )

            if not crypto_result:
                await callback.answer(
                    texts.t(
                        "CRYPTOBOT_PAYMENT_ERROR",
                        "❌ Error creating CryptoBot payment. Please try again later or contact support."
                    ),
                    show_alert=True,
                )
                return

            payment_url = (
                crypto_result.get("mini_app_invoice_url")
                or crypto_result.get("bot_invoice_url")
                or crypto_result.get("web_app_invoice_url")
            )

            if not payment_url:
                await callback.answer(
                    texts.t("CRYPTOBOT_PAYMENT_URL_ERROR", "❌ Failed to get payment link. Please contact support."),
                    show_alert=True,
                )
                return

            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t("PAY_CRYPTOBOT_BUTTON", "🪙 Pay via CryptoBot"),
                            url=payment_url,
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                            callback_data=f"check_simple_cryptobot_{crypto_result['local_payment_id']}",
                        )
                    ],
                    [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")],
                ]
            )

            message_template = texts.t(
                "SIMPLE_SUBSCRIPTION_CRYPTOBOT_INSTRUCTIONS",
                "🪙 <b>Payment via CryptoBot</b>\n\n"
                "💰 Amount to pay: {amount_rubles}\n"
                "💵 In dollars: {amount_usd} USD\n"
                "🪙 Asset: {asset}\n"
                "💱 Rate: 1 USD ≈ {rate} {currency}\n"
                "🆔 Payment ID: {payment_id}\n\n"
                "📱 <b>Instructions:</b>\n"
                "1. Click 'Pay via CryptoBot' button\n"
                "2. Select asset and follow prompts\n"
                "3. Confirm transfer\n"
                "4. Funds will be credited automatically\n\n"
                "❓ If you have any problems, contact {support}"
            )
            message_text = message_template.format(
                amount_rubles=settings.format_price(price_kopeks),
                amount_usd=f"{amount_usd:.2f}",
                asset=crypto_result['asset'],
                rate=f"{usd_rate:.2f}",
                currency=settings.format_price(100).split()[-1] if settings.format_price(100) else texts.t("CURRENCY_RUB", "RUB"),
                payment_id=crypto_result['invoice_id'][:8] + "...",
                support=settings.get_support_contact_display_html()
            )

            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )

            await state.clear()
            await callback.answer()
            return

        elif payment_method == "heleket":
            if not settings.is_heleket_enabled():
                await callback.answer(
                    texts.t("HELEKET_DISABLED", "❌ Payment via Heleket is temporarily unavailable"),
                    show_alert=True
                )
                return

            amount_rubles = price_kopeks / 100
            if amount_rubles < 100 or amount_rubles > 100000:
                await callback.answer(
                    texts.t(
                        "HELEKET_AMOUNT_RANGE_ERROR",
                        "❌ Amount must be between {min} and {max} for Heleket payment"
                    ).format(
                        min=settings.format_price(10000),
                        max=settings.format_price(10000000)
                    ),
                    show_alert=True,
                )
                return

            heleket_result = await payment_service.create_heleket_payment(
                db=db,
                user_id=db_user.id,
                amount_kopeks=price_kopeks,
                description=settings.get_subscription_payment_description(
                    subscription_params["period_days"],
                    price_kopeks,
                ),
                language=db_user.language,
            )

            if not heleket_result:
                await callback.answer(
                    texts.t(
                        "HELEKET_PAYMENT_ERROR",
                        "❌ Error creating Heleket payment. Please try again later or contact support."
                    ),
                    show_alert=True,
                )
                return

            payment_url = heleket_result.get("payment_url")
            if not payment_url:
                await callback.answer(
                    texts.t("HELEKET_PAYMENT_URL_ERROR", "❌ Failed to get Heleket payment link. Please contact support."),
                    show_alert=True,
                )
                return

            local_payment_id = heleket_result.get("local_payment_id")
            payer_amount = heleket_result.get("payer_amount")
            payer_currency = heleket_result.get("payer_currency")
            discount_percent = heleket_result.get("discount_percent")

            markup_percent = None
            if discount_percent is not None:
                try:
                    markup_percent = -int(discount_percent)
                except (TypeError, ValueError):
                    markup_percent = None

            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t("PAY_HELEKET_BUTTON", "🪙 Pay via Heleket"),
                            url=payment_url,
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                            callback_data=f"check_simple_heleket_{local_payment_id}",
                        )
                    ],
                    [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")],
                ]
            )

            message_lines = [
                texts.t("SIMPLE_SUBSCRIPTION_HELEKET_TITLE", "🪙 <b>Payment via Heleket</b>"),
                "",
                texts.t("SIMPLE_SUBSCRIPTION_AMOUNT", "💰 Amount: {amount}").format(amount=settings.format_price(price_kopeks)),
            ]

            if payer_amount and payer_currency:
                message_lines.append(
                    texts.t("SIMPLE_SUBSCRIPTION_PAYER_AMOUNT", "🪙 To pay: {amount} {currency}").format(
                        amount=payer_amount,
                        currency=payer_currency
                    )
                )
                try:
                    payer_amount_float = float(payer_amount)
                    if payer_amount_float > 0:
                        rub_per_currency = amount_rubles / payer_amount_float
                        currency_symbol = settings.format_price(100).split()[-1] if settings.format_price(100) else texts.t("CURRENCY_RUB", "RUB")
                        message_lines.append(
                            texts.t("SIMPLE_SUBSCRIPTION_EXCHANGE_RATE", "💱 Rate: 1 {currency} ≈ {rate} {rub}").format(
                                currency=payer_currency,
                                rate=f"{rub_per_currency:.2f}",
                                rub=currency_symbol
                            )
                        )
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

            if markup_percent:
                sign = "+" if markup_percent > 0 else ""
                message_lines.append(
                    texts.t("SIMPLE_SUBSCRIPTION_MARKUP", "📈 Markup: {sign}{percent}%").format(
                        sign=sign,
                        percent=markup_percent
                    )
                )

            instructions_template = texts.t(
                "SIMPLE_SUBSCRIPTION_HELEKET_INSTRUCTIONS",
                "📱 <b>Instructions:</b>\n"
                "1. Click 'Pay via Heleket' button\n"
                "2. Follow prompts on payment page\n"
                "3. Confirm transfer\n"
                "4. Funds will be credited automatically\n\n"
                "❓ If you have any problems, contact {support}"
            )
            message_lines.extend([
                "",
                instructions_template.format(support=settings.get_support_contact_display_html())
            ])

            await callback.message.edit_text(
                "\n".join(message_lines),
                reply_markup=keyboard,
                parse_mode="HTML",
            )

            await state.clear()
            await callback.answer()
            return

        elif payment_method == "mulenpay":
            # Payment via MulenPay
            mulenpay_name = settings.get_mulenpay_display_name()
            if not settings.is_mulenpay_enabled():
                await callback.answer(
                    texts.t("MULENPAY_DISABLED", "❌ Payment via {name} is temporarily unavailable").format(name=mulenpay_name),
                    show_alert=True,
                )
                return

            if price_kopeks < settings.MULENPAY_MIN_AMOUNT_KOPEKS or price_kopeks > settings.MULENPAY_MAX_AMOUNT_KOPEKS:
                await callback.answer(
                    texts.t(
                        "MULENPAY_AMOUNT_RANGE_ERROR",
                        "❌ Amount for Mulen Pay must be between {min_amount} and {max_amount}"
                    ).format(
                        min_amount=settings.format_price(settings.MULENPAY_MIN_AMOUNT_KOPEKS),
                        max_amount=settings.format_price(settings.MULENPAY_MAX_AMOUNT_KOPEKS),
                    ),
                    show_alert=True,
                )
                return

            payment_service = PaymentService(callback.bot)
            mulen_result = await payment_service.create_mulenpay_payment(
                db=db,
                user_id=db_user.id,
                amount_kopeks=price_kopeks,
                description=settings.get_subscription_payment_description(
                    subscription_params["period_days"],
                    price_kopeks,
                ),
                language=db_user.language,
            )

            if not mulen_result or not mulen_result.get("payment_url"):
                await callback.answer(
                    texts.t(
                        "MULENPAY_PAYMENT_ERROR",
                        "❌ Error creating Mulen Pay payment. Please try again later or contact support.",
                    ),
                    show_alert=True,
                )
                return

            payment_url = mulen_result["payment_url"]
            local_payment_id = mulen_result.get("local_payment_id")
            payment_id_display = mulen_result.get("mulen_payment_id") or local_payment_id

            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t("MULENPAY_PAY_BUTTON", "💳 Pay via Mulen Pay"),
                            url=payment_url,
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                            callback_data=f"check_simple_mulenpay_{local_payment_id}",
                        )
                    ],
                    [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")],
                ]
            )

            message_template = texts.t(
                "MULENPAY_PAYMENT_INSTRUCTIONS",
                (
                    "💳 <b>Payment via {mulenpay_name_html}</b>\n\n"
                    "💰 Amount: {amount}\n"
                    "🆔 Payment ID: {payment_id}\n\n"
                    "📱 <b>Instructions:</b>\n"
                    "1. Click 'Pay via {mulenpay_name}' button\n"
                    "2. Follow payment system prompts\n"
                    "3. Confirm transfer\n"
                    "4. Funds will be credited automatically\n\n"
                    "❓ If you have any problems, contact {support}"
                ),
            )

            await callback.message.edit_text(
                message_template.format(
                    mulenpay_name=mulenpay_name,
                    mulenpay_name_html=settings.get_mulenpay_display_name_html(),
                    amount=settings.format_price(price_kopeks),
                    payment_id=payment_id_display,
                    support=settings.get_support_contact_display_html(),
                ),
                reply_markup=keyboard,
                parse_mode="HTML",
            )

            await state.clear()
            await callback.answer()
            return
            
        elif payment_method == "pal24":
            # Payment via PayPalych
            if not settings.is_pal24_enabled():
                await callback.answer(
                    texts.t("PAL24_DISABLED", "❌ Payment via PayPalych is temporarily unavailable"),
                    show_alert=True
                )
                return

            payment_service = PaymentService(callback.bot)
            pal24_result = await payment_service.create_pal24_payment(
                db=db,
                user_id=db_user.id,
                amount_kopeks=price_kopeks,
                description=settings.get_subscription_payment_description(
                    subscription_params["period_days"],
                    price_kopeks,
                ),
                language=db_user.language,
            )

            if not pal24_result:
                await callback.answer(
                    texts.t(
                        "PAL24_PAYMENT_ERROR",
                        "❌ Error creating PayPalych payment. Please try again later or contact support.",
                    ),
                    show_alert=True,
                )
                return

            sbp_url = pal24_result.get("sbp_url") or pal24_result.get("transfer_url")
            card_url = pal24_result.get("card_url")
            fallback_url = pal24_result.get("link_page_url") or pal24_result.get("link_url")

            if not (sbp_url or card_url or fallback_url):
                await callback.answer(
                    texts.t(
                        "PAL24_PAYMENT_ERROR",
                        "❌ Error creating PayPalych payment. Please try again later or contact support.",
                    ),
                    show_alert=True,
                )
                return

            if not sbp_url:
                sbp_url = fallback_url

            bill_id = pal24_result.get("bill_id")
            local_payment_id = pal24_result.get("local_payment_id")

            pay_buttons: list[list[types.InlineKeyboardButton]] = []
            steps: list[str] = []
            step_counter = 1

            default_sbp_text = texts.t(
                "PAL24_SBP_PAY_BUTTON",
                "🏦 Pay via PayPalych (SBP)",
            )
            sbp_button_text = settings.get_pal24_sbp_button_text(default_sbp_text)

            if sbp_url and settings.is_pal24_sbp_button_visible():
                pay_buttons.append(
                    [
                        types.InlineKeyboardButton(
                            text=sbp_button_text,
                            url=sbp_url,
                        )
                    ]
                )
                steps.append(
                    texts.t(
                        "PAL24_INSTRUCTION_BUTTON",
                        "{step}. Click button «{button}»",
                    ).format(step=step_counter, button=html.escape(sbp_button_text))
                )
                step_counter += 1

            default_card_text = texts.t(
                "PAL24_CARD_PAY_BUTTON",
                "💳 Pay with bank card (PayPalych)",
            )
            card_button_text = settings.get_pal24_card_button_text(default_card_text)

            if card_url and card_url != sbp_url and settings.is_pal24_card_button_visible():
                pay_buttons.append(
                    [
                        types.InlineKeyboardButton(
                            text=card_button_text,
                            url=card_url,
                        )
                    ]
                )
                steps.append(
                    texts.t(
                        "PAL24_INSTRUCTION_BUTTON",
                        "{step}. Click button «{button}»",
                    ).format(step=step_counter, button=html.escape(card_button_text))
                )
                step_counter += 1

            if not pay_buttons and fallback_url and settings.is_pal24_sbp_button_visible():
                pay_buttons.append(
                    [
                        types.InlineKeyboardButton(
                            text=sbp_button_text,
                            url=fallback_url,
                        )
                    ]
                )
                steps.append(
                    texts.t(
                        "PAL24_INSTRUCTION_BUTTON",
                        "{step}. Click button «{button}»",
                    ).format(step=step_counter, button=html.escape(sbp_button_text))
                )
                step_counter += 1

            follow_template = texts.t(
                "PAL24_INSTRUCTION_FOLLOW",
                "{step}. Follow payment system prompts",
            )
            steps.append(follow_template.format(step=step_counter))
            step_counter += 1

            confirm_template = texts.t(
                "PAL24_INSTRUCTION_CONFIRM",
                "{step}. Confirm transfer",
            )
            steps.append(confirm_template.format(step=step_counter))
            step_counter += 1

            success_template = texts.t(
                "PAL24_INSTRUCTION_COMPLETE",
                "{step}. Funds will be credited automatically",
            )
            steps.append(success_template.format(step=step_counter))

            message_template = texts.t(
                "PAL24_PAYMENT_INSTRUCTIONS",
                (
                    "🏦 <b>Payment via PayPalych</b>\n\n"
                    "💰 Amount: {amount}\n"
                    "🆔 Bill ID: {bill_id}\n\n"
                    "📱 <b>Instructions:</b>\n{steps}\n\n"
                    "❓ If you have any problems, contact {support}"
                ),
            )

            keyboard_rows = pay_buttons + [
                [
                    types.InlineKeyboardButton(
                        text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                        callback_data=f"check_simple_pal24_{local_payment_id}",
                    )
                ],
                [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")],
            ]

            keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

            message_text = message_template.format(
                amount=settings.format_price(price_kopeks),
                bill_id=bill_id,
                steps="\n".join(steps),
                support=settings.get_support_contact_display_html(),
            )

            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )

            await state.clear()
            await callback.answer()
            return

        elif payment_method == "wata":
            # Payment via WATA
            if not settings.is_wata_enabled():
                await callback.answer(
                    texts.t("WATA_DISABLED", "❌ Payment via WATA is temporarily unavailable"),
                    show_alert=True
                )
                return
            if price_kopeks < settings.WATA_MIN_AMOUNT_KOPEKS or price_kopeks > settings.WATA_MAX_AMOUNT_KOPEKS:
                await callback.answer(
                    texts.t(
                        "WATA_AMOUNT_RANGE_ERROR",
                        "❌ Amount for WATA must be between {min_amount} and {max_amount}"
                    ).format(
                        min_amount=settings.format_price(settings.WATA_MIN_AMOUNT_KOPEKS),
                        max_amount=settings.format_price(settings.WATA_MAX_AMOUNT_KOPEKS),
                    ),
                    show_alert=True,
                )
                return

            payment_service = PaymentService(callback.bot)
            try:
                wata_result = await payment_service.create_wata_payment(
                    db=db,
                    user_id=db_user.id,
                    amount_kopeks=price_kopeks,
                    description=settings.get_subscription_payment_description(
                        subscription_params["period_days"],
                        price_kopeks,
                    ),
                    language=db_user.language,
                )
            except Exception as error:
                logger.error("Error creating WATA payment: %s", error)
                wata_result = None

            if not wata_result or not wata_result.get("payment_url"):
                await callback.answer(
                    texts.t(
                        "WATA_PAYMENT_ERROR",
                        "❌ Error creating WATA payment. Please try again later or contact support.",
                    ),
                    show_alert=True,
                )
                return

            payment_url = wata_result["payment_url"]
            payment_link_id = wata_result.get("payment_link_id")
            local_payment_id = wata_result.get("local_payment_id")

            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t("WATA_PAY_BUTTON", "💳 Pay via WATA"),
                            url=payment_url,
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                            callback_data=f"check_simple_wata_{local_payment_id}",
                        )
                    ],
                    [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")],
                ]
            )

            message_template = texts.t(
                "WATA_PAYMENT_INSTRUCTIONS",
                (
                    "💳 <b>Payment via WATA</b>\n\n"
                    "💰 Amount: {amount}\n"
                    "🆔 Payment ID: {payment_id}\n\n"
                    "📱 <b>Instructions:</b>\n"
                    "1. Click 'Pay via WATA' button\n"
                    "2. Follow payment system prompts\n"
                    "3. Confirm transfer\n"
                    "4. Funds will be credited automatically\n\n"
                    "❓ If you have any problems, contact {support}"
                ),
            )

            await callback.message.edit_text(
                message_template.format(
                    amount=settings.format_price(price_kopeks),
                    payment_id=payment_link_id,
                    support=settings.get_support_contact_display_html(),
                ),
                reply_markup=keyboard,
                parse_mode="HTML",
            )

            await state.clear()
            await callback.answer()
            return
            
        else:
            await callback.answer(
                texts.t("SIMPLE_SUBSCRIPTION_UNKNOWN_PAYMENT_METHOD", "❌ Unknown payment method"),
                show_alert=True
            )
            
    except Exception as e:
        logger.error("Error processing simple subscription payment method: %s", e)
        await callback.answer(
            texts.t(
                "SIMPLE_SUBSCRIPTION_PAYMENT_PROCESSING_ERROR",
                "❌ Error processing request. Please try again later or contact support."
            ),
            show_alert=True
        )
        await state.clear()


@error_handler
async def check_simple_pal24_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession,
):
    try:
        local_payment_id = int(callback.data.rsplit('_', 1)[-1])
        payment_service = PaymentService(callback.bot)
        status_info = await payment_service.get_pal24_payment_status(db, local_payment_id)

        if not status_info:
            db_user = getattr(callback, "db_user", None)
            texts = get_texts(db_user.language if db_user else settings.DEFAULT_LANGUAGE)
            await callback.answer(
                texts.t("PAYMENT_NOT_FOUND", "❌ Payment not found"),
                show_alert=True
            )
            return

        payment = status_info["payment"]
        db_user = getattr(callback, "db_user", None)
        texts = get_texts(db_user.language if db_user else settings.DEFAULT_LANGUAGE)

        status_labels = {
            "NEW": ("⏳", texts.t("PAYMENT_STATUS_PENDING", "Pending payment")),
            "PROCESS": ("⌛", texts.t("PAYMENT_STATUS_PROCESSING", "Processing")),
            "SUCCESS": ("✅", texts.t("PAYMENT_STATUS_PAID", "Paid")),
            "FAIL": ("❌", texts.t("PAYMENT_STATUS_CANCELED", "Canceled")),
            "UNDERPAID": ("⚠️", texts.t("PAYMENT_STATUS_UNDERPAID", "Underpaid")),
            "OVERPAID": ("⚠️", texts.t("PAYMENT_STATUS_OVERPAID", "Overpaid")),
        }

        emoji, status_text = status_labels.get(payment.status, ("❓", texts.t("PAYMENT_STATUS_UNKNOWN", "Unknown")))

        metadata = payment.metadata_json or {}
        links_meta = metadata.get("links") if isinstance(metadata, dict) else {}
        if not isinstance(links_meta, dict):
            links_meta = {}

        links_info = status_info.get("links") or {}
        sbp_link = (
            links_info.get("sbp")
            or links_meta.get("sbp")
            or status_info.get("sbp_url")
            or payment.link_url
        )
        card_link = (
            links_info.get("card")
            or links_meta.get("card")
            or status_info.get("card_url")
        )
        if not card_link and payment.link_page_url and payment.link_page_url != sbp_link:
            card_link = payment.link_page_url

        message_lines = [
            texts.t("PAL24_PAYMENT_STATUS_TITLE", "🏦 PayPalych payment status:"),
            "",
            texts.t("PAL24_BILL_ID", "🆔 Bill ID: {id}").format(id=payment.bill_id),
            texts.t("PAYMENT_AMOUNT", "💰 Amount: {amount}").format(amount=settings.format_price(payment.amount_kopeks)),
            texts.t("PAYMENT_STATUS", "📊 Status: {emoji} {status}").format(emoji=emoji, status=status_text),
            texts.t("PAYMENT_CREATED", "📅 Created: {date}").format(date=payment.created_at.strftime('%d.%m.%Y %H:%M')),
        ]

        if payment.is_paid:
            message_lines += ["", texts.t("PAYMENT_SUCCESS_COMPLETE", "✅ Payment successfully completed! Funds have been credited.")]
        elif payment.status in {"NEW", "PROCESS"}:
            message_lines += [
                "",
                texts.t("PAYMENT_NOT_COMPLETE", "⏳ Payment not yet completed. Pay the bill and check status later."),
            ]
            if sbp_link:
                message_lines += ["", texts.t("PAYMENT_SBP_LINK", "🏦 SBP: {link}").format(link=sbp_link)]
            if card_link and card_link != sbp_link:
                message_lines.append(texts.t("PAYMENT_CARD_LINK", "💳 Card: {link}").format(link=card_link))
        elif payment.status in {"FAIL", "UNDERPAID", "OVERPAID"}:
            message_lines += [
                "",
                texts.t("PAYMENT_NOT_COMPLETE_CORRECTLY", "❌ Payment not completed correctly. Contact {support}").format(
                    support=settings.get_support_contact_display()
                ),
            ]

        pay_rows: list[list[types.InlineKeyboardButton]] = []

        if not payment.is_paid and payment.status in {"NEW", "PROCESS"}:
            default_sbp_text = texts.t(
                "PAL24_SBP_PAY_BUTTON",
                "🏦 Pay via PayPalych (SBP)",
            )
            sbp_button_text = settings.get_pal24_sbp_button_text(default_sbp_text)

            if sbp_link and settings.is_pal24_sbp_button_visible():
                pay_rows.append(
                    [
                        types.InlineKeyboardButton(
                            text=sbp_button_text,
                            url=sbp_link,
                        )
                    ]
                )

            default_card_text = texts.t(
                "PAL24_CARD_PAY_BUTTON",
                "💳 Pay with bank card (PayPalych)",
            )
            card_button_text = settings.get_pal24_card_button_text(default_card_text)

            if card_link and settings.is_pal24_card_button_visible():
                if not pay_rows or pay_rows[-1][0].url != card_link:
                    pay_rows.append(
                        [
                            types.InlineKeyboardButton(
                                text=card_button_text,
                                url=card_link,
                            )
                        ]
                    )

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=pay_rows
            + [
                [
                    types.InlineKeyboardButton(
                        text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                        callback_data=f"check_simple_pal24_{local_payment_id}",
                    )
                ],
                [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")],
            ]
        )

        await callback.answer()
        try:
            await callback.message.edit_text(
                "\n".join(message_lines),
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except TelegramBadRequest as error:
            if "message is not modified" in str(error).lower():
                await callback.answer(texts.t("CHECK_STATUS_NO_CHANGES", "Status has not changed"))
            else:
                raise

    except Exception as error:
        logger.error("Error checking PayPalych payment status for simple subscription: %s", error)
        db_user = getattr(callback, "db_user", None)
        texts = get_texts(db_user.language if db_user else settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("PAYMENT_STATUS_CHECK_ERROR", "❌ Error checking status"),
            show_alert=True
        )


@error_handler
async def check_simple_mulenpay_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession,
):
    try:
        local_payment_id = int(callback.data.rsplit('_', 1)[-1])
    except (ValueError, IndexError):
        texts = get_texts(settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("PAYMENT_ID_INVALID", "❌ Invalid payment identifier"),
            show_alert=True
        )
        return

    payment_service = PaymentService(callback.bot)
    status_info = await payment_service.get_mulenpay_payment_status(db, local_payment_id)

    if not status_info:
        texts = get_texts(settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("PAYMENT_NOT_FOUND", "❌ Payment not found"),
            show_alert=True
        )
        return

    payment = status_info["payment"]

    user_language = settings.DEFAULT_LANGUAGE
    try:
        from app.services.payment_service import get_user_by_id as fetch_user_by_id

        user = await fetch_user_by_id(db, payment.user_id)
        if user and getattr(user, "language", None):
            user_language = user.language
    except Exception as error:
        logger.debug("Failed to get user for MulenPay status: %s", error)

    texts = get_texts(user_language)
    status_labels = {
        "created": ("⏳", texts.t("PAYMENT_STATUS_PENDING", "Pending payment")),
        "processing": ("⌛", texts.t("PAYMENT_STATUS_PROCESSING", "Processing")),
        "success": ("✅", texts.t("PAYMENT_STATUS_PAID", "Paid")),
        "canceled": ("❌", texts.t("PAYMENT_STATUS_CANCELED", "Canceled")),
        "error": ("⚠️", texts.t("PAYMENT_STATUS_ERROR", "Error")),
        "hold": ("🔒", texts.t("PAYMENT_STATUS_HOLD", "Hold")),
        "unknown": ("❓", texts.t("PAYMENT_STATUS_UNKNOWN", "Unknown")),
    }

    emoji, status_text = status_labels.get(payment.status, ("❓", texts.t("PAYMENT_STATUS_UNKNOWN", "Unknown")))

    message_lines = [
        texts.t("MULENPAY_PAYMENT_STATUS_TITLE", "💳 Mulen Pay payment status:"),
        "",
        texts.t("PAYMENT_ID", "🆔 ID: {id}").format(id=payment.mulen_payment_id or payment.id),
        texts.t("PAYMENT_AMOUNT", "💰 Amount: {amount}").format(amount=settings.format_price(payment.amount_kopeks)),
        texts.t("PAYMENT_STATUS", "📊 Status: {emoji} {status}").format(emoji=emoji, status=status_text),
        texts.t("PAYMENT_CREATED", "📅 Created: {date}").format(date=payment.created_at.strftime('%d.%m.%Y %H:%M') if payment.created_at else '—'),
    ]

    if payment.is_paid:
        message_lines.append("\n" + texts.t("PAYMENT_SUCCESS_COMPLETE", "✅ Payment successfully completed! Funds have been credited."))
    elif payment.status in {"created", "processing"}:
        message_lines.append("\n" + texts.t("PAYMENT_NOT_COMPLETE_YET", "⏳ Payment not yet completed. Complete payment and check status later."))

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                    callback_data=f"check_simple_mulenpay_{local_payment_id}",
                )
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")],
        ]
    )

    await callback.answer()
    await callback.message.edit_text(
        "\n".join(message_lines),
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@error_handler
async def check_simple_cryptobot_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession,
):
    try:
        local_payment_id = int(callback.data.rsplit('_', 1)[-1])
    except (ValueError, IndexError):
        texts = get_texts(settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("PAYMENT_ID_INVALID", "❌ Invalid payment identifier"),
            show_alert=True
        )
        return

    from app.database.crud.cryptobot import get_cryptobot_payment_by_id

    payment = await get_cryptobot_payment_by_id(db, local_payment_id)
    if not payment:
        texts = get_texts(settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("PAYMENT_NOT_FOUND", "❌ Payment not found"),
            show_alert=True
        )
        return

    language = settings.DEFAULT_LANGUAGE
    try:
        from app.services.payment_service import get_user_by_id as fetch_user_by_id

        user = await fetch_user_by_id(db, payment.user_id)
        if user and getattr(user, "language", None):
            language = user.language
    except Exception as error:
        logger.debug("Failed to get user for CryptoBot status: %s", error)

    texts = get_texts(language)
    status_labels = {
        "active": ("⏳", texts.t("PAYMENT_STATUS_PENDING", "Pending payment")),
        "paid": ("✅", texts.t("PAYMENT_STATUS_PAID", "Paid")),
        "expired": ("❌", texts.t("PAYMENT_STATUS_EXPIRED", "Expired")),
    }
    emoji, status_text = status_labels.get(payment.status, ("❓", texts.t("PAYMENT_STATUS_UNKNOWN", "Unknown")))

    message_lines = [
        texts.t("CRYPTOBOT_PAYMENT_STATUS_TITLE", "🪙 <b>CryptoBot payment status</b>"),
        "",
        texts.t("PAYMENT_ID", "🆔 ID: {id}").format(id=payment.invoice_id),
        texts.t("CRYPTOBOT_PAYMENT_AMOUNT", "💰 Amount: {amount} {asset}").format(amount=payment.amount, asset=payment.asset),
        texts.t("PAYMENT_STATUS", "📊 Status: {emoji} {status}").format(emoji=emoji, status=status_text),
        texts.t("PAYMENT_CREATED", "📅 Created: {date}").format(date=payment.created_at.strftime('%d.%m.%Y %H:%M') if payment.created_at else '—'),
    ]

    if payment.status == "paid":
        message_lines.append("\n" + texts.t("PAYMENT_CONFIRMED", "✅ Payment confirmed. Funds have been credited."))
    elif payment.status == "active":
        message_lines.append("\n" + texts.t("PAYMENT_AWAITING_CONFIRMATION", "⏳ Payment still awaiting confirmation. Pay the bill and check status later."))

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                    callback_data=f"check_simple_cryptobot_{local_payment_id}",
                )
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")],
        ]
    )

    await callback.answer()
    await callback.message.edit_text(
        "\n".join(message_lines),
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@error_handler
async def check_simple_heleket_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession,
):
    try:
        local_payment_id = int(callback.data.rsplit('_', 1)[-1])
    except (ValueError, IndexError):
        texts = get_texts(settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("PAYMENT_ID_INVALID", "❌ Invalid payment identifier"),
            show_alert=True
        )
        return

    from app.database.crud.heleket import get_heleket_payment_by_id

    payment = await get_heleket_payment_by_id(db, local_payment_id)
    if not payment:
        texts = get_texts(settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("PAYMENT_NOT_FOUND", "❌ Payment not found"),
            show_alert=True
        )
        return

    language = settings.DEFAULT_LANGUAGE
    try:
        from app.services.payment_service import get_user_by_id as fetch_user_by_id

        user = await fetch_user_by_id(db, payment.user_id)
        if user and getattr(user, "language", None):
            language = user.language
    except Exception as error:
        logger.debug("Failed to get user for Heleket status: %s", error)

    texts = get_texts(language)
    status_labels = {
        "check": ("⏳", texts.t("PAYMENT_STATUS_PENDING", "Pending payment")),
        "paid": ("✅", texts.t("PAYMENT_STATUS_PAID", "Paid")),
        "paid_over": ("✅", texts.t("PAYMENT_STATUS_PAID_OVER", "Paid (overpaid)")),
        "wrong_amount": ("⚠️", texts.t("PAYMENT_STATUS_WRONG_AMOUNT", "Wrong amount")),
        "cancel": ("❌", texts.t("PAYMENT_STATUS_CANCELED", "Canceled")),
        "fail": ("❌", texts.t("PAYMENT_STATUS_ERROR", "Error")),
        "process": ("⌛", texts.t("PAYMENT_STATUS_PROCESSING", "Processing")),
        "confirm_check": ("⌛", texts.t("PAYMENT_STATUS_AWAITING_CONFIRMATION", "Awaiting confirmation")),
    }

    emoji, status_text = status_labels.get(payment.status, ("❓", texts.t("PAYMENT_STATUS_UNKNOWN", "Unknown")))

    message_lines = [
        texts.t("HELEKET_PAYMENT_STATUS_TITLE", "🪙 Heleket payment status:"),
        "",
        texts.t("PAYMENT_UUID", "🆔 UUID: {uuid}").format(uuid=payment.uuid[:8] + "..."),
        texts.t("PAYMENT_AMOUNT", "💰 Amount: {amount}").format(amount=settings.format_price(payment.amount_kopeks)),
        texts.t("PAYMENT_STATUS", "📊 Status: {emoji} {status}").format(emoji=emoji, status=status_text),
        texts.t("PAYMENT_CREATED", "📅 Created: {date}").format(date=payment.created_at.strftime('%d.%m.%Y %H:%M') if payment.created_at else '—'),
    ]

    if payment.payer_amount and payment.payer_currency:
        message_lines.append(
            texts.t("HELEKET_PAYER_AMOUNT", "🪙 Payment: {amount} {currency}").format(
                amount=payment.payer_amount,
                currency=payment.payer_currency
            )
        )

    if payment.is_paid:
        message_lines.append("\n" + texts.t("PAYMENT_SUCCESS_COMPLETE", "✅ Payment successfully completed! Funds have been credited."))
    elif payment.status in {"check", "process", "confirm_check"}:
        message_lines.append("\n" + texts.t("PAYMENT_STILL_PROCESSING", "⏳ Payment is still processing. Complete payment and check status later."))
        if payment.payment_url:
            message_lines.append("\n" + texts.t("PAYMENT_URL", "🔗 Payment link: {url}").format(url=payment.payment_url))
    elif payment.status in {"fail", "cancel", "wrong_amount"}:
        message_lines.append(
            "\n" + texts.t("PAYMENT_NOT_COMPLETE_CORRECTLY", "❌ Payment not completed correctly. Contact {support}").format(
                support=settings.get_support_contact_display()
            )
        )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                    callback_data=f"check_simple_heleket_{local_payment_id}",
                )
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")],
        ]
    )

    await callback.answer()
    await callback.message.edit_text(
        "\n".join(message_lines),
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@error_handler
async def check_simple_wata_payment_status(
    callback: types.CallbackQuery,
    db: AsyncSession,
):
    try:
        local_payment_id = int(callback.data.rsplit('_', 1)[-1])
    except (ValueError, IndexError):
        texts = get_texts(settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("PAYMENT_ID_INVALID", "❌ Invalid payment identifier"),
            show_alert=True
        )
        return

    payment_service = PaymentService(callback.bot)
    status_info = await payment_service.get_wata_payment_status(db, local_payment_id)

    if not status_info:
        texts = get_texts(settings.DEFAULT_LANGUAGE)
        await callback.answer(
            texts.t("PAYMENT_NOT_FOUND", "❌ Payment not found"),
            show_alert=True
        )
        return

    payment = status_info["payment"]
    texts = get_texts(settings.DEFAULT_LANGUAGE)

    status_labels = {
        "Opened": ("⏳", texts.t("WATA_STATUS_OPENED", "Pending payment")),
        "Closed": ("⌛", texts.t("WATA_STATUS_CLOSED", "Processing")),
        "Paid": ("✅", texts.t("WATA_STATUS_PAID", "Paid")),
        "Declined": ("❌", texts.t("WATA_STATUS_DECLINED", "Declined")),
    }
    emoji, status_text = status_labels.get(payment.status, ("❓", texts.t("WATA_STATUS_UNKNOWN", "Unknown")))

    message_lines = [
        texts.t("WATA_STATUS_TITLE", "💳 <b>WATA payment status</b>"),
        "",
        texts.t("PAYMENT_ID", "🆔 ID: {id}").format(id=payment.payment_link_id),
        texts.t("PAYMENT_AMOUNT", "💰 Amount: {amount}").format(amount=settings.format_price(payment.amount_kopeks)),
        texts.t("PAYMENT_STATUS", "📊 Status: {emoji} {status}").format(emoji=emoji, status=status_text),
        texts.t("PAYMENT_CREATED", "📅 Created: {date}").format(date=payment.created_at.strftime('%d.%m.%Y %H:%M') if payment.created_at else '—'),
    ]

    if payment.is_paid:
        message_lines.append("\n" + texts.t("PAYMENT_SUCCESS_COMPLETE", "✅ Payment successfully completed! Funds have been credited."))
    elif payment.status in {"Opened", "Closed"}:
        message_lines.append("\n" + texts.t("PAYMENT_NOT_COMPLETE_YET", "⏳ Payment not yet completed. Complete payment and check status later."))

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("CHECK_STATUS_BUTTON", "📊 Check status"),
                    callback_data=f"check_simple_wata_{local_payment_id}",
                )
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="subscription_purchase")],
        ]
    )

    await callback.answer()
    await callback.message.edit_text(
        "\n".join(message_lines),
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@error_handler
async def confirm_simple_subscription_purchase(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    """Handles confirmation of simple subscription purchase when user has an active paid subscription."""
    texts = get_texts(db_user.language)
    
    data = await state.get_data()
    subscription_params = data.get("subscription_params", {})
    
    if not subscription_params:
        await callback.answer(
            texts.t("SIMPLE_SUBSCRIPTION_DATA_EXPIRED", "❌ Subscription data has expired. Please start over."),
            show_alert=True
        )
        return

    resolved_squad_uuid = await _ensure_simple_subscription_squad_uuid(
        db,
        state,
        subscription_params,
        user_id=db_user.id,
        state_data=data,
    )

    # Calculate subscription price
    price_kopeks, price_breakdown = await _calculate_simple_subscription_price(
        db,
        subscription_params,
        user=db_user,
        resolved_squad_uuid=resolved_squad_uuid,
    )
    total_required = price_kopeks
    logger.warning(
        "SIMPLE_SUBSCRIPTION_DEBUG_CONFIRM | user=%s | period=%s | base=%s | traffic=%s | devices=%s | servers=%s | discount=%s | total_required=%s | balance=%s",
        db_user.id,
        subscription_params["period_days"],
        price_breakdown.get("base_price", 0),
        price_breakdown.get("traffic_price", 0),
        price_breakdown.get("devices_price", 0),
        price_breakdown.get("servers_price", 0),
        price_breakdown.get("total_discount", 0),
        total_required,
        getattr(db_user, "balance_kopeks", 0),
    )

    # Check user balance
    user_balance_kopeks = getattr(db_user, "balance_kopeks", 0)

    if user_balance_kopeks < total_required:
        await callback.answer(
            texts.t("SIMPLE_SUBSCRIPTION_INSUFFICIENT_BALANCE", "❌ Insufficient balance to pay for subscription"),
            show_alert=True
        )
        return
    
    try:
        # Deduct funds from user balance
        from app.database.crud.user import subtract_user_balance
        period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
        payment_description = texts.t("SIMPLE_SUBSCRIPTION_PAYMENT_DESCRIPTION", "Subscription payment for {period}").format(period=period_text)
        success = await subtract_user_balance(
            db,
            db_user,
            price_kopeks,
            payment_description,
            consume_promo_offer=False,
        )
        
        if not success:
            await callback.answer(
                texts.t("SIMPLE_SUBSCRIPTION_BALANCE_DEDUCTION_ERROR", "❌ Error deducting funds from balance"),
                show_alert=True
            )
            return
        
        # Check if user already has a subscription
        from app.database.crud.subscription import get_subscription_by_user_id, extend_subscription
        
        existing_subscription = await get_subscription_by_user_id(db, db_user.id)
        
        if existing_subscription:
            # If subscription already exists, extend it
            # Save information about current subscription, especially if it's a trial
            was_trial = getattr(existing_subscription, "is_trial", False)
            
            subscription = await extend_subscription(
                db=db,
                subscription=existing_subscription,
                days=subscription_params["period_days"]
            )
            # Update subscription parameters
            subscription.traffic_limit_gb = subscription_params["traffic_limit_gb"]
            subscription.device_limit = subscription_params["device_limit"]
            
            # If current subscription was a trial, and we're updating it
            # need to change subscription status
            if was_trial:
                from app.database.models import SubscriptionStatus
                # Convert subscription from trial to active paid
                subscription.status = SubscriptionStatus.ACTIVE.value
                subscription.is_trial = False
            
            # Set the new selected squad
            if resolved_squad_uuid:
                subscription.connected_squads = [resolved_squad_uuid]
            
            await db.commit()
            await db.refresh(subscription)
        else:
            # If subscription doesn't exist, create a new one
            from app.database.crud.subscription import create_paid_subscription
            subscription = await create_paid_subscription(
                db=db,
                user_id=db_user.id,
                duration_days=subscription_params["period_days"],
                traffic_limit_gb=subscription_params["traffic_limit_gb"],
                device_limit=subscription_params["device_limit"],
                connected_squads=[resolved_squad_uuid] if resolved_squad_uuid else [],
                update_server_counters=True,
            )
        
        if not subscription:
            # Refund to balance in case of error
            from app.services.payment_service import add_user_balance
            period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
            refund_description = texts.t("SIMPLE_SUBSCRIPTION_REFUND_DESCRIPTION", "Refund for failed subscription for {period}").format(period=period_text)
            await add_user_balance(
                db,
                db_user.id,
                price_kopeks,
                refund_description,
            )
            await callback.answer(
                texts.t("SIMPLE_SUBSCRIPTION_CREATION_ERROR", "❌ Error creating subscription. Funds have been refunded to balance."),
                show_alert=True
            )
            return
        
        # Update user balance
        await db.refresh(db_user)

        # Update or create subscription link in RemnaWave
        try:
            from app.services.subscription_service import SubscriptionService
            subscription_service = SubscriptionService()
            remnawave_user = await subscription_service.create_remnawave_user(db, subscription)
            if remnawave_user:
                await db.refresh(subscription)
        except Exception as sync_error:
            logger.error(
                "Error syncing subscription with RemnaWave for user %s: %s",
                db_user.id,
                sync_error,
                exc_info=True
            )
        
        # Send success notification
        server_label = _get_simple_subscription_server_label(
            texts,
            subscription_params,
            resolved_squad_uuid,
        )
        show_devices = settings.is_devices_selection_enabled()

        period_text = texts.t("SUBSCRIPTION_PERIOD_DAYS", "{days} days").format(days=subscription_params['period_days'])
        success_lines = [
            texts.t("SIMPLE_SUBSCRIPTION_ACTIVATED", "✅ <b>Subscription successfully activated!</b>"),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_PERIOD", "📅 Period: {period}").format(period=period_text),
        ]

        if show_devices:
            devices_text = texts.t("SIMPLE_SUBSCRIPTION_DEVICES", "📱 Devices: {count}").format(count=subscription_params['device_limit'])
            success_lines.append(devices_text)

        success_traffic_gb = subscription_params["traffic_limit_gb"]
        if success_traffic_gb == 0:
            success_traffic_label = texts.t("TRAFFIC_UNLIMITED_LABEL", "Unlimited")
        else:
            success_traffic_label = texts.t("TRAFFIC_GB", "{gb} GB").format(gb=success_traffic_gb)

        success_lines.extend([
            texts.t("SIMPLE_SUBSCRIPTION_TRAFFIC", "📊 Traffic: {traffic}").format(traffic=success_traffic_label),
            texts.t("SIMPLE_SUBSCRIPTION_SERVER", "🌍 Server: {server}").format(server=server_label),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_DEDUCTED", "💰 Deducted from balance: {amount}").format(amount=settings.format_price(price_kopeks)),
            texts.t("SIMPLE_SUBSCRIPTION_BALANCE", "💳 Your balance: {balance}").format(balance=settings.format_price(db_user.balance_kopeks)),
            "",
            texts.t("SIMPLE_SUBSCRIPTION_CONNECT_HINT", "🔗 To connect, go to the 'Connect' section"),
        ])

        success_message = "\n".join(success_lines)
        
        connect_mode = settings.CONNECT_BUTTON_MODE
        subscription_link = get_display_subscription_link(subscription)
        connect_button_text = texts.t("CONNECT_BUTTON", "🔗 Connect")

        def _fallback_connect_button() -> types.InlineKeyboardButton:
            return types.InlineKeyboardButton(
                text=connect_button_text,
                callback_data="subscription_connect",
            )

        if connect_mode == "miniapp_subscription":
            if subscription_link:
                connect_row = [
                    types.InlineKeyboardButton(
                        text=connect_button_text,
                        web_app=types.WebAppInfo(url=subscription_link),
                    )
                ]
            else:
                connect_row = [_fallback_connect_button()]
        elif connect_mode == "miniapp_custom":
            custom_url = settings.MINIAPP_CUSTOM_URL
            if custom_url:
                connect_row = [
                    types.InlineKeyboardButton(
                        text=connect_button_text,
                        web_app=types.WebAppInfo(url=custom_url),
                    )
                ]
            else:
                connect_row = [_fallback_connect_button()]
        elif connect_mode == "link":
            if subscription_link:
                connect_row = [
                    types.InlineKeyboardButton(
                        text=connect_button_text,
                        url=subscription_link,
                    )
                ]
            else:
                connect_row = [_fallback_connect_button()]
        elif connect_mode == "happ_cryptolink":
            if subscription_link:
                connect_row = [
                    types.InlineKeyboardButton(
                        text=connect_button_text,
                        callback_data="open_subscription_link",
                    )
                ]
            else:
                connect_row = [_fallback_connect_button()]
        else:
            connect_row = [_fallback_connect_button()]

        keyboard_rows = [connect_row]

        happ_row = get_happ_download_button_row(texts)
        if happ_row:
            keyboard_rows.append(happ_row)

        keyboard_rows.append(
            [types.InlineKeyboardButton(text=texts.t("BACK_TO_MAIN_MENU_BUTTON", "🏠 Main menu"), callback_data="back_to_menu")]
        )

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        await callback.message.edit_text(
            success_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Send notification to admins
        try:
            from app.services.admin_notification_service import AdminNotificationService
            notification_service = AdminNotificationService(callback.bot)
            await notification_service.send_subscription_purchase_notification(
                db,
                db_user,
                subscription,
                None,  # transaction
                subscription_params["period_days"],
                False,  # was_trial_conversion
                amount_kopeks=price_kopeks,
            )
        except Exception as e:
            logger.error("Error sending purchase notification to admins: %s", e)
        
        await state.clear()
        await callback.answer()

        logger.info(
            "User %s successfully purchased subscription from balance for %s",
            db_user.telegram_id,
            settings.format_price(price_kopeks)
        )

    except Exception as error:
        logger.error(
            "Error confirming simple subscription from balance for user %s: %s",
            db_user.id,
            error,
            exc_info=True,
        )
        await callback.answer(
            texts.t(
                "SIMPLE_SUBSCRIPTION_PAYMENT_ERROR",
                "❌ Error paying for subscription. Please try again later or contact support."
            ),
            show_alert=True,
        )
        await state.clear()

def register_simple_subscription_handlers(dp):
    """Registers handlers for simple subscription purchase."""
    
    dp.callback_query.register(
        start_simple_subscription_purchase,
        F.data == "simple_subscription_purchase"
    )
    
    dp.callback_query.register(
        confirm_simple_subscription_purchase,
        F.data == "simple_subscription_confirm_purchase"
    )
    
    dp.callback_query.register(
        handle_simple_subscription_pay_with_balance,
        F.data == "simple_subscription_pay_with_balance"
    )
    
    dp.callback_query.register(
        handle_simple_subscription_pay_with_balance_disabled,
        F.data == "simple_subscription_pay_with_balance_disabled"
    )
    
    dp.callback_query.register(
        handle_simple_subscription_other_payment_methods,
        F.data == "simple_subscription_other_payment_methods"
    )
    
    dp.callback_query.register(
        handle_simple_subscription_payment_method,
        F.data.startswith("simple_subscription_")
    )

    dp.callback_query.register(
        check_simple_pal24_payment_status,
        F.data.startswith("check_simple_pal24_")
    )

    dp.callback_query.register(
        check_simple_mulenpay_payment_status,
        F.data.startswith("check_simple_mulenpay_")
    )

    dp.callback_query.register(
        check_simple_cryptobot_payment_status,
        F.data.startswith("check_simple_cryptobot_")
    )

    dp.callback_query.register(
        check_simple_heleket_payment_status,
        F.data.startswith("check_simple_heleket_")
    )

    dp.callback_query.register(
        check_simple_wata_payment_status,
        F.data.startswith("check_simple_wata_")
    )

    dp.callback_query.register(
        check_simple_pal24_payment_status,
        F.data.startswith("check_simple_pal24_")
    )
