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
from app.services.bot_config_service import BotConfigService

from ..dependencies import get_db_session, require_api_token
from ..schemas.bots import (
    BotCreateRequest,
    BotCreateResponse,
    BotListResponse,
    BotResponse,
    BotUpdateRequest,
)

router = APIRouter()


async def _serialize_bot(bot: Bot, db: AsyncSession) -> BotResponse:
    """Serialize Bot model to response schema (excludes sensitive data like tokens).
    
    Uses BotConfigService to fetch configs and feature flags from dedicated tables.
    """
    # Fetch feature flags and configs using BotConfigService
    card_to_card_enabled = await BotConfigService.is_feature_enabled(db, bot.id, 'card_to_card')
    zarinpal_enabled = await BotConfigService.is_feature_enabled(db, bot.id, 'zarinpal')
    
    default_language = await BotConfigService.get_config(db, bot.id, 'DEFAULT_LANGUAGE', 'fa')
    support_username = await BotConfigService.get_config(db, bot.id, 'SUPPORT_USERNAME')
    admin_chat_id = await BotConfigService.get_config(db, bot.id, 'ADMIN_NOTIFICATIONS_CHAT_ID')
    admin_topic_id = await BotConfigService.get_config(db, bot.id, 'ADMIN_NOTIFICATIONS_TOPIC_ID')
    notification_group_id = await BotConfigService.get_config(db, bot.id, 'NOTIFICATION_GROUP_ID')
    notification_topic_id = await BotConfigService.get_config(db, bot.id, 'NOTIFICATION_TOPIC_ID')
    card_receipt_topic_id = await BotConfigService.get_config(db, bot.id, 'CARD_RECEIPT_TOPIC_ID')
    zarinpal_merchant_id = await BotConfigService.get_config(db, bot.id, 'ZARINPAL_MERCHANT_ID')
    zarinpal_sandbox = await BotConfigService.get_config(db, bot.id, 'ZARINPAL_SANDBOX', False)
    
    return BotResponse(
        id=bot.id,
        name=bot.name,
        is_master=bot.is_master,
        is_active=bot.is_active,
        card_to_card_enabled=card_to_card_enabled,
        card_receipt_topic_id=card_receipt_topic_id,
        zarinpal_enabled=zarinpal_enabled,
        zarinpal_merchant_id=zarinpal_merchant_id,
        zarinpal_sandbox=zarinpal_sandbox,
        default_language=default_language,
        support_username=support_username,
        admin_chat_id=admin_chat_id,
        admin_topic_id=admin_topic_id,
        notification_group_id=notification_group_id,
        notification_topic_id=notification_topic_id,
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
    
    # Serialize bots (async operation)
    items = []
    for bot in bots:
        items.append(await _serialize_bot(bot, db))
    
    return BotListResponse(
        items=items,
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
    
    return await _serialize_bot(bot, db)


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
    
    # Create bot (without redundant config columns - they'll be set via BotConfigService)
    bot, api_token = await create_bot(
        db=db,
        name=request.name,
        telegram_bot_token=request.telegram_bot_token,
        is_master=request.is_master,
        is_active=request.is_active,
    )
    
    # Set feature flags using BotConfigService
    await BotConfigService.set_feature_enabled(db, bot.id, 'card_to_card', request.card_to_card_enabled)
    await BotConfigService.set_feature_enabled(db, bot.id, 'zarinpal', request.zarinpal_enabled)
    
    # Set configurations using BotConfigService
    if request.card_receipt_topic_id is not None:
        await BotConfigService.set_config(db, bot.id, 'CARD_RECEIPT_TOPIC_ID', request.card_receipt_topic_id)
    if request.zarinpal_merchant_id is not None:
        await BotConfigService.set_config(db, bot.id, 'ZARINPAL_MERCHANT_ID', request.zarinpal_merchant_id)
    await BotConfigService.set_config(db, bot.id, 'ZARINPAL_SANDBOX', request.zarinpal_sandbox)
    await BotConfigService.set_config(db, bot.id, 'DEFAULT_LANGUAGE', request.default_language)
    if request.support_username is not None:
        await BotConfigService.set_config(db, bot.id, 'SUPPORT_USERNAME', request.support_username)
    if request.admin_chat_id is not None:
        await BotConfigService.set_config(db, bot.id, 'ADMIN_NOTIFICATIONS_CHAT_ID', request.admin_chat_id)
    if request.admin_topic_id is not None:
        await BotConfigService.set_config(db, bot.id, 'ADMIN_NOTIFICATIONS_TOPIC_ID', request.admin_topic_id)
    if request.notification_group_id is not None:
        await BotConfigService.set_config(db, bot.id, 'NOTIFICATION_GROUP_ID', request.notification_group_id)
    if request.notification_topic_id is not None:
        await BotConfigService.set_config(db, bot.id, 'NOTIFICATION_TOPIC_ID', request.notification_topic_id)
    
    return BotCreateResponse(
        bot=await _serialize_bot(bot, db),
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
    
    # Prepare update data (exclude config fields - they'll be updated via BotConfigService)
    update_data = request.model_dump(exclude_unset=True)
    config_fields = {
        'card_to_card_enabled', 'zarinpal_enabled', 'card_receipt_topic_id',
        'zarinpal_merchant_id', 'zarinpal_sandbox', 'default_language',
        'support_username', 'admin_chat_id', 'admin_topic_id',
        'notification_group_id', 'notification_topic_id'
    }
    
    # Separate config updates from bot updates
    config_updates = {k: v for k, v in update_data.items() if k in config_fields}
    bot_updates = {k: v for k, v in update_data.items() if k not in config_fields}
    
    # Update bot (non-config fields)
    if bot_updates:
        updated_bot = await update_bot(db, bot_id, **bot_updates)
        if not updated_bot:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update bot",
            )
    else:
        updated_bot = bot
    
    # Update configs using BotConfigService
    if 'card_to_card_enabled' in config_updates:
        await BotConfigService.set_feature_enabled(db, bot_id, 'card_to_card', config_updates['card_to_card_enabled'])
    if 'zarinpal_enabled' in config_updates:
        await BotConfigService.set_feature_enabled(db, bot_id, 'zarinpal', config_updates['zarinpal_enabled'])
    if 'card_receipt_topic_id' in config_updates:
        await BotConfigService.set_config(db, bot_id, 'CARD_RECEIPT_TOPIC_ID', config_updates['card_receipt_topic_id'])
    if 'zarinpal_merchant_id' in config_updates:
        await BotConfigService.set_config(db, bot_id, 'ZARINPAL_MERCHANT_ID', config_updates['zarinpal_merchant_id'])
    if 'zarinpal_sandbox' in config_updates:
        await BotConfigService.set_config(db, bot_id, 'ZARINPAL_SANDBOX', config_updates['zarinpal_sandbox'])
    if 'default_language' in config_updates:
        await BotConfigService.set_config(db, bot_id, 'DEFAULT_LANGUAGE', config_updates['default_language'])
    if 'support_username' in config_updates:
        await BotConfigService.set_config(db, bot_id, 'SUPPORT_USERNAME', config_updates['support_username'])
    if 'admin_chat_id' in config_updates:
        await BotConfigService.set_config(db, bot_id, 'ADMIN_NOTIFICATIONS_CHAT_ID', config_updates['admin_chat_id'])
    if 'admin_topic_id' in config_updates:
        await BotConfigService.set_config(db, bot_id, 'ADMIN_NOTIFICATIONS_TOPIC_ID', config_updates['admin_topic_id'])
    if 'notification_group_id' in config_updates:
        await BotConfigService.set_config(db, bot_id, 'NOTIFICATION_GROUP_ID', config_updates['notification_group_id'])
    if 'notification_topic_id' in config_updates:
        await BotConfigService.set_config(db, bot_id, 'NOTIFICATION_TOPIC_ID', config_updates['notification_topic_id'])
    
    # Refresh bot to get latest data
    updated_bot = await get_bot_by_id(db, bot_id)
    return await _serialize_bot(updated_bot, db)


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
    return await _serialize_bot(bot, db)


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
    return await _serialize_bot(bot, db)


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
    
    # Update using BotConfigService
    if card_to_card_enabled is not None:
        await BotConfigService.set_feature_enabled(db, bot_id, 'card_to_card', card_to_card_enabled)
    if card_receipt_topic_id is not None:
        await BotConfigService.set_config(db, bot_id, 'CARD_RECEIPT_TOPIC_ID', card_receipt_topic_id)
    
    if card_to_card_enabled is None and card_receipt_topic_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided",
        )
    
    # Refresh bot to get latest data
    updated_bot = await get_bot_by_id(db, bot_id)
    return await _serialize_bot(updated_bot, db)



