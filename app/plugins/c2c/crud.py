"""CRUD helpers for C2C receipts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.database.models import C2cReceipt, C2cReceiptStatus


async def get_pending_receipt_for_user(db: AsyncSession, user_id: int) -> C2cReceipt | None:
    result = await db.execute(
        select(C2cReceipt).where(
            C2cReceipt.user_id == user_id,
            C2cReceipt.status == C2cReceiptStatus.PENDING.value,
        )
    )
    return result.scalar_one_or_none()


async def create_pending_receipt(
    db: AsyncSession,
    *,
    user_id: int,
    amount_kopeks: int,
    card_index: int,
    card_label: str | None,
) -> C2cReceipt:
    expires_at = datetime.now(UTC) + timedelta(hours=settings.C2C_RECEIPT_TTL_HOURS)
    receipt = C2cReceipt(
        user_id=user_id,
        amount_kopeks=amount_kopeks,
        status=C2cReceiptStatus.PENDING.value,
        card_index=card_index,
        card_label=card_label,
        expires_at=expires_at,
    )
    db.add(receipt)
    await db.flush()
    await db.refresh(receipt)
    return receipt


async def get_c2c_receipt_by_id(db: AsyncSession, receipt_id: int) -> C2cReceipt | None:
    result = await db.execute(select(C2cReceipt).where(C2cReceipt.id == receipt_id))
    return result.scalar_one_or_none()


async def get_c2c_receipt_with_user(db: AsyncSession, receipt_id: int) -> C2cReceipt | None:
    result = await db.execute(
        select(C2cReceipt)
        .options(joinedload(C2cReceipt.user))
        .where(C2cReceipt.id == receipt_id)
    )
    return result.scalar_one_or_none()


async def get_c2c_receipt_for_update(db: AsyncSession, receipt_id: int) -> C2cReceipt | None:
    result = await db.execute(select(C2cReceipt).where(C2cReceipt.id == receipt_id).with_for_update())
    return result.scalar_one_or_none()


async def user_has_pending_receipt(db: AsyncSession, user_id: int) -> bool:
    return await get_pending_receipt_for_user(db, user_id) is not None


async def get_reviewable_pending_receipt_for_user(db: AsyncSession, user_id: int) -> C2cReceipt | None:
    pending = await get_pending_receipt_for_user(db, user_id)
    if pending and is_reviewable_pending_receipt(pending):
        return pending
    return None


def is_reviewable_pending_receipt(receipt: C2cReceipt) -> bool:
    return (
        receipt.status == C2cReceiptStatus.PENDING.value
        and receipt.receipt_type is not None
        and receipt.admin_message_id is not None
    )


def _reviewable_pending_filters():
    return (
        C2cReceipt.status == C2cReceiptStatus.PENDING.value,
        C2cReceipt.receipt_type.isnot(None),
        C2cReceipt.admin_message_id.isnot(None),
    )


async def count_reviewable_pending_receipts(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(C2cReceipt)
        .where(*_reviewable_pending_filters())
    )
    return int(result.scalar_one() or 0)


async def list_reviewable_pending_receipts(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> list[C2cReceipt]:
    result = await db.execute(
        select(C2cReceipt)
        .options(joinedload(C2cReceipt.user))
        .where(*_reviewable_pending_filters())
        .order_by(C2cReceipt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().unique().all())


async def count_pending_receipts(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(C2cReceipt)
        .where(C2cReceipt.status == C2cReceiptStatus.PENDING.value)
    )
    return int(result.scalar_one() or 0)


async def list_pending_receipts(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> list[C2cReceipt]:
    result = await db.execute(
        select(C2cReceipt)
        .options(joinedload(C2cReceipt.user))
        .where(C2cReceipt.status == C2cReceiptStatus.PENDING.value)
        .order_by(C2cReceipt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().unique().all())


def resolve_stale_receipt_status(receipt: C2cReceipt) -> str:
    if receipt.receipt_type is None or receipt.admin_message_id is None:
        return C2cReceiptStatus.CANCELLED.value
    return C2cReceiptStatus.EXPIRED.value


async def expire_stale_c2c_receipts(db: AsyncSession) -> int:
    now = datetime.now(UTC)
    result = await db.execute(
        select(C2cReceipt).where(
            C2cReceipt.status == C2cReceiptStatus.PENDING.value,
            C2cReceipt.expires_at.isnot(None),
            C2cReceipt.expires_at < now,
        )
    )
    rows = list(result.scalars().all())
    if not rows:
        return 0

    for receipt in rows:
        receipt.status = resolve_stale_receipt_status(receipt)
        receipt.processed_at = now
        receipt.updated_at = now

    await db.flush()
    return len(rows)
