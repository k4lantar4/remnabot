"""Multi-tariff subscription endpoints for cabinet API.

GET /subscriptions — list all user subscriptions (multi-tariff)
GET /subscriptions/{id} — get specific subscription details
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.subscription import (
    get_all_subscriptions_by_user_id,
    get_subscription_by_id_for_user,
)
from app.database.models import SubscriptionStatus, User

from ...dependencies import get_cabinet_db, get_current_cabinet_user


logger = structlog.get_logger(__name__)

router = APIRouter(prefix='/subscriptions', tags=['Cabinet Multi-Tariff'], redirect_slashes=False)


class SubscriptionListItem(BaseModel):
    id: int
    status: str
    tariff_id: int | None = None
    tariff_name: str | None = None
    account_sequence: int = 1
    panel_username: str | None = None
    traffic_limit_gb: int = 0
    traffic_used_gb: float = 0.0
    device_limit: int = 1
    end_date: str | None = None
    subscription_url: str | None = None
    subscription_crypto_link: str | None = None
    is_trial: bool = False
    is_daily: bool = False
    is_daily_paused: bool = False
    autopay_enabled: bool = False
    connected_squads: list[str] | None = None
    purchase_note: str | None = None
    user_disabled: bool = False


class SubscriptionsListResponse(BaseModel):
    subscriptions: list[SubscriptionListItem]
    multi_tariff_enabled: bool
    total: int = 0


def _subscription_matches_search(sub, search: str) -> bool:
    """Match panel_username, tariff name, subscription id, or purchase note."""
    q = search.strip().lower()
    if not q:
        return True
    if q.isdigit() and sub.id == int(q):
        return True
    panel_username = (getattr(sub, 'panel_username', None) or '').lower()
    if q in panel_username:
        return True
    tariff_name = (sub.tariff.name if sub.tariff else '').lower()
    if q in tariff_name:
        return True
    note = (getattr(sub, 'purchase_note', None) or '').strip().lower()
    return bool(note and q in note)


def _subscription_to_list_item(sub) -> SubscriptionListItem:
    tariff_name = None
    if sub.tariff:
        tariff_name = sub.tariff.name

    return SubscriptionListItem(
        id=sub.id,
        status=sub.actual_status,
        tariff_id=sub.tariff_id,
        tariff_name=tariff_name,
        account_sequence=getattr(sub, 'account_sequence', 1) or 1,
        panel_username=getattr(sub, 'panel_username', None) or None,
        traffic_limit_gb=sub.traffic_limit_gb or 0,
        traffic_used_gb=sub.traffic_used_gb or 0.0,
        device_limit=sub.device_limit or 1,
        end_date=sub.end_date.isoformat() if sub.end_date else None,
        subscription_url=sub.subscription_url,
        subscription_crypto_link=sub.subscription_crypto_link,
        is_trial=sub.is_trial or False,
        is_daily=bool(sub.tariff and getattr(sub.tariff, 'is_daily', False)),
        is_daily_paused=bool(getattr(sub, 'is_daily_paused', False)),
        autopay_enabled=sub.autopay_enabled or False,
        connected_squads=sub.connected_squads,
        purchase_note=getattr(sub, 'purchase_note', None),
        user_disabled=bool(getattr(sub, 'user_disabled', False)),
    )


@router.get('', response_model=SubscriptionsListResponse)
async def list_subscriptions(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    user: User = Depends(get_current_cabinet_user),
    db: AsyncSession = Depends(get_cabinet_db),
) -> SubscriptionsListResponse:
    """List user subscriptions with optional search and pagination."""
    subscriptions = await get_all_subscriptions_by_user_id(db, user.id)
    if search and search.strip():
        subscriptions = [s for s in subscriptions if _subscription_matches_search(s, search)]
    total = len(subscriptions)
    page = subscriptions[offset : offset + limit]
    items = [_subscription_to_list_item(sub) for sub in page]
    return SubscriptionsListResponse(
        subscriptions=items,
        multi_tariff_enabled=settings.is_multi_tariff_enabled(),
        total=total,
    )


@router.get('/{subscription_id}', response_model=SubscriptionListItem)
async def get_subscription_detail(
    subscription_id: int,
    user: User = Depends(get_current_cabinet_user),
    db: AsyncSession = Depends(get_cabinet_db),
) -> SubscriptionListItem:
    """Get specific subscription details with ownership check."""
    subscription = await get_subscription_by_id_for_user(db, subscription_id, user.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Subscription not found',
        )
    return _subscription_to_list_item(subscription)


@router.delete('/{subscription_id}')
async def delete_subscription(
    subscription_id: int,
    user: User = Depends(get_current_cabinet_user),
    db: AsyncSession = Depends(get_cabinet_db),
) -> dict:
    """Delete an expired/disabled subscription. Active subscriptions cannot be deleted."""
    subscription = await get_subscription_by_id_for_user(db, subscription_id, user.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Subscription not found',
        )

    # Only expired/disabled subscriptions can be deleted
    deletable_statuses = {
        SubscriptionStatus.EXPIRED.value,
        SubscriptionStatus.DISABLED.value,
    }
    if getattr(subscription, 'actual_status', subscription.status) not in deletable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Only expired or disabled subscriptions can be deleted',
        )

    from app.services.grace_access_runtime import GraceAccessDeletionBlocked
    from app.services.subscription_deletion_service import delete_subscription_record

    try:
        await delete_subscription_record(db, subscription, deleted_by='user')
    except GraceAccessDeletionBlocked as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Temporary renewal access is still active. Finish or restore grace access before deletion.',
        ) from error

    return {'message': 'Subscription deleted'}
