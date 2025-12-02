"""Mixin with CryptoBot payment processing logic."""

from __future__ import annotations
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.database import AsyncSessionLocal
from app.database.models import PaymentMethod, TransactionType
from app.services.subscription_auto_purchase_service import (
    auto_purchase_saved_cart_after_topup,
)
from app.services.subscription_renewal_service import (
    SubscriptionRenewalChargeError,
    SubscriptionRenewalPricing,
    SubscriptionRenewalService,
    RenewalPaymentDescriptor,
    build_renewal_period_id,
    decode_payment_payload,
    parse_payment_metadata,
)
from app.utils.currency_converter import currency_converter
from app.utils.user_utils import format_referrer_info

logger = logging.getLogger(__name__)


renewal_service = SubscriptionRenewalService()


@dataclass(slots=True)
class _AdminNotificationContext:
    user_id: int
    transaction_id: int
    old_balance: int
    topup_status: str
    referrer_info: str


@dataclass(slots=True)
class _UserNotificationPayload:
    telegram_id: int
    text: str
    parse_mode: Optional[str]
    reply_markup: Any
    amount_rubles: float
    asset: str


@dataclass(slots=True)
class _SavedCartNotificationPayload:
    telegram_id: int
    text: str
    reply_markup: Any
    user_id: int


class CryptoBotPaymentMixin:
    """Mixin responsible for generating CryptoBot invoices and handling webhooks."""

    async def create_cryptobot_payment(
        self,
        db: AsyncSession,
        user_id: int,
        amount_usd: float,
        asset: str = "USDT",
        description: str = "Balance top-up",
        payload: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Creates an invoice in CryptoBot and stores a local record."""
        if not getattr(self, "cryptobot_service", None):
            logger.error("CryptoBot service is not initialised")
            return None

        try:
            amount_str = f"{amount_usd:.2f}"

            invoice_data = await self.cryptobot_service.create_invoice(
                amount=amount_str,
                asset=asset,
                description=description,
                payload=payload or f"balance_topup_{user_id}_{int(amount_usd * 100)}",
                expires_in=settings.get_cryptobot_invoice_expires_seconds(),
            )

            if not invoice_data:
                logger.error("Failed to create CryptoBot invoice")
                return None

            cryptobot_crud = import_module("app.database.crud.cryptobot")

            local_payment = await cryptobot_crud.create_cryptobot_payment(
                db=db,
                user_id=user_id,
                invoice_id=str(invoice_data["invoice_id"]),
                amount=amount_str,
                asset=asset,
                status="active",
                description=description,
                payload=payload,
                bot_invoice_url=invoice_data.get("bot_invoice_url"),
                mini_app_invoice_url=invoice_data.get("mini_app_invoice_url"),
                web_app_invoice_url=invoice_data.get("web_app_invoice_url"),
            )

            logger.info(
                "Created CryptoBot payment %s for user %s: %s %s",
                invoice_data["invoice_id"],
                user_id,
                amount_str,
                asset,
            )

            return {
                "local_payment_id": local_payment.id,
                "invoice_id": str(invoice_data["invoice_id"]),
                "amount": amount_str,
                "asset": asset,
                "bot_invoice_url": invoice_data.get("bot_invoice_url"),
                "mini_app_invoice_url": invoice_data.get("mini_app_invoice_url"),
                "web_app_invoice_url": invoice_data.get("web_app_invoice_url"),
                "status": "active",
                "created_at": (
                    local_payment.created_at.isoformat()
                    if local_payment.created_at
                    else None
                ),
            }

        except Exception as error:
            logger.error("Error creating CryptoBot payment: %s", error)
            return None

    async def process_cryptobot_webhook(
        self,
        db: AsyncSession,
        webhook_data: Dict[str, Any],
    ) -> bool:
        """Processes a CryptoBot webhook and credits funds to the user."""
        try:
            update_type = webhook_data.get("update_type")

            if update_type != "invoice_paid":
                logger.info("Skipping CryptoBot webhook with type: %s", update_type)
                return True

            payload = webhook_data.get("payload", {})
            invoice_id = str(payload.get("invoice_id"))
            status = "paid"

            if not invoice_id:
                logger.error("CryptoBot webhook without invoice_id")
                return False

            cryptobot_crud = import_module("app.database.crud.cryptobot")
            payment = await cryptobot_crud.get_cryptobot_payment_by_invoice_id(
                db, invoice_id
            )
            if not payment:
                logger.error("CryptoBot payment not found in DB: %s", invoice_id)
                return False

            if payment.status == "paid":
                logger.info("CryptoBot payment %s already processed", invoice_id)
                return True

            paid_at_str = payload.get("paid_at")
            if paid_at_str:
                try:
                    paid_at = datetime.fromisoformat(
                        paid_at_str.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except Exception:
                    paid_at = datetime.utcnow()
            else:
                paid_at = datetime.utcnow()

            updated_payment = await cryptobot_crud.update_cryptobot_payment_status(
                db, invoice_id, status, paid_at
            )

            descriptor = decode_payment_payload(
                getattr(updated_payment, "payload", "") or "",
                expected_user_id=updated_payment.user_id,
            )

            if descriptor is None:
                inline_payload = payload.get("payload")
                if isinstance(inline_payload, str) and inline_payload:
                    descriptor = decode_payment_payload(
                        inline_payload,
                        expected_user_id=updated_payment.user_id,
                    )

            if descriptor is None:
                metadata = payload.get("metadata")
                if isinstance(metadata, dict) and metadata:
                    descriptor = parse_payment_metadata(
                        metadata,
                        expected_user_id=updated_payment.user_id,
                    )
            if descriptor:
                renewal_handled = await self._process_subscription_renewal_payment(
                    db,
                    updated_payment,
                    descriptor,
                    cryptobot_crud,
                )
                if renewal_handled:
                    return True

            if not updated_payment.transaction_id:
                amount_usd = updated_payment.amount_float

                try:
                    amount_rubles = await currency_converter.usd_to_rub(amount_usd)
                    amount_rubles_rounded = math.ceil(amount_rubles)
                    amount_kopeks = int(amount_rubles_rounded * 100)
                    conversion_rate = (
                        amount_rubles / amount_usd if amount_usd > 0 else 0
                    )
                    logger.info(
                        "Conversion USD->RUB: $%s -> %s RUB (rounded to %s RUB, rate: %.2f)",
                        amount_usd,
                        amount_rubles,
                        amount_rubles_rounded,
                        conversion_rate,
                    )
                except Exception as error:
                    logger.warning(
                        "Currency conversion error for payment %s, falling back to 1:1 rate: %s",
                        invoice_id,
                        error,
                    )
                    amount_rubles = amount_usd
                    amount_rubles_rounded = math.ceil(amount_rubles)
                    amount_kopeks = int(amount_rubles_rounded * 100)
                    conversion_rate = 1.0

                if amount_kopeks <= 0:
                    logger.error(
                        "Invalid amount after conversion: %s kopeks for payment %s",
                        amount_kopeks,
                        invoice_id,
                    )
                    return False

                payment_service_module = import_module("app.services.payment_service")
                transaction = await payment_service_module.create_transaction(
                    db,
                    user_id=updated_payment.user_id,
                    type=TransactionType.DEPOSIT,
                    amount_kopeks=amount_kopeks,
                    description=(
                        "Top-up via CryptoBot "
                        f"({updated_payment.amount} {updated_payment.asset} → {amount_rubles_rounded:.2f} RUB)"
                    ),
                    payment_method=PaymentMethod.CRYPTOBOT,
                    external_id=invoice_id,
                    is_completed=True,
                )

                await cryptobot_crud.link_cryptobot_payment_to_transaction(
                    db, invoice_id, transaction.id
                )

                get_user_by_id = payment_service_module.get_user_by_id
                user = await get_user_by_id(db, updated_payment.user_id)
                if not user:
                    logger.error(
                        "User with ID %s not found while processing balance top-up",
                        updated_payment.user_id,
                    )
                    return False

                old_balance = user.balance_kopeks
                was_first_topup = not user.has_made_first_topup

                user.balance_kopeks += amount_kopeks
                user.updated_at = datetime.utcnow()

                referrer_info = format_referrer_info(user)
                topup_status = (
                    "🆕 First top-up" if was_first_topup else "🔄 Top-up"
                )

                await db.commit()

                try:
                    from app.services.referral_service import process_referral_topup

                    await process_referral_topup(
                        db,
                        user.id,
                        amount_kopeks,
                        getattr(self, "bot", None),
                    )
                except Exception as error:
                    logger.error(
                        "Error processing referral top-up for CryptoBot: %s",
                        error,
                    )

                if was_first_topup and not user.has_made_first_topup:
                    user.has_made_first_topup = True
                    await db.commit()

                await db.refresh(user)

                admin_notification: Optional[_AdminNotificationContext] = None
                user_notification: Optional[_UserNotificationPayload] = None
                saved_cart_notification: Optional[_SavedCartNotificationPayload] = None

                bot_instance = getattr(self, "bot", None)
                if bot_instance:
                    admin_notification = _AdminNotificationContext(
                        user_id=user.id,
                        transaction_id=transaction.id,
                        old_balance=old_balance,
                        topup_status=topup_status,
                        referrer_info=referrer_info,
                    )

                    try:
                        keyboard = await self.build_topup_success_keyboard(user)
                        message_text = (
                            "✅ <b>Top-up successful!</b>\n\n"
                            f"💰 Amount: {settings.format_price(amount_kopeks)}\n"
                            f"🪙 Payment: {updated_payment.amount} {updated_payment.asset}\n"
                            f"💱 Rate: 1 USD = {conversion_rate:.2f} RUB\n"
                            f"🆔 Transaction: {invoice_id[:8]}...\n\n"
                            "The balance has been credited automatically."
                        )
                        user_notification = _UserNotificationPayload(
                            telegram_id=user.telegram_id,
                            text=message_text,
                            parse_mode="HTML",
                            reply_markup=keyboard,
                            amount_rubles=amount_rubles_rounded,
                            asset=updated_payment.asset,
                        )
                    except Exception as error:
                        logger.error(
                            "Error preparing CryptoBot top-up notification: %s",
                            error,
                        )

                # Check for a saved cart to offer returning to subscription checkout
                try:
                    from app.services.user_cart_service import user_cart_service
                    from aiogram import types

                    has_saved_cart = await user_cart_service.has_user_cart(user.id)
                    auto_purchase_success = False
                    if has_saved_cart:
                        try:
                            auto_purchase_success = await auto_purchase_saved_cart_after_topup(
                                db,
                                user,
                                bot=bot_instance,
                            )
                        except Exception as auto_error:
                            logger.error(
                                "Error during automatic subscription purchase for user %s: %s",
                                user.id,
                                auto_error,
                                exc_info=True,
                            )

                        if auto_purchase_success:
                            has_saved_cart = False

                    if has_saved_cart and bot_instance:
                        from app.localization.texts import get_texts

                        texts = get_texts(user.language)
                        cart_message = texts.BALANCE_TOPUP_CART_REMINDER_DETAILED.format(
                            total_amount=settings.format_price(amount_kopeks)
                        )

                        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                            [types.InlineKeyboardButton(
                                text=texts.RETURN_TO_SUBSCRIPTION_CHECKOUT,
                                callback_data="return_to_saved_cart"
                            )],
                            [types.InlineKeyboardButton(
                                text="💰 My balance",
                                callback_data="menu_balance"
                            )],
                            [types.InlineKeyboardButton(
                                text="🏠 Main menu",
                                callback_data="back_to_menu"
                            )]
                        ])

                        saved_cart_notification = _SavedCartNotificationPayload(
                            telegram_id=user.telegram_id,
                                text=(
                                    f"✅ Balance has been topped up by {settings.format_price(amount_kopeks)}!\n\n"
                                    f"⚠️ <b>Important:</b> Topping up your balance does not activate a subscription automatically. "
                                    f"Be sure to activate your subscription separately.\n\n"
                                    f"🔄 If you have a saved subscription cart and auto-purchase is enabled, "
                                    f"the subscription will be purchased automatically after the top-up.\n\n{cart_message}"
                                ),
                            reply_markup=keyboard,
                            user_id=user.id,
                        )
                except Exception as error:
                    logger.error(
                        "Error while working with saved cart for user %s: %s",
                        user.id,
                        error,
                        exc_info=True,
                    )

                if admin_notification:
                    await self._deliver_admin_topup_notification(admin_notification)

                if user_notification and bot_instance:
                    await self._deliver_user_topup_notification(user_notification)

                if saved_cart_notification and bot_instance:
                    await self._deliver_saved_cart_reminder(saved_cart_notification)

            return True

        except Exception as error:
            logger.error(
                "Error processing CryptoBot webhook: %s", error, exc_info=True
            )
            return False

    async def _process_subscription_renewal_payment(
        self,
        db: AsyncSession,
        payment: Any,
        descriptor: RenewalPaymentDescriptor,
        cryptobot_crud: Any,
    ) -> bool:
        try:
            payment_service_module = import_module("app.services.payment_service")
            user = await payment_service_module.get_user_by_id(db, payment.user_id)
        except Exception as error:
            logger.error(
                "Failed to load user %s for renewal via CryptoBot: %s",
                getattr(payment, "user_id", None),
                error,
            )
            return False

        if not user:
            logger.error(
                "User %s not found while processing renewal via CryptoBot",
                getattr(payment, "user_id", None),
            )
            return False

        subscription = getattr(user, "subscription", None)
        if not subscription or subscription.id != descriptor.subscription_id:
            logger.warning(
                "Renewal via CryptoBot rejected: subscription %s does not match expected %s",
                getattr(subscription, "id", None),
                descriptor.subscription_id,
            )
            return False

        pricing_model: Optional[SubscriptionRenewalPricing] = None
        if descriptor.pricing_snapshot:
            try:
                pricing_model = SubscriptionRenewalPricing.from_payload(
                    descriptor.pricing_snapshot
                )
            except Exception as error:
                logger.warning(
                    "Failed to restore saved renewal pricing from payload %s: %s",
                    payment.invoice_id,
                    error,
                )

        if pricing_model is None:
            try:
                pricing_model = await renewal_service.calculate_pricing(
                    db,
                    user,
                    subscription,
                    descriptor.period_days,
                )
            except Exception as error:
                logger.error(
                    "Failed to recalculate renewal pricing for CryptoBot %s: %s",
                    payment.invoice_id,
                    error,
                )
                return False

            if pricing_model.final_total != descriptor.total_amount_kopeks:
                logger.warning(
                    "Renewal amount via CryptoBot %s has changed (expected %s, got %s)",
                    payment.invoice_id,
                    descriptor.total_amount_kopeks,
                    pricing_model.final_total,
                )
                pricing_model.final_total = descriptor.total_amount_kopeks
                pricing_model.per_month = (
                    descriptor.total_amount_kopeks // pricing_model.months
                    if pricing_model.months
                    else descriptor.total_amount_kopeks
                )

        pricing_model.period_days = descriptor.period_days
        pricing_model.period_id = build_renewal_period_id(descriptor.period_days)

        required_balance = max(
            0,
            min(
                pricing_model.final_total,
                descriptor.balance_component_kopeks,
            ),
        )

        current_balance = getattr(user, "balance_kopeks", 0)
        if current_balance < required_balance:
            logger.warning(
                "Insufficient user balance %s to complete renewal: required %s, available %s",
                user.id,
                required_balance,
                current_balance,
            )
            return False

        description = f"Subscription renewal for {descriptor.period_days} days"

        try:
            result = await renewal_service.finalize(
                db,
                user,
                subscription,
                pricing_model,
                charge_balance_amount=required_balance,
                description=description,
                payment_method=PaymentMethod.CRYPTOBOT,
            )
        except SubscriptionRenewalChargeError as error:
            logger.error(
                "Balance charge failed while renewing via CryptoBot %s: %s",
                payment.invoice_id,
                error,
            )
            return False
        except Exception as error:
            logger.error(
                "Error finalising renewal via CryptoBot %s: %s",
                payment.invoice_id,
                error,
                exc_info=True,
            )
            return False

        transaction = result.transaction
        if transaction:
            try:
                await cryptobot_crud.link_cryptobot_payment_to_transaction(
                    db,
                    payment.invoice_id,
                    transaction.id,
                )
            except Exception as error:
                logger.warning(
                    "Failed to link CryptoBot payment %s with transaction %s: %s",
                    payment.invoice_id,
                    transaction.id,
                    error,
                )

        external_amount_label = settings.format_price(descriptor.missing_amount_kopeks)
        balance_amount_label = settings.format_price(required_balance)

        logger.info(
            "Subscription %s renewed via CryptoBot invoice %s (external payment %s, charged from balance %s)",
            subscription.id,
            payment.invoice_id,
            external_amount_label,
            balance_amount_label,
        )

        return True

    async def _deliver_admin_topup_notification(
        self, context: _AdminNotificationContext
    ) -> None:
        bot_instance = getattr(self, "bot", None)
        if not bot_instance:
            return

        try:
            from app.services.admin_notification_service import AdminNotificationService
            from app.database.crud.user import get_user_by_id
            from app.database.crud.transaction import get_transaction_by_id
        except Exception as error:
            logger.error(
                "Failed to import dependencies for CryptoBot admin notification: %s",
                error,
                exc_info=True,
            )
            return

        async with AsyncSessionLocal() as session:
            try:
                user = await get_user_by_id(session, context.user_id)
                transaction = await get_transaction_by_id(session, context.transaction_id)
            except Exception as error:
                logger.error(
                    "Error loading data for CryptoBot admin notification: %s",
                    error,
                    exc_info=True,
                )
                await session.rollback()
                return

            if not user or not transaction:
                logger.warning(
                    "Skipped CryptoBot admin notification: user=%s transaction=%s",
                    bool(user),
                    bool(transaction),
                )
                return

            notification_service = AdminNotificationService(bot_instance)
            try:
                await notification_service.send_balance_topup_notification(
                    user,
                    transaction,
                    context.old_balance,
                    topup_status=context.topup_status,
                    referrer_info=context.referrer_info,
                    subscription=getattr(user, "subscription", None),
                    promo_group=getattr(user, "promo_group", None),
                    db=session,
                )
            except Exception as error:
                logger.error(
                    "Error sending CryptoBot admin top-up notification: %s",
                    error,
                    exc_info=True,
                )

    async def _deliver_user_topup_notification(
        self, payload: _UserNotificationPayload
    ) -> None:
        bot_instance = getattr(self, "bot", None)
        if not bot_instance:
            return

        try:
            await bot_instance.send_message(
                payload.telegram_id,
                payload.text,
                parse_mode=payload.parse_mode,
                reply_markup=payload.reply_markup,
            )
            logger.info(
                "✅ Sent notification to user %s about top-up of %s RUB (%s)",
                payload.telegram_id,
                f"{payload.amount_rubles:.2f}",
                payload.asset,
            )
        except Exception as error:
            logger.error(
                "Error sending CryptoBot top-up notification: %s",
                error,
            )

    async def _deliver_saved_cart_reminder(
        self, payload: _SavedCartNotificationPayload
    ) -> None:
        bot_instance = getattr(self, "bot", None)
        if not bot_instance:
            return

        try:
            await bot_instance.send_message(
                chat_id=payload.telegram_id,
                text=payload.text,
                reply_markup=payload.reply_markup,
            )
            logger.info(
                "Sent notification with return-to-checkout button to user %s",
                payload.user_id,
            )
        except Exception as error:
            logger.error(
                "Error sending saved-cart notification for user %s: %s",
                payload.user_id,
                error,
                exc_info=True,
            )

    async def get_cryptobot_payment_status(
        self,
        db: AsyncSession,
        local_payment_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Fetches the current CryptoBot invoice status and synchronises it."""

        cryptobot_crud = import_module("app.database.crud.cryptobot")
        payment = await cryptobot_crud.get_cryptobot_payment_by_id(db, local_payment_id)
        if not payment:
            logger.warning("CryptoBot payment %s not found", local_payment_id)
            return None

        if not self.cryptobot_service:
            logger.warning("CryptoBot service is not initialised for manual check")
            return {"payment": payment}

        invoice_id = payment.invoice_id
        try:
            invoices = await self.cryptobot_service.get_invoices(
                invoice_ids=[invoice_id]
            )
        except Exception as error:  # pragma: no cover - network errors
            logger.error(
                "Error requesting CryptoBot invoice %s status: %s",
                invoice_id,
                error,
            )
            return {"payment": payment}

        remote_invoice: Optional[Dict[str, Any]] = None
        if invoices:
            for item in invoices:
                if str(item.get("invoice_id")) == str(invoice_id):
                    remote_invoice = item
                    break

        if not remote_invoice:
            logger.info(
                "CryptoBot invoice %s not found via API during manual check",
                invoice_id,
            )
            refreshed = await cryptobot_crud.get_cryptobot_payment_by_id(db, local_payment_id)
            return {"payment": refreshed or payment}

        status = (remote_invoice.get("status") or "").lower()
        paid_at_str = remote_invoice.get("paid_at")
        paid_at = None
        if paid_at_str:
            try:
                paid_at = datetime.fromisoformat(paid_at_str.replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except Exception:  # pragma: no cover - defensive parsing
                paid_at = None

        if status == "paid":
            webhook_payload = {
                "update_type": "invoice_paid",
                "payload": {
                    "invoice_id": remote_invoice.get("invoice_id") or invoice_id,
                    "amount": remote_invoice.get("amount") or payment.amount,
                    "asset": remote_invoice.get("asset") or payment.asset,
                    "paid_at": paid_at_str,
                    "payload": remote_invoice.get("payload") or payment.payload,
                },
            }
            await self.process_cryptobot_webhook(db, webhook_payload)
        else:
            if status and status != (payment.status or "").lower():
                await cryptobot_crud.update_cryptobot_payment_status(
                    db,
                    invoice_id,
                    status,
                    paid_at,
                )

        refreshed = await cryptobot_crud.get_cryptobot_payment_by_id(db, local_payment_id)
        return {"payment": refreshed or payment}
