"""Return a committed balance debit when the purchase it paid for was not delivered.

``subtract_user_balance`` commits the debit on its own, so a purchase that fails afterwards keeps the
user's money unless it is refunded. Callers track two flags (charged / delivered, as the admin buy in
``app/handlers/admin/users.py`` does) and call this only when the debit committed and delivery didn't:
a blanket except-refund would also refund a delivered purchase whose final message failed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Transaction, TransactionType, User


logger = structlog.get_logger(__name__)


async def refund_undelivered_debit(db: AsyncSession, user: User, amount_toman: int, reason: str) -> bool:
    """Roll back the half-done purchase, then credit ``amount_toman`` back as a ``refund`` row.

    The rollback drops pending, unpaid changes (``add_user_balance`` commits the session, and so would the
    bot middleware). It expires ``user``, so the user is reloaded before ``add_user_balance`` reads ``user.id``
    — without that the refund dies on MissingGreenlet. ``reason`` must be built before the rollback too.
    A refund that still fails is recorded as a ``failed_refund`` row from a fresh session.
    """
    from app.database.crud.user import add_user_balance

    identity = sa_inspect(user).identity  # readable without a load, unlike an expired user.id
    user_id = identity[0] if identity else None
    try:
        await db.rollback()
        await db.refresh(user)
        refunded = await add_user_balance(
            db, user, amount_toman, reason, create_transaction=True, transaction_type=TransactionType.REFUND
        )
        if not refunded:
            raise RuntimeError('add_user_balance returned False')
        return True
    except Exception as refund_error:
        logger.critical(
            'CRITICAL: refund of an undelivered purchase failed, manual correction needed',
            user_id=user_id,
            amount_toman=amount_toman,
            reason=reason,
            refund_error=refund_error,
        )
        await _record_failed_refund(user_id, amount_toman, reason, refund_error)
        return False


async def _record_failed_refund(user_id: int | None, amount_toman: int, reason: str, error: Exception) -> None:
    if user_id is None:
        return
    from app.database.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            session.add(
                Transaction(
                    user_id=user_id,
                    type=TransactionType.FAILED_REFUND.value,
                    amount_kopeks=amount_toman,
                    description=f'{reason} | error: {error}',
                    is_completed=False,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
    except Exception as persist_error:
        logger.critical(
            'Could not record failed_refund, manual correction needed',
            user_id=user_id,
            amount_toman=amount_toman,
            reason=reason,
            persist_error=persist_error,
        )
