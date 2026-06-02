"""CRUD helpers for C2C receipts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def get_c2c_receipt_for_update(db: AsyncSession, receipt_id: int) -> C2cReceipt | None:
    result = await db.execute(
        select(C2cReceipt).where(C2cReceipt.id == receipt_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def user_has_pending_receipt(db: AsyncSession, user_id: int) -> bool:
    return await get_pending_receipt_for_user(db, user_id) is not None
