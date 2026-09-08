"""C2C payment orchestration (submit, approve, reject, finalize)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from aiogram import Bot
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.transaction import create_transaction, get_transaction_by_external_id
from app.database.crud.user import add_user_balance, get_user_by_id, lock_user_for_update
from app.database.models import C2cReceipt, C2cReceiptStatus, PaymentMethod, Transaction, TransactionType, User
from app.localization.texts import get_texts
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.admin_delivery import build_delivery_kwargs, send_with_admin_topic_fallback
from app.plugins.c2c.constants import (
    C2C_RECEIPT_TYPE_DOCUMENT,
    C2C_RECEIPT_TYPE_PHOTO,
    C2C_RECEIPT_TYPE_TEXT,
)
from app.plugins.c2c.admin_messages import build_c2c_admin_receipt_body
from app.plugins.c2c.keyboards import get_c2c_admin_review_keyboard
from app.services.admin_notification_service import AdminNotificationService, NotificationCategory
from app.utils.user_utils import format_referrer_info


logger = structlog.get_logger(__name__)

_fsm_storage: BaseStorage | None = None


def set_c2c_fsm_storage(storage: BaseStorage | None) -> None:
    global _fsm_storage
    _fsm_storage = storage


def get_c2c_fsm_storage() -> BaseStorage | None:
    return _fsm_storage


def c2c_external_id(receipt_id: int) -> str:
    return f'c2c:{receipt_id}'


class C2cPaymentService:
    def __init__(self, bot: Bot | None = None) -> None:
        self.bot = bot

    async def submit_receipt(
        self,
        db: AsyncSession,
        *,
        receipt: C2cReceipt,
        receipt_type: str,
        receipt_file_id: str | None,
        receipt_text: str | None,
        user_receipt_message_id: int | None,
        user: User,
    ) -> tuple[bool, str, int | None]:
        """Attach receipt payload and forward to admin chat."""
        if receipt.status != C2cReceiptStatus.PENDING.value:
            return False, 'Receipt is no longer pending', None

        admin_chat_id = settings.get_c2c_admin_chat_id()
        if not admin_chat_id or not self.bot:
            return False, 'C2C admin chat is not configured', None

        if receipt_type == C2C_RECEIPT_TYPE_TEXT and not (receipt_text or '').strip():
            return False, 'Receipt text is empty', None

        configured_c2c_raw = (settings.C2C_ADMIN_CHAT_ID or '').strip()
        if configured_c2c_raw:
            try:
                configured_c2c_id = int(configured_c2c_raw)
            except (ValueError, TypeError):
                configured_c2c_id = None
            if configured_c2c_id is not None and configured_c2c_id != admin_chat_id:
                logger.warning(
                    'C2C_ADMIN_CHAT_ID does not match resolved admin supergroup; using notifications chat',
                    configured_chat_id=configured_c2c_id,
                    resolved_chat_id=admin_chat_id,
                )

        admin_text = build_c2c_admin_receipt_body(
            receipt,
            user,
            lang=settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa',
            receipt_text=receipt_text,
        )
        keyboard = get_c2c_admin_review_keyboard(
            receipt.id,
            settings.format_balance(receipt.amount_kopeks),
        )
        notification_service = AdminNotificationService(self.bot)
        delivery_kwargs = build_delivery_kwargs(
            notification_service,
            chat_id=admin_chat_id,
            category=NotificationCategory.BALANCE,
        )
        send_kwargs: dict[str, Any] = {
            **delivery_kwargs,
            'parse_mode': 'HTML',
            'reply_markup': keyboard,
        }
        logger.info(
            'Sending C2C receipt to admin chat',
            receipt_id=receipt.id,
            chat_id=send_kwargs.get('chat_id'),
            message_thread_id=send_kwargs.get('message_thread_id'),
            forum_topics_enabled=settings.admin_forum_topics_apply_to_chat(admin_chat_id),
        )

        try:
            if receipt_type == C2C_RECEIPT_TYPE_PHOTO and receipt_file_id:
                admin_message = await send_with_admin_topic_fallback(
                    lambda kw: self.bot.send_photo(
                        photo=receipt_file_id,
                        caption=admin_text,
                        **kw,
                    ),
                    send_kwargs,
                )
            elif receipt_type == C2C_RECEIPT_TYPE_DOCUMENT and receipt_file_id:
                admin_message = await send_with_admin_topic_fallback(
                    lambda kw: self.bot.send_document(
                        document=receipt_file_id,
                        caption=admin_text,
                        **kw,
                    ),
                    send_kwargs,
                )
            elif receipt_type == C2C_RECEIPT_TYPE_TEXT:
                admin_message = await send_with_admin_topic_fallback(
                    lambda kw: self.bot.send_message(text=admin_text, **kw),
                    send_kwargs,
                )
            else:
                return False, 'Unsupported receipt type', None
        except Exception as error:
            logger.error('Failed to send C2C receipt to admin chat', receipt_id=receipt.id, error=error)
            return False, 'Failed to notify administrators', None

        receipt.receipt_type = receipt_type
        receipt.receipt_file_id = receipt_file_id
        receipt.receipt_text = receipt_text
        receipt.user_receipt_message_id = user_receipt_message_id
        receipt.admin_chat_id = admin_message.chat.id
        receipt.admin_message_id = admin_message.message_id
        receipt.expires_at = datetime.now(UTC) + timedelta(hours=settings.C2C_RECEIPT_TTL_HOURS)
        receipt.updated_at = datetime.now(UTC)
        await db.flush()
        return True, 'OK', admin_message.message_id

    async def approve_receipt(
        self,
        db: AsyncSession,
        receipt_id: int,
        admin_telegram_id: int,
        *,
        credited_amount_kopeks: int | None = None,
    ) -> tuple[bool, str, C2cReceipt | None]:
        receipt = await c2c_crud.get_c2c_receipt_for_update(db, receipt_id)
        if not receipt:
            return False, 'Receipt not found', None

        if receipt.status != C2cReceiptStatus.PENDING.value:
            return False, 'Already processed', receipt

        existing = await get_transaction_by_external_id(db, c2c_external_id(receipt_id), PaymentMethod.C2C)
        if existing:
            receipt.status = C2cReceiptStatus.APPROVED.value
            receipt.transaction_id = existing.id
            receipt.reviewed_by_telegram_id = admin_telegram_id
            receipt.processed_at = datetime.now(UTC)
            await db.commit()
            return True, 'Already credited', receipt

        user = await get_user_by_id(db, receipt.user_id)
        if not user:
            return False, 'User not found', receipt

        user = await lock_user_for_update(db, user)
        old_balance = user.balance_kopeks
        was_first_topup = not user.has_made_first_topup

        credit = credited_amount_kopeks if credited_amount_kopeks is not None else receipt.amount_kopeks
        receipt.approved_amount_kopeks = credit
        texts = get_texts(getattr(user, 'language', 'ru'))
        if credit != receipt.amount_kopeks:
            description = texts.t(
                'C2C_TOPUP_LEDGER_DESC_PARTIAL',
                'Пополнение C2C: {amount} (запрошено {requested}, чек #{receipt_id})',
            ).format(
                amount=settings.format_balance(credit),
                requested=settings.format_balance(receipt.amount_kopeks),
                receipt_id=receipt_id,
            )
        else:
            description = texts.t(
                'C2C_TOPUP_LEDGER_DESC',
                'Пополнение C2C: {amount} (чек #{receipt_id})',
            ).format(
                amount=settings.format_balance(credit),
                receipt_id=receipt_id,
            )

        balance_credit_toman = credit

        credited = await add_user_balance(
            db,
            user,
            balance_credit_toman,
            description=description,
            create_transaction=False,
            payment_method=PaymentMethod.C2C,
            commit=False,
        )
        if not credited:
            await db.rollback()
            return False, 'Failed to credit balance', receipt

        transaction = await create_transaction(
            db=db,
            user_id=user.id,
            type=TransactionType.DEPOSIT,
            amount_kopeks=balance_credit_toman,
            description=description,
            payment_method=PaymentMethod.C2C,
            external_id=c2c_external_id(receipt_id),
            commit=False,
        )

        receipt.status = C2cReceiptStatus.APPROVED.value
        receipt.transaction_id = transaction.id
        receipt.reviewed_by_telegram_id = admin_telegram_id
        receipt.processed_at = datetime.now(UTC)
        receipt.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(user)
        await db.refresh(receipt)

        await self.finalize_approved_topup(
            db,
            user,
            transaction,
            balance_credit_toman,
            old_balance=old_balance,
            was_first_topup=was_first_topup,
            send_admin_balance_notification=False,
        )
        if self.bot:
            await clear_user_c2c_fsm_state(user, bot_id=self.bot.id)
        return True, 'Approved', receipt

    async def reject_receipt(
        self,
        db: AsyncSession,
        receipt_id: int,
        admin_telegram_id: int,
        *,
        reason: str | None = None,
        reason_key: str | None = None,
        notify_user: bool = True,
    ) -> tuple[bool, str, C2cReceipt | None]:
        receipt = await c2c_crud.get_c2c_receipt_for_update(db, receipt_id)
        if not receipt:
            return False, 'Receipt not found', None

        if receipt.status != C2cReceiptStatus.PENDING.value:
            return False, 'Already processed', receipt

        if reason_key == 'silent':
            notify_user = False

        receipt.status = C2cReceiptStatus.REJECTED.value
        receipt.reviewed_by_telegram_id = admin_telegram_id
        receipt.rejection_reason_key = reason_key
        receipt.rejection_reason = reason or reason_key or 'Rejected by administrator'
        receipt.processed_at = datetime.now(UTC)
        receipt.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(receipt)

        user = await get_user_by_id(db, receipt.user_id)
        if user and user.telegram_id and self.bot and notify_user:
            from app.plugins.c2c.reject_reasons import resolve_user_reject_reason_text

            texts = get_texts(user.language)
            reason_text = resolve_user_reject_reason_text(reason_key, texts) if reason_key else None
            try:
                if reason_text:
                    message = texts.t(
                        'C2C_RECEIPT_REJECTED_REASON',
                        '❌ <b>Your card transfer receipt was rejected</b>\n\n'
                        'Receipt #{id} for {requested} was not approved.\n'
                        '<b>Reason:</b> {reason}\n\n'
                        'Contact support if you believe this is a mistake.',
                    ).format(
                        id=receipt.id,
                        requested=texts.format_balance(receipt.amount_kopeks),
                        reason=reason_text,
                    )
                else:
                    message = texts.t(
                        'C2C_RECEIPT_REJECTED',
                        '❌ <b>Your card transfer receipt was rejected</b>\n\n'
                        'Receipt #{id} for {amount} was not approved.\n'
                        'Contact support if you believe this is a mistake.',
                    ).format(id=receipt.id, amount=texts.format_balance(receipt.amount_kopeks))
                await self.bot.send_message(
                    user.telegram_id,
                    message,
                    parse_mode='HTML',
                )
            except Exception as error:
                logger.error('Failed to notify user about C2C rejection', user_id=user.id, error=error)

        if user and self.bot:
            await clear_user_c2c_fsm_state(user, bot_id=self.bot.id)
        return True, 'Rejected', receipt

    async def finalize_approved_topup(
        self,
        db: AsyncSession,
        user: User,
        transaction: Transaction,
        balance_credit_toman: int,
        *,
        old_balance: int,
        was_first_topup: bool,
        send_admin_balance_notification: bool = True,
    ) -> None:
        """Mirror post-top-up side effects from automatic gateways."""
        promo_group = user.get_primary_promo_group()
        subscription = getattr(user, 'subscription', None)
        referrer_info = format_referrer_info(user)
        topup_status = '🆕 Первое пополнение' if was_first_topup else '🔄 Пополнение'

        description_for_referral = f'Пополнение C2C: {settings.format_balance(balance_credit_toman)}'
        lower_description = description_for_referral.lower()
        allow_referral = (
            any(word in lower_description for word in ['пополнение', 'c2c', 'topup'])
            and 'бонус' not in lower_description
        )

        if allow_referral:
            try:
                from app.services.referral_service import process_referral_topup

                # Referral service expects catalog kopeks scale (÷100 → Toman).
                await process_referral_topup(db, user.id, balance_credit_toman * 100, self.bot)
            except Exception as error:
                logger.error('C2C referral topup error', user_id=user.id, error=error)

        if was_first_topup and not user.has_made_first_topup and not user.referred_by_id:
            user.has_made_first_topup = True
            await db.commit()

        await db.refresh(user)

        if self.bot:
            if send_admin_balance_notification:
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
                except Exception as error:
                    logger.error('C2C admin balance notification error', error=error)

            autopurchase_succeeded = False
            checkout_cart = None
            try:
                from app.services.payment.common import send_cart_notification_after_topup
                from app.services.user_cart_service import user_cart_service

                checkout_cart = await user_cart_service.get_user_cart(user.id)
                if checkout_cart and checkout_cart.get('return_to_cart'):
                    await user_cart_service.refresh_topup_intent(user.id)

                autopurchase_succeeded = await send_cart_notification_after_topup(
                    user, balance_credit_toman, db, self.bot
                )
            except Exception as error:
                logger.error('C2C cart notification error', user_id=user.id, error=error)

            if not autopurchase_succeeded:
                try:
                    from app.services.payment_service import PaymentService

                    payment_service = PaymentService(self.bot)
                    has_checkout_cart = bool(checkout_cart and checkout_cart.get('return_to_cart'))
                    await payment_service._send_payment_success_notification(
                        user.telegram_id,
                        balance_credit_toman,
                        user=user,
                        db=db,
                        payment_method_title=settings.get_c2c_display_name(),
                        cart_autopurchase_failed=has_checkout_cart,
                    )
                except Exception as error:
                    logger.error('C2C user success notification error', error=error)

    @staticmethod
    def _build_admin_notification_text(receipt: C2cReceipt, user: User) -> str:
        lang = settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa'
        return build_c2c_admin_receipt_body(receipt, user, lang=lang)


async def clear_user_c2c_fsm_state(user: User, *, bot_id: int | None = None) -> None:
    if not _fsm_storage or not user.telegram_id:
        return
    resolved_bot_id = bot_id
    if resolved_bot_id is None:
        return
    key = StorageKey(bot_id=resolved_bot_id, chat_id=user.telegram_id, user_id=user.telegram_id)
    try:
        await _fsm_storage.set_state(key=key, state=None)
        await _fsm_storage.set_data(key=key, data={})
    except Exception as error:
        logger.debug('Could not clear C2C FSM state', user_id=user.id, error=error)
