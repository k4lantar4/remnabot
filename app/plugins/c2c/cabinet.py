"""Cabinet adapter for card-to-card top-ups.

The bot adapter is ``handlers/user.py``; this is its HTTP twin. Both sit on the same crud and
``C2cPaymentService``, so a receipt started in the cabinet is forwarded to the admin group and
reviewed exactly like one sent to the bot, and the one-pending-receipt-per-user rule holds across
both. Amounts here are Toman 1:1 (the database scale); the cabinet's x100 wire scale is converted by
the route in ``app/cabinet/routes/balance.py``, never here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot_factory import create_bot
from app.config import settings
from app.database.models import C2cReceipt, C2cReceiptStatus, User
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.config_helpers import C2cCard, get_card_by_index, get_next_card
from app.plugins.c2c.constants import (
    C2C_RECEIPT_TYPE_DOCUMENT,
    C2C_RECEIPT_TYPE_PHOTO,
    C2C_RECEIPT_TYPE_TEXT,
)
from app.plugins.c2c.reject_reasons import C2C_REJECT_REASONS, resolve_user_reject_reason_text
from app.plugins.c2c.service import C2cPaymentService
from app.services.user_cart_service import user_cart_service


logger = structlog.get_logger(__name__)

# Error codes; the route maps each one to an HTTP status and a localized message.
UNAVAILABLE = 'unavailable'
ALREADY_SUBMITTED = 'already_submitted'
EMPTY = 'empty'
NOT_FOUND = 'not_found'
ADMIN_UNREACHABLE = 'admin_unreachable'


class C2cCabinetError(Exception):
    def __init__(self, code: str, *, receipt: C2cReceipt | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.receipt = receipt


def has_receipt(receipt: C2cReceipt) -> bool:
    return receipt.receipt_type is not None


def card_for_receipt(receipt: C2cReceipt) -> C2cCard | None:
    return get_card_by_index(receipt.card_index)


def rejection_reason_for_user(receipt: C2cReceipt, texts) -> str | None:
    """The reason the user is shown, resolved the way the bot's rejection message resolves it."""
    key = getattr(receipt, 'rejection_reason_key', None)
    if key and key in C2C_REJECT_REASONS:
        return resolve_user_reject_reason_text(key, texts)
    return receipt.rejection_reason


async def _own_open_pending(db: AsyncSession, user: User, receipt_id: int) -> C2cReceipt:
    # Locked until the caller commits: a parallel session must not re-price the receipt while it is
    # being submitted, or the admin would approve an amount other than the one in their message.
    pending = await c2c_crud.get_pending_receipt_for_user_for_update(db, user.id)
    if not pending or pending.id != receipt_id:
        raise C2cCabinetError(NOT_FOUND)
    if has_receipt(pending):
        raise C2cCabinetError(ALREADY_SUBMITTED, receipt=pending)
    return pending


async def start_cabinet_receipt(db: AsyncSession, user: User, amount_toman: int) -> C2cReceipt:
    """Assign the next card and hold the user's single pending receipt for ``amount_toman``.

    Mirrors ``process_c2c_payment_amount``: a pending receipt without an attachment is re-priced and
    re-carded instead of inserting a second one; one that already carries a receipt is left alone.
    The amount range is checked by the route against the method's configured limits.
    """
    try:
        card, card_index = await get_next_card()
    except ValueError as error:
        raise C2cCabinetError(UNAVAILABLE) from error

    await c2c_crud.expire_stale_c2c_receipts(db)
    await db.commit()

    for attempt in range(2):
        pending = await c2c_crud.get_pending_receipt_for_user_for_update(db, user.id)
        if pending:
            if has_receipt(pending):
                raise C2cCabinetError(ALREADY_SUBMITTED, receipt=pending)
            now = datetime.now(UTC)
            pending.amount_kopeks = amount_toman
            pending.card_index = card_index
            pending.card_label = card.get('label')
            pending.expires_at = now + timedelta(hours=settings.C2C_RECEIPT_TTL_HOURS)
            pending.updated_at = now
            await db.flush()
            await db.commit()
            return pending
        try:
            receipt = await c2c_crud.create_pending_receipt(
                db,
                user_id=user.id,
                amount_kopeks=amount_toman,
                card_index=card_index,
                card_label=card.get('label'),
            )
        except IntegrityError:
            # A parallel session inserted this user's pending receipt first
            # (uq_c2c_receipts_user_pending): re-price that one instead of failing.
            await db.rollback()
            if attempt:
                raise
            continue
        await db.commit()
        return receipt

    raise AssertionError('unreachable')  # pragma: no cover


async def attach_cabinet_receipt(
    db: AsyncSession,
    user: User,
    receipt_id: int,
    *,
    media_file_id: str | None,
    media_type: str | None,
    text: str | None,
) -> C2cReceipt:
    """Attach an uploaded image (Telegram ``file_id``) and/or a note, and forward it for review."""
    pending = await _own_open_pending(db, user, receipt_id)

    note = (text or '').strip() or None
    if media_file_id:
        receipt_type = C2C_RECEIPT_TYPE_DOCUMENT if media_type == 'document' else C2C_RECEIPT_TYPE_PHOTO
    elif note:
        receipt_type = C2C_RECEIPT_TYPE_TEXT
    else:
        raise C2cCabinetError(EMPTY)

    async with create_bot() as bot:
        success, reason, _admin_message_id = await C2cPaymentService(bot).submit_receipt(
            db,
            receipt=pending,
            receipt_type=receipt_type,
            receipt_file_id=media_file_id or None,
            receipt_text=note,
            user_receipt_message_id=None,
            user=user,
        )
    if not success:
        logger.warning('Cabinet C2C receipt was not forwarded', receipt_id=pending.id, reason=reason)
        raise C2cCabinetError(ADMIN_UNREACHABLE)

    await db.commit()

    try:
        await user_cart_service.refresh_topup_intent(user.id)
    except Exception as error:
        logger.warning('Could not refresh top-up intent after C2C receipt', user_id=user.id, error=error)
    return pending


async def current_cabinet_receipt(
    db: AsyncSession,
    user: User,
    *,
    receipt_id: int | None = None,
) -> C2cReceipt | None:
    """The user's pending receipt, or — when polling one receipt — that receipt in any status."""
    if receipt_id is None:
        return await c2c_crud.get_pending_receipt_for_user(db, user.id)
    receipt = await c2c_crud.get_c2c_receipt_by_id(db, receipt_id)
    if receipt is None or receipt.user_id != user.id:
        return None
    return receipt


async def cancel_cabinet_receipt(db: AsyncSession, user: User, receipt_id: int) -> C2cReceipt:
    """Cancel a pending receipt the user has not attached anything to yet."""
    pending = await _own_open_pending(db, user, receipt_id)
    now = datetime.now(UTC)
    pending.status = C2cReceiptStatus.CANCELLED.value
    pending.processed_at = now
    pending.updated_at = now
    await db.commit()
    return pending
