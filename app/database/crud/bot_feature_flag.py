from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload

from app.database.models import BotFeatureFlag, Bot


async def get_feature_flag(db: AsyncSession, bot_id: int, feature_key: str) -> Optional[BotFeatureFlag]:
    """Get a specific feature flag for a bot."""
    result = await db.execute(
        select(BotFeatureFlag)
        .options(selectinload(BotFeatureFlag.bot))
        .where(BotFeatureFlag.bot_id == bot_id, BotFeatureFlag.feature_key == feature_key)
    )
    return result.scalar_one_or_none()


async def is_feature_enabled(db: AsyncSession, bot_id: int, feature_key: str) -> bool:
    """Check if a feature is enabled for a bot."""
    feature_flag = await get_feature_flag(db, bot_id, feature_key)
    return feature_flag.enabled if feature_flag else False


async def get_feature_config(db: AsyncSession, bot_id: int, feature_key: str) -> Optional[Dict[str, Any]]:
    """Get feature configuration (JSONB config field)."""
    feature_flag = await get_feature_flag(db, bot_id, feature_key)
    if feature_flag and feature_flag.config:
        return feature_flag.config if isinstance(feature_flag.config, dict) else {}
    return None


async def set_feature_flag(
    db: AsyncSession, bot_id: int, feature_key: str, enabled: bool, config: Optional[Dict[str, Any]] = None
) -> BotFeatureFlag:
    """
    Set or update a feature flag for a bot.
    Creates if doesn't exist, updates if exists.
    """
    existing = await get_feature_flag(db, bot_id, feature_key)

    if existing:
        # Update existing
        existing.enabled = enabled
        if config is not None:
            existing.config = config or {}
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        # Create new
        feature_flag = BotFeatureFlag(bot_id=bot_id, feature_key=feature_key, enabled=enabled, config=config or {})
        db.add(feature_flag)
        await db.commit()
        await db.refresh(feature_flag)
        return feature_flag


async def get_all_feature_flags(db: AsyncSession, bot_id: int, enabled_only: bool = False) -> List[BotFeatureFlag]:
    """Get all feature flags for a bot."""
    query = select(BotFeatureFlag).where(BotFeatureFlag.bot_id == bot_id)

    if enabled_only:
        query = query.where(BotFeatureFlag.enabled == True)

    result = await db.execute(query.order_by(BotFeatureFlag.feature_key))
    return list(result.scalars().all())


async def delete_feature_flag(db: AsyncSession, bot_id: int, feature_key: str) -> bool:
    """Delete a feature flag."""
    result = await db.execute(
        delete(BotFeatureFlag).where(BotFeatureFlag.bot_id == bot_id, BotFeatureFlag.feature_key == feature_key)
    )
    await db.commit()
    return result.rowcount > 0


async def enable_feature(
    db: AsyncSession, bot_id: int, feature_key: str, config: Optional[Dict[str, Any]] = None
) -> BotFeatureFlag:
    """Enable a feature (convenience method)."""
    return await set_feature_flag(db, bot_id, feature_key, enabled=True, config=config)


async def disable_feature(db: AsyncSession, bot_id: int, feature_key: str) -> BotFeatureFlag:
    """Disable a feature (convenience method)."""
    return await set_feature_flag(db, bot_id, feature_key, enabled=False)


async def toggle_feature(db: AsyncSession, bot_id: int, feature_key: str) -> Optional[BotFeatureFlag]:
    """Toggle a feature flag (enable if disabled, disable if enabled)."""
    feature_flag = await get_feature_flag(db, bot_id, feature_key)
    if not feature_flag:
        return None

    return await set_feature_flag(db, bot_id, feature_key, enabled=not feature_flag.enabled, config=feature_flag.config)
