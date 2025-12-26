"""Telegram Stars logic moved to a separate mixin.

These methods handle Stars-specific flows to keep the main service compact and
make scenario testing simpler.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Optional

from aiogram.types import LabeledPrice
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.transaction import create_transaction
from app.database.crud.user import get_user_by_id
from app.database.models import PaymentMethod, TransactionType
from app.external.telegram_stars import TelegramStarsService
from app.services.subscription_auto_purchase_service import (
    auto_purchase_saved_cart_after_topup,
)
from app.utils.user_utils import format_referrer_info

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _SimpleSubscriptionPayload:
    """Data for a simple subscription extracted from a Stars payment payload."""

    subscription_id: Optional[int]
    period_days: Optional[int]


class TelegramStarsMixin:
    """Mixin with operations for creating and processing Telegram Stars payments."""

    async def create_stars_invoice(
        self,
        amount_toman: int,
        description: str,
        payload: Optional[str] = None,
        *,
        stars_amount: Optional[int] = None,
    ) -> str:
        """Creates a Telegram Stars invoice, auto-calculating the stars amount."""
        if not self.bot or not getattr(self, "stars_service", None):
            raise ValueError("Bot instance required for Stars payments")

        try:
            # Convert toman to rubles for Telegram Stars API (which expects rubles)
            amount_rubles = Decimal(amount_toman) / Decimal(100)

            # If stars_count is not provided, calculate it from the exchange rate.
            if stars_amount is None:
                stars_amount = settings.rubles_to_stars(float(amount_rubles))

            if stars_amount <= 0:
                raise ValueError("Stars amount must be positive")

            invoice_link = await self.bot.create_invoice_link(
                title="VPN balance top-up",
                description=f"{description} (≈{stars_amount} ⭐)",
                payload=payload or f"balance_topup_{amount_toman}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label="Top-up", amount=stars_amount)],
            )

            logger.info(
                "Created Stars invoice for %s stars (~%s)",
                stars_amount,
                settings.format_price(amount_toman),
            )
            return invoice_link

        except Exception as error:
            logger.error("Failed to create Stars invoice: %s", error)
            raise

    async def process_stars_payment(
        self,
        db: AsyncSession,
        user_id: int,
        stars_amount: int,
        payload: str,
        telegram_payment_charge_id: str,
    ) -> bool:
        """Finalizes a Telegram Stars payment and updates the user balance."""
        try:
            rubles_amount = TelegramStarsService.calculate_rubles_from_stars(
                stars_amount
            )
            # Convert rubles from Telegram Stars API to toman
            amount_toman = int(
                (rubles_amount * Decimal(100)).to_integral_value(
                    rounding=ROUND_HALF_UP
                )
            )

            simple_payload = self._parse_simple_subscription_payload(
                payload,
                user_id,
            )

            transaction_description = (
                f"Subscription payment via Telegram Stars ({stars_amount} ⭐)"
                if simple_payload
                else f"Balance top-up via Telegram Stars ({stars_amount} ⭐)"
            )
            transaction_type = (
                TransactionType.SUBSCRIPTION_PAYMENT
                if simple_payload
                else TransactionType.DEPOSIT
            )

            transaction = await create_transaction(
                db=db,
                user_id=user_id,
                type=transaction_type,
                amount_toman=amount_toman,
                description=transaction_description,
                payment_method=PaymentMethod.TELEGRAM_STARS,
                external_id=telegram_payment_charge_id,
                is_completed=True,
            )

            user = await get_user_by_id(db, user_id)
            if not user:
                logger.error(
                    "User with ID %s not found while processing Stars payment",
                    user_id,
                )
                return False

            if simple_payload:
                return await self._finalize_simple_subscription_stars_payment(
                    db=db,
                    user=user,
                    transaction=transaction,
                    amount_toman=amount_toman,
                    stars_amount=stars_amount,
                    payload_data=simple_payload,
                    telegram_payment_charge_id=telegram_payment_charge_id,
                )

            return await self._finalize_stars_balance_topup(
                db=db,
                user=user,
                transaction=transaction,
                amount_toman=amount_toman,
                stars_amount=stars_amount,
                telegram_payment_charge_id=telegram_payment_charge_id,
            )

        except Exception as error:
            logger.error("Failed to process Stars payment: %s", error, exc_info=True)
            return False

    @staticmethod
    def _parse_simple_subscription_payload(
        payload: str,
        expected_user_id: int,
    ) -> Optional[_SimpleSubscriptionPayload]:
        """Attempts to extract simple subscription params from a Stars payload."""

        prefix = "simple_sub_"
        if not payload or not payload.startswith(prefix):
            return None

        tail = payload[len(prefix) :]
        parts = tail.split("_", 2)
        if len(parts) < 3:
            logger.warning(
                "Stars simple subscription payload has an invalid format: %s",
                payload,
            )
            return None

        user_part, subscription_part, period_part = parts

        try:
            payload_user_id = int(user_part)
        except ValueError:
            logger.warning(
                "Unable to parse user_id in Stars simple subscription payload: %s",
                payload,
            )
            return None

        if payload_user_id != expected_user_id:
            logger.warning(
                "Received Stars simple subscription payload with mismatched user_id: %s (expected %s)",
                payload_user_id,
                expected_user_id,
            )
            return None

        try:
            subscription_id = int(subscription_part)
        except ValueError:
            logger.warning(
                "Unable to parse subscription_id in Stars simple subscription payload: %s",
                payload,
            )
            return None

        period_days: Optional[int] = None
        try:
            period_days = int(period_part)
        except ValueError:
            logger.warning(
                "Unable to parse period in Stars simple subscription payload: %s",
                payload,
            )

        return _SimpleSubscriptionPayload(
            subscription_id=subscription_id,
            period_days=period_days,
        )

    async def _finalize_simple_subscription_stars_payment(
        self,
        db: AsyncSession,
        user,
        transaction,
        amount_toman: int,
        stars_amount: int,
        payload_data: _SimpleSubscriptionPayload,
        telegram_payment_charge_id: str,
    ) -> bool:
        """Activate a simple subscription paid via Telegram Stars."""

        period_days = payload_data.period_days or settings.SIMPLE_SUBSCRIPTION_PERIOD_DAYS
        pending_subscription = None

        if payload_data.subscription_id is not None:
            try:
                from sqlalchemy import select
                from app.database.models import Subscription

                result = await db.execute(
                    select(Subscription).where(
                        Subscription.id == payload_data.subscription_id,
                        Subscription.user_id == user.id,
                    )
                )
                pending_subscription = result.scalar_one_or_none()
            except Exception as lookup_error:  # pragma: no cover - diagnostic log
                logger.error(
                    "Error fetching pending subscription %s for user %s: %s",
                    payload_data.subscription_id,
                    user.id,
                    lookup_error,
                    exc_info=True,
                )
                pending_subscription = None

            if not pending_subscription:
                logger.error(
                    "Pending subscription %s for user %s not found",
                    payload_data.subscription_id,
                    user.id,
                )
                return False

            if payload_data.period_days is None:
                start_point = pending_subscription.start_date or datetime.utcnow()
                end_point = pending_subscription.end_date or start_point
                computed_days = max(1, (end_point - start_point).days or 0)
                period_days = max(period_days, computed_days)

        try:
            from app.database.crud.subscription import activate_pending_subscription

            subscription = await activate_pending_subscription(
                db=db,
                user_id=user.id,
                period_days=period_days,
            )
        except Exception as error:
            logger.error(
                "Error activating pending subscription for user %s: %s",
                user.id,
                error,
                exc_info=True,
            )
            return False

        if not subscription:
            logger.error(
                "Failed to activate pending subscription for user %s",
                user.id,
            )
            return False

        try:
            from app.services.subscription_service import SubscriptionService

            subscription_service = SubscriptionService()
            remnawave_user = await subscription_service.create_remnawave_user(
                db,
                subscription,
            )
            if remnawave_user:
                await db.refresh(subscription)
        except Exception as sync_error:  # pragma: no cover - diagnostic log
            logger.error(
                "Error syncing subscription with RemnaWave for user %s: %s",
                user.id,
                sync_error,
                exc_info=True,
            )

        period_display = period_days
        if not period_display and getattr(subscription, "start_date", None) and getattr(
            subscription, "end_date", None
        ):
            period_display = max(1, (subscription.end_date - subscription.start_date).days or 0)
        if not period_display:
            period_display = settings.SIMPLE_SUBSCRIPTION_PERIOD_DAYS

        if getattr(self, "bot", None):
            try:
                from aiogram import types
                from app.localization.texts import get_texts

                texts = get_texts(user.language)
                traffic_limit = getattr(subscription, "traffic_limit_gb", 0) or 0
                traffic_label = (
                    "Unlimited" if traffic_limit == 0 else f"{int(traffic_limit)} GB"
                )

                success_message = (
                    "✅ <b>Subscription activated!</b>\n\n"
                    f"📅 Duration: {period_display} days\n"
                    f"📱 Devices: {getattr(subscription, 'device_limit', 1)}\n"
                    f"📊 Traffic: {traffic_label}\n"
                    f"⭐ Payment: {stars_amount} ⭐ ({settings.format_price(amount_toman)})\n\n"
                    "🔗 Open 'My subscription' to connect"
                )

                keyboard = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="📱 My subscription",
                                callback_data="menu_subscription",
                            )
                        ],
                        [
                            types.InlineKeyboardButton(
                                text="🏠 Main menu",
                                callback_data="back_to_menu",
                            )
                        ],
                    ]
                )

                await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=success_message,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                logger.info(
                    "✅ User %s received Stars subscription payment notification",
                    user.telegram_id,
                )
            except Exception as error:  # pragma: no cover - diagnostic log
                logger.error(
                    "Failed to send Stars subscription notification: %s",
                    error,
                    exc_info=True,
                )

        if getattr(self, "bot", None):
            try:
                from app.services.admin_notification_service import AdminNotificationService

                notification_service = AdminNotificationService(self.bot)
                await notification_service.send_subscription_purchase_notification(
                    db,
                    user,
                    subscription,
                    transaction,
                    period_display,
                    was_trial_conversion=False,
                )
            except Exception as admin_error:  # pragma: no cover - diagnostic log
                logger.error(
                    "Failed to notify admins about Stars subscription: %s",
                    admin_error,
                    exc_info=True,
                )

        logger.info(
            "✅ Stars payment processed as subscription purchase: user %s, %s stars → %s",
            user.id,
            stars_amount,
            settings.format_price(amount_toman),
        )
        return True

    async def _finalize_stars_balance_topup(
        self,
        db: AsyncSession,
        user,
        transaction,
        amount_toman: int,
        stars_amount: int,
        telegram_payment_charge_id: str,
    ) -> bool:
        """Credits balance after a Stars payment and triggers auto-purchase."""

        # Remember previous values to build notifications correctly.
        old_balance = user.balance_toman
        was_first_topup = not user.has_made_first_topup

        # Update balance in DB.
        user.balance_toman += amount_toman
        user.updated_at = datetime.utcnow()

        promo_group = user.get_primary_promo_group()
        subscription = getattr(user, "subscription", None)
        referrer_info = format_referrer_info(user)
        topup_status = "🆕 First top-up" if was_first_topup else "🔄 Top-up"

        await db.commit()

        description_for_referral = (
            f"Stars top-up: {settings.format_price(amount_toman)} ({stars_amount} ⭐)"
        )
        logger.info(
            "🔍 Checking referral logic for description: '%s'",
            description_for_referral,
        )

        lower_description = description_for_referral.lower()
        contains_allowed_keywords = any(
            word in lower_description for word in ["topup", "stars", "yookassa"]
        )
        contains_forbidden_keywords = any(
            word in lower_description for word in ["commission", "bonus"]
        )
        allow_referral = contains_allowed_keywords and not contains_forbidden_keywords

        if allow_referral:
            logger.info(
                "🔞 Calling process_referral_topup for user %s",
                user.id,
            )
            try:
                from app.services.referral_service import process_referral_topup

                await process_referral_topup(
                    db,
                    user.id,
                    amount_toman,
                    getattr(self, "bot", None),
                )
            except Exception as error:  # pragma: no cover - diagnostic log
                logger.error(
                    "Failed to process referral top-up: %s",
                    error,
                )
        else:
            logger.info(
                "❌ Description '%s' does not match referral logic",
                description_for_referral,
            )

        if was_first_topup and not user.has_made_first_topup:
            user.has_made_first_topup = True
            await db.commit()

        await db.refresh(user)

        logger.info(
            "💰 User %s balance changed: %s → %s (Δ +%s)",
            user.telegram_id,
            old_balance,
            user.balance_toman,
            amount_toman,
        )

        if getattr(self, "bot", None):
            try:
                from app.services.admin_notification_service import AdminNotificationService

                notification_service = AdminNotificationService(self.bot)
                await notification_service.send_balance_topup_notification(
                    user,
                    transaction,
                    old_balance,
                    topup_status=topup_status,
                    referrer_info=referrer_info,
                    subscription=subscription,
                    promo_group=promo_group,
                    db=db,
                )
            except Exception as error:  # pragma: no cover - diagnostic log
                logger.error(
                    "Failed to send Stars top-up notification: %s",
                    error,
                    exc_info=True,
                )

        # Check for a saved cart to return the user to subscription checkout
        try:
            from aiogram import types
            from app.localization.texts import get_texts
            from app.services.user_cart_service import user_cart_service

            has_saved_cart = await user_cart_service.has_user_cart(user.id)
            auto_purchase_success = False
            if has_saved_cart:
                try:
                    auto_purchase_success = await auto_purchase_saved_cart_after_topup(
                        db,
                        user,
                        bot=getattr(self, "bot", None),
                    )
                except Exception as auto_error:  # pragma: no cover - diagnostic log
                    logger.error(
                        "Failed to auto-purchase subscription for user %s: %s",
                        user.id,
                        auto_error,
                        exc_info=True,
                    )

                if auto_purchase_success:
                    has_saved_cart = False

            if has_saved_cart and getattr(self, "bot", None):
                texts = get_texts(user.language)
                cart_message = texts.t(
                    "BALANCE_TOPUP_CART_REMINDER_DETAILED",
                    "🛒 You have an unfinished order.\n\n"
                    "You can continue checkout with the same parameters.",
                )

                keyboard = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=texts.RETURN_TO_SUBSCRIPTION_CHECKOUT,
                                callback_data="return_to_saved_cart",
                            )
                        ],
                        [
                            types.InlineKeyboardButton(
                                text="💰 My balance",
                                callback_data="menu_balance",
                            )
                        ],
                        [
                            types.InlineKeyboardButton(
                                text="🏠 Main menu",
                                callback_data="back_to_menu",
                            )
                        ],
                    ]
                )

                await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"✅ Balance topped up by {settings.format_price(amount_toman)}!\n\n"
                         f"⚠️ <b>Important:</b> Balance top-up does not activate a subscription automatically. "
                         f"Please activate the subscription separately.\n\n"
                         f"🔄 If a saved subscription cart exists and auto-purchase is enabled, "
                         f"the subscription will be purchased automatically after the top-up.\n\n{cart_message}",
                    reply_markup=keyboard,
                )
                logger.info(
                    "Sent notification with return-to-subscription button to user %s",
                    user.id,
                )
        except Exception as error:  # pragma: no cover - diagnostic log
            logger.error(
                "Error handling saved cart for user %s: %s",
                user.id,
                error,
                exc_info=True,
            )

        logger.info(
            "✅ Stars payment processed: user %s, %s stars → %s",
            user.id,
            stars_amount,
            settings.format_price(amount_toman),
        )
        return True
