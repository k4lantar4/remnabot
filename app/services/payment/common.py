"""Common tools for the payment service.

This module contains helpers that are shared across all payment channels:
keyboard construction, basic notifications and standard handling
of successful payments.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.user import get_user_by_telegram_id
from app.database.database import get_db
from app.localization.texts import get_texts
from app.services.subscription_checkout_service import (
    has_subscription_checkout_draft,
    should_offer_checkout_resume,
)
from app.services.user_cart_service import user_cart_service
from app.utils.miniapp_buttons import build_miniapp_or_callback_button

logger = logging.getLogger(__name__)


class PaymentCommonMixin:
    """Mixin with base logic used by all other payment blocks."""

    async def build_topup_success_keyboard(self, user: Any) -> InlineKeyboardMarkup:
        """Builds a post-payment keyboard adapted to the specific user."""
        # Load texts taking the user's language into account.
        texts = get_texts(user.language if user else "ru")

        # Determine subscription status to show the appropriate button.
        has_active_subscription = False
        subscription = None
        if user:
            try:
                subscription = user.subscription
                has_active_subscription = bool(
                    subscription
                    and not getattr(subscription, "is_trial", False)
                    and getattr(subscription, "is_active", False)
                )
            except MissingGreenlet as error:
                logger.warning(
                    "Failed to lazy-load subscription for user %s "
                    "while building keyboard after top-up: %s",
                    getattr(user, "id", None),
                    error,
                )
            except Exception as error:  # pragma: no cover - defensive code
                logger.error(
                    "Error loading subscription for user %s while building keyboard "
                    "after top-up: %s",
                    getattr(user, "id", None),
                    error,
                )

        # Build the primary button: extend if subscription is active, otherwise buy
        first_button = build_miniapp_or_callback_button(
            text=(
                texts.MENU_EXTEND_SUBSCRIPTION
                if has_active_subscription
                else texts.MENU_BUY_SUBSCRIPTION
            ),
            callback_data=(
                "subscription_extend" if has_active_subscription else "menu_buy"
            ),
        )

        # Subscription activation button (always shown)
        activate_subscription_button = build_miniapp_or_callback_button(
            text="🚀 Activate subscription",
            callback_data="menu_buy",  # Use same callback_data as for 'Buy subscription'
        )

        keyboard_rows: list[list[InlineKeyboardButton]] = [
            [first_button],
            [activate_subscription_button]
        ]

        # If the user has an unfinished checkout, offer to return to it.
        if user:
            try:
                has_saved_cart = await user_cart_service.has_user_cart(user.id)
            except Exception as cart_error:
                logger.warning(
                    "Failed to check presence of saved cart for user %s: %s",
                    user.id,
                    cart_error,
                )
                has_saved_cart = False

            if has_saved_cart:
                keyboard_rows.append([
                    build_miniapp_or_callback_button(
                        text=texts.RETURN_TO_SUBSCRIPTION_CHECKOUT,
                        callback_data="return_to_saved_cart",
                    )
                ])
            else:
                draft_exists = await has_subscription_checkout_draft(user.id)
                if should_offer_checkout_resume(user, draft_exists, subscription=subscription):
                    keyboard_rows.append([
                        build_miniapp_or_callback_button(
                            text=texts.RETURN_TO_SUBSCRIPTION_CHECKOUT,
                            callback_data="subscription_resume_checkout",
                        )
                    ])

        # Standard quick-access buttons to balance and main menu.
        keyboard_rows.append([
            build_miniapp_or_callback_button(
                text="💰 My balance",
                callback_data="menu_balance",
            )
        ])
        keyboard_rows.append([
            InlineKeyboardButton(
                text="🏠 Main menu",
                callback_data="back_to_menu",
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    async def _send_payment_success_notification(
        self,
        telegram_id: int,
        amount_kopeks: int,
        user: Any | None = None,
        *,
        db: AsyncSession | None = None,
        payment_method_title: str | None = None,
    ) -> None:
        """Sends a notification to the user about a successful payment."""
        if not getattr(self, "bot", None):
            # If bot instance is not provided (e.g. inside background tasks), skip notification.
            return

        user_snapshot = await self._ensure_user_snapshot(
            telegram_id,
            user,
            db=db,
        )

        try:
            keyboard = await self.build_topup_success_keyboard(user_snapshot)

            payment_method = payment_method_title or "Bank card (YooKassa)"
            message = (
                "✅ <b>Payment completed successfully!</b>\n\n"
                f"💰 Amount: {settings.format_price(amount_kopeks)}\n"
                f"💳 Method: {payment_method}\n\n"
                "The funds have been credited to your balance!\n\n"
                "⚠️ <b>Important:</b> Topping up your balance does not activate a subscription "
                "automatically. You must activate your subscription separately.\n\n"
                "🔄 If you have a saved subscription cart and auto-purchase is enabled, "
                "the subscription will be purchased automatically after the top-up."
            )

            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception as error:
            logger.error(
                "Error sending payment success notification to user %s: %s",
                telegram_id,
                error,
            )

    async def _ensure_user_snapshot(
        self,
        telegram_id: int,
        user: Any | None,
        *,
        db: AsyncSession | None = None,
    ) -> Any | None:
        """Ensures that user data is safe to use for keyboard construction."""

        def _build_snapshot(source: Any | None) -> SimpleNamespace | None:
            if source is None:
                return None

            subscription = getattr(source, "subscription", None)
            subscription_snapshot = None

            if subscription is not None:
                subscription_snapshot = SimpleNamespace(
                    is_trial=getattr(subscription, "is_trial", False),
                    is_active=getattr(subscription, "is_active", False),
                    actual_status=getattr(subscription, "actual_status", None),
                )

            return SimpleNamespace(
                id=getattr(source, "id", None),
                telegram_id=getattr(source, "telegram_id", None),
                language=getattr(source, "language", "ru"),
                subscription=subscription_snapshot,
            )

        try:
            snapshot = _build_snapshot(user)
        except MissingGreenlet:
            snapshot = None

        if snapshot is not None:
            return snapshot

        fetch_session = db

        if fetch_session is not None:
            try:
                fetched_user = await get_user_by_telegram_id(fetch_session, telegram_id)
                return _build_snapshot(fetched_user)
            except Exception as fetch_error:
                logger.warning(
                    "Failed to refresh user %s from provided session: %s",
                    telegram_id,
                    fetch_error,
                )

        try:
            async for db_session in get_db():
                fetched_user = await get_user_by_telegram_id(db_session, telegram_id)
                return _build_snapshot(fetched_user)
        except Exception as fetch_error:
            logger.warning(
                "Failed to load user %s from DB for notification: %s",
                telegram_id,
                fetch_error,
            )

        return None

    async def process_successful_payment(
        self,
        payment_id: str,
        amount_kopeks: int,
        user_id: int,
        payment_method: str,
    ) -> bool:
        """Common accounting entry point for successful payments (used by providers as needed)."""
        try:
            logger.info(
                "Processed successful payment: %s, %s RUB, user %s, method %s",
                payment_id,
                amount_kopeks / 100,
                user_id,
                payment_method,
            )
            return True
        except Exception as error:
            logger.error("Error processing payment %s: %s", payment_id, error)
            return False
