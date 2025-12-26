from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.bot import get_bot_by_id
from app.database.crud.tenant_payment_card import (
    activate_card,
    create_payment_card,
    deactivate_card,
    get_card_statistics,
    get_payment_card,
    get_payment_cards,
    update_payment_card,
)
from app.database.models import TenantPaymentCard

from ..dependencies import get_db_session, require_api_token
from ..schemas.payment_cards import (
    PaymentCardCreateRequest,
    PaymentCardListResponse,
    PaymentCardResponse,
    PaymentCardStatisticsResponse,
    PaymentCardUpdateRequest,
)

router = APIRouter()


def _serialize_payment_card(card: TenantPaymentCard) -> PaymentCardResponse:
    """Serialize PaymentCard model to response schema."""
    return PaymentCardResponse(
        id=card.id,
        bot_id=card.bot_id,
        card_number=card.card_number,
        card_holder_name=card.card_holder_name,
        rotation_strategy=card.rotation_strategy,
        rotation_interval_minutes=card.rotation_interval_minutes,
        weight=card.weight,
        success_count=card.success_count,
        failure_count=card.failure_count,
        is_active=card.is_active,
        last_used_at=card.last_used_at,
        current_usage_count=card.current_usage_count,
        created_at=card.created_at,
        updated_at=card.updated_at,
        created_by=card.created_by,
    )


@router.get("/bots/{bot_id}/payment-cards", response_model=PaymentCardListResponse, tags=["payment-cards"])
async def list_payment_cards(
    bot_id: int,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(False),
) -> PaymentCardListResponse:
    """Get list of payment cards for a bot."""
    # Verify bot exists
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with ID {bot_id} not found",
        )
    
    # Get cards
    cards = await get_payment_cards(db, bot_id, active_only=active_only)
    total = len(cards)
    
    # Apply pagination
    cards = cards[offset : offset + limit]
    
    return PaymentCardListResponse(
        items=[_serialize_payment_card(card) for card in cards],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/payment-cards/{card_id}", response_model=PaymentCardResponse, tags=["payment-cards"])
async def get_payment_card_endpoint(
    card_id: int,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> PaymentCardResponse:
    """Get payment card details by ID."""
    card = await get_payment_card(db, card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment card with ID {card_id} not found",
        )
    
    return _serialize_payment_card(card)


@router.post("/bots/{bot_id}/payment-cards", response_model=PaymentCardResponse, status_code=status.HTTP_201_CREATED, tags=["payment-cards"])
async def create_payment_card_endpoint(
    bot_id: int,
    request: PaymentCardCreateRequest,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> PaymentCardResponse:
    """Create a new payment card for a bot."""
    # Verify bot exists
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with ID {bot_id} not found",
        )
    
    # Ensure bot_id matches
    if request.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bot_id in request body must match URL parameter",
        )
    
    # Create card
    card = await create_payment_card(
        db=db,
        bot_id=request.bot_id,
        card_number=request.card_number,
        card_holder_name=request.card_holder_name,
        rotation_strategy=request.rotation_strategy,
        rotation_interval_minutes=request.rotation_interval_minutes,
        weight=request.weight,
        is_active=request.is_active,
    )
    
    return _serialize_payment_card(card)


@router.patch("/payment-cards/{card_id}", response_model=PaymentCardResponse, tags=["payment-cards"])
async def update_payment_card_endpoint(
    card_id: int,
    request: PaymentCardUpdateRequest,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> PaymentCardResponse:
    """Update payment card settings."""
    card = await get_payment_card(db, card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment card with ID {card_id} not found",
        )
    
    # Prepare update data
    update_data = request.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided",
        )
    
    # Update card
    updated_card = await update_payment_card(db, card_id, **update_data)
    if not updated_card:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update payment card",
        )
    
    return _serialize_payment_card(updated_card)


@router.post("/payment-cards/{card_id}/activate", response_model=PaymentCardResponse, tags=["payment-cards"])
async def activate_payment_card_endpoint(
    card_id: int,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> PaymentCardResponse:
    """Activate a payment card."""
    card = await get_payment_card(db, card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment card with ID {card_id} not found",
        )
    
    success = await activate_card(db, card_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate payment card",
        )
    
    # Refresh card
    card = await get_payment_card(db, card_id)
    return _serialize_payment_card(card)


@router.post("/payment-cards/{card_id}/deactivate", response_model=PaymentCardResponse, tags=["payment-cards"])
async def deactivate_payment_card_endpoint(
    card_id: int,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> PaymentCardResponse:
    """Deactivate a payment card."""
    card = await get_payment_card(db, card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment card with ID {card_id} not found",
        )
    
    success = await deactivate_card(db, card_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate payment card",
        )
    
    # Refresh card
    card = await get_payment_card(db, card_id)
    return _serialize_payment_card(card)


@router.get("/payment-cards/{card_id}/statistics", response_model=PaymentCardStatisticsResponse, tags=["payment-cards"])
async def get_payment_card_statistics(
    card_id: int,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> PaymentCardStatisticsResponse:
    """Get payment card usage statistics."""
    card = await get_payment_card(db, card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment card with ID {card_id} not found",
        )
    
    stats = await get_card_statistics(db, card_id)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get card statistics",
        )
    
    return PaymentCardStatisticsResponse(**stats)



