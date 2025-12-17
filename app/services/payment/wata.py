"""Mixin for WATA integration."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from importlib import import_module
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import PaymentMethod, TransactionType
from app.services.subscription_auto_purchase_service import (
    auto_purchase_saved_cart_after_topup,
)
from app.services.wata_service import WataAPIError
from app.utils.user_utils import format_referrer_info

logger = logging.getLogger(__name__)


class WataPaymentMixin:
    """Mixin for creating WATA payment links, processing webhooks, and querying status."""

    async def create_wata_payment(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        amount_kopeks: int,
        description: str,
        language: str,
    ) -> Optional[Dict[str, Any]]:
        """Creates a payment link in WATA and saves a local record."""
        service = getattr(self, "wata_service", None)
        if not service or not service.is_configured:
            logger.error("WATA service is not initialized")
            return None

        if amount_kopeks < settings.WATA_MIN_AMOUNT_KOPEKS:
            logger.warning(
                "WATA amount is less than minimum: %s < %s",
                amount_kopeks,
                settings.WATA_MIN_AMOUNT_KOPEKS,
            )
            return None

        if amount_kopeks > settings.WATA_MAX_AMOUNT_KOPEKS:
            logger.warning(
                "WATA amount is greater than maximum: %s > %s",
                amount_kopeks,
                settings.WATA_MAX_AMOUNT_KOPEKS,
            )
            return None

        order_id = f"wata_{user_id}_{uuid.uuid4().hex}"

        payment_module = import_module("app.services.payment_service")

        try:
            response = await service.create_payment_link(
                amount_kopeks=amount_kopeks,
                order_id=order_id,
                description=description,
            )
        except WataAPIError as error:
            logger.error("WATA API error when creating payment link: %s", error)
            return None

        if not response:
            logger.error("WATA did not return a response when creating payment link")
            return None

        payment_link_id = response.get("id")
        if not payment_link_id:
            logger.error("WATA did not return payment link id: %s", response)
            return None

        payment_url = response.get("url")
        status = response.get("status", "Opened")
        payment_type = response.get("type")
        terminal_public_id = response.get("terminalPublicId")
        success_redirect_url = response.get("successRedirectUrl")
        fail_redirect_url = response.get("failRedirectUrl")
        expiration_datetime_str = response.get("expirationDateTime")

        expires_at = None
        if expiration_datetime_str:
            try:
                expires_at = service._parse_datetime(expiration_datetime_str)
            except Exception as error:
                logger.warning(
                    "Failed to parse WATA expiration datetime: %s", error
                )

        metadata_payload = {
            "user_id": user_id,
            "amount_kopeks": amount_kopeks,
            "description": description,
            "language": language,
            "raw_response": response,
        }

        payment = await payment_module.create_wata_payment(
            db,
            user_id=user_id,
            payment_link_id=payment_link_id,
            amount_kopeks=amount_kopeks,
            currency="RUB",
            description=description,
            status=status,
            type_=payment_type,
            url=payment_url,
            order_id=order_id,
            metadata=metadata_payload,
            expires_at=expires_at,
            terminal_public_id=terminal_public_id,
            success_redirect_url=success_redirect_url,
            fail_redirect_url=fail_redirect_url,
        )

        logger.info(
            "Created WATA payment link %s for user %s (%s RUB)",
            payment_link_id,
            user_id,
            amount_kopeks / 100,
        )

        return {
            "local_payment_id": payment.id,
            "payment_link_id": payment_link_id,
            "order_id": order_id,
            "amount_kopeks": amount_kopeks,
            "payment_url": payment_url,
            "status": status,
        }

    async def process_wata_webhook(
        self,
        db: AsyncSession,
        payload: Dict[str, Any],
    ) -> bool:
        """Processes webhook from WATA and credits balance on success."""
        try:
            payment_module = import_module("app.services.payment_service")

            order_id = payload.get("orderId")
            payment_link_id = payload.get("paymentLinkId") or payload.get("id")
            transaction_status = payload.get("transactionStatus")

            if not order_id and not payment_link_id:
                logger.error("WATA webhook without identifiers: %s", payload)
                return False

            payment = None
            if order_id:
                payment = await payment_module.get_wata_payment_by_order_id(
                    db, order_id
                )
            if not payment and payment_link_id:
                payment = await payment_module.get_wata_payment_by_link_id(
                    db, payment_link_id
                )

            if not payment:
                logger.error(
                    "WATA payment not found: order_id=%s, link_id=%s",
                    order_id,
                    payment_link_id,
                )
                return False

            if payment.is_paid:
                logger.info(
                    "WATA payment %s already processed", payment.payment_link_id
                )
                return True

            terminal_public_id = payload.get("terminalPublicId")
            metadata = dict(getattr(payment, "metadata_json", {}) or {})
            metadata["last_webhook"] = payload

            is_paid = transaction_status == "Paid"

            payment = await payment_module.update_wata_payment_status(
                db,
                payment,
                status=transaction_status,
                is_paid=is_paid,
                paid_at=datetime.utcnow() if is_paid else None,
                callback_payload=payload,
                terminal_public_id=terminal_public_id,
                metadata=metadata,
            )

            if is_paid:
                return await self._finalize_wata_payment(
                    db,
                    payment,
                    trigger="webhook",
                )

            logger.info(
                "Updated WATA payment %s to status %s",
                payment.payment_link_id,
                transaction_status,
            )
            return True

        except Exception as error:
            logger.error("Error processing WATA webhook: %s", error, exc_info=True)
            return False

    async def _finalize_wata_payment(
        self,
        db: AsyncSession,
        payment: Any,
        *,
        trigger: str,
    ) -> bool:
        """Creates transaction, credits balance, and sends notifications."""

        payment_module = import_module("app.services.payment_service")

        metadata = dict(getattr(payment, "metadata_json", {}) or {})
        invoice_message = metadata.get("invoice_message") or {}
        invoice_message_removed = False

        if getattr(self, "bot", None) and invoice_message:
            chat_id = invoice_message.get("chat_id")
            message_id = invoice_message.get("message_id")
            if chat_id and message_id:
                try:
                    await self.bot.delete_message(chat_id, message_id)
                except Exception as delete_error:  # pragma: no cover - depends on rights
                    logger.warning(
                        "Failed to delete WATA payment message %s: %s",
                        message_id,
                        delete_error,
                    )
                else:
                    metadata.pop("invoice_message", None)
                    invoice_message_removed = True

        if invoice_message_removed:
            try:
                await payment_module.update_wata_payment_status(
                    db,
                    payment,
                    status=payment.status,
                    metadata=metadata,
                )
                payment.metadata_json = metadata
            except Exception as error:  # pragma: no cover - diagnostics
                logger.warning(
                    "Failed to update WATA metadata after deleting message: %s",
                    error,
                )

        if payment.transaction_id:
            logger.info(
                "WATA payment %s already linked to transaction (trigger=%s)",
                payment.payment_link_id,
                trigger,
            )
            return True

        user = await payment_module.get_user_by_id(db, payment.user_id)
        if not user:
            logger.error(
                "User %s not found for WATA payment %s (trigger=%s)",
                payment.user_id,
                payment.payment_link_id,
                trigger,
            )
            return False

        transaction = await payment_module.create_transaction(
            db,
            user_id=payment.user_id,
            type=TransactionType.DEPOSIT,
            amount_kopeks=payment.amount_kopeks,
            description=f"Top-up via WATA ({payment.payment_link_id})",
            payment_method=PaymentMethod.WATA,
            external_id=payment.payment_link_id,
            is_completed=True,
        )

        await payment_module.link_wata_payment_to_transaction(
            db, payment, transaction.id
        )

        old_balance = user.balance_kopeks
        was_first_topup = not user.has_made_first_topup

        user.balance_kopeks += payment.amount_kopeks
        user.updated_at = datetime.utcnow()

        promo_group = user.get_primary_promo_group()
        subscription = getattr(user, "subscription", None)
        referrer_info = format_referrer_info(user)
        topup_status = "🆕 First top-up" if was_first_topup else "🔄 Top-up"

        await db.commit()

        try:
            from app.services.referral_service import process_referral_topup

            await process_referral_topup(
                db, user.id, payment.amount_kopeks, getattr(self, "bot", None)
            )
        except Exception as error:
            logger.error(
                "Error processing WATA referral top-up: %s",
                error,
            )

        if was_first_topup and not user.has_made_first_topup:
            user.has_made_first_topup = True
            await db.commit()

        await db.refresh(user)
        await db.refresh(payment)

        if getattr(self, "bot", None):
            try:
                from app.services.admin_notification_service import (
                    AdminNotificationService,
                )

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
            except Exception as error:
                logger.error(
                    "Error sending WATA admin notification: %s",
                    error,
                )

        if getattr(self, "bot", None):
            try:
                from app.localization.texts import get_texts

                texts = get_texts(user.language)
                keyboard = await self.build_topup_success_keyboard(user)
                message_text = texts.t(
                    "WATA_TOPUP_SUCCESS",
                    "✅ <b>Top-up successful!</b>\n\n"
                    "💰 Amount: {amount}\n"
                    "💳 Method: WATA\n"
                    "🆔 Transaction: {transaction_id}\n\n"
                    "Balance has been credited automatically!",
                ).format(
                    amount=settings.format_price(payment.amount_kopeks),
                    transaction_id=transaction.id,
                )
                await self.bot.send_message(
                    user.telegram_id,
                    message_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            except Exception as error:
                logger.error(
                    "Error sending WATA user notification: %s",
                    error,
                )

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
                        bot=getattr(self, "bot", None),
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

            if has_saved_cart and getattr(self, "bot", None):
                from app.localization.texts import get_texts

                texts = get_texts(user.language)
                cart_message = texts.t(
                    "BALANCE_TOPUP_CART_REMINDER",
                    "You have an unfinished subscription checkout. Return?",
                )

                keyboard = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=texts.t(
                                    "BALANCE_TOPUP_CART_BUTTON",
                                    "🛒 Continue checkout",
                                ),
                                callback_data="return_to_saved_cart",
                            )
                        ],
                        [
                            types.InlineKeyboardButton(
                                text=texts.t("MAIN_MENU_BUTTON", "🏠 Main menu"),
                                callback_data="back_to_menu",
                            )
                        ],
                    ]
                )

                topup_message = texts.t(
                    "WATA_TOPUP_CART_REMINDER",
                    "✅ Balance has been topped up by {amount}!\n\n"
                    "⚠️ <b>Important:</b> Topping up your balance does not activate a subscription automatically. "
                    "Be sure to activate your subscription separately!\n\n"
                    "🔄 If you have a saved subscription cart and auto-purchase is enabled, "
                    "the subscription will be purchased automatically after the top-up.\n\n{cart_message}",
                ).format(
                    amount=settings.format_price(payment.amount_kopeks),
                    cart_message=cart_message,
                )
                await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=topup_message,
                    reply_markup=keyboard,
                )
                logger.info(
                    "Sent notification with return-to-checkout button to user %s",
                    user.id,
                )
            else:
                logger.info(
                    "User %s has no saved cart or auto-purchase completed",
                    user.id,
                )
        except Exception as error:
            logger.error(
                "Error while working with saved cart for user %s: %s",
                user.id,
                error,
                exc_info=True,
            )

        logger.info(
            "✅ Processed WATA payment %s for user %s (trigger=%s)",
            payment.payment_link_id,
            payment.user_id,
            trigger,
        )

        return True

    async def get_wata_payment_status(
        self,
        db: AsyncSession,
        local_payment_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Queries current payment status from local record."""
        try:
            payment_module = import_module("app.services.payment_service")

            payment = await payment_module.get_wata_payment_by_id(
                db, local_payment_id
            )
            if not payment:
                return None

            if payment.is_paid and not payment.transaction_id:
                try:
                    finalized = await self._finalize_wata_payment(
                        db,
                        payment,
                        trigger="status_check",
                    )
                    if finalized:
                        payment = await payment_module.get_wata_payment_by_id(
                            db, local_payment_id
                        )
                except Exception as error:
                    logger.error(
                        "Error during automatic credit by WATA status: %s",
                        error,
                        exc_info=True,
                    )

            return {
                "payment": payment,
                "status": payment.status,
                "is_paid": payment.is_paid,
            }

        except Exception as error:
            logger.error("Error getting WATA status: %s", error, exc_info=True)
            return None
