"""C2C payment orchestration (submit, approve, reject, finalize)."""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Any

import structlog
from aiogram import Bot
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.transaction import create_transaction, get_transaction_by_external_id
from app.database.crud.user import add_user_balance, get_user_by_id, lock_user_for_update
from app.database.models import C2cReceipt, C2cReceiptStatus, PaymentMethod, Transaction, TransactionType, User
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.constants import (
    C2C_RECEIPT_TYPE_DOCUMENT,
    C2C_RECEIPT_TYPE_PHOTO,
    C2C_RECEIPT_TYPE_TEXT,
)
from app.plugins.c2c.admin_delivery import build_delivery_kwargs, send_with_admin_topic_fallback
from app.plugins.c2c.keyboards import get_c2c_admin_review_keyboard
from app.services.admin_notification_service import AdminNotificationService, NotificationCategory
from app.utils.user_utils import format_referrer_info


logger = structlog.get_logger(__name__)

_fsm_storage: BaseStorage | None = None


def set_c2c_fsm_storage(storage: BaseStorage | None) -> None:
    global _fsm_storage
    _fsm_storage = storage


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

        receipt.receipt_type = receipt_type
        receipt.receipt_file_id = receipt_file_id
        receipt.receipt_text = receipt_text
        receipt.user_receipt_message_id = user_receipt_message_id
        receipt.updated_at = datetime.now(UTC)
        await db.flush()

        admin_chat_id = settings.get_c2c_admin_chat_id()
        if not admin_chat_id or not self.bot:
            return False, 'C2C admin chat is not configured', None

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

        if receipt_type == C2C_RECEIPT_TYPE_TEXT and not (receipt_text or '').strip():
            return False, 'Receipt text is empty', None

        admin_text = self._build_admin_notification_text(receipt, user)
        keyboard = get_c2c_admin_review_keyboard(receipt.id)
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
                body = admin_text
                if receipt_text:
                    safe_receipt = html.escape(receipt_text)
                    from app.localization.texts import get_texts

                    lang = settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa'
                    attach_label = get_texts(lang).t('ADMIN_NOTIFY_C2C_RECEIPT_ATTACH', '📎 <b>Receipt:</b>')
                    body = f'{admin_text}\n\n{attach_label}\n{safe_receipt}'
                admin_message = await send_with_admin_topic_fallback(
                    lambda kw: self.bot.send_message(text=body, **kw),
                    send_kwargs,
                )
            else:
                return False, 'Unsupported receipt type', None
        except Exception as error:
            logger.error('Failed to send C2C receipt to admin chat', receipt_id=receipt.id, error=error)
            return False, 'Failed to notify administrators', None

        receipt.admin_chat_id = admin_message.chat.id
        receipt.admin_message_id = admin_message.message_id
        await db.flush()
        return True, 'OK', admin_message.message_id

    async def approve_receipt(
        self,
        db: AsyncSession,
        receipt_id: int,
        admin_telegram_id: int,
    ) -> tuple[bool, str, C2cReceipt | None]:
        receipt = await c2c_crud.get_c2c_receipt_for_update(db, receipt_id)
        if not receipt:
            return False, 'Receipt not found', None

        if receipt.status != C2cReceiptStatus.PENDING.value:
            return False, 'Already processed', receipt

        existing = await get_transaction_by_external_id(
            db, c2c_external_id(receipt_id), PaymentMethod.C2C
        )
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

        description = (
            f'Card-to-card top-up: {settings.format_price(receipt.amount_kopeks)} (receipt #{receipt_id})'
        )

        credited = await add_user_balance(
            db,
            user,
            receipt.amount_kopeks,
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
            amount_kopeks=receipt.amount_kopeks,
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
            receipt.amount_kopeks,
            old_balance=old_balance,
            was_first_topup=was_first_topup,
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
    ) -> tuple[bool, str, C2cReceipt | None]:
        receipt = await c2c_crud.get_c2c_receipt_for_update(db, receipt_id)
        if not receipt:
            return False, 'Receipt not found', None

        if receipt.status != C2cReceiptStatus.PENDING.value:
            return False, 'Already processed', receipt

        receipt.status = C2cReceiptStatus.REJECTED.value
        receipt.reviewed_by_telegram_id = admin_telegram_id
        receipt.rejection_reason = reason or 'Rejected by administrator'
        receipt.processed_at = datetime.now(UTC)
        receipt.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(receipt)

        user = await get_user_by_id(db, receipt.user_id)
        if user and user.telegram_id and self.bot:
            from app.localization.texts import get_texts

            texts = get_texts(user.language)
            try:
                await self.bot.send_message(
                    user.telegram_id,
                    texts.t(
                        'C2C_RECEIPT_REJECTED',
                        '❌ <b>Your card transfer receipt was rejected</b>\n\n'
                        'Receipt #{id} for {amount} was not approved.\n'
                        'Contact support if you believe this is a mistake.',
                    ).format(id=receipt.id, amount=texts.format_price(receipt.amount_kopeks)),
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
        amount_kopeks: int,
        *,
        old_balance: int,
        was_first_topup: bool,
    ) -> None:
        """Mirror post-top-up side effects from automatic gateways."""
        promo_group = user.get_primary_promo_group()
        subscription = getattr(user, 'subscription', None)
        referrer_info = format_referrer_info(user)
        topup_status = '🆕 Первое пополнение' if was_first_topup else '🔄 Пополнение'

        description_for_referral = f'Пополнение C2C: {settings.format_price(amount_kopeks)}'
        lower_description = description_for_referral.lower()
        allow_referral = any(word in lower_description for word in ['пополнение', 'c2c', 'topup']) and 'бонус' not in lower_description

        if allow_referral:
            try:
                from app.services.referral_service import process_referral_topup

                await process_referral_topup(db, user.id, amount_kopeks, self.bot)
            except Exception as error:
                logger.error('C2C referral topup error', user_id=user.id, error=error)

        if was_first_topup and not user.has_made_first_topup and not user.referred_by_id:
            user.has_made_first_topup = True
            await db.commit()

        await db.refresh(user)

        if self.bot:
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

            try:
                from app.services.payment_service import PaymentService

                payment_service = PaymentService(self.bot)
                await payment_service._send_payment_success_notification(
                    user.telegram_id,
                    amount_kopeks,
                    user=user,
                    db=db,
                    payment_method_title=settings.get_c2c_display_name(),
                )
            except Exception as error:
                logger.error('C2C user success notification error', error=error)

        try:
            from app.services.payment.common import send_cart_notification_after_topup

            await send_cart_notification_after_topup(user, amount_kopeks, db, self.bot)
        except Exception as error:
            logger.error('C2C cart notification error', user_id=user.id, error=error)

    @staticmethod
    def _build_admin_notification_text(receipt: C2cReceipt, user: User) -> str:
        from app.localization.texts import get_texts

        lang = settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa'
        texts = get_texts(lang)
        name = user.full_name or user.username or f'User {user.id}'
        telegram_id = user.telegram_id or '—'
        card_label = receipt.card_label or '—'
        return '\n'.join(
            [
                texts.t('ADMIN_NOTIFY_C2C_TITLE', '🔔 <b>C2C Receipt #{receipt_id}</b>').format(receipt_id=receipt.id),
                texts.t('ADMIN_NOTIFY_C2C_USER', '👤 <b>User:</b> {name} (ID: {telegram_id})').format(
                    name=name, telegram_id=telegram_id
                ),
                texts.t('ADMIN_NOTIFY_C2C_AMOUNT', '💰 <b>Amount:</b> {amount}').format(
                    amount=settings.format_price(receipt.amount_kopeks)
                ),
                texts.t('ADMIN_NOTIFY_C2C_CARD', '💳 <b>Card shown:</b> {card}').format(card=card_label),
            ]
        )


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
