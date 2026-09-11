"""Return a committed balance debit when the purchase it paid for was not delivered.

``subtract_user_balance`` commits the debit on its own, so a purchase that fails afterwards keeps the
user's money unless it is refunded. Callers track two flags (charged / delivered, as the admin buy in
``app/handlers/admin/users.py`` does) and call this only when the debit committed and delivery didn't:
a blanket except-refund would also refund a delivered purchase whose final message failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Transaction, TransactionType, User


logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PromoOfferSnapshot:
    """The promo-offer fields a ``consume_promo_offer=True`` debit is about to zero."""

    percent: int
    source: str | None
    expires_at: datetime | None


def snapshot_promo_offer(user: User, consume: bool) -> PromoOfferSnapshot | None:
    """Take this right before ``subtract_user_balance(..., consume_promo_offer=consume)``.

    ``None`` when the debit won't consume anything, so a refund has nothing to give back.
    """
    if not consume:
        return None
    try:
        percent = int(getattr(user, 'promo_offer_discount_percent', 0) or 0)
    except (TypeError, ValueError):
        return None
    if percent <= 0:
        return None
    return PromoOfferSnapshot(
        percent=percent,
        source=getattr(user, 'promo_offer_discount_source', None),
        expires_at=getattr(user, 'promo_offer_discount_expires_at', None),
    )


async def restore_promo_offer(db: AsyncSession, user: User, snapshot: PromoOfferSnapshot | None) -> None:
    """Give back the offer a refunded debit consumed; the caller's refund commits it.

    Flushed, not committed: ``add_user_balance`` reloads the user with ``populate_existing``, which would
    silently drop unflushed attribute changes (autoflush is off), and it commits the flushed ones together
    with the refund.
    """
    if snapshot is None:
        return
    user.promo_offer_discount_percent = snapshot.percent
    user.promo_offer_discount_source = snapshot.source
    user.promo_offer_discount_expires_at = snapshot.expires_at
    await db.flush()


async def refund_undelivered_debit(
    db: AsyncSession,
    user: User,
    amount_toman: int,
    reason: str,
    *,
    promo_snapshot: PromoOfferSnapshot | None = None,
) -> bool:
    """Roll back the half-done purchase, then credit ``amount_toman`` back as a ``refund`` row.

    The rollback drops pending, unpaid changes (``add_user_balance`` commits the session, and so would the
    bot middleware). It expires ``user``, so the user is reloaded before ``add_user_balance`` reads ``user.id``
    — without that the refund dies on MissingGreenlet. ``reason`` must be built before the rollback too.
    ``promo_snapshot`` (from ``snapshot_promo_offer``) puts back the promo offer the debit consumed, in the
    same commit as the money. A refund that still fails is recorded as a ``failed_refund`` row from a fresh session.
    """
    from app.database.crud.user import add_user_balance

    identity = sa_inspect(user).identity  # readable without a load, unlike an expired user.id
    user_id = identity[0] if identity else None
    try:
        await db.rollback()
        await db.refresh(user)
        await restore_promo_offer(db, user, promo_snapshot)
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
