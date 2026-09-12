"""CRUD helpers for C2C receipts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload

from app.config import settings
from app.database.models import C2cReceipt, C2cReceiptStatus, User


async def get_pending_receipt_for_user(db: AsyncSession, user_id: int) -> C2cReceipt | None:
    result = await db.execute(
        select(C2cReceipt).where(
            C2cReceipt.user_id == user_id,
            C2cReceipt.status == C2cReceiptStatus.PENDING.value,
        )
    )
    return result.scalar_one_or_none()


async def get_pending_receipt_for_user_for_update(db: AsyncSession, user_id: int) -> C2cReceipt | None:
    """The user's pending receipt, row-locked until commit and re-read from the database.

    For callers that change a pending receipt while another request may do the same (the cabinet
    re-pricing a session while its receipt is being submitted). ``populate_existing`` matters: a
    copy already in the session's identity map would otherwise be returned unrefreshed.
    """
    result = await db.execute(
        select(C2cReceipt)
        .where(
            C2cReceipt.user_id == user_id,
            C2cReceipt.status == C2cReceiptStatus.PENDING.value,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
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
        select(C2cReceipt).options(joinedload(C2cReceipt.user)).where(C2cReceipt.id == receipt_id)
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
    result = await db.execute(select(func.count()).select_from(C2cReceipt).where(*_reviewable_pending_filters()))
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
        select(func.count()).select_from(C2cReceipt).where(C2cReceipt.status == C2cReceiptStatus.PENDING.value)
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


# ---- cabinet admin review: search over every receipt ----------------------------------------

_SEARCH_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
_INT32_MAX = 2**31 - 1
_INT64_MAX = 2**63 - 1  # beyond bigint the driver cannot even bind the value


def _receipt_search_clause(term: str):
    """Match a receipt by ``#id``, a number (receipt/user/telegram id, exact Toman amount) or user text."""
    normalized = term.translate(_SEARCH_DIGITS)
    if normalized.startswith('#') and normalized[1:].isdigit():
        return C2cReceipt.id == int(normalized[1:])

    digits = normalized.replace(',', '').replace('٬', '').replace(' ', '')
    if digits.isdigit():
        number = int(digits)
        if number > _INT64_MAX:
            return false()
        clauses = [User.telegram_id == number]
        if number <= _INT32_MAX:
            clauses += [C2cReceipt.id == number, User.id == number, C2cReceipt.amount_kopeks == number]
        return or_(*clauses)

    text = normalized.lstrip('@').replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    pattern = f'%{text}%'
    full_name = func.coalesce(User.first_name, '') + ' ' + func.coalesce(User.last_name, '')
    return or_(
        User.username.ilike(pattern, escape='\\'),
        User.first_name.ilike(pattern, escape='\\'),
        User.last_name.ilike(pattern, escape='\\'),
        User.email.ilike(pattern, escape='\\'),
        full_name.ilike(pattern, escape='\\'),
    )


def _receipt_search_filters(
    *,
    status: str | None,
    search: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list:
    filters = []
    if status and status != 'all':
        filters.append(C2cReceipt.status == status)
    if date_from is not None:
        filters.append(C2cReceipt.created_at >= date_from)
    if date_to is not None:
        filters.append(C2cReceipt.created_at < date_to)
    term = (search or '').strip()
    if term:
        filters.append(_receipt_search_clause(term))
    return filters


async def search_receipts(
    db: AsyncSession,
    *,
    status: str | None = 'all',
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int,
    offset: int,
) -> list[C2cReceipt]:
    filters = _receipt_search_filters(status=status, search=search, date_from=date_from, date_to=date_to)
    result = await db.execute(
        select(C2cReceipt)
        .join(User, C2cReceipt.user_id == User.id)
        .options(contains_eager(C2cReceipt.user))
        .where(*filters)
        .order_by(C2cReceipt.created_at.desc(), C2cReceipt.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().unique().all())


async def count_receipts(
    db: AsyncSession,
    *,
    status: str | None = 'all',
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    filters = _receipt_search_filters(status=status, search=search, date_from=date_from, date_to=date_to)
    result = await db.execute(
        select(func.count(C2cReceipt.id))
        .select_from(C2cReceipt)
        .join(User, C2cReceipt.user_id == User.id)
        .where(*filters)
    )
    return int(result.scalar_one() or 0)


async def receipt_status_counts(
    db: AsyncSession,
    *,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, int]:
    """Per-status counts of the filtered set, every status present (zero when absent)."""
    filters = _receipt_search_filters(status='all', search=search, date_from=date_from, date_to=date_to)
    result = await db.execute(
        select(C2cReceipt.status, func.count(C2cReceipt.id))
        .select_from(C2cReceipt)
        .join(User, C2cReceipt.user_id == User.id)
        .where(*filters)
        .group_by(C2cReceipt.status)
    )
    counts = {status.value: 0 for status in C2cReceiptStatus}
    for status, count in result.all():
        counts[status] = int(count)
    return counts


async def get_receipt_with_user_for_admin(db: AsyncSession, receipt_id: int) -> C2cReceipt | None:
    result = await db.execute(
        select(C2cReceipt)
        .options(joinedload(C2cReceipt.user))
        .where(C2cReceipt.id == receipt_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_reviewer_users(
    db: AsyncSession,
    *,
    user_ids: set[int],
    telegram_ids: set[int],
) -> tuple[dict[int, User], dict[int, User]]:
    """Reviewers by ``users.id`` and by telegram id (receipts decided in the bot before 0119)."""
    clauses = []
    if user_ids:
        clauses.append(User.id.in_(user_ids))
    if telegram_ids:
        clauses.append(User.telegram_id.in_(telegram_ids))
    if not clauses:
        return {}, {}
    result = await db.execute(select(User).where(or_(*clauses)))
    users = list(result.scalars().all())
    by_id = {user.id: user for user in users if user.id in user_ids}
    by_telegram = {user.telegram_id: user for user in users if user.telegram_id in telegram_ids}
    return by_id, by_telegram
