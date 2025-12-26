from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.bot import (
    activate_bot,
    create_bot,
    deactivate_bot,
    get_active_bots,
    get_all_bots,
    get_bot_by_id,
    update_bot,
)
from app.database.models import Bot

from ..dependencies import get_db_session, require_api_token
from ..schemas.bots import (
    BotCreateRequest,
    BotCreateResponse,
    BotListResponse,
    BotResponse,
    BotUpdateRequest,
)

router = APIRouter()


def _serialize_bot(bot: Bot) -> BotResponse:
    """Serialize Bot model to response schema (excludes sensitive data like tokens)."""
    return BotResponse(
        id=bot.id,
        name=bot.name,
        is_master=bot.is_master,
        is_active=bot.is_active,
        card_to_card_enabled=bot.card_to_card_enabled,
        card_receipt_topic_id=bot.card_receipt_topic_id,
        zarinpal_enabled=bot.zarinpal_enabled,
        zarinpal_merchant_id=bot.zarinpal_merchant_id,
        zarinpal_sandbox=bot.zarinpal_sandbox,
        default_language=bot.default_language,
        support_username=bot.support_username,
        admin_chat_id=bot.admin_chat_id,
        admin_topic_id=bot.admin_topic_id,
        notification_group_id=bot.notification_group_id,
        notification_topic_id=bot.notification_topic_id,
        wallet_balance_toman=bot.wallet_balance_toman,
        traffic_consumed_bytes=bot.traffic_consumed_bytes,
        traffic_sold_bytes=bot.traffic_sold_bytes,
        created_at=bot.created_at,
        updated_at=bot.updated_at,
        created_by=bot.created_by,
    )


@router.get("", response_model=BotListResponse, tags=["bots"])
async def list_bots(
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(False),
) -> BotListResponse:
    """Get list of all bots (tenants)."""
    if active_only:
        bots = await get_active_bots(db)
        total = len(bots)
        # Apply pagination
        bots = bots[offset : offset + limit]
    else:
        bots = await get_all_bots(db)
        total = len(bots)
        # Apply pagination
        bots = bots[offset : offset + limit]
    
    return BotListResponse(
        items=[_serialize_bot(bot) for bot in bots],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{bot_id}", response_model=BotResponse, tags=["bots"])
async def get_bot(
    bot_id: int,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> BotResponse:
    """Get bot details by ID."""
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with ID {bot_id} not found",
        )
    
    return _serialize_bot(bot)


@router.post("", response_model=BotCreateResponse, status_code=status.HTTP_201_CREATED, tags=["bots"])
async def create_bot_endpoint(
    request: BotCreateRequest,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> BotCreateResponse:
    """Create a new bot (tenant)."""
    # Check if token already exists
    from app.database.crud.bot import get_bot_by_token
    existing = await get_bot_by_token(db, request.telegram_bot_token)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bot with this Telegram token already exists",
        )
    
    # Create bot
    bot, api_token = await create_bot(
        db=db,
        name=request.name,
        telegram_bot_token=request.telegram_bot_token,
        is_master=request.is_master,
        is_active=request.is_active,
        card_to_card_enabled=request.card_to_card_enabled,
        card_receipt_topic_id=request.card_receipt_topic_id,
        zarinpal_enabled=request.zarinpal_enabled,
        zarinpal_merchant_id=request.zarinpal_merchant_id,
        zarinpal_sandbox=request.zarinpal_sandbox,
        default_language=request.default_language,
        support_username=request.support_username,
        admin_chat_id=request.admin_chat_id,
        admin_topic_id=request.admin_topic_id,
        notification_group_id=request.notification_group_id,
        notification_topic_id=request.notification_topic_id,
    )
    
    return BotCreateResponse(
        bot=_serialize_bot(bot),
        api_token=api_token,
    )


@router.patch("/{bot_id}", response_model=BotResponse, tags=["bots"])
async def update_bot_endpoint(
    bot_id: int,
    request: BotUpdateRequest,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> BotResponse:
    """Update bot settings."""
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with ID {bot_id} not found",
        )
    
    # Check if token is being updated and if it's unique
    if request.telegram_bot_token:
        from app.database.crud.bot import get_bot_by_token
        existing = await get_bot_by_token(db, request.telegram_bot_token)
        if existing and existing.id != bot_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bot with this Telegram token already exists",
            )
    
    # Prepare update data
    update_data = request.model_dump(exclude_unset=True)
    
    # Update bot
    updated_bot = await update_bot(db, bot_id, **update_data)
    if not updated_bot:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update bot",
        )
    
    return _serialize_bot(updated_bot)


@router.post("/{bot_id}/activate", response_model=BotResponse, tags=["bots"])
async def activate_bot_endpoint(
    bot_id: int,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> BotResponse:
    """Activate a bot."""
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with ID {bot_id} not found",
        )
    
    success = await activate_bot(db, bot_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate bot",
        )
    
    # Refresh bot
    bot = await get_bot_by_id(db, bot_id)
    return _serialize_bot(bot)


@router.post("/{bot_id}/deactivate", response_model=BotResponse, tags=["bots"])
async def deactivate_bot_endpoint(
    bot_id: int,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> BotResponse:
    """Deactivate a bot."""
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with ID {bot_id} not found",
        )
    
    # Prevent deactivating master bot
    if bot.is_master:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate master bot",
        )
    
    success = await deactivate_bot(db, bot_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate bot",
        )
    
    # Refresh bot
    bot = await get_bot_by_id(db, bot_id)
    return _serialize_bot(bot)


@router.patch("/{bot_id}/card-to-card", response_model=BotResponse, tags=["bots"])
async def update_card_to_card_settings(
    bot_id: int,
    card_to_card_enabled: Optional[bool] = None,
    card_receipt_topic_id: Optional[int] = None,
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> BotResponse:
    """Update card-to-card payment settings for a bot."""
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with ID {bot_id} not found",
        )
    
    update_data = {}
    if card_to_card_enabled is not None:
        update_data["card_to_card_enabled"] = card_to_card_enabled
    if card_receipt_topic_id is not None:
        update_data["card_receipt_topic_id"] = card_receipt_topic_id
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided",
        )
    
    updated_bot = await update_bot(db, bot_id, **update_data)
    if not updated_bot:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update card-to-card settings",
        )
    
    return _serialize_bot(updated_bot)



