"""Multi-tariff subscription endpoints for cabinet API.

GET /subscriptions — list all user subscriptions (multi-tariff)
GET /subscriptions/{id} — get specific subscription details
PATCH /subscriptions/{id}/note — update purchase note
POST /subscriptions/{id}/disable — user-initiated disable
POST /subscriptions/{id}/enable — user-initiated enable (no payment)
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.subscription import (
    decrement_subscription_server_counts,
    get_all_subscriptions_by_user_id,
    get_subscription_by_id_for_user,
)
from app.database.models import SubscriptionStatus, User
from app.services.partner_checkout import sanitize_purchase_note
from app.services.subscription_user_toggle_service import (
    SubscriptionToggleError,
    disable_user_subscription,
    enable_user_subscription,
)
from app.utils.autopay_utils import effective_autopay_enabled

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


class PurchaseNoteUpdateRequest(BaseModel):
    purchase_note: str | None = Field(None, max_length=500)


class SubscriptionToggleResponse(BaseModel):
    success: bool = True
    status: str
    user_disabled: bool


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
        autopay_enabled=effective_autopay_enabled(sub),
        connected_squads=sub.connected_squads,
        purchase_note=getattr(sub, 'purchase_note', None),
        user_disabled=bool(getattr(sub, 'user_disabled', False)),
    )


async def _get_owned_subscription(
    db: AsyncSession,
    subscription_id: int,
    user: User,
):
    subscription = await get_subscription_by_id_for_user(db, subscription_id, user.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Subscription not found',
        )
    return subscription


def _toggle_http_error(exc: SubscriptionToggleError) -> HTTPException:
    code_map = {
        'not_active': status.HTTP_400_BAD_REQUEST,
        'not_user_disabled': status.HTTP_400_BAD_REQUEST,
        'not_disabled': status.HTTP_400_BAD_REQUEST,
        'expired': status.HTTP_400_BAD_REQUEST,
        'panel_error': status.HTTP_502_BAD_GATEWAY,
    }
    return HTTPException(
        status_code=code_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=exc.message,
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


@router.patch('/{subscription_id}/note', response_model=SubscriptionListItem)
async def update_subscription_note(
    subscription_id: int,
    body: PurchaseNoteUpdateRequest,
    user: User = Depends(get_current_cabinet_user),
    db: AsyncSession = Depends(get_cabinet_db),
) -> SubscriptionListItem:
    """Update purchase note on a subscription (all users)."""
    subscription = await _get_owned_subscription(db, subscription_id, user)
    subscription.purchase_note = sanitize_purchase_note(body.purchase_note)
    subscription.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(subscription)
    return _subscription_to_list_item(subscription)


@router.post('/{subscription_id}/disable', response_model=SubscriptionToggleResponse)
async def disable_subscription(
    subscription_id: int,
    user: User = Depends(get_current_cabinet_user),
    db: AsyncSession = Depends(get_cabinet_db),
) -> SubscriptionToggleResponse:
    """Disable an active subscription (user toggle)."""
    subscription = await _get_owned_subscription(db, subscription_id, user)
    try:
        subscription = await disable_user_subscription(db, subscription, user)
    except SubscriptionToggleError as exc:
        raise _toggle_http_error(exc) from exc
    return SubscriptionToggleResponse(
        status=subscription.actual_status,
        user_disabled=bool(subscription.user_disabled),
    )


@router.post('/{subscription_id}/enable', response_model=SubscriptionToggleResponse)
async def enable_subscription(
    subscription_id: int,
    user: User = Depends(get_current_cabinet_user),
    db: AsyncSession = Depends(get_cabinet_db),
) -> SubscriptionToggleResponse:
    """Re-enable a user-disabled subscription without payment."""
    subscription = await _get_owned_subscription(db, subscription_id, user)
    try:
        subscription = await enable_user_subscription(db, subscription, user)
    except SubscriptionToggleError as exc:
        raise _toggle_http_error(exc) from exc
    return SubscriptionToggleResponse(
        status=subscription.actual_status,
        user_disabled=bool(subscription.user_disabled),
    )


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

    # Delete from RemnaWave panel (stops webhooks / phantom notifications)
    if subscription.remnawave_uuid:
        try:
            from app.services.subscription_service import SubscriptionService

            service = SubscriptionService()
            await service.delete_remnawave_user(subscription.remnawave_uuid)
        except Exception as e:
            logger.warning('Failed to delete RemnaWave user on subscription delete', error=e)

    # Decrement server counts
    await decrement_subscription_server_counts(db, subscription)

    # Delete the subscription
    await db.delete(subscription)
    await db.commit()

    logger.info(
        'Subscription deleted by user',
        subscription_id=subscription_id,
        user_id=user.id,
        tariff_id=subscription.tariff_id,
    )

    return {'message': 'Subscription deleted'}
