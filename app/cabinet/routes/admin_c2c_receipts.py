"""Cabinet admin: review card-to-card receipts (list, search, detail).

A second front end over the same ``c2c_receipts`` rows the Telegram admin group reviews. Access is by
permission (``payments:read`` to read, ``payments:edit`` to decide), not by ownership.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot_factory import create_bot
from app.cabinet.routes.media import make_media_token
from app.cabinet.schemas.c2c_receipts import (
    C2cReceiptAdminDetail,
    C2cReceiptAdminItem,
    C2cReceiptAdminListResponse,
    C2cReceiptAdminStats,
    C2cReceiptApproveRequest,
    C2cReceiptRejectRequest,
    C2cReceiptReviewerInfo,
    C2cReceiptUserInfo,
    C2cRejectReasonItem,
)
from app.config import settings
from app.database.models import C2cReceipt, User
from app.localization.texts import get_texts
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.config_helpers import get_card_by_index
from app.plugins.c2c.decision import resolved_receipt_message, sync_group_admin_message
from app.plugins.c2c.reject_reasons import get_admin_reject_button_label, get_reject_reason_codes
from app.plugins.c2c.service import C2cPaymentService
from app.utils.wire_scale import toman_from_wire_catalog, wire_catalog_kopeks

from ..dependencies import get_cabinet_db, require_permission


logger = structlog.get_logger(__name__)

router = APIRouter(prefix='/admin/c2c-receipts', tags=['Cabinet Admin C2C Receipts'])

StatusFilter = Literal['all', 'pending', 'approved', 'rejected', 'expired', 'cancelled']
MEDIA_RECEIPT_TYPES = frozenset({'photo', 'document'})

Reviewers = tuple[dict[int, User], dict[int, User]]


def _user_label(user: User) -> str:
    return user.username or user.full_name or str(user.id)


def _user_info(user: User) -> C2cReceiptUserInfo:
    full_name = ' '.join(part for part in (user.first_name, user.last_name) if part) or None
    return C2cReceiptUserInfo(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        full_name=full_name,
        email=user.email,
    )


async def _load_reviewers(db: AsyncSession, receipts: list[C2cReceipt]) -> Reviewers:
    user_ids = {r.reviewed_by_user_id for r in receipts if r.reviewed_by_user_id}
    telegram_ids = {
        r.reviewed_by_telegram_id for r in receipts if r.reviewed_by_telegram_id and not r.reviewed_by_user_id
    }
    return await c2c_crud.get_reviewer_users(db, user_ids=user_ids, telegram_ids=telegram_ids)


def _reviewer_info(receipt: C2cReceipt, reviewers: Reviewers) -> C2cReceiptReviewerInfo:
    by_id, by_telegram = reviewers
    reviewer = by_id.get(receipt.reviewed_by_user_id) or by_telegram.get(receipt.reviewed_by_telegram_id)
    if reviewer is not None:
        label = _user_label(reviewer)
    elif receipt.reviewed_by_telegram_id:
        label = str(receipt.reviewed_by_telegram_id)
    else:
        label = None
    return C2cReceiptReviewerInfo(
        user_id=receipt.reviewed_by_user_id,
        telegram_id=receipt.reviewed_by_telegram_id,
        label=label,
        via=receipt.reviewed_via,
    )


def _item_fields(receipt: C2cReceipt, reviewers: Reviewers) -> dict:
    return {
        'id': receipt.id,
        'status': receipt.status,
        'amount_kopeks': wire_catalog_kopeks(receipt.amount_kopeks),
        'amount_toman': receipt.amount_kopeks,
        'approved_amount_toman': receipt.approved_amount_kopeks,
        'card_label': receipt.card_label,
        'receipt_type': receipt.receipt_type,
        'has_receipt': receipt.receipt_type is not None,
        'created_at': receipt.created_at,
        'processed_at': receipt.processed_at,
        'expires_at': receipt.expires_at,
        'user': _user_info(receipt.user),
        'reviewer': _reviewer_info(receipt, reviewers),
        'rejection_reason_key': receipt.rejection_reason_key,
        'rejection_reason': receipt.rejection_reason,
    }


def _masked_card_number(receipt: C2cReceipt) -> str | None:
    """Last four digits of the card the receipt was issued for.

    Cards are configuration and receipts only store the rotation index, so the number is shown only
    while that index still carries the receipt's label — never a different card's digits.
    """
    card = get_card_by_index(receipt.card_index or 0)
    if not card or card['label'] != receipt.card_label:
        return None
    digits = re.sub(r'\D', '', card['number'])
    return f'**** {digits[-4:]}' if len(digits) >= 4 else None


async def build_receipt_detail(db: AsyncSession, receipt: C2cReceipt) -> C2cReceiptAdminDetail:
    reviewers = await _load_reviewers(db, [receipt])
    has_media = bool(receipt.receipt_file_id) and receipt.receipt_type in MEDIA_RECEIPT_TYPES
    return C2cReceiptAdminDetail(
        **_item_fields(receipt, reviewers),
        receipt_media_file_id=receipt.receipt_file_id if has_media else None,
        receipt_media_token=make_media_token(receipt.receipt_file_id) if has_media else None,
        receipt_text=receipt.receipt_text,
        transaction_id=receipt.transaction_id,
        user_balance_toman=receipt.user.balance_kopeks or 0,
        card_number_masked=_masked_card_number(receipt),
    )


async def load_receipt_detail(db: AsyncSession, receipt_id: int) -> C2cReceiptAdminDetail:
    receipt = await c2c_crud.get_receipt_with_user_for_admin(db, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Receipt not found')
    return await build_receipt_detail(db, receipt)


@router.get('', response_model=C2cReceiptAdminListResponse)
async def list_c2c_receipts(
    status_filter: StatusFilter = Query('all', alias='status'),
    search: str | None = Query(None, max_length=128),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_permission('payments:read')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> C2cReceiptAdminListResponse:
    filters = {'status': status_filter, 'search': search, 'date_from': date_from, 'date_to': date_to}
    total = await c2c_crud.count_receipts(db, **filters)
    receipts = await c2c_crud.search_receipts(db, **filters, limit=per_page, offset=(page - 1) * per_page)
    reviewers = await _load_reviewers(db, receipts)
    return C2cReceiptAdminListResponse(
        items=[C2cReceiptAdminItem(**_item_fields(receipt, reviewers)) for receipt in receipts],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get('/stats', response_model=C2cReceiptAdminStats)
async def c2c_receipt_stats(
    search: str | None = Query(None, max_length=128),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    admin: User = Depends(require_permission('payments:read')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> C2cReceiptAdminStats:
    counts = await c2c_crud.receipt_status_counts(db, search=search, date_from=date_from, date_to=date_to)
    return C2cReceiptAdminStats(total=sum(counts.values()), **counts)


def _admin_texts(admin: User):
    return get_texts(getattr(admin, 'language', None) or settings.DEFAULT_LANGUAGE)


def _error(status_code: int, texts, key: str, default: str, **fmt) -> HTTPException:
    message = texts.t(key, default)
    return HTTPException(status_code=status_code, detail=message.format(**fmt) if fmt else message)


def _decision_error(message: str, texts) -> HTTPException:
    """Map ``C2cPaymentService`` failure messages to HTTP; the service's strings are its contract."""
    if message == 'Already processed':
        # Decided by the other channel meanwhile: the screen refetches to show who and when.
        return _error(
            status.HTTP_409_CONFLICT,
            texts,
            'CABINET_C2C_ADMIN_ALREADY_PROCESSED',
            'This receipt has already been reviewed.',
        )
    if message in {'Receipt not found', 'User not found'}:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Receipt not found')
    logger.error('C2C receipt decision failed in the cabinet', message=message)
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Receipt decision failed')


async def _sync_group_post(db: AsyncSession, bot, receipt: C2cReceipt, admin: User) -> None:
    """Rewrite the Telegram group post to its resolved form. The money moved already: never fail here."""
    try:
        # Same label the bot records (username, else telegram id); the post prints it as @label.
        label = admin.username or str(admin.telegram_id or admin.id)
        body, keyboard = await resolved_receipt_message(db, receipt, label)
        await sync_group_admin_message(bot, receipt, status_html=body, reply_markup=keyboard)
    except Exception as error:
        logger.warning('Could not sync the C2C group post after a cabinet decision', receipt_id=receipt.id, error=error)


@router.get('/reject-reasons', response_model=list[C2cRejectReasonItem])
async def list_c2c_reject_reasons(
    admin: User = Depends(require_permission('payments:read')),
) -> list[C2cRejectReasonItem]:
    texts = _admin_texts(admin)
    return [
        C2cRejectReasonItem(code=code, label=get_admin_reject_button_label(code, texts))
        for code in get_reject_reason_codes()
    ]


@router.get('/{receipt_id}', response_model=C2cReceiptAdminDetail)
async def get_c2c_receipt(
    receipt_id: int,
    admin: User = Depends(require_permission('payments:read')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> C2cReceiptAdminDetail:
    return await load_receipt_detail(db, receipt_id)


@router.post('/{receipt_id}/approve', response_model=C2cReceiptAdminDetail)
async def approve_c2c_receipt(
    receipt_id: int,
    payload: C2cReceiptApproveRequest,
    admin: User = Depends(require_permission('payments:edit')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> C2cReceiptAdminDetail:
    texts = _admin_texts(admin)
    credit_toman = None
    if payload.amount_kopeks is not None:
        credit_toman = toman_from_wire_catalog(payload.amount_kopeks)
        if not settings.C2C_MIN_AMOUNT_KOPEKS <= credit_toman <= settings.C2C_MAX_AMOUNT_KOPEKS:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                texts,
                'CABINET_C2C_ADMIN_AMOUNT_OUT_OF_RANGE',
                'The amount must be between {min} and {max}.',
                min=texts.format_balance(settings.C2C_MIN_AMOUNT_KOPEKS),
                max=texts.format_balance(settings.C2C_MAX_AMOUNT_KOPEKS),
            )

    async with create_bot() as bot:
        success, message, receipt = await C2cPaymentService(bot).approve_receipt(
            db,
            receipt_id,
            admin.telegram_id,
            credited_amount_kopeks=credit_toman,
            reviewed_by_user_id=admin.id,
            reviewed_via='cabinet',
        )
        if not success:
            raise _decision_error(message, texts)
        await _sync_group_post(db, bot, receipt, admin)

    return await load_receipt_detail(db, receipt_id)


@router.post('/{receipt_id}/reject', response_model=C2cReceiptAdminDetail)
async def reject_c2c_receipt(
    receipt_id: int,
    payload: C2cReceiptRejectRequest,
    admin: User = Depends(require_permission('payments:edit')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> C2cReceiptAdminDetail:
    texts = _admin_texts(admin)
    if payload.reason_key not in get_reject_reason_codes():
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            texts,
            'CABINET_C2C_ADMIN_BAD_REASON',
            'Choose a valid rejection reason.',
        )

    # The comment is for admins only: the user is told the catalog reason for ``reason_key``.
    comment = (payload.comment or '').strip() or None
    async with create_bot() as bot:
        success, message, receipt = await C2cPaymentService(bot).reject_receipt(
            db,
            receipt_id,
            admin.telegram_id,
            reason=comment,
            reason_key=payload.reason_key,
            reviewed_by_user_id=admin.id,
            reviewed_via='cabinet',
        )
        if not success:
            raise _decision_error(message, texts)
        await _sync_group_post(db, bot, receipt, admin)

    return await load_receipt_detail(db, receipt_id)
